"""Exception hierarchy for provider errors."""


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(
        self, message: str, provider: str, cause: Exception | None = None
    ) -> None:
        self.provider = provider
        self.cause = cause
        super().__init__(f"[{provider}] {message}")


class ConfigurationError(ProviderError):
    """Raised when provider configuration is invalid."""

    pass


class AuthenticationError(ProviderError):
    """Raised when API key is missing or invalid."""

    pass


class ProviderNotFoundError(ProviderError):
    """Raised when requested provider type is not registered."""

    pass


class ProviderMismatchError(ProviderError):
    """Raised when current provider doesn't match indexed data."""

    def __init__(
        self,
        current_provider: str,
        current_model: str,
        indexed_provider: str,
        indexed_model: str,
    ) -> None:
        message = (
            f"Provider mismatch: index was created with "
            f"{indexed_provider}/{indexed_model}, "
            f"but current config uses {current_provider}/{current_model}. "
            f"Re-index with --force to update."
        )
        super().__init__(message, current_provider)
        self.current_model = current_model
        self.indexed_provider = indexed_provider
        self.indexed_model = indexed_model


class RateLimitError(ProviderError):
    """Raised when provider rate limit is hit."""

    def __init__(self, provider: str, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after}s"
        super().__init__(message, provider)


class ModelNotFoundError(ProviderError):
    """Raised when specified model is not available."""

    def __init__(
        self, provider: str, model: str, available_models: list[str] | None = None
    ) -> None:
        self.model = model
        self.available_models = available_models or []
        if available_models:
            message = (
                f"Model '{model}' not found. "
                f"Available: {', '.join(available_models[:5])}"
            )
        else:
            message = f"Model '{model}' not found"
        super().__init__(message, provider)


class OllamaConnectionError(ProviderError):
    """Raised when Ollama is not running or unreachable."""

    def __init__(self, base_url: str, cause: Exception | None = None) -> None:
        message = (
            f"Cannot connect to Ollama at {base_url}. "
            "Ensure Ollama is running with 'ollama serve' command."
        )
        super().__init__(message, "ollama", cause)
        self.base_url = base_url
