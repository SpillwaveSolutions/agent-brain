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

**C/C++:**
- Functions and methods kept as complete units
- Struct/class definitions preserved together
- Preprocessor directives (#include, #define) grouped with related code
- Template instantiations and specializations handled appropriately

**Java:**
- Methods grouped within class boundaries
- Inner classes kept with their containing classes
- Package declarations and imports preserved
- Annotations and generics handled correctly

**Kotlin:**
- Functions and methods kept as complete units
- Class/data class/object declarations preserved together
- Extension functions and properties handled correctly
- Null safety operators and type inference respected

**Go:**
- Functions and methods kept as complete units
- Struct types and interfaces preserved together
- Package declarations and imports maintained
- Goroutines and channel operations respected

**Rust:**
- Functions and impl blocks kept together
- Struct/enum/trait definitions preserved
- Macro invocations and derive attributes handled
- Async functions and lifetime annotations respected

**Swift:**
- Functions and methods kept as complete units
- Class/struct/enum definitions preserved together
- Protocol conformance and extensions handled
- Property observers and computed properties respected

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

| Language | PyPI Package | Grammar Repo | Status |
|----------|--------------|--------------|--------|
| Python | `tree-sitter-python` | tree-sitter/tree-sitter-python | ✅ Production |
| JavaScript | `tree-sitter-javascript` | tree-sitter/tree-sitter-javascript | ✅ Production |
| TypeScript | `tree-sitter-typescript` | tree-sitter/tree-sitter-typescript | ✅ Production |
| Kotlin | `tree-sitter-kotlin` | fwcd/tree-sitter-kotlin | ✅ Production |
| C | `tree-sitter-c` | tree-sitter/tree-sitter-c | ✅ Production |
| C++ | `tree-sitter-cpp` | tree-sitter/tree-sitter-cpp | ✅ Production |
| Java | `tree-sitter-java` | tree-sitter/tree-sitter-java | ✅ Production |
| Go | `tree-sitter-go` | tree-sitter/tree-sitter-go | ✅ Production |
| Rust | `tree-sitter-rust` | tree-sitter/tree-sitter-rust | ✅ Production |
| Swift | `tree-sitter-swift` | tree-sitter/tree-sitter-swift | ✅ Production |

**Note:** TypeScript package contains two grammars: `typescript` and `tsx`.

### Installation

```bash
pip install tree-sitter tree-sitter-python tree-sitter-javascript
```

### Direct Usage (for custom parsing)

```python
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript

# Initialize languages
PY_LANGUAGE = Language(tspython.language())
TS_LANGUAGE = Language(tstypescript.language_typescript())
TSX_LANGUAGE = Language(tstypescript.language_tsx())

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

**Python Query:**
```python
from tree_sitter import Query

# Find all function and class definitions
py_query = Query(
    PY_LANGUAGE,
    """
    (function_definition
      name: (identifier) @symbol_name
      parameters: (parameters) @params
      return_type: (type)? @return_type) @symbol_node

    (class_definition
      name: (identifier) @symbol_name) @symbol_node
    """
)
```

**TypeScript/JavaScript Query:**
```python
# Find all function, class, and method definitions
ts_query = Query(
    TS_LANGUAGE,
    """
    (function_declaration
      name: (identifier) @symbol_name) @symbol_node

    (class_declaration
      name: (type_identifier) @symbol_name) @symbol_node

    (method_definition
      name: (property_identifier) @symbol_name) @symbol_node
      
    (arrow_function
      (variable_declarator
        name: (identifier) @symbol_name)) @symbol_node
    """
)
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

| Query Type | Best Strategy | Language Examples |
|------------|---------------|-------------------|
| Exact function name | BM25 (keyword) | `authenticate_user`, `malloc`, `println` |
| Error code lookup | BM25 (keyword) | `HTTP_404`, `ENOENT`, `NullPointerException` |
| API endpoint patterns | BM25 (keyword) | `GET /api/users`, `@GetMapping`, `app.get()` |
| "How to authenticate" | Vector (semantic) | Cross-language authentication patterns |
| "UserService implementation" | Hybrid | Find class + usage examples |
| "Memory management" | Hybrid | C malloc + Rust ownership patterns |
| "HTTP client setup" | Hybrid | curl in C + requests in Python |

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

**New class needed:** `CodeChunker`

**AST Boundary Detection Strategy (US5):**
1.  **Parse**: Parse the entire file using `tree-sitter` for the detected language.
2.  **Traverse**: Traverse the AST to identify "top-level" nodes (functions, classes, imports).
3.  **Map**: Create a mapping of line ranges to symbol metadata (name, kind, docstring).
4.  **Split**: Use `CodeSplitter` to get text chunks.
5.  **Enrich**: For each chunk:
    - Determine its `start_line` and `end_line` in the original file.
    - Intersect these lines with the AST symbol mapping.
    - Assign `symbol_name` and `symbol_kind` to the chunk metadata.
    - If a chunk contains multiple symbols, use the "dominant" one or the first significant one.
    - If a chunk is part of a large symbol (e.g., a method in a large class), assign the parent class name to `symbol_name`.

**Symbol Name Extraction (US5):**
- **Python**: `identifier` node under `function_definition` or `class_definition`.
- **TypeScript**: `identifier` under `function_declaration`, `type_identifier` under `class_declaration`, or `property_identifier` under `method_definition`.
- **Hierarchical names**: For methods, combine class and method name (e.g., `UserService.get_user`).

**Line Number Tracking (US5):**
- Use `node.start_point[0]` and `node.end_point[0]` from `tree-sitter` nodes (0-indexed, convert to 1-indexed for metadata).
- For `CodeSplitter` output, calculate line numbers by counting `\n` in the original text up to the chunk's content.

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
    KOTLIN = "kotlin"
    C = "c"
    CPP = "cpp"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    SWIFT = "swift"
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
| Kotlin | `.kt`, `.kts` | `kotlin` |
| C | `.c`, `.h` | `c` |
| C++ | `.cpp`, `.cxx`, `.cc`, `.hpp`, `.hxx`, `.hh` | `cpp` |
| Java | `.java` | `java` |
| Go | `.go` | `go` |
| Rust | `.rs` | `rust` |
| Swift | `.swift` | `swift` |

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
    # Python
    ".py": "python",

    # JavaScript/TypeScript
    ".js": "javascript",
    ".jsx": "javascript",  # JSX uses javascript parser
    ".ts": "typescript",
    ".tsx": "typescript",  # TSX uses typescript parser

    # Systems languages
    ".c": "c",
    ".h": "c",  # Header files
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".hh": "cpp",

    # JVM/Object-oriented
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",  # Kotlin script files

    # Modern systems languages
    ".go": "go",
    ".rs": "rust",
    ".swift": "swift",
}
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
# Core languages
tree-sitter-python = "^0.21"
tree-sitter-javascript = "^0.21"
tree-sitter-typescript = "^0.21"
# Systems languages
tree-sitter-c = "^0.21"
tree-sitter-cpp = "^0.21"
# JVM/Object-oriented
tree-sitter-java = "^0.21"
tree-sitter-kotlin = "^0.21"
# Modern languages
tree-sitter-go = "^0.21"
tree-sitter-rust = "^0.21"
tree-sitter-swift = "^0.21"
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

## 10. Config-Driven Language Support Architecture

### Overview

The current implementation uses hardcoded language support. To enable 160+ languages from tree-sitter-language-pack without code changes, we need a configuration-driven architecture.

### Key Design Decisions

#### 1. Language Configuration File

**File**: `doc-serve-server/config/languages.yaml`

**Structure**:
```yaml
# Language Support Configuration
defaults:
  chunk_lines: 50
  chunk_overlap: 20
  max_chars: 2000

categories:
  compact:      # Terse languages (C, Go, Rust)
    chunk_lines: 40
    chunk_overlap: 15
  standard:     # Most languages (Python, JS, TS, Java)
    chunk_lines: 50
    chunk_overlap: 20
  verbose:      # Verbose languages (Java, C#)
    chunk_lines: 80
    chunk_overlap: 30
  markup:       # HTML, XML, JSON
    chunk_lines: 60
    chunk_overlap: 25

languages:
  python:
    extensions: [.py, .pyw, .pyi]
    key: python
    category: standard
    enabled: true
    exclude_patterns:
      - "*_test.py"
      - "test_*.py"
      - "**/tests/**"
      - "conftest.py"

  typescript:
    extensions: [.ts, .tsx]
    key: typescript
    category: standard
    enabled: true
    exclude_patterns:
      - "*.spec.ts"
      - "*.test.ts"
      - "**/__tests__/**"
      - "*.d.ts"

# 160+ languages can be added here...
```

#### 2. LanguageConfig Pydantic Model

**File**: `doc-serve-server/config/language_config.py`

```python
from pydantic import BaseModel
from pathlib import Path
import yaml

class ChunkConfig(BaseModel):
    chunk_lines: int = 50
    chunk_overlap: int = 20
    max_chars: int = 2000

class LanguageEntry(BaseModel):
    extensions: list[str]
    key: str                    # tree-sitter-language-pack key
    category: str = "standard"
    enabled: bool = True
    exclude_patterns: list[str] = []

class LanguageConfig(BaseModel):
    defaults: ChunkConfig
    categories: dict[str, ChunkConfig]
    languages: dict[str, LanguageEntry]

    @classmethod
    def load(cls, path: Path | None = None) -> "LanguageConfig":
        if path is None:
            path = Path(__file__).parent / "languages.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def get_enabled_extensions(self) -> set[str]:
        """Get all enabled file extensions."""
        exts = set()
        for lang in self.languages.values():
            if lang.enabled:
                exts.update(lang.extensions)
        return exts

    def extension_to_key(self, language_name: str) -> str | None:
        """Map language name to tree-sitter key."""
        lang = self.languages.get(language_name)
        return lang.key if lang and lang.enabled else None
```

#### 3. Simplified LanguageDetector

**Updated**: `doc-serve-server/indexing/document_loader.py`

```python
class LanguageDetector:
    def __init__(self, config: LanguageConfig | None = None):
        self.config = config or LanguageConfig.load()
        self._ext_map = self._build_extension_map()

    def _build_extension_map(self) -> dict[str, str]:
        """Build extension -> language name mapping from config."""
        mapping = {}
        for name, lang in self.config.languages.items():
            if lang.enabled:
                for ext in lang.extensions:
                    mapping[ext.lower()] = name
        return mapping

    def detect(self, file_path: str) -> str | None:
        """Detect language from file path."""
        ext = Path(file_path).suffix.lower()
        return self._ext_map.get(ext)
```

#### 4. Runtime Override via Settings

**Updated**: `doc-serve-server/config/settings.py`

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Language configuration overrides
    LANGUAGE_CONFIG_PATH: str | None = None  # Custom config file path
    ENABLED_LANGUAGES: list[str] | None = None  # Override enabled languages
    DISABLED_LANGUAGES: list[str] | None = None  # Disable specific languages
```

### Benefits

1. **Zero code changes** to add languages - Pure YAML config
2. **160+ languages ready** - Just enable them in config
3. **User customizable** - Override via env vars or custom config
4. **Categorized defaults** - Sensible chunk sizes per language type
5. **Maintainable** - Single source of truth for language support
6. **Testable** - Config validation via Pydantic

### Implementation Impact

**Files to Modify**:
- `config/languages.yaml` - NEW - Language configuration
- `config/language_config.py` - NEW - Pydantic config loader
- `indexing/document_loader.py` - Simplify to use config
- `config/settings.py` - Add override settings

**Migration Path**:
- Current hardcoded languages become default config
- Backward compatibility maintained
- Users can opt into new system via settings

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
- [tree-sitter-language-pack](https://pypi.org/project/tree-sitter-language-pack/) - 160+ bundled grammars
- [tree-sitter-languages](https://pypi.org/project/tree-sitter-languages/) - 40+ bundled grammars

### ChromaDB
- [Metadata Filtering](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)
- [Query API](https://docs.trychroma.com/docs/querying-collections/query)

### Doc-Serve Internal References
- [Product Roadmap](../../docs/roadmaps/product-roadmap.md) - Phase 3 requirements
- [Spec Mapping](../../docs/roadmaps/spec-mapping.md) - Spec workflow
- [Feature Spec](./spec.md) - Detailed user stories and requirements
- [Developer Guide: Adding Languages](../../docs/DEVELOPERS_GUIDE.md#adding-support-for-new-languages) - How to add new language support

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
