"""Tests for model registry functionality."""

import re

from mcpbr.models import (
    DEFAULT_MODEL,
    SUPPORTED_MODELS,
    ModelInfo,
    get_model_info,
    get_models_by_provider,
    is_model_supported,
    list_supported_models,
    validate_model,
)

# Claude 4.5 model IDs (full names)
CLAUDE_45_MODELS = [
    "claude-opus-4-5-20251101",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
]

# Model aliases
MODEL_ALIASES = ["sonnet", "opus", "haiku"]


class TestClaude45ModelsRegistered:
    """Tests for Claude 4.5 model registration."""

    def test_all_45_models_registered(self) -> None:
        """Verify all three 4.5 models are in the registry."""
        for model_id in CLAUDE_45_MODELS:
            assert model_id in SUPPORTED_MODELS, f"Model {model_id} not in registry"

    def test_model_ids_format(self) -> None:
        """Verify model IDs follow Anthropic's naming pattern."""
        # Pattern: claude-{variant}-{version}-{date}
        pattern = r"^claude-(opus|sonnet|haiku)-4-5-\d{8}$"
        for model_id in CLAUDE_45_MODELS:
            assert re.match(pattern, model_id), (
                f"Model ID {model_id} doesn't match expected pattern"
            )

    def test_model_context_windows(self) -> None:
        """Verify all 4.5 models have 200K context window."""
        for model_id in CLAUDE_45_MODELS:
            model = SUPPORTED_MODELS[model_id]
            assert model.context_window == 200000, f"Model {model_id} has wrong context window"

    def test_model_provider_is_anthropic(self) -> None:
        """Verify all 4.5 models are from Anthropic."""
        for model_id in CLAUDE_45_MODELS:
            model = SUPPORTED_MODELS[model_id]
            assert model.provider == "Anthropic", f"Model {model_id} has wrong provider"

    def test_model_supports_tools(self) -> None:
        """Verify all 4.5 models support tool calling."""
        for model_id in CLAUDE_45_MODELS:
            model = SUPPORTED_MODELS[model_id]
            assert model.supports_tools is True, f"Model {model_id} should support tools"

    def test_model_display_names(self) -> None:
        """Verify display names include '4.5'."""
        expected_names = {
            "claude-opus-4-5-20251101": "Claude Opus 4.5",
            "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
            "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
        }
        for model_id, expected_name in expected_names.items():
            model = SUPPORTED_MODELS[model_id]
            assert model.display_name == expected_name, f"Model {model_id} has wrong display name"


class TestModelAliases:
    """Tests for model alias support."""

    def test_all_aliases_registered(self) -> None:
        """Verify all aliases are in the registry."""
        for alias in MODEL_ALIASES:
            assert alias in SUPPORTED_MODELS, f"Alias {alias} not in registry"

    def test_aliases_are_valid(self) -> None:
        """Verify aliases are recognized as supported models."""
        for alias in MODEL_ALIASES:
            assert is_model_supported(alias) is True


class TestDefaultModel:
    """Tests for default model configuration."""

    def test_default_model_is_sonnet_alias(self) -> None:
        """Ensure default model is the sonnet alias."""
        assert DEFAULT_MODEL == "sonnet", "Default model should be 'sonnet' alias"

    def test_default_model_exists(self) -> None:
        """Ensure default model is in the registry."""
        assert DEFAULT_MODEL in SUPPORTED_MODELS, "Default model not found in registry"


class TestIsModelSupported:
    """Tests for is_model_supported function."""

    def test_supported_45_models(self) -> None:
        """Test that 4.5 models are recognized as supported."""
        for model_id in CLAUDE_45_MODELS:
            assert is_model_supported(model_id) is True

    def test_unsupported_model(self) -> None:
        """Test that unknown model returns False."""
        assert is_model_supported("gpt-4-turbo") is False
        assert is_model_supported("claude-99") is False
        assert is_model_supported("") is False

    def test_case_sensitive(self) -> None:
        """Model IDs should be case-sensitive."""
        assert is_model_supported("CLAUDE-SONNET-4-5-20250929") is False
        assert is_model_supported("Claude-Sonnet-4-5-20250929") is False
        assert is_model_supported("SONNET") is False


class TestGetModelInfo:
    """Tests for get_model_info function."""

    def test_get_45_model_info(self) -> None:
        """Test retrieving info for a 4.5 model."""
        info = get_model_info("claude-sonnet-4-5-20250929")
        assert info is not None
        assert info.id == "claude-sonnet-4-5-20250929"
        assert info.display_name == "Claude Sonnet 4.5"
        assert info.context_window == 200000
        assert info.provider == "Anthropic"

    def test_get_alias_info(self) -> None:
        """Test retrieving info for an alias."""
        info = get_model_info("sonnet")
        assert info is not None
        assert info.id == "sonnet"
        assert "Sonnet" in info.display_name

    def test_get_unknown_model_returns_none(self) -> None:
        """Test that unknown model returns None."""
        info = get_model_info("nonexistent-model")
        assert info is None

    def test_returns_model_info_instance(self) -> None:
        """Test that returned value is a ModelInfo instance."""
        info = get_model_info("claude-opus-4-5-20251101")
        assert isinstance(info, ModelInfo)


class TestListSupportedModels:
    """Tests for list_supported_models function."""

    def test_returns_list(self) -> None:
        """Test that function returns a list."""
        models = list_supported_models()
        assert isinstance(models, list)

    def test_list_not_empty(self) -> None:
        """Test that list is not empty."""
        models = list_supported_models()
        assert len(models) > 0

    def test_contains_45_models(self) -> None:
        """Test that list contains all 4.5 models."""
        models = list_supported_models()
        model_ids = [m.id for m in models]
        for model_id in CLAUDE_45_MODELS:
            assert model_id in model_ids

    def test_all_items_are_model_info(self) -> None:
        """Test that all items are ModelInfo instances."""
        models = list_supported_models()
        for model in models:
            assert isinstance(model, ModelInfo)


class TestGetModelsByProvider:
    """Tests for get_models_by_provider function."""

    def test_get_anthropic_models(self) -> None:
        """Test retrieving Anthropic models."""
        models = get_models_by_provider("Anthropic")
        assert len(models) > 0
        for model in models:
            assert model.provider == "Anthropic"

    def test_case_insensitive(self) -> None:
        """Test that provider lookup is case-insensitive."""
        models_lower = get_models_by_provider("anthropic")
        models_upper = get_models_by_provider("ANTHROPIC")
        models_mixed = get_models_by_provider("Anthropic")

        assert len(models_lower) == len(models_upper) == len(models_mixed)

    def test_unknown_provider_returns_empty(self) -> None:
        """Test that unknown provider returns empty list."""
        models = get_models_by_provider("OpenAI")
        assert models == []


class TestValidateModel:
    """Tests for validate_model function."""

    def test_valid_45_model(self) -> None:
        """Test validation of valid 4.5 model."""
        is_valid, error = validate_model("claude-sonnet-4-5-20250929")
        assert is_valid is True
        assert error == ""

    def test_valid_alias(self) -> None:
        """Test validation of model alias."""
        is_valid, error = validate_model("sonnet")
        assert is_valid is True
        assert error == ""

    def test_invalid_model(self) -> None:
        """Test validation of invalid model."""
        is_valid, error = validate_model("invalid-model-123")
        assert is_valid is False
        assert "not in the list" in error

    def test_suggestion_for_typo(self) -> None:
        """Test that validation suggests similar model for typos."""
        # Partial match should suggest the correct model
        is_valid, error = validate_model("claude-sonnet-4-5")
        assert is_valid is False
        assert "Did you mean" in error

    def test_suggestion_contains_model_command(self) -> None:
        """Test that error message mentions mcpbr models command."""
        is_valid, error = validate_model("bad-model")
        assert is_valid is False
        assert "mcpbr models" in error


class TestModelInfoDataclass:
    """Tests for ModelInfo dataclass."""

    def test_create_model_info(self) -> None:
        """Test creating a ModelInfo instance."""
        info = ModelInfo(
            id="test-model",
            provider="TestProvider",
            display_name="Test Model",
            context_window=100000,
        )
        assert info.id == "test-model"
        assert info.provider == "TestProvider"
        assert info.display_name == "Test Model"
        assert info.context_window == 100000
        assert info.supports_tools is True  # default
        assert info.notes == ""  # default

    def test_model_info_with_all_fields(self) -> None:
        """Test ModelInfo with all fields specified."""
        info = ModelInfo(
            id="custom-model",
            provider="CustomProvider",
            display_name="Custom Model",
            context_window=50000,
            supports_tools=False,
            notes="Some notes",
        )
        assert info.supports_tools is False
        assert info.notes == "Some notes"
