"""Tests for multi-provider support (OpenAI, Gemini, Qwen).

Since openai and google-generativeai are optional dependencies that may not
be installed in the test environment, we inject mock modules into sys.modules
before importing the provider classes.
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Inject mock modules for optional dependencies BEFORE importing providers
# ---------------------------------------------------------------------------

# Create mock openai module
_mock_openai_module = MagicMock()
_mock_openai_module.OpenAI = MagicMock()

# Create mock google.generativeai module hierarchy
_mock_google = MagicMock()
_mock_google_generativeai = MagicMock()
_mock_google.generativeai = _mock_google_generativeai

# Store original modules to restore later if needed
_original_openai = sys.modules.get("openai")
_original_google = sys.modules.get("google")
_original_google_generativeai = sys.modules.get("google.generativeai")

# Only inject if they are not already available
if "openai" not in sys.modules:
    sys.modules["openai"] = _mock_openai_module
if "google" not in sys.modules:
    sys.modules["google"] = _mock_google
if "google.generativeai" not in sys.modules:
    sys.modules["google.generativeai"] = _mock_google_generativeai

from mcpbr.config import VALID_PROVIDERS  # noqa: E402
from mcpbr.models import SUPPORTED_MODELS, get_models_by_provider  # noqa: E402
from mcpbr.pricing import MODEL_PRICING, get_model_pricing  # noqa: E402
from mcpbr.providers import (  # noqa: E402
    PROVIDER_REGISTRY,
    ChatResponse,
    GeminiProvider,
    OpenAIProvider,
    QwenProvider,
    create_provider,
)

# ---------------------------------------------------------------------------
# Helper: reset mock openai module before each test that uses it
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_mock_modules():
    """Reset mock module state between tests."""
    _mock_openai_module.OpenAI.reset_mock()
    _mock_google_generativeai.configure.reset_mock()
    _mock_google_generativeai.GenerativeModel.reset_mock()
    yield


# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------


class TestProviderRegistry:
    """Tests for the PROVIDER_REGISTRY containing all four providers."""

    def test_registry_has_anthropic(self) -> None:
        assert "anthropic" in PROVIDER_REGISTRY

    def test_registry_has_openai(self) -> None:
        assert "openai" in PROVIDER_REGISTRY

    def test_registry_has_gemini(self) -> None:
        assert "gemini" in PROVIDER_REGISTRY

    def test_registry_has_qwen(self) -> None:
        assert "qwen" in PROVIDER_REGISTRY

    def test_registry_has_exactly_four_providers(self) -> None:
        assert len(PROVIDER_REGISTRY) == 4

    def test_registry_maps_to_correct_classes(self) -> None:
        assert PROVIDER_REGISTRY["openai"] is OpenAIProvider
        assert PROVIDER_REGISTRY["gemini"] is GeminiProvider
        assert PROVIDER_REGISTRY["qwen"] is QwenProvider


# ---------------------------------------------------------------------------
# VALID_PROVIDERS config
# ---------------------------------------------------------------------------


class TestValidProviders:
    """Tests for VALID_PROVIDERS in config.py."""

    def test_includes_anthropic(self) -> None:
        assert "anthropic" in VALID_PROVIDERS

    def test_includes_openai(self) -> None:
        assert "openai" in VALID_PROVIDERS

    def test_includes_gemini(self) -> None:
        assert "gemini" in VALID_PROVIDERS

    def test_includes_qwen(self) -> None:
        assert "qwen" in VALID_PROVIDERS

    def test_has_four_providers(self) -> None:
        assert len(VALID_PROVIDERS) == 4


# ---------------------------------------------------------------------------
# OpenAIProvider
# ---------------------------------------------------------------------------


class TestOpenAIProviderInit:
    """Tests for OpenAIProvider initialization."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key-123"})
    def test_init_with_env_key(self) -> None:
        provider = OpenAIProvider(model="gpt-4o")
        assert provider.model == "gpt-4o"
        _mock_openai_module.OpenAI.assert_called_with(api_key="test-key-123")

    def test_init_with_explicit_key(self) -> None:
        provider = OpenAIProvider(model="gpt-4o", api_key="explicit-key")
        assert provider.model == "gpt-4o"
        _mock_openai_module.OpenAI.assert_called_with(api_key="explicit-key")

    @patch.dict("os.environ", {}, clear=True)
    def test_init_missing_key_raises(self) -> None:
        with pytest.raises(ValueError, match="OpenAI API key required"):
            OpenAIProvider(model="gpt-4o")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_get_tool_format(self) -> None:
        provider = OpenAIProvider(model="gpt-4o")
        assert provider.get_tool_format() == "openai"


class TestOpenAIProviderChat:
    """Tests for OpenAIProvider.chat() with mocked API calls."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_chat_simple_response(self) -> None:
        mock_client = MagicMock()
        _mock_openai_module.OpenAI.return_value = mock_client

        # Build a mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello!"
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(model="gpt-4o")
        result = provider.chat(messages=[{"role": "user", "content": "Hi"}])

        assert isinstance(result, ChatResponse)
        assert result.message.content == "Hello!"
        assert result.message.role == "assistant"
        assert result.finish_reason == "stop"
        assert result.input_tokens == 10
        assert result.output_tokens == 5

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_chat_with_tool_calls(self) -> None:
        mock_client = MagicMock()
        _mock_openai_module.OpenAI.return_value = mock_client

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "read_file"
        mock_tool_call.function.arguments = json.dumps({"path": "/tmp/test.txt"})

        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_choice.message.tool_calls = [mock_tool_call]
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(model="gpt-4o")
        result = provider.chat(
            messages=[{"role": "user", "content": "Read the file"}],
            tools=[{"type": "function", "function": {"name": "read_file"}}],
        )

        assert result.finish_reason == "tool_calls"
        assert len(result.message.tool_calls) == 1
        assert result.message.tool_calls[0].name == "read_file"
        assert result.message.tool_calls[0].id == "call_123"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_chat_passes_tools_and_max_tokens(self) -> None:
        mock_client = MagicMock()
        _mock_openai_module.OpenAI.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "ok"
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 1
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(model="gpt-4o")
        tools = [{"type": "function", "function": {"name": "foo"}}]
        provider.chat(
            messages=[{"role": "user", "content": "test"}],
            tools=tools,
            max_tokens=1024,
        )

        call_kwargs = mock_client.chat.completions.create.call_args
        # Check tools were passed (could be positional or keyword)
        passed_tools = call_kwargs.kwargs.get("tools") or call_kwargs[1].get("tools")
        assert passed_tools == tools


# ---------------------------------------------------------------------------
# GeminiProvider
# ---------------------------------------------------------------------------


class TestGeminiProviderInit:
    """Tests for GeminiProvider initialization."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-gemini-key"})
    def test_init_with_env_key(self) -> None:
        provider = GeminiProvider(model="gemini-2.0-flash")
        assert provider.model == "gemini-2.0-flash"
        _mock_google_generativeai.configure.assert_called_with(api_key="test-gemini-key")

    def test_init_with_explicit_key(self) -> None:
        provider = GeminiProvider(model="gemini-1.5-pro", api_key="explicit-gemini-key")
        assert provider.model == "gemini-1.5-pro"
        _mock_google_generativeai.configure.assert_called_with(api_key="explicit-gemini-key")

    @patch.dict("os.environ", {}, clear=True)
    def test_init_missing_key_raises(self) -> None:
        with pytest.raises(ValueError, match="Google API key required"):
            GeminiProvider(model="gemini-2.0-flash")

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    def test_get_tool_format(self) -> None:
        provider = GeminiProvider(model="gemini-2.0-flash")
        assert provider.get_tool_format() == "openai"


class TestGeminiProviderChat:
    """Tests for GeminiProvider.chat() with mocked API calls."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    def test_chat_simple_response(self) -> None:
        mock_model = MagicMock()
        _mock_google_generativeai.GenerativeModel.return_value = mock_model

        # Build mock response -- function_call=None means no tool call
        mock_part = MagicMock()
        mock_part.text = "Hello from Gemini!"
        mock_part.function_call = None

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_candidate.finish_reason = MagicMock()
        mock_candidate.finish_reason.name = "STOP"

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_response.usage_metadata.prompt_token_count = 12
        mock_response.usage_metadata.candidates_token_count = 8
        mock_model.generate_content.return_value = mock_response

        provider = GeminiProvider(model="gemini-2.0-flash")
        result = provider.chat(messages=[{"role": "user", "content": "Hi"}])

        assert isinstance(result, ChatResponse)
        assert result.message.content == "Hello from Gemini!"
        assert result.message.role == "assistant"
        assert result.finish_reason == "stop"
        assert result.input_tokens == 12
        assert result.output_tokens == 8

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    def test_chat_with_tool_calls(self) -> None:
        mock_model = MagicMock()
        _mock_google_generativeai.GenerativeModel.return_value = mock_model

        mock_fc = MagicMock()
        mock_fc.name = "read_file"
        mock_fc.args = {"path": "/tmp/test.txt"}

        mock_part = MagicMock()
        mock_part.text = ""
        mock_part.function_call = mock_fc

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_candidate.finish_reason = MagicMock()
        mock_candidate.finish_reason.name = "STOP"

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_response.usage_metadata.prompt_token_count = 20
        mock_response.usage_metadata.candidates_token_count = 10
        mock_model.generate_content.return_value = mock_response

        provider = GeminiProvider(model="gemini-2.0-flash")
        result = provider.chat(
            messages=[{"role": "user", "content": "Read file"}],
            tools=[{"type": "function", "function": {"name": "read_file"}}],
        )

        assert len(result.message.tool_calls) == 1
        assert result.message.tool_calls[0].name == "read_file"


# ---------------------------------------------------------------------------
# QwenProvider
# ---------------------------------------------------------------------------


class TestQwenProviderInit:
    """Tests for QwenProvider initialization (OpenAI-compatible API)."""

    @patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test-qwen-key"})
    def test_init_with_env_key(self) -> None:
        provider = QwenProvider(model="qwen-plus")
        assert provider.model == "qwen-plus"
        _mock_openai_module.OpenAI.assert_called_with(
            api_key="test-qwen-key",
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )

    def test_init_with_explicit_key(self) -> None:
        provider = QwenProvider(model="qwen-turbo", api_key="explicit-qwen-key")
        assert provider.model == "qwen-turbo"
        _mock_openai_module.OpenAI.assert_called_with(
            api_key="explicit-qwen-key",
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_init_missing_key_raises(self) -> None:
        with pytest.raises(ValueError, match="DashScope API key required"):
            QwenProvider(model="qwen-plus")

    @patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test-key"})
    def test_get_tool_format(self) -> None:
        provider = QwenProvider(model="qwen-plus")
        assert provider.get_tool_format() == "openai"


class TestQwenProviderChat:
    """Tests for QwenProvider.chat() with mocked API calls."""

    @patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test-key"})
    def test_chat_simple_response(self) -> None:
        mock_client = MagicMock()
        _mock_openai_module.OpenAI.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from Qwen!"
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 8
        mock_response.usage.completion_tokens = 4
        mock_client.chat.completions.create.return_value = mock_response

        provider = QwenProvider(model="qwen-plus")
        result = provider.chat(messages=[{"role": "user", "content": "Hi"}])

        assert isinstance(result, ChatResponse)
        assert result.message.content == "Hello from Qwen!"
        assert result.message.role == "assistant"
        assert result.finish_reason == "stop"
        assert result.input_tokens == 8
        assert result.output_tokens == 4

    @patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test-key"})
    def test_chat_with_tool_calls(self) -> None:
        mock_client = MagicMock()
        _mock_openai_module.OpenAI.return_value = mock_client

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_qwen_456"
        mock_tool_call.function.name = "list_files"
        mock_tool_call.function.arguments = json.dumps({"dir": "/tmp"})

        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_choice.message.tool_calls = [mock_tool_call]
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 10
        mock_client.chat.completions.create.return_value = mock_response

        provider = QwenProvider(model="qwen-plus")
        result = provider.chat(
            messages=[{"role": "user", "content": "List files"}],
            tools=[{"type": "function", "function": {"name": "list_files"}}],
        )

        assert result.finish_reason == "tool_calls"
        assert len(result.message.tool_calls) == 1
        assert result.message.tool_calls[0].name == "list_files"
        assert result.message.tool_calls[0].id == "call_qwen_456"


# ---------------------------------------------------------------------------
# create_provider factory
# ---------------------------------------------------------------------------


class TestCreateProviderFactory:
    """Tests for create_provider factory function."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("anthropic.Anthropic")
    def test_create_anthropic(self, mock_anthropic: MagicMock) -> None:
        provider = create_provider("anthropic", "sonnet")
        assert provider.model == "sonnet"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_create_openai(self) -> None:
        provider = create_provider("openai", "gpt-4o")
        assert provider.model == "gpt-4o"

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    def test_create_gemini(self) -> None:
        provider = create_provider("gemini", "gemini-2.0-flash")
        assert provider.model == "gemini-2.0-flash"

    @patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test-key"})
    def test_create_qwen(self) -> None:
        provider = create_provider("qwen", "qwen-plus")
        assert provider.model == "qwen-plus"

    def test_create_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider("unknown", "some-model")


# ---------------------------------------------------------------------------
# Model Registry - new provider models
# ---------------------------------------------------------------------------


class TestNewProviderModels:
    """Tests that model registry includes models for new providers."""

    # OpenAI models
    def test_gpt4o_in_registry(self) -> None:
        assert "gpt-4o" in SUPPORTED_MODELS

    def test_gpt4_turbo_in_registry(self) -> None:
        assert "gpt-4-turbo" in SUPPORTED_MODELS

    def test_gpt4o_mini_in_registry(self) -> None:
        assert "gpt-4o-mini" in SUPPORTED_MODELS

    # Gemini models
    def test_gemini_20_flash_in_registry(self) -> None:
        assert "gemini-2.0-flash" in SUPPORTED_MODELS

    def test_gemini_15_pro_in_registry(self) -> None:
        assert "gemini-1.5-pro" in SUPPORTED_MODELS

    def test_gemini_15_flash_in_registry(self) -> None:
        assert "gemini-1.5-flash" in SUPPORTED_MODELS

    # Qwen models
    def test_qwen_plus_in_registry(self) -> None:
        assert "qwen-plus" in SUPPORTED_MODELS

    def test_qwen_turbo_in_registry(self) -> None:
        assert "qwen-turbo" in SUPPORTED_MODELS

    def test_qwen_max_in_registry(self) -> None:
        assert "qwen-max" in SUPPORTED_MODELS

    # Provider attribute checks
    def test_openai_models_provider(self) -> None:
        for model_id in ("gpt-4o", "gpt-4-turbo", "gpt-4o-mini"):
            assert SUPPORTED_MODELS[model_id].provider == "OpenAI"

    def test_gemini_models_provider(self) -> None:
        for model_id in ("gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"):
            assert SUPPORTED_MODELS[model_id].provider == "Google"

    def test_qwen_models_provider(self) -> None:
        for model_id in ("qwen-plus", "qwen-turbo", "qwen-max"):
            assert SUPPORTED_MODELS[model_id].provider == "Alibaba"

    def test_all_new_models_support_tools(self) -> None:
        new_models = [
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4o-mini",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "qwen-plus",
            "qwen-turbo",
            "qwen-max",
        ]
        for model_id in new_models:
            assert SUPPORTED_MODELS[model_id].supports_tools is True

    def test_get_models_by_provider_openai(self) -> None:
        models = get_models_by_provider("OpenAI")
        ids = [m.id for m in models]
        assert "gpt-4o" in ids
        assert "gpt-4-turbo" in ids
        assert "gpt-4o-mini" in ids

    def test_get_models_by_provider_google(self) -> None:
        models = get_models_by_provider("Google")
        ids = [m.id for m in models]
        assert "gemini-2.0-flash" in ids
        assert "gemini-1.5-pro" in ids

    def test_get_models_by_provider_alibaba(self) -> None:
        models = get_models_by_provider("Alibaba")
        ids = [m.id for m in models]
        assert "qwen-plus" in ids
        assert "qwen-turbo" in ids
        assert "qwen-max" in ids


# ---------------------------------------------------------------------------
# Pricing - new provider models
# ---------------------------------------------------------------------------


class TestNewProviderPricing:
    """Tests that pricing entries exist for new provider models."""

    def test_gpt4o_pricing(self) -> None:
        pricing = get_model_pricing("gpt-4o")
        assert pricing is not None
        assert pricing.provider == "OpenAI"
        assert pricing.input_price_per_mtok > 0
        assert pricing.output_price_per_mtok > 0

    def test_gpt4_turbo_pricing(self) -> None:
        pricing = get_model_pricing("gpt-4-turbo")
        assert pricing is not None
        assert pricing.provider == "OpenAI"

    def test_gpt4o_mini_pricing(self) -> None:
        pricing = get_model_pricing("gpt-4o-mini")
        assert pricing is not None
        assert pricing.provider == "OpenAI"

    def test_gemini_20_flash_pricing(self) -> None:
        pricing = get_model_pricing("gemini-2.0-flash")
        assert pricing is not None
        assert pricing.provider == "Google"

    def test_gemini_15_pro_pricing(self) -> None:
        pricing = get_model_pricing("gemini-1.5-pro")
        assert pricing is not None
        assert pricing.provider == "Google"

    def test_gemini_15_flash_pricing(self) -> None:
        pricing = get_model_pricing("gemini-1.5-flash")
        assert pricing is not None
        assert pricing.provider == "Google"

    def test_qwen_plus_pricing(self) -> None:
        pricing = get_model_pricing("qwen-plus")
        assert pricing is not None
        assert pricing.provider == "Alibaba"

    def test_qwen_turbo_pricing(self) -> None:
        pricing = get_model_pricing("qwen-turbo")
        assert pricing is not None
        assert pricing.provider == "Alibaba"

    def test_qwen_max_pricing(self) -> None:
        pricing = get_model_pricing("qwen-max")
        assert pricing is not None
        assert pricing.provider == "Alibaba"

    def test_all_new_models_in_pricing(self) -> None:
        new_models = [
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4o-mini",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "qwen-plus",
            "qwen-turbo",
            "qwen-max",
        ]
        for model_id in new_models:
            assert model_id in MODEL_PRICING, f"Missing pricing for {model_id}"
