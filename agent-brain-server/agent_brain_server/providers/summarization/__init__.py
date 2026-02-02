"""Summarization providers for Agent Brain.

This module provides summarization/LLM implementations for:
- Anthropic (Claude models)
- OpenAI (GPT-4, GPT-4o, etc.)
- Gemini (gemini-1.5-flash, gemini-1.5-pro, etc.)
- Grok (grok-beta, etc.)
- Ollama (llama3.2, mistral, etc.)
"""

from agent_brain_server.providers.factory import ProviderRegistry
from agent_brain_server.providers.summarization.anthropic import (
    AnthropicSummarizationProvider,
)
from agent_brain_server.providers.summarization.gemini import (
    GeminiSummarizationProvider,
)
from agent_brain_server.providers.summarization.grok import GrokSummarizationProvider
from agent_brain_server.providers.summarization.ollama import (
    OllamaSummarizationProvider,
)
from agent_brain_server.providers.summarization.openai import (
    OpenAISummarizationProvider,
)

# Register summarization providers
ProviderRegistry.register_summarization_provider(
    "anthropic", AnthropicSummarizationProvider
)
ProviderRegistry.register_summarization_provider("openai", OpenAISummarizationProvider)
ProviderRegistry.register_summarization_provider("gemini", GeminiSummarizationProvider)
ProviderRegistry.register_summarization_provider("grok", GrokSummarizationProvider)
ProviderRegistry.register_summarization_provider("ollama", OllamaSummarizationProvider)

__all__ = [
    "AnthropicSummarizationProvider",
    "OpenAISummarizationProvider",
    "GeminiSummarizationProvider",
    "GrokSummarizationProvider",
    "OllamaSummarizationProvider",
]
