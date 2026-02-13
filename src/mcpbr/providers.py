"""Model provider abstractions for different LLM APIs."""

import json
import os
import uuid
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


class OpenAIProvider:
    """Provider for OpenAI API (GPT models)."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
    ) -> None:
        """Initialize OpenAI provider.

        Args:
            model: OpenAI model ID (e.g., 'gpt-4o', 'gpt-4-turbo').
            api_key: API key. If None, uses OPENAI_API_KEY env var.
        """
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        import openai  # type: ignore[import-not-found]

        self._client = openai.OpenAI(api_key=self._api_key)

    @property
    def model(self) -> str:
        return self._model

    def get_tool_format(self) -> str:
        return "openai"

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat.completions.create(**kwargs)

        if not response.choices:
            raise RuntimeError("OpenAI API returned empty response choices")

        choice = response.choices[0]
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                )

        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=choice.message.content,
                tool_calls=tool_calls,
            ),
            finish_reason=choice.finish_reason,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )


class GeminiProvider:
    """Provider for Google Gemini API."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
    ) -> None:
        """Initialize Gemini provider.

        Args:
            model: Gemini model ID (e.g., 'gemini-2.0-flash', 'gemini-1.5-pro').
            api_key: API key. If None, uses GOOGLE_API_KEY env var.
        """
        self._model = model
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Google API key required. Set GOOGLE_API_KEY environment variable "
                "or pass api_key parameter."
            )
        import google.generativeai as genai  # type: ignore[import-not-found]

        genai.configure(api_key=self._api_key)
        self._genai = genai
        self._client = genai.GenerativeModel(model)

    @property
    def model(self) -> str:
        return self._model

    def get_tool_format(self) -> str:
        return "openai"

    def _convert_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Convert OpenAI-style messages to Gemini content format.

        Extracts system messages to use as system_instruction (Gemini's native
        system prompt support), and converts the remaining messages.

        Args:
            messages: List of OpenAI-style message dicts.

        Returns:
            Tuple of (contents, system_instruction). system_instruction is None
            if no system message was found.
        """
        contents: list[dict[str, Any]] = []
        system_instruction: str | None = None
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                system_instruction = msg.get("content", "")
            elif role == "assistant":
                contents.append({"role": "model", "parts": [msg.get("content", "")]})
            else:
                contents.append({"role": role, "parts": [msg.get("content", "")]})
        return contents, system_instruction

    def _convert_tools(self, tools: list[dict[str, Any]] | None) -> list[Any] | None:
        """Convert OpenAI-style tool definitions to Gemini function declarations.

        Args:
            tools: List of OpenAI-style tool dicts.

        Returns:
            List of Gemini Tool objects, or None.
        """
        if not tools:
            return None

        function_declarations = []
        for tool in tools:
            func = tool.get("function", {})
            function_declarations.append(
                self._genai.protos.FunctionDeclaration(
                    name=func.get("name", ""),
                    description=func.get("description", ""),
                    parameters=func.get("parameters"),
                )
            )
        return [self._genai.protos.Tool(function_declarations=function_declarations)]

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        contents, system_instruction = self._convert_messages(messages)
        gemini_tools = self._convert_tools(tools)

        kwargs: dict[str, Any] = {
            "contents": contents,
            "generation_config": {"max_output_tokens": max_tokens},
        }
        if gemini_tools:
            kwargs["tools"] = gemini_tools
        if system_instruction:
            kwargs["system_instruction"] = system_instruction

        response = self._client.generate_content(**kwargs)

        if not response.candidates:
            raise RuntimeError("Gemini API returned empty candidates")

        content_text = ""
        tool_calls = []
        candidate = response.candidates[0]

        for part in candidate.content.parts:
            if part.function_call and part.function_call.name:
                args_dict = dict(part.function_call.args) if part.function_call.args else {}
                tool_calls.append(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:24]}",
                        name=part.function_call.name,
                        arguments=json.dumps(args_dict),
                    )
                )
            elif part.text:
                content_text = part.text

        finish_reason = "stop"
        if tool_calls:
            finish_reason = "tool_calls"
        elif hasattr(candidate.finish_reason, "name"):
            reason_name = candidate.finish_reason.name
            if reason_name == "STOP":
                finish_reason = "stop"
            elif reason_name == "MAX_TOKENS":
                finish_reason = "length"

        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=content_text if content_text else None,
                tool_calls=tool_calls,
            ),
            finish_reason=finish_reason,
            input_tokens=getattr(response.usage_metadata, "prompt_token_count", 0)
            if response.usage_metadata
            else 0,
            output_tokens=getattr(response.usage_metadata, "candidates_token_count", 0)
            if response.usage_metadata
            else 0,
        )


class QwenProvider:
    """Provider for Alibaba Qwen API (OpenAI-compatible via DashScope).

    Qwen models are accessed through the DashScope international API endpoint
    which provides an OpenAI-compatible interface.
    """

    DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
    ) -> None:
        """Initialize Qwen provider.

        Args:
            model: Qwen model ID (e.g., 'qwen-plus', 'qwen-turbo', 'qwen-max').
            api_key: API key. If None, uses DASHSCOPE_API_KEY env var.
        """
        self._model = model
        self._api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not self._api_key:
            raise ValueError(
                "DashScope API key required. Set DASHSCOPE_API_KEY environment variable "
                "or pass api_key parameter."
            )
        import openai  # type: ignore[import-not-found]

        self._client = openai.OpenAI(
            api_key=self._api_key,
            base_url=self.DASHSCOPE_BASE_URL,
        )

    @property
    def model(self) -> str:
        return self._model

    def get_tool_format(self) -> str:
        return "openai"

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat.completions.create(**kwargs)

        if not response.choices:
            raise RuntimeError("Qwen API returned empty response choices")

        choice = response.choices[0]
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                )

        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=choice.message.content,
                tool_calls=tool_calls,
            ),
            finish_reason=choice.finish_reason,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )


PROVIDER_REGISTRY: dict[str, type] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "qwen": QwenProvider,
}


def create_provider(
    provider_name: str,
    model: str,
    api_key: str | None = None,
) -> ModelProvider:
    """Factory function to create a model provider.

    Args:
        provider_name: Name of the provider ('anthropic', 'openai', 'gemini', 'qwen').
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
    provider: ModelProvider = provider_class(model=model, api_key=api_key)
    return provider


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
