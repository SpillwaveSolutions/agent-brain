# Data Model: Pluggable Model Providers

**Feature**: 103-pluggable-providers
**Date**: 2026-02-01
**Status**: Complete

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      ProviderSettings                            │
│  (Top-level YAML configuration)                                  │
├─────────────────────────────────────────────────────────────────┤
│  embedding: EmbeddingConfig                                      │
│  summarization: SummarizationConfig                              │
└─────────────────────────────────────────────────────────────────┘
                    │                         │
                    ▼                         ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│     EmbeddingConfig       │   │    SummarizationConfig        │
├───────────────────────────┤   ├───────────────────────────────┤
│  provider: EmbeddingType  │   │  provider: SummarizationType  │
│  model: str               │   │  model: str                   │
│  api_key_env: str?        │   │  api_key_env: str?            │
│  base_url: str?           │   │  base_url: str?               │
│  params: dict             │   │  params: dict                 │
└───────────────────────────┘   └───────────────────────────────┘
```

## Enumerations

### EmbeddingProviderType

```python
from enum import Enum

class EmbeddingProviderType(str, Enum):
    """Supported embedding providers."""
    OPENAI = "openai"
    OLLAMA = "ollama"
    COHERE = "cohere"
```

### SummarizationProviderType

```python
class SummarizationProviderType(str, Enum):
    """Supported summarization providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    GROK = "grok"
    OLLAMA = "ollama"
```

## Configuration Models

### EmbeddingConfig

Configuration for embedding provider selection.

```python
from pydantic import BaseModel, Field
from typing import Optional

class EmbeddingConfig(BaseModel):
    """Configuration for embedding provider."""

    provider: EmbeddingProviderType = Field(
        default=EmbeddingProviderType.OPENAI,
        description="Embedding provider to use"
    )
    model: str = Field(
        default="text-embedding-3-large",
        description="Model name for embeddings"
    )
    api_key_env: Optional[str] = Field(
        default="OPENAI_API_KEY",
        description="Environment variable name containing API key"
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Custom base URL (for Ollama or compatible APIs)"
    )
    params: dict = Field(
        default_factory=dict,
        description="Provider-specific parameters"
    )

    class Config:
        use_enum_values = True
```

**Fields**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | EmbeddingProviderType | `openai` | Which provider to use |
| `model` | str | `text-embedding-3-large` | Model identifier |
| `api_key_env` | str? | `OPENAI_API_KEY` | Env var name for API key |
| `base_url` | str? | `None` | Override base URL |
| `params` | dict | `{}` | Extra provider params |

**Validation Rules**:
- `provider` must be a valid EmbeddingProviderType
- `model` must not be empty
- `api_key_env` required unless provider is `ollama`
- If `provider` is `ollama`, `base_url` defaults to `http://localhost:11434/v1`

---

### SummarizationConfig

Configuration for summarization/LLM provider selection.

```python
class SummarizationConfig(BaseModel):
    """Configuration for summarization provider."""

    provider: SummarizationProviderType = Field(
        default=SummarizationProviderType.ANTHROPIC,
        description="Summarization provider to use"
    )
    model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model name for summarization"
    )
    api_key_env: Optional[str] = Field(
        default="ANTHROPIC_API_KEY",
        description="Environment variable name containing API key"
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Custom base URL (for Grok or Ollama)"
    )
    params: dict = Field(
        default_factory=dict,
        description="Provider-specific parameters"
    )

    class Config:
        use_enum_values = True
```

**Fields**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | SummarizationProviderType | `anthropic` | Which provider to use |
| `model` | str | `claude-haiku-4-5-20251001` | Model identifier |
| `api_key_env` | str? | `ANTHROPIC_API_KEY` | Env var name for API key |
| `base_url` | str? | `None` | Override base URL |
| `params` | dict | `{}` | Extra provider params (max_tokens, temperature) |

**Validation Rules**:
- `provider` must be a valid SummarizationProviderType
- `model` must not be empty
- `api_key_env` required unless provider is `ollama`

---

### ProviderSettings

Top-level configuration container.

```python
class ProviderSettings(BaseModel):
    """Top-level provider configuration."""

    embedding: EmbeddingConfig = Field(
        default_factory=EmbeddingConfig,
        description="Embedding provider configuration"
    )
    summarization: SummarizationConfig = Field(
        default_factory=SummarizationConfig,
        description="Summarization provider configuration"
    )
```

---

## Provider-Specific Parameters

### OpenAI Embedding Params

```python
class OpenAIEmbeddingParams(BaseModel):
    """OpenAI-specific embedding parameters."""
    batch_size: int = Field(default=100, ge=1, le=2048)
    dimensions: Optional[int] = Field(default=None, description="Override dimensions")
```

### Ollama Embedding Params

```python
class OllamaEmbeddingParams(BaseModel):
    """Ollama-specific embedding parameters."""
    num_ctx: int = Field(default=2048, description="Context window size")
    num_threads: Optional[int] = Field(default=None, description="Number of threads")
```

### Cohere Embedding Params

```python
class CohereEmbeddingParams(BaseModel):
    """Cohere-specific embedding parameters."""
    input_type: str = Field(
        default="search_document",
        description="Input type: search_document, search_query, classification, clustering"
    )
    truncate: str = Field(default="END", description="Truncation strategy")
```

### Anthropic Summarization Params

```python
class AnthropicSummarizationParams(BaseModel):
    """Anthropic-specific summarization parameters."""
    max_tokens: int = Field(default=300, ge=1, le=4096)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
```

### Gemini Summarization Params

```python
class GeminiSummarizationParams(BaseModel):
    """Gemini-specific summarization parameters."""
    max_output_tokens: int = Field(default=300, ge=1, le=8192)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
```

---

## Index Metadata

Stored with the index to detect provider changes.

```python
class IndexMetadata(BaseModel):
    """Metadata stored with the index for provider tracking."""

    embedding_provider: str = Field(description="Provider used for embeddings")
    embedding_model: str = Field(description="Model used for embeddings")
    embedding_dimensions: int = Field(description="Embedding vector dimensions")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_indexed_at: Optional[datetime] = Field(default=None)
    document_count: int = Field(default=0)
```

**Validation on Startup**:
1. Load existing IndexMetadata from storage
2. Compare with current ProviderSettings
3. If provider or model changed → raise `ProviderMismatchError`
4. User must explicitly re-index with `--force` flag

---

## Default Model Mappings

### Embedding Models

| Provider | Default Model | Dimensions |
|----------|---------------|------------|
| openai | text-embedding-3-large | 3072 |
| ollama | nomic-embed-text | 768 |
| cohere | embed-english-v3.0 | 1024 |

### Summarization Models

| Provider | Default Model |
|----------|---------------|
| anthropic | claude-haiku-4-5-20251001 |
| openai | gpt-5-mini |
| gemini | gemini-3-flash |
| grok | grok-4 |
| ollama | llama4:scout |

---

## YAML Configuration Examples

### Default (OpenAI + Anthropic)

```yaml
# config.yaml - uses defaults, can be omitted entirely
embedding:
  provider: openai
  model: text-embedding-3-large
  api_key_env: OPENAI_API_KEY

summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY
```

### Fully Local (Ollama)

```yaml
# config.yaml - offline operation
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: http://localhost:11434/v1

summarization:
  provider: ollama
  model: llama4:scout
  base_url: http://localhost:11434/v1
  params:
    max_tokens: 500
```

### Mixed Providers

```yaml
# config.yaml - Cohere embeddings, GPT-4 summarization
embedding:
  provider: cohere
  model: embed-english-v3.0
  api_key_env: COHERE_API_KEY
  params:
    input_type: search_document

summarization:
  provider: openai
  model: gpt-5
  api_key_env: OPENAI_API_KEY
  params:
    max_tokens: 500
    temperature: 0.2
```

---

## State Transitions

### Provider Configuration Lifecycle

```
┌─────────────────┐
│  No Config      │
│  (defaults)     │
└────────┬────────┘
         │ Server starts
         ▼
┌─────────────────┐
│  Load Config    │
│  (YAML/env)     │
└────────┬────────┘
         │ Validate
         ▼
┌─────────────────┐        ┌─────────────────┐
│  Valid Config   │───────▶│  Check Index    │
└─────────────────┘        │  Metadata       │
                           └────────┬────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
         ┌─────────────────┐             ┌─────────────────┐
         │  Match: OK      │             │  Mismatch:      │
         │  Use providers  │             │  Require reindex│
         └─────────────────┘             └─────────────────┘
```

---

## Relationships

```
ProviderSettings
    │
    ├── embedding: EmbeddingConfig
    │       │
    │       └── provider → EmbeddingProvider (runtime instance)
    │
    └── summarization: SummarizationConfig
            │
            └── provider → SummarizationProvider (runtime instance)

IndexMetadata
    │
    └── tracks: embedding_provider, embedding_model, embedding_dimensions
```
