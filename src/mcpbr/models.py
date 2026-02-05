"""Model registry for supported LLMs with tool-calling capability."""

from dataclasses import dataclass


@dataclass
class ModelInfo:
    """Information about a supported model."""

    id: str
    provider: str
    display_name: str
    context_window: int
    supports_tools: bool = True
    notes: str = ""


SUPPORTED_MODELS: dict[str, ModelInfo] = {
    # Anthropic models via Claude Code CLI
    # Claude 4.5 models (latest)
    "claude-opus-4-5-20251101": ModelInfo(
        id="claude-opus-4-5-20251101",
        provider="Anthropic",
        display_name="Claude Opus 4.5",
        context_window=200000,
        notes="Alias: opus",
    ),
    "claude-sonnet-4-5-20250929": ModelInfo(
        id="claude-sonnet-4-5-20250929",
        provider="Anthropic",
        display_name="Claude Sonnet 4.5",
        context_window=200000,
        notes="Alias: sonnet (default)",
    ),
    "claude-haiku-4-5-20251001": ModelInfo(
        id="claude-haiku-4-5-20251001",
        provider="Anthropic",
        display_name="Claude Haiku 4.5",
        context_window=200000,
        notes="Alias: haiku",
    ),
    # Aliases (Claude Code CLI shortcuts)
    "sonnet": ModelInfo(
        id="sonnet",
        provider="Anthropic",
        display_name="Claude Sonnet (alias)",
        context_window=200000,
        notes="Resolves to latest Sonnet model",
    ),
    "opus": ModelInfo(
        id="opus",
        provider="Anthropic",
        display_name="Claude Opus (alias)",
        context_window=200000,
        notes="Resolves to latest Opus model",
    ),
    "haiku": ModelInfo(
        id="haiku",
        provider="Anthropic",
        display_name="Claude Haiku (alias)",
        context_window=200000,
        notes="Resolves to latest Haiku model",
    ),
    # OpenAI models
    "gpt-4o": ModelInfo(
        id="gpt-4o",
        provider="OpenAI",
        display_name="GPT-4o",
        context_window=128000,
        notes="Most capable OpenAI model with vision",
    ),
    "gpt-4-turbo": ModelInfo(
        id="gpt-4-turbo",
        provider="OpenAI",
        display_name="GPT-4 Turbo",
        context_window=128000,
        notes="High capability with faster inference",
    ),
    "gpt-4o-mini": ModelInfo(
        id="gpt-4o-mini",
        provider="OpenAI",
        display_name="GPT-4o Mini",
        context_window=128000,
        notes="Compact and cost-effective GPT-4o variant",
    ),
    # Google Gemini models
    "gemini-2.0-flash": ModelInfo(
        id="gemini-2.0-flash",
        provider="Google",
        display_name="Gemini 2.0 Flash",
        context_window=1048576,
        notes="Latest fast Gemini model",
    ),
    "gemini-1.5-pro": ModelInfo(
        id="gemini-1.5-pro",
        provider="Google",
        display_name="Gemini 1.5 Pro",
        context_window=2097152,
        notes="High-capability model with 2M token context",
    ),
    "gemini-1.5-flash": ModelInfo(
        id="gemini-1.5-flash",
        provider="Google",
        display_name="Gemini 1.5 Flash",
        context_window=1048576,
        notes="Fast and cost-effective Gemini model",
    ),
    # Alibaba Qwen models (via DashScope)
    "qwen-plus": ModelInfo(
        id="qwen-plus",
        provider="Alibaba",
        display_name="Qwen Plus",
        context_window=131072,
        notes="Balanced Qwen model for general tasks",
    ),
    "qwen-turbo": ModelInfo(
        id="qwen-turbo",
        provider="Alibaba",
        display_name="Qwen Turbo",
        context_window=131072,
        notes="Fast and cost-effective Qwen model",
    ),
    "qwen-max": ModelInfo(
        id="qwen-max",
        provider="Alibaba",
        display_name="Qwen Max",
        context_window=131072,
        notes="Most capable Qwen model",
    ),
}

DEFAULT_MODEL = "sonnet"


def is_model_supported(model_id: str) -> bool:
    """Check if a model is in the supported list.

    Args:
        model_id: Anthropic model ID.

    Returns:
        True if the model is supported.
    """
    return model_id in SUPPORTED_MODELS


def get_model_info(model_id: str) -> ModelInfo | None:
    """Get information about a model.

    Args:
        model_id: Anthropic model ID.

    Returns:
        ModelInfo if found, None otherwise.
    """
    return SUPPORTED_MODELS.get(model_id)


def list_supported_models() -> list[ModelInfo]:
    """Get a list of all supported models.

    Returns:
        List of ModelInfo objects.
    """
    return list(SUPPORTED_MODELS.values())


def get_models_by_provider(provider: str) -> list[ModelInfo]:
    """Get models filtered by provider.

    Args:
        provider: Provider name (e.g., "Anthropic").

    Returns:
        List of ModelInfo objects from that provider.
    """
    result = []
    for model in SUPPORTED_MODELS.values():
        if model.provider.lower() == provider.lower():
            result.append(model)
    return result


def validate_model(model_id: str) -> tuple[bool, str]:
    """Validate a model ID and return a helpful error message if invalid.

    Args:
        model_id: Anthropic model ID to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if is_model_supported(model_id):
        return True, ""

    supported_ids = list(SUPPORTED_MODELS.keys())
    suggestion = ""

    model_lower = model_id.lower()
    for supported_id in supported_ids:
        if model_lower in supported_id.lower() or supported_id.lower() in model_lower:
            suggestion = f" Did you mean '{supported_id}'?"
            break

    return False, (
        f"Model '{model_id}' is not in the list of supported tool-capable models.{suggestion}\n"
        f"Run 'mcpbr models' to see available models."
    )
