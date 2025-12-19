# Phase 3: Source Code Ingestion - Research & Analysis

**Version:** 1.0.0
**Date:** 2025-12-18
**Status:** Research Complete

---

## Executive Summary

This document presents comprehensive research for implementing source code ingestion in Doc-Serve (Phase 3). The research covers LlamaIndex's code-specific components, tree-sitter integration, unified search architecture, and extension points in the current implementation.

**Key Findings:**

1. **LlamaIndex CodeSplitter** provides AST-aware chunking via tree-sitter, maintaining function/class boundaries
2. **SummaryExtractor** can generate natural language descriptions for code chunks to improve semantic retrieval
3. The current Doc-Serve architecture has clear extension points for code support
4. **ChromaDB** already supports the metadata filtering needed for `source_type` and `language` queries
5. **Hybrid search** (Phase 2) is particularly valuable for code, combining exact identifier matches with semantic similarity

**Recommended Approach:**

- Extend `DocumentLoader` with code-specific extensions
- Create `CodeChunker` using LlamaIndex `CodeSplitter`
- Add `SummaryExtractor` to ingestion pipeline for code descriptions
- Enhance metadata schema with `source_type`, `language`, `symbol_name`, `line_numbers`
- Leverage existing `VectorStoreManager` `where` parameter for filtering

---

## 1. LlamaIndex CodeSplitter Analysis

### Overview

LlamaIndex's `CodeSplitter` is an AST-based node parser that uses tree-sitter to parse source code and chunk it at syntactic boundaries (functions, classes, methods).

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `language` | Required | Target language: `"python"`, `"typescript"`, `"javascript"` |
| `chunk_lines` | 40 | Approximate lines per chunk |
| `chunk_lines_overlap` | 15 | Overlapping lines between chunks |
| `max_chars` | 1500 | Maximum characters per chunk |

### Usage Pattern

```python
from llama_index.core.node_parser import CodeSplitter

# Create language-specific splitter
python_splitter = CodeSplitter.from_defaults(
    language="python",
    chunk_lines=40,
    chunk_lines_overlap=15,
    max_chars=1500,
)

# Parse documents into nodes
nodes = python_splitter.get_nodes_from_documents(documents)
```

### Chunking Behavior by Language

**Python:**
- Chunks centered on module-level functions and classes
- Methods grouped within class chunks when possible
- Imports and decorators preserved with their functions
- `if __name__ == "__main__"` blocks kept together

**TypeScript/JavaScript:**
- Chunks aligned to top-level function declarations
- Classes and methods preserved together
- Exported symbols (`export function`, `export class`) respected
- JSX trees kept intact, not split mid-expression

### Recommended Configuration for Doc-Serve

```python
CODE_CHUNK_LINES = 50        # Slightly larger for complete functions
CODE_CHUNK_OVERLAP = 20      # More overlap for cross-reference context
CODE_MAX_CHARS = 2000        # Accommodate larger functions
```

### Integration with Ingestion Pipeline

```python
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import CodeSplitter

pipeline = IngestionPipeline(
    transformations=[
        CodeSplitter(language="python", chunk_lines=50, chunk_lines_overlap=20),
        embedding_model,  # EmbeddingGenerator
    ],
)
```

---

## 2. SummaryExtractor for Code

### Purpose

`SummaryExtractor` uses an LLM to generate natural language descriptions for each code chunk. This bridges the semantic gap between natural language queries and code implementations.

### Configuration

```python
from llama_index.core.extractors import SummaryExtractor

code_summary_prompt = """You are a senior software engineer.
Given the following code snippet, write a concise natural-language description
that explains what the code does, its purpose, and key inputs/outputs.
Avoid restating the code line by line.

Code:
{context_str}

Summary:"""

summary_extractor = SummaryExtractor(
    summaries=["self", "prev"],  # Include previous chunk context
    prompt_template=code_summary_prompt,
    llm=Settings.llm,  # Claude Haiku for speed
)
```

### Metadata Output

| Field | Description |
|-------|-------------|
| `section_summary` | Natural language description of current chunk |
| `prev_section_summary` | Description of previous chunk (context) |
| `next_section_summary` | Description of next chunk (optional) |

### Usage in Pipeline

```python
pipeline = IngestionPipeline(
    transformations=[
        CodeSplitter(language="python"),
        SummaryExtractor(summaries=["self", "prev"], prompt_template=code_prompt),
        embedding_model,
    ],
)
```

### Alternatives for Code Summaries

1. **Extract from docstrings** - Fast, no LLM calls, but incomplete
2. **AST-based descriptions** - Generate from function signatures and types
3. **Hybrid approach** - Use docstrings when present, LLM when missing

**Recommendation:** Use hybrid approach - extract docstrings first, then LLM-generate only for undocumented code.

---

## 3. Tree-sitter Integration

### Official Language Packages

| Language | PyPI Package | Grammar Repo |
|----------|--------------|--------------|
| Python | `tree-sitter-python` | tree-sitter/tree-sitter-python |
| JavaScript | `tree-sitter-javascript` | tree-sitter/tree-sitter-javascript |
| TypeScript | `tree-sitter-typescript` | tree-sitter/tree-sitter-typescript |

**Note:** TypeScript package contains two grammars: `typescript` and `tsx`.

### Installation

```bash
pip install tree-sitter tree-sitter-python tree-sitter-javascript
```

### Direct Usage (for custom parsing)

```python
from tree_sitter import Language, Parser
import tree_sitter_python as tspython

PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)

code = b"""
def greet(name: str) -> str:
    \"\"\"Return a greeting.\"\"\"
    return f"Hello, {name}!"
"""

tree = parser.parse(code)
root = tree.root_node

# Walk the AST
for child in root.children:
    print(child.type, child.start_point, child.end_point)
```

### AST Queries for Metadata Extraction

```python
from tree_sitter import Query

# Find all function definitions
query = Query(
    PY_LANGUAGE,
    """
    (function_definition
      name: (identifier) @func_name
      parameters: (parameters) @params
      return_type: (type)? @return_type)
    """
)

captures = query.captures(root)
for node, capture_name in captures:
    print(f"{capture_name}: {node.text.decode('utf8')}")
```

### Extractable Metadata via AST

| Metadata | Source |
|----------|--------|
| `function_name` | Function definition name node |
| `class_name` | Class definition name node |
| `parameters` | Parameter list nodes |
| `return_type` | Return type annotation |
| `decorators` | Decorator nodes |
| `docstring` | First string literal in function body |
| `imports` | Import statement nodes |
| `line_numbers` | `node.start_point.row`, `node.end_point.row` |

---

## 4. Unified Search Architecture

### Single Collection Design

Store both documentation and code in a single ChromaDB collection with rich metadata for filtering.

```python
# Unified metadata schema
metadata = {
    # Source classification
    "source_type": "code",           # "doc" | "code" | "test"
    "language": "python",            # "python" | "typescript" | "javascript" | "markdown"

    # File information
    "file_path": "src/app/user.py",
    "file_name": "user.py",

    # Code-specific (when source_type == "code")
    "symbol_name": "UserService.get_user",
    "symbol_kind": "method",          # "class" | "function" | "method" | "module"
    "start_line": 120,
    "end_line": 165,

    # Context
    "section_summary": "Retrieves a user by ID from the database",

    # Standard
    "chunk_id": "chunk_abc123",
    "chunk_index": 5,
    "total_chunks": 12,
}
```

### ChromaDB Filtering Patterns

**Filter by source type:**
```python
results = collection.query(
    query_texts=["authentication handler"],
    n_results=10,
    where={"source_type": {"$eq": "code"}},
)
```

**Filter by language:**
```python
results = collection.query(
    query_texts=["parse JSON"],
    n_results=10,
    where={
        "$and": [
            {"source_type": {"$eq": "code"}},
            {"language": {"$in": ["python", "typescript"]}},
        ]
    },
)
```

**Cross-reference search (code + docs):**
```python
results = collection.query(
    query_texts=["user authentication flow"],
    n_results=20,
    where={
        "source_type": {"$in": ["code", "doc"]},
    },
)
```

### Hybrid Search Value for Code

Hybrid search (Phase 2) is particularly valuable for code:

| Query Type | Best Strategy |
|------------|---------------|
| Exact function name | BM25 (keyword) |
| Error code lookup | BM25 (keyword) |
| "How to authenticate" | Vector (semantic) |
| "UserService implementation" | Hybrid |

**Example hybrid query:**
```python
# mode=hybrid combines BM25 exact match with vector semantic similarity
POST /query
{
    "query": "RecursiveCharacterTextSplitter",
    "mode": "hybrid",
    "alpha": 0.3,  # Favor BM25 for exact identifiers
    "source_type": "code"
}
```

---

## 5. Current Implementation Extension Points

### DocumentLoader Extension

**Current file:** `doc_serve_server/indexing/document_loader.py`

**Current extensions:**
```python
SUPPORTED_EXTENSIONS: set[str] = {".txt", ".md", ".pdf", ".docx", ".html", ".rst"}
```

**Proposed addition:**
```python
CODE_EXTENSIONS: set[str] = {".py", ".ts", ".tsx", ".js", ".jsx"}
```

**New method needed:**
```python
def load_code_files(
    folder_path: str,
    languages: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[LoadedDocument]:
    """Load source code files with language detection."""
    ...
```

### Chunker Extension

**Current file:** `doc_serve_server/indexing/chunking.py`

**Current class:** `ContextAwareChunker` (text-based splitting)

**New class needed:**
```python
class CodeChunker:
    """AST-aware code chunking using LlamaIndex CodeSplitter."""

    def __init__(
        self,
        chunk_lines: int = 50,
        chunk_overlap: int = 20,
        max_chars: int = 2000,
        generate_summaries: bool = True,
    ):
        self.splitters: dict[str, CodeSplitter] = {}
        self._init_splitters()

    def chunk_code_file(
        self,
        document: LoadedDocument,
        language: str,
    ) -> list[CodeChunk]:
        """Chunk a code file using language-specific AST splitting."""
        ...
```

### IndexingService Extension

**Current file:** `doc_serve_server/services/indexing_service.py`

**Current pipeline:**
```
Load Documents → Chunk → Embed → Store → BM25 Index
```

**Extended pipeline:**
```
Load Documents ─┬─→ Doc Chunker ─────────────────────┐
                │                                     │
Load Code Files ─┴─→ Code Chunker → Summary Extract ─┴→ Embed → Store → BM25 Index
```

**New parameter on index endpoint:**
```python
class IndexRequest(BaseModel):
    folder_path: str
    chunk_size: int = 512
    chunk_overlap: int = 50
    recursive: bool = True
    include_code: bool = False        # NEW
    languages: list[str] | None = None # NEW: ["python", "typescript"]
    exclude_patterns: list[str] | None = None  # NEW: ["*test*", "node_modules"]
```

### VectorStoreManager Extension

**Current file:** `doc_serve_server/storage/vector_store.py`

**Already supports filtering:**
```python
def similarity_search(
    self,
    query_embedding: list[float],
    top_k: int,
    similarity_threshold: float = 0.0,
    where: dict | None = None,  # Already supports ChromaDB filtering
) -> list[SearchResult]:
```

**No changes needed** - just pass appropriate `where` clause from query endpoint.

### Query Endpoint Extension

**Current file:** `doc_serve_server/api/routers/query.py`

**New query parameters:**
```python
class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    similarity_threshold: float = 0.7
    mode: str = "hybrid"
    alpha: float = 0.5
    source_type: str | None = None    # NEW: "doc" | "code" | "all"
    language: str | None = None        # NEW: "python" | "typescript" | etc.
```

---

## 6. Metadata Schema Design

### Complete Metadata Schema

```python
@dataclass
class ChunkMetadata:
    # Universal fields (all chunks)
    chunk_id: str
    source: str                    # File path
    file_name: str
    file_path: str
    chunk_index: int
    total_chunks: int
    source_type: Literal["doc", "code", "test"]

    # Code-specific fields (when source_type == "code")
    language: str | None           # "python", "typescript", "javascript"
    symbol_name: str | None        # "UserService.get_user"
    symbol_kind: str | None        # "class", "function", "method", "module"
    start_line: int | None
    end_line: int | None

    # Summary fields (from SummaryExtractor)
    section_summary: str | None
    prev_section_summary: str | None

    # Document-specific fields (when source_type == "doc")
    section_title: str | None
    heading_path: str | None       # "Chapter 1 > Setup > Installation"
```

### Enum Definitions

```python
from enum import Enum

class SourceType(str, Enum):
    DOC = "doc"
    CODE = "code"
    TEST = "test"

class LanguageType(str, Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    MARKDOWN = "markdown"

class SymbolKind(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
```

---

## 7. File Extension & Filtering Strategy

### Supported Extensions

| Language | Extensions | Detect As |
|----------|------------|-----------|
| Python | `.py` | `python` |
| TypeScript | `.ts`, `.tsx` | `typescript` |
| JavaScript | `.js`, `.jsx` | `javascript` |

### Default Exclude Patterns

```python
DEFAULT_EXCLUDE_PATTERNS = [
    # Package managers
    "node_modules/",
    "vendor/",
    ".venv/",
    "venv/",
    "__pycache__/",

    # Build outputs
    "dist/",
    "build/",
    "out/",
    ".next/",

    # Generated files
    "*.d.ts",           # TypeScript declarations
    "*.js.map",         # Source maps
    "*.min.js",         # Minified
    "*.pyc",            # Python bytecode

    # Test files (optional - configurable)
    "*test*.py",
    "*_test.py",
    "test_*.py",
    "*.test.ts",
    "*.spec.ts",
    "__tests__/",

    # IDE/tool files
    ".git/",
    ".idea/",
    ".vscode/",
    "coverage/",
]
```

### Language Detection

```python
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",  # TSX uses typescript parser
    ".js": "javascript",
    ".jsx": "javascript",  # JSX uses javascript parser
}

def detect_language(file_path: str) -> str | None:
    """Detect programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(ext)
```

---

## 8. Implementation Recommendations

### Phase 3 Implementation Order

1. **Core Infrastructure**
   - Add `CODE_EXTENSIONS` to `DocumentLoader`
   - Create `CodeChunker` class with `CodeSplitter` integration
   - Define `CodeChunk` and `ChunkMetadata` dataclasses

2. **Metadata Enhancement**
   - Update `TextChunk` to include code-specific fields
   - Add `source_type` and `language` to all chunk metadata
   - Ensure backward compatibility with existing doc chunks

3. **Pipeline Integration**
   - Create `CodeIndexingService` or extend `IndexingService`
   - Add optional `SummaryExtractor` step for code
   - Integrate code chunks into existing embed/store flow

4. **API Extensions**
   - Add `include_code`, `languages`, `exclude_patterns` to `/index`
   - Add `source_type`, `language` filters to `/query`
   - Update response models with code metadata

5. **CLI Extensions**
   - Add `--include-code` flag to `index` command
   - Add `--languages` flag for language filtering
   - Add `--source-type` and `--language` to `query` command

### Dependencies to Add

```toml
# pyproject.toml additions
[tool.poetry.dependencies]
tree-sitter = "^0.21"
tree-sitter-python = "^0.21"
tree-sitter-javascript = "^0.21"
# tree-sitter-typescript requires building - evaluate
```

**Note:** LlamaIndex's `CodeSplitter` handles tree-sitter internally; direct dependency may not be needed if using only `CodeSplitter`.

### Performance Considerations

1. **Batch code summaries** - Don't call LLM per-chunk; batch similar chunks
2. **Cache language parsers** - Initialize `CodeSplitter` once per language
3. **Parallel file loading** - Use async for loading multiple code files
4. **Skip binary files** - Detect and skip non-text files early

### Testing Strategy

1. **Unit tests** - `CodeChunker` produces correct boundaries
2. **Integration tests** - Full pipeline with mixed docs + code
3. **Query tests** - Verify filtering by `source_type` and `language`
4. **Cross-reference tests** - Unified search returns both docs and code

---

## 9. References

### LlamaIndex Documentation
- [CodeSplitter API](https://developers.llamaindex.ai/python/framework-api-reference/node_parsers/code/)
- [SummaryExtractor API](https://developers.llamaindex.ai/python/framework-api-reference/extractors/summary/)
- [Metadata Extraction Guide](https://llamaindexxx.readthedocs.io/en/latest/module_guides/indexing/metadata_extraction.html)
- [IngestionPipeline](https://developers.llamaindex.ai/python/examples/ingestion/ingestion_pipeline/)

### Tree-sitter
- [Official Documentation](https://tree-sitter.github.io)
- [Python Bindings](https://github.com/tree-sitter/py-tree-sitter)
- [Python Grammar](https://github.com/tree-sitter/tree-sitter-python)
- [JavaScript Grammar](https://github.com/tree-sitter/tree-sitter-javascript)
- [TypeScript Grammar](https://github.com/tree-sitter/tree-sitter-typescript)

### ChromaDB
- [Metadata Filtering](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)
- [Query API](https://docs.trychroma.com/docs/querying-collections/query)

### Doc-Serve Internal References
- [Product Roadmap](../../docs/roadmaps/product-roadmap.md) - Phase 3 requirements
- [Spec Mapping](../../docs/roadmaps/spec-mapping.md) - Spec workflow
- [Feature Spec](./spec.md) - Detailed user stories and requirements

---

## Appendix A: Example Code Chunk Output

```json
{
  "chunk_id": "chunk_a1b2c3d4e5f6",
  "text": "def authenticate_user(username: str, password: str) -> User | None:\n    \"\"\"Authenticate user with username and password.\n    \n    Args:\n        username: The user's login name\n        password: The user's password (plaintext)\n    \n    Returns:\n        User object if authenticated, None otherwise\n    \"\"\"\n    user = db.get_user_by_username(username)\n    if user and verify_password(password, user.password_hash):\n        return user\n    return None",
  "metadata": {
    "source_type": "code",
    "language": "python",
    "file_path": "src/auth/service.py",
    "file_name": "service.py",
    "symbol_name": "authenticate_user",
    "symbol_kind": "function",
    "start_line": 42,
    "end_line": 58,
    "section_summary": "Authenticates a user by verifying their username and password against the database. Returns the User object on success or None on failure.",
    "chunk_index": 3,
    "total_chunks": 8
  }
}
```

## Appendix B: Query Examples

**Find all Python authentication code:**
```bash
doc-svr-ctl query "authentication" --source-type code --language python
```

**Search both docs and code for API patterns:**
```bash
doc-svr-ctl query "REST API endpoint" --source-type all --mode hybrid
```

**Find specific function:**
```bash
doc-svr-ctl query "authenticate_user" --source-type code --mode bm25
```
