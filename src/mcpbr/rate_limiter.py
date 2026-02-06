"""Rate limiting for MCP server benchmark API calls.

Provides token bucket rate limiting, configurable backoff strategies,
Retry-After header parsing, and request/token quota tracking with metrics.
"""

import asyncio
import random
import time
from dataclasses import dataclass
from enum import Enum


class RateLimitStrategy(Enum):
    """Strategy for calculating backoff delays after rate limit errors."""

    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    ADAPTIVE = "adaptive"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting behavior.

    Attributes:
        max_requests_per_minute: Maximum number of requests allowed per minute.
        max_tokens_per_minute: Maximum number of tokens allowed per minute.
        strategy: Backoff strategy to use when rate limited.
        initial_delay_seconds: Base delay in seconds for backoff calculations.
        max_delay_seconds: Maximum delay in seconds to cap backoff growth.
        safety_margin: Fraction of quota to actually use (e.g., 0.9 = 90%).
        parse_retry_after: Whether to parse Retry-After headers from responses.
    """

    max_requests_per_minute: int = 60
    max_tokens_per_minute: int = 100000
    strategy: RateLimitStrategy = RateLimitStrategy.ADAPTIVE
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    safety_margin: float = 0.9
    parse_retry_after: bool = True


@dataclass
class RateLimitMetrics:
    """Metrics collected during rate-limited operation.

    Attributes:
        total_requests: Total number of requests that passed through the limiter.
        throttled_requests: Number of requests that had to wait before proceeding.
        total_wait_seconds: Cumulative time spent waiting for rate limit tokens.
        rate_limit_errors: Number of 429 rate limit errors recorded.
        retry_after_parsed: Number of times a Retry-After header was successfully parsed.
    """

    total_requests: int = 0
    throttled_requests: int = 0
    total_wait_seconds: float = 0.0
    rate_limit_errors: int = 0
    retry_after_parsed: int = 0


class TokenBucket:
    """Token bucket algorithm for rate limiting.

    Allows bursts up to the bucket capacity while enforcing a sustained
    average rate. Tokens are refilled continuously based on elapsed time.

    Args:
        rate: Token refill rate in tokens per second.
        capacity: Maximum number of tokens the bucket can hold (burst size).
    """

    def __init__(self, rate: float, capacity: float) -> None:
        """Initialize the token bucket.

        Args:
            rate: Token refill rate in tokens per second.
            capacity: Maximum number of tokens the bucket can hold.
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def consume(self, tokens: float = 1.0) -> float:
        """Attempt to consume tokens from the bucket.

        Refills the bucket based on elapsed time, then checks whether
        enough tokens are available. If not, returns the time to wait.

        Args:
            tokens: Number of tokens to consume.

        Returns:
            Wait time in seconds. Returns 0.0 if tokens were consumed
            immediately, or a positive value indicating how long to wait
            before retrying.
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return 0.0

        # Calculate how long until enough tokens are available
        deficit = tokens - self.tokens
        wait_time = deficit / self.rate
        return wait_time

    def _refill(self) -> None:
        """Refill tokens based on time elapsed since the last refill.

        Adds tokens proportional to the elapsed time at the configured
        rate, capping at the bucket capacity.
        """
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.last_refill = now

        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)


def parse_retry_after_header(value: str | None) -> float | None:
    """Parse a Retry-After HTTP header value.

    Supports both formats defined in RFC 7231:
    - Delay in seconds (e.g., "120")
    - HTTP-date (e.g., "Fri, 31 Dec 1999 23:59:59 GMT")

    Args:
        value: The Retry-After header value, or None.

    Returns:
        Delay in seconds as a float, or None if the value could not be parsed
        or was None.
    """
    if value is None:
        return None

    value = value.strip()
    if not value:
        return None

    # Try parsing as a number of seconds first
    try:
        delay = float(value)
        if delay >= 0:
            return delay
        return None
    except ValueError:
        pass

    # Try parsing as an HTTP-date (RFC 7231)
    # Format: "Sun, 06 Nov 1994 08:49:37 GMT"
    try:
        import email.utils

        parsed = email.utils.parsedate(value)
        if parsed is not None:
            retry_time = time.mktime(parsed)
            now = time.time()
            delay = retry_time - now
            return max(0.0, delay)
    except (ValueError, OverflowError, OSError):
        pass

    return None


class RateLimiter:
    """Rate limiter with configurable backoff strategies and metrics.

    Wraps a TokenBucket to provide async-friendly rate limiting with
    automatic waiting, backoff delay calculation, and usage metrics.

    Args:
        config: Rate limiting configuration.
    """

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize the rate limiter.

        Creates a token bucket calibrated to the configured requests-per-minute
        rate, applying the safety margin to avoid hitting hard limits.

        Args:
            config: Rate limiting configuration.
        """
        self.config = config
        self._metrics = RateLimitMetrics()

        # Convert requests per minute to tokens per second, applying safety margin
        effective_rate = (config.max_requests_per_minute / 60.0) * config.safety_margin
        capacity = max(1.0, config.max_requests_per_minute * config.safety_margin)
        self._bucket = TokenBucket(rate=effective_rate, capacity=capacity)

    async def acquire(self) -> float:
        """Acquire permission to make a request, waiting if necessary.

        Blocks asynchronously until a rate limit token is available. Updates
        metrics to reflect the wait time and whether throttling occurred.

        Returns:
            Wait time in seconds. Returns 0.0 if the request proceeded
            immediately without throttling.
        """
        self._metrics.total_requests += 1

        wait_time = self._bucket.consume(1.0)
        if wait_time > 0:
            self._metrics.throttled_requests += 1
            self._metrics.total_wait_seconds += wait_time
            await asyncio.sleep(wait_time)
            # After waiting, consume the token
            self._bucket.consume(1.0)

        return wait_time

    def record_rate_limit_error(self, retry_after: float | None = None) -> None:
        """Record a 429 rate limit error from the server.

        Increments the error counter and optionally adjusts the token bucket
        based on a parsed Retry-After value, draining tokens to enforce the
        server's requested delay.

        Args:
            retry_after: Delay in seconds from a Retry-After header, or None
                if no header was present or parsing is disabled.
        """
        self._metrics.rate_limit_errors += 1

        if retry_after is not None and self.config.parse_retry_after:
            self._metrics.retry_after_parsed += 1
            # Drain the bucket to enforce the server-requested delay.
            # Setting tokens negative means the bucket must refill before
            # any new requests are allowed.
            self._bucket.tokens = -(retry_after * self._bucket.rate)

    def get_metrics(self) -> RateLimitMetrics:
        """Get a copy of the current rate limiting metrics.

        Returns:
            A new RateLimitMetrics instance with the current counter values.
        """
        return RateLimitMetrics(
            total_requests=self._metrics.total_requests,
            throttled_requests=self._metrics.throttled_requests,
            total_wait_seconds=self._metrics.total_wait_seconds,
            rate_limit_errors=self._metrics.rate_limit_errors,
            retry_after_parsed=self._metrics.retry_after_parsed,
        )

    def get_backoff_delay(self, attempt: int) -> float:
        """Calculate the backoff delay for a given retry attempt.

        Uses the configured strategy to determine how long to wait:
        - FIXED: Always returns the initial delay.
        - EXPONENTIAL: Doubles the delay with each attempt, capped at max.
        - ADAPTIVE: Exponential backoff plus random jitter (0-25%).

        Args:
            attempt: Zero-based retry attempt number. Attempt 0 is the first
                retry after the initial failure.

        Returns:
            Delay in seconds before the next retry attempt.
        """
        if self.config.strategy == RateLimitStrategy.FIXED:
            return self.config.initial_delay_seconds

        # Exponential: initial * 2^attempt, capped at max
        delay = min(
            self.config.initial_delay_seconds * (2**attempt),
            self.config.max_delay_seconds,
        )

        if self.config.strategy == RateLimitStrategy.ADAPTIVE:
            # Add random jitter of 0-25% to prevent thundering herd
            jitter = delay * random.uniform(0.0, 0.25)
            delay += jitter

        return delay
