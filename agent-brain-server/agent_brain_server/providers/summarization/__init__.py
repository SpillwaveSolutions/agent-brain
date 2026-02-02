"""Summarization providers for Agent Brain.

This module provides summarization/LLM implementations for:
- Anthropic (Claude 4.5 Haiku, Sonnet, Opus)
- OpenAI (GPT-5, GPT-5 Mini)
- Gemini (gemini-3-flash, gemini-3-pro)
- Grok (grok-4, grok-4-fast)
- Ollama (llama4:scout, mistral-small3.2, qwen3-coder, gemma3)
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
