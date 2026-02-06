"""Tests for rate limiting module."""

# ruff: noqa: N801

import asyncio
import time

import pytest

from mcpbr.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    RateLimitMetrics,
    RateLimitStrategy,
    TokenBucket,
    parse_retry_after_header,
)


class TestRateLimitStrategy:
    """Tests for RateLimitStrategy enum."""

    def test_fixed_value(self) -> None:
        """Test fixed strategy value."""
        assert RateLimitStrategy.FIXED.value == "fixed"

    def test_exponential_value(self) -> None:
        """Test exponential strategy value."""
        assert RateLimitStrategy.EXPONENTIAL.value == "exponential"

    def test_adaptive_value(self) -> None:
        """Test adaptive strategy value."""
        assert RateLimitStrategy.ADAPTIVE.value == "adaptive"

    def test_all_strategies_are_strings(self) -> None:
        """Test that all strategy values are strings."""
        for strategy in RateLimitStrategy:
            assert isinstance(strategy.value, str)


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_defaults(self) -> None:
        """Test default configuration values."""
        config = RateLimitConfig()
        assert config.max_requests_per_minute == 60
        assert config.max_tokens_per_minute == 100000
        assert config.strategy == RateLimitStrategy.ADAPTIVE
        assert config.initial_delay_seconds == 1.0
        assert config.max_delay_seconds == 60.0
        assert config.safety_margin == 0.9
        assert config.parse_retry_after is True

    def test_custom_values(self) -> None:
        """Test configuration with custom values."""
        config = RateLimitConfig(
            max_requests_per_minute=120,
            max_tokens_per_minute=200000,
            strategy=RateLimitStrategy.FIXED,
            initial_delay_seconds=2.0,
            max_delay_seconds=30.0,
            safety_margin=0.8,
            parse_retry_after=False,
        )
        assert config.max_requests_per_minute == 120
        assert config.max_tokens_per_minute == 200000
        assert config.strategy == RateLimitStrategy.FIXED
        assert config.initial_delay_seconds == 2.0
        assert config.max_delay_seconds == 30.0
        assert config.safety_margin == 0.8
        assert config.parse_retry_after is False

    def test_partial_custom_values(self) -> None:
        """Test configuration with only some custom values."""
        config = RateLimitConfig(
            max_requests_per_minute=30,
            strategy=RateLimitStrategy.EXPONENTIAL,
        )
        assert config.max_requests_per_minute == 30
        assert config.strategy == RateLimitStrategy.EXPONENTIAL
        # Remaining fields should be defaults
        assert config.max_tokens_per_minute == 100000
        assert config.initial_delay_seconds == 1.0


class TestRateLimitMetrics:
    """Tests for RateLimitMetrics dataclass."""

    def test_defaults(self) -> None:
        """Test default metrics are all zeroes."""
        metrics = RateLimitMetrics()
        assert metrics.total_requests == 0
        assert metrics.throttled_requests == 0
        assert metrics.total_wait_seconds == 0.0
        assert metrics.rate_limit_errors == 0
        assert metrics.retry_after_parsed == 0

    def test_custom_values(self) -> None:
        """Test metrics with custom values."""
        metrics = RateLimitMetrics(
            total_requests=10,
            throttled_requests=3,
            total_wait_seconds=5.5,
            rate_limit_errors=1,
            retry_after_parsed=1,
        )
        assert metrics.total_requests == 10
        assert metrics.throttled_requests == 3
        assert metrics.total_wait_seconds == 5.5
        assert metrics.rate_limit_errors == 1
        assert metrics.retry_after_parsed == 1

    def test_incrementing(self) -> None:
        """Test that metrics fields can be incremented."""
        metrics = RateLimitMetrics()
        metrics.total_requests += 1
        metrics.throttled_requests += 1
        metrics.total_wait_seconds += 0.5
        metrics.rate_limit_errors += 1
        metrics.retry_after_parsed += 1

        assert metrics.total_requests == 1
        assert metrics.throttled_requests == 1
        assert metrics.total_wait_seconds == pytest.approx(0.5)
        assert metrics.rate_limit_errors == 1
        assert metrics.retry_after_parsed == 1

    def test_multiple_increments(self) -> None:
        """Test accumulating multiple increments."""
        metrics = RateLimitMetrics()
        for _ in range(5):
            metrics.total_requests += 1
            metrics.total_wait_seconds += 0.1

        assert metrics.total_requests == 5
        assert metrics.total_wait_seconds == pytest.approx(0.5)


class TestTokenBucket:
    """Tests for TokenBucket class."""

    def test_creation(self) -> None:
        """Test creating a token bucket with rate and capacity."""
        bucket = TokenBucket(rate=10.0, capacity=100.0)
        assert bucket.rate == 10.0
        assert bucket.capacity == 100.0
        assert bucket.tokens == 100.0

    def test_consume_returns_zero_when_available(self) -> None:
        """Test that consume returns 0.0 when tokens are available."""
        bucket = TokenBucket(rate=10.0, capacity=100.0)
        wait = bucket.consume(1.0)
        assert wait == 0.0

    def test_consume_decrements_tokens(self) -> None:
        """Test that consume decrements the token count."""
        bucket = TokenBucket(rate=10.0, capacity=100.0)
        bucket.consume(1.0)
        # Tokens should be less than capacity (approximately 99, small refill possible)
        assert bucket.tokens < 100.0

    def test_consume_returns_positive_wait_when_exhausted(self) -> None:
        """Test that consume returns positive wait time when bucket is empty."""
        bucket = TokenBucket(rate=1.0, capacity=2.0)
        # Consume all tokens
        wait1 = bucket.consume(2.0)
        assert wait1 == 0.0

        # Next consume should require waiting
        wait2 = bucket.consume(1.0)
        assert wait2 > 0.0

    def test_consume_wait_time_proportional_to_deficit(self) -> None:
        """Test that wait time is proportional to token deficit divided by rate."""
        bucket = TokenBucket(rate=2.0, capacity=2.0)
        # Consume all tokens
        bucket.consume(2.0)
        # Try to consume 2 more tokens with rate=2/sec, deficit should be ~2
        wait = bucket.consume(2.0)
        # Wait should be approximately deficit / rate = 2 / 2 = 1 second
        assert wait == pytest.approx(1.0, abs=0.1)

    def test_refill_behavior_over_time(self) -> None:
        """Test that tokens are refilled over time."""
        bucket = TokenBucket(rate=100.0, capacity=10.0)
        # Consume all tokens
        bucket.consume(10.0)

        # Wait a short time for refill
        time.sleep(0.05)

        # Should have some tokens refilled (100 tokens/sec * 0.05s = ~5 tokens)
        wait = bucket.consume(1.0)
        assert wait == 0.0

    def test_capacity_limits_refill(self) -> None:
        """Test that tokens do not exceed capacity after refill."""
        bucket = TokenBucket(rate=1000.0, capacity=10.0)
        # Wait to allow refill beyond capacity
        time.sleep(0.05)

        # Trigger refill by consuming
        bucket.consume(0.0)
        assert bucket.tokens <= bucket.capacity

    def test_consume_default_tokens_is_one(self) -> None:
        """Test that consume defaults to consuming 1 token."""
        bucket = TokenBucket(rate=10.0, capacity=5.0)
        wait = bucket.consume()
        assert wait == 0.0
        # Should have consumed 1 token, leaving ~4 (plus tiny refill)
        assert bucket.tokens < 5.0
        assert bucket.tokens >= 3.9

    def test_large_consume_exceeds_capacity(self) -> None:
        """Test consuming more tokens than capacity results in wait time."""
        bucket = TokenBucket(rate=10.0, capacity=5.0)
        # Try to consume more than capacity
        wait = bucket.consume(10.0)
        # Not enough tokens even at full capacity, so should wait
        assert wait > 0.0


class TestParseRetryAfterHeader:
    """Tests for parse_retry_after_header function."""

    def test_numeric_value(self) -> None:
        """Test parsing a numeric Retry-After value."""
        result = parse_retry_after_header("120")
        assert result == 120.0

    def test_none_input_returns_none(self) -> None:
        """Test that None input returns None."""
        result = parse_retry_after_header(None)
        assert result is None

    def test_invalid_value_returns_none(self) -> None:
        """Test that an invalid string returns None."""
        result = parse_retry_after_header("not-a-number-or-date")
        assert result is None

    def test_zero_returns_zero(self) -> None:
        """Test that '0' returns 0.0."""
        result = parse_retry_after_header("0")
        assert result == 0.0

    def test_negative_returns_none(self) -> None:
        """Test that a negative value returns None."""
        result = parse_retry_after_header("-5")
        assert result is None

    def test_float_value(self) -> None:
        """Test parsing a float Retry-After value."""
        result = parse_retry_after_header("1.5")
        assert result == 1.5

    def test_whitespace_stripped(self) -> None:
        """Test that leading/trailing whitespace is stripped."""
        result = parse_retry_after_header("  30  ")
        assert result == 30.0

    def test_empty_string_returns_none(self) -> None:
        """Test that an empty string returns None."""
        result = parse_retry_after_header("")
        assert result is None

    def test_whitespace_only_returns_none(self) -> None:
        """Test that a whitespace-only string returns None."""
        result = parse_retry_after_header("   ")
        assert result is None


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_creation_from_config(self) -> None:
        """Test creating a RateLimiter from a RateLimitConfig."""
        config = RateLimitConfig()
        limiter = RateLimiter(config)
        assert limiter.config is config
        assert limiter._bucket is not None
        assert limiter._metrics is not None

    def test_creation_bucket_rate_applies_safety_margin(self) -> None:
        """Test that the bucket rate reflects the safety margin."""
        config = RateLimitConfig(max_requests_per_minute=60, safety_margin=0.9)
        limiter = RateLimiter(config)
        # Expected: (60 / 60) * 0.9 = 0.9 tokens/sec
        assert limiter._bucket.rate == pytest.approx(0.9)

    def test_creation_bucket_capacity_applies_safety_margin(self) -> None:
        """Test that the bucket capacity reflects the safety margin."""
        config = RateLimitConfig(max_requests_per_minute=60, safety_margin=0.9)
        limiter = RateLimiter(config)
        # Expected: max(1.0, 60 * 0.9) = 54.0
        assert limiter._bucket.capacity == pytest.approx(54.0)

    def test_creation_bucket_capacity_minimum_is_one(self) -> None:
        """Test that bucket capacity has a minimum of 1.0."""
        config = RateLimitConfig(max_requests_per_minute=0, safety_margin=0.5)
        limiter = RateLimiter(config)
        assert limiter._bucket.capacity >= 1.0

    def test_async_acquire_returns_zero_for_first_call(self) -> None:
        """Test that the first acquire returns 0.0 (no waiting)."""

        async def _test():
            config = RateLimitConfig(max_requests_per_minute=60)
            limiter = RateLimiter(config)
            wait = await limiter.acquire()
            assert wait == 0.0

        asyncio.run(_test())

    def test_get_metrics_tracks_calls(self) -> None:
        """Test that get_metrics tracks total_requests after acquire calls."""

        async def _test():
            config = RateLimitConfig(max_requests_per_minute=600)
            limiter = RateLimiter(config)
            await limiter.acquire()
            await limiter.acquire()
            await limiter.acquire()

            metrics = limiter.get_metrics()
            assert metrics.total_requests == 3

        asyncio.run(_test())

    def test_get_metrics_returns_copy(self) -> None:
        """Test that get_metrics returns a copy, not the internal object."""

        async def _test():
            config = RateLimitConfig(max_requests_per_minute=600)
            limiter = RateLimiter(config)
            await limiter.acquire()

            metrics1 = limiter.get_metrics()
            metrics2 = limiter.get_metrics()

            assert metrics1 is not metrics2
            assert metrics1.total_requests == metrics2.total_requests

        asyncio.run(_test())

    def test_record_rate_limit_error_increments_metrics(self) -> None:
        """Test that record_rate_limit_error increments the error counter."""
        config = RateLimitConfig()
        limiter = RateLimiter(config)
        limiter.record_rate_limit_error()
        limiter.record_rate_limit_error()

        metrics = limiter.get_metrics()
        assert metrics.rate_limit_errors == 2

    def test_record_rate_limit_error_with_retry_after(self) -> None:
        """Test that retry_after value is parsed and recorded."""
        config = RateLimitConfig(parse_retry_after=True)
        limiter = RateLimiter(config)
        limiter.record_rate_limit_error(retry_after=30.0)

        metrics = limiter.get_metrics()
        assert metrics.rate_limit_errors == 1
        assert metrics.retry_after_parsed == 1

    def test_record_rate_limit_error_without_retry_after(self) -> None:
        """Test that retry_after_parsed is not incremented when retry_after is None."""
        config = RateLimitConfig(parse_retry_after=True)
        limiter = RateLimiter(config)
        limiter.record_rate_limit_error(retry_after=None)

        metrics = limiter.get_metrics()
        assert metrics.rate_limit_errors == 1
        assert metrics.retry_after_parsed == 0

    def test_record_rate_limit_error_parse_disabled(self) -> None:
        """Test that retry_after is ignored when parse_retry_after is False."""
        config = RateLimitConfig(parse_retry_after=False)
        limiter = RateLimiter(config)
        limiter.record_rate_limit_error(retry_after=30.0)

        metrics = limiter.get_metrics()
        assert metrics.rate_limit_errors == 1
        assert metrics.retry_after_parsed == 0

    def test_get_backoff_delay_fixed_strategy(self) -> None:
        """Test that FIXED strategy always returns initial_delay_seconds."""
        config = RateLimitConfig(
            strategy=RateLimitStrategy.FIXED,
            initial_delay_seconds=2.0,
        )
        limiter = RateLimiter(config)
        assert limiter.get_backoff_delay(0) == 2.0
        assert limiter.get_backoff_delay(1) == 2.0
        assert limiter.get_backoff_delay(5) == 2.0
        assert limiter.get_backoff_delay(10) == 2.0

    def test_get_backoff_delay_exponential_strategy(self) -> None:
        """Test that EXPONENTIAL strategy grows with each attempt."""
        config = RateLimitConfig(
            strategy=RateLimitStrategy.EXPONENTIAL,
            initial_delay_seconds=1.0,
            max_delay_seconds=60.0,
        )
        limiter = RateLimiter(config)
        assert limiter.get_backoff_delay(0) == 1.0  # 1 * 2^0 = 1
        assert limiter.get_backoff_delay(1) == 2.0  # 1 * 2^1 = 2
        assert limiter.get_backoff_delay(2) == 4.0  # 1 * 2^2 = 4
        assert limiter.get_backoff_delay(3) == 8.0  # 1 * 2^3 = 8
        assert limiter.get_backoff_delay(4) == 16.0  # 1 * 2^4 = 16

    def test_get_backoff_delay_exponential_capped_at_max(self) -> None:
        """Test that EXPONENTIAL strategy is capped at max_delay_seconds."""
        config = RateLimitConfig(
            strategy=RateLimitStrategy.EXPONENTIAL,
            initial_delay_seconds=1.0,
            max_delay_seconds=10.0,
        )
        limiter = RateLimiter(config)
        # 1 * 2^10 = 1024, but capped at 10
        assert limiter.get_backoff_delay(10) == 10.0

    def test_get_backoff_delay_adaptive_strategy_has_jitter(self) -> None:
        """Test that ADAPTIVE strategy adds jitter to the delay."""
        config = RateLimitConfig(
            strategy=RateLimitStrategy.ADAPTIVE,
            initial_delay_seconds=1.0,
            max_delay_seconds=60.0,
        )
        limiter = RateLimiter(config)

        # For attempt 0, base delay is 1.0, jitter adds 0-25%
        # So result should be between 1.0 and 1.25
        delay = limiter.get_backoff_delay(0)
        assert 1.0 <= delay <= 1.25

    def test_get_backoff_delay_adaptive_strategy_varies(self) -> None:
        """Test that ADAPTIVE strategy produces varying delays due to jitter."""
        config = RateLimitConfig(
            strategy=RateLimitStrategy.ADAPTIVE,
            initial_delay_seconds=4.0,
            max_delay_seconds=60.0,
        )
        limiter = RateLimiter(config)

        # Collect multiple delays and check they are not all identical
        delays = [limiter.get_backoff_delay(2) for _ in range(20)]
        # Base delay for attempt 2 is 4 * 2^2 = 16, jitter adds 0-25% => [16, 20]
        for d in delays:
            assert 16.0 <= d <= 20.0

        # With 20 samples, it is extremely unlikely all are identical
        unique_delays = set(delays)
        assert len(unique_delays) > 1

    def test_rate_limiter_with_custom_config(self) -> None:
        """Test RateLimiter with a fully custom config."""

        async def _test():
            config = RateLimitConfig(
                max_requests_per_minute=120,
                max_tokens_per_minute=50000,
                strategy=RateLimitStrategy.EXPONENTIAL,
                initial_delay_seconds=0.5,
                max_delay_seconds=30.0,
                safety_margin=0.8,
                parse_retry_after=False,
            )
            limiter = RateLimiter(config)

            # Should be able to acquire without waiting
            wait = await limiter.acquire()
            assert wait == 0.0

            metrics = limiter.get_metrics()
            assert metrics.total_requests == 1
            assert metrics.throttled_requests == 0

            # Backoff should use exponential strategy
            assert limiter.get_backoff_delay(0) == 0.5
            assert limiter.get_backoff_delay(1) == 1.0
            assert limiter.get_backoff_delay(2) == 2.0

        asyncio.run(_test())


class TestRateLimiterIntegration:
    """Integration tests for RateLimiter under load."""

    def test_multiple_rapid_acquires_track_total_wait(self) -> None:
        """Test that rapid acquires result in throttled requests being tracked."""

        async def _test():
            # Very low rate to force throttling quickly
            config = RateLimitConfig(
                max_requests_per_minute=6,  # 0.1 req/sec after safety margin
                safety_margin=1.0,
            )
            limiter = RateLimiter(config)

            # Consume all burst capacity by making many requests
            # Capacity = max(1.0, 6 * 1.0) = 6
            for _ in range(6):
                await limiter.acquire()

            # The next acquire should be throttled
            await limiter.acquire()
            # It should have been throttled (wait > 0)
            metrics = limiter.get_metrics()
            assert metrics.total_requests == 7
            assert metrics.throttled_requests >= 1
            assert metrics.total_wait_seconds > 0.0

        asyncio.run(_test())

    def test_metrics_reflect_all_operations(self) -> None:
        """Test that metrics accurately reflect acquires and errors."""

        async def _test():
            config = RateLimitConfig(
                max_requests_per_minute=600,
                parse_retry_after=True,
            )
            limiter = RateLimiter(config)

            # Make several acquires
            for _ in range(5):
                await limiter.acquire()

            # Record some rate limit errors
            limiter.record_rate_limit_error()
            limiter.record_rate_limit_error(retry_after=10.0)
            limiter.record_rate_limit_error(retry_after=None)

            metrics = limiter.get_metrics()
            assert metrics.total_requests == 5
            assert metrics.rate_limit_errors == 3
            assert metrics.retry_after_parsed == 1

        asyncio.run(_test())

    def test_record_rate_limit_error_drains_bucket(self) -> None:
        """Test that recording a rate limit error with retry_after drains the bucket."""

        async def _test():
            config = RateLimitConfig(
                max_requests_per_minute=600,
                parse_retry_after=True,
            )
            limiter = RateLimiter(config)

            # First acquire should be immediate
            wait1 = await limiter.acquire()
            assert wait1 == 0.0

            # Record error with retry_after, which drains the bucket
            limiter.record_rate_limit_error(retry_after=60.0)

            # The bucket tokens should now be negative, so next consume requires waiting
            wait2 = limiter._bucket.consume(1.0)
            assert wait2 > 0.0

        asyncio.run(_test())

    def test_backoff_delays_across_strategies(self) -> None:
        """Test backoff delay behavior across all three strategies at once."""
        fixed_limiter = RateLimiter(
            RateLimitConfig(strategy=RateLimitStrategy.FIXED, initial_delay_seconds=5.0)
        )
        exp_limiter = RateLimiter(
            RateLimitConfig(
                strategy=RateLimitStrategy.EXPONENTIAL,
                initial_delay_seconds=1.0,
                max_delay_seconds=32.0,
            )
        )
        adaptive_limiter = RateLimiter(
            RateLimitConfig(
                strategy=RateLimitStrategy.ADAPTIVE,
                initial_delay_seconds=1.0,
                max_delay_seconds=32.0,
            )
        )

        for attempt in range(6):
            fixed_delay = fixed_limiter.get_backoff_delay(attempt)
            exp_delay = exp_limiter.get_backoff_delay(attempt)
            adaptive_delay = adaptive_limiter.get_backoff_delay(attempt)

            # Fixed is always the same
            assert fixed_delay == 5.0

            # Exponential grows: min(1 * 2^attempt, 32)
            expected_exp = min(1.0 * (2**attempt), 32.0)
            assert exp_delay == expected_exp

            # Adaptive is at least the exponential base, at most 25% more
            assert adaptive_delay >= expected_exp
            assert adaptive_delay <= expected_exp * 1.25
