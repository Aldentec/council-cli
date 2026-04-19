from __future__ import annotations

from council.providers.anthropic.provider import AnthropicProvider
from council.providers.base import LLMProvider
from council.providers.ollama.provider import OllamaProvider


def detect_provider(model: str, explicit: str | None = None) -> str:
    """Return 'anthropic' for Claude models, 'ollama' for everything else."""
    if explicit:
        return explicit
    return "anthropic" if model.startswith("claude-") else "ollama"


def make_provider(
    provider_name: str,
    ollama_base_url: str = "http://localhost:11434",
    ollama_default_model: str = "llama3.2",
) -> LLMProvider:
    if provider_name == "anthropic":
        return AnthropicProvider()
    if provider_name == "ollama":
        return OllamaProvider(base_url=ollama_base_url, default_model=ollama_default_model)
    raise ValueError(f"Unknown provider: {provider_name!r}")


__all__ = ["LLMProvider", "AnthropicProvider", "OllamaProvider", "detect_provider", "make_provider"]
