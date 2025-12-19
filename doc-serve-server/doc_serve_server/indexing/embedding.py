"""Embedding generation using OpenAI's text-embedding models."""

import logging
from collections.abc import Awaitable, Callable
from typing import Optional

from anthropic import AsyncAnthropic
from llama_index.core.extractors import SummaryExtractor
from openai import AsyncOpenAI

from doc_serve_server.config import settings

from .chunking import TextChunk

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generates embeddings using OpenAI's embedding models.

    Supports batch processing with configurable batch sizes
    and automatic retry on rate limits.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
    ):
        """
        Initialize the embedding generator.

        Args:
            api_key: OpenAI API key. Defaults to config value.
            model: Embedding model name. Defaults to config value.
            batch_size: Number of texts to embed per API call. Defaults to 100.
        """
        self.model = model or settings.EMBEDDING_MODEL
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE

        # Initialize OpenAI async client
        self.client = AsyncOpenAI(
            api_key=api_key or settings.OPENAI_API_KEY,
        )

        # Initialize Anthropic client for summarization
        self.anthropic_client = AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
        )

        # Store prompt template for later use
        self.summary_prompt_template = self._get_summary_prompt_template()

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    async def embed_texts(
        self,
        texts: list[str],
        progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.
            progress_callback: Optional callback(processed, total) for progress.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        # Process in batches to respect API limits
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]

            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                )

                # Extract embeddings in order
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                if progress_callback:
                    await progress_callback(
                        min(i + self.batch_size, len(texts)),
                        len(texts),
                    )

                logger.debug(
                    f"Generated embeddings for batch {i // self.batch_size + 1} "
                    f"({len(batch)} texts)"
                )

            except Exception as e:
                logger.error(f"Failed to generate embeddings for batch: {e}")
                raise

        return all_embeddings

    async def embed_chunks(
        self,
        chunks: list[TextChunk],
        progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for a list of text chunks.

        Args:
            chunks: List of TextChunk objects.
            progress_callback: Optional callback for progress updates.

        Returns:
            List of embedding vectors corresponding to each chunk.
        """
        texts = [chunk.text for chunk in chunks]
        return await self.embed_texts(texts, progress_callback)

    async def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding for a search query.

        This is a convenience wrapper around embed_text for queries.

        Args:
            query: The search query text.

        Returns:
            Query embedding vector.
        """
        return await self.embed_text(query)

    def get_embedding_dimensions(self) -> int:
        """
        Get the expected embedding dimensions for the current model.

        Returns:
            Number of dimensions in the embedding vector.
        """
        # Known dimensions for OpenAI models
        model_dimensions = {
            "text-embedding-3-large": 3072,
            "text-embedding-3-small": 1536,
            "text-embedding-ada-002": 1536,
        }
        return model_dimensions.get(self.model, settings.EMBEDDING_DIMENSIONS)

    def get_code_summary_prompt(self, language: str = "unknown", code_type: str = "general") -> str:
        """
        Get a code-specific prompt template for summarization.

        Args:
            language: Programming language (python, javascript, etc.)
            code_type: Type of code (function, class, module, etc.)

        Returns:
            Tailored prompt template for the specific code type.
        """
        base_prompt = (
            "You are an expert software engineer analyzing source code. "
            "Provide a concise 1-2 sentence summary of what this code does. "
            "Focus on the functionality, purpose, and behavior. "
            "Be specific about inputs, outputs, and side effects. "
            "Ignore implementation details and focus on what the code accomplishes.\n\n"
            "Code to summarize:\n{context_str}\n\n"
            "Summary:"
        )

        # Language-specific enhancements
        if language.lower() == "python":
            base_prompt = (
                "You are analyzing Python source code. "
                "Consider Python-specific patterns like decorators, generators, context managers, etc. "
                + base_prompt
            )
        elif language.lower() == "javascript":
            base_prompt = (
                "You are analyzing JavaScript/TypeScript code. "
                "Consider async/await patterns, promises, React components, etc. "
                + base_prompt
            )
        elif language.lower() == "java":
            base_prompt = (
                "You are analyzing Java code. "
                "Consider OOP patterns, exception handling, annotations, etc. "
                + base_prompt
            )

        # Code type specific guidance
        if code_type == "function":
            base_prompt = (
                "This is a function definition. "
                "Focus on what the function accomplishes, its parameters, and return value. "
                + base_prompt
            )
        elif code_type == "class":
            base_prompt = (
                "This is a class definition. "
                "Focus on the class responsibilities, key methods, and overall purpose. "
                + base_prompt
            )
        elif code_type == "method":
            base_prompt = (
                "This is a class method. "
                "Focus on what the method does within the context of its class. "
                + base_prompt
            )

        return base_prompt

    def _get_summary_prompt_template(self) -> str:
        """
        Get the default prompt template for code summarization.

        Returns:
            Default prompt template string.
        """
        return self.get_code_summary_prompt()

    async def generate_summary(self, code_text: str) -> str:
        """
        Generate a natural language summary of code using Claude.

        Args:
            code_text: The source code to summarize.

        Returns:
            Natural language summary of the code's functionality.
        """
        try:
            # Use Claude directly with custom prompt
            prompt = self.summary_prompt_template.format(context_str=code_text)

            response = await self.anthropic_client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=300,
                temperature=0.1,  # Low temperature for consistent summaries
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            summary = response.content[0].text.strip()

            if summary and len(summary) > 10:  # Ensure we got a meaningful summary
                return summary
            else:
                logger.warning("Claude returned empty or too short summary")
                return self._extract_fallback_summary(code_text)

        except Exception as e:
            logger.error(f"Failed to generate code summary: {e}")
            # Fallback: try to extract from docstrings/comments
            return self._extract_fallback_summary(code_text)

    def _extract_fallback_summary(self, code_text: str) -> str:
        """
        Extract summary from docstrings or comments as fallback.

        Args:
            code_text: Source code to analyze.

        Returns:
            Extracted summary or empty string.
        """
        import re

        # Try to find Python docstrings
        docstring_match = re.search(r'""".*?"""', code_text, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(0).strip('"""').strip()
            if len(docstring) > 10:  # Only use if substantial
                return docstring[:200] + "..." if len(docstring) > 200 else docstring

        # Try to find function/class comments
        comment_match = re.search(r'#.*(?:function|class|method|def)', code_text, re.IGNORECASE)
        if comment_match:
            return comment_match.group(0).strip('#').strip()

        # Last resort: first line if it looks like a comment
        lines = code_text.strip().split('\n')
        first_line = lines[0].strip()
        if first_line.startswith(('#', '//', '/*')):
            return first_line.lstrip('#/*').strip()

        return ""  # No summary available


# Singleton instance
_embedding_generator: Optional[EmbeddingGenerator] = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Get the global embedding generator instance."""
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    return _embedding_generator
