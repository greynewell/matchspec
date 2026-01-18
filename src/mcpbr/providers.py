"""Model provider abstractions for different LLM APIs."""

import os
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ToolCall:
    """Represents a tool call from the model."""

    id: str
    name: str
    arguments: str


@dataclass
class ChatMessage:
    """Represents a message in the chat response."""

    role: str
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class ChatResponse:
    """Standardized response from any model provider."""

    message: ChatMessage
    finish_reason: str
    input_tokens: int = 0
    output_tokens: int = 0


@runtime_checkable
class ModelProvider(Protocol):
    """Protocol for LLM providers.

    To add a new provider:
    1. Create a class implementing this protocol
    2. Add it to PROVIDER_REGISTRY
    3. Add the provider name to VALID_PROVIDERS in config.py
    """

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """Send a chat completion request.

        Args:
            messages: List of message dictionaries.
            tools: Optional list of tool definitions.
            max_tokens: Maximum tokens to generate.

        Returns:
            Standardized ChatResponse.
        """
        ...

    def get_tool_format(self) -> str:
        """Return the tool format this provider uses.

        Returns:
            'openai' or 'anthropic'
        """
        ...

    @property
    def model(self) -> str:
        """Return the model identifier."""
        ...


class AnthropicProvider:
    """Provider for direct Anthropic API."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
    ) -> None:
        """Initialize Anthropic provider.

        Args:
            model: Anthropic model ID or alias (e.g., 'sonnet' or 'claude-sonnet-4-5-20250929').
            api_key: API key. If None, uses ANTHROPIC_API_KEY env var.
        """
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )
        import anthropic

        self._client = anthropic.Anthropic(api_key=self._api_key)

    @property
    def model(self) -> str:
        return self._model

    def get_tool_format(self) -> str:
        return "anthropic"

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        system_content = None
        filtered_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_content = msg.get("content", "")
            else:
                filtered_messages.append(msg)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": filtered_messages,
        }

        if system_content:
            kwargs["system"] = system_content

        if tools:
            kwargs["tools"] = tools

        response = self._client.messages.create(**kwargs)

        content_text = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                import json

                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=json.dumps(block.input),
                    )
                )

        finish_reason = "stop"
        if response.stop_reason == "tool_use":
            finish_reason = "tool_calls"
        elif response.stop_reason == "end_turn":
            finish_reason = "stop"

        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=content_text if content_text else None,
                tool_calls=tool_calls,
            ),
            finish_reason=finish_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


PROVIDER_REGISTRY: dict[str, type] = {
    "anthropic": AnthropicProvider,
}


def create_provider(
    provider_name: str,
    model: str,
    api_key: str | None = None,
) -> ModelProvider:
    """Factory function to create a model provider.

    Args:
        provider_name: Name of the provider (currently only 'anthropic').
        model: Model identifier for the provider.
        api_key: Optional API key.

    Returns:
        Configured ModelProvider instance.

    Raises:
        ValueError: If provider_name is not recognized.
    """
    if provider_name not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Available providers: {list(PROVIDER_REGISTRY.keys())}"
        )

    provider_class = PROVIDER_REGISTRY[provider_name]
    return provider_class(model=model, api_key=api_key)


def validate_provider_config(provider_name: str, model: str) -> tuple[bool, str | None]:
    """Validate provider configuration by making a simple test request.

    Args:
        provider_name: Name of the provider.
        model: Model identifier.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    try:
        provider = create_provider(provider_name, model)
        provider.chat(
            messages=[{"role": "user", "content": "Say 'ok'"}],
            max_tokens=5,
        )
        return True, None
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        error_str = str(e)
        if "not a valid model ID" in error_str:
            return False, f"Invalid model ID '{model}' for provider '{provider_name}'"
        if "401" in error_str or "unauthorized" in error_str.lower():
            return (
                False,
                f"Authentication failed for provider '{provider_name}'. Check your API key.",
            )
        if "403" in error_str or "forbidden" in error_str.lower():
            return False, f"Access forbidden for model '{model}'. Check your API key permissions."
        return False, f"Provider validation failed: {error_str}"
