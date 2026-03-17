---
last_validated: 2026-03-16
---

# Code Indexing Deep Dive

Agent Brain's AST-aware code indexing is what sets it apart from generic RAG solutions. This guide explains how code is processed, what metadata is extracted, and how to get the best results from code-aware search.

## Table of Contents

- [Why AST-Aware Indexing?](#why-ast-aware-indexing)
- [Supported Languages](#supported-languages)
- [The Indexing Pipeline](#the-indexing-pipeline)
- [Chunk Metadata](#chunk-metadata)
- [Code-Specific Queries](#code-specific-queries)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Why AST-Aware Indexing?

### The Problem with Text-Based Chunking

Generic RAG systems split code like any other text. This creates problems:

```python
# Text-based chunking might split here ---v
def authenticate_user(username: str, password: str) -> User:
    """Authenticate a user against the database."""
    user = db.get_user(username)
    if not user:
        raise AuthenticationError("User not found")
# ---^ And continue the function in another chunk
    if not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid password")
    return user
```

**Problems**:
- Function split mid-body loses semantic coherence
- Docstrings separated from their functions
- Queries for "authenticate_user" may not find complete implementation
- Symbol metadata (name, signature) not available

### AST-Aware Solution

Agent Brain uses **tree-sitter** parsers to understand code structure:

```python
# AST parser identifies function boundaries
def authenticate_user(username: str, password: str) -> User:
    """Authenticate a user against the database."""
    user = db.get_user(username)
    if not user:
        raise AuthenticationError("User not found")
    if not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid password")
    return user
# ^^^ Entire function stays in one chunk ^^^
```

**Advantages**:
- Complete functions/classes in single chunks
- Rich metadata extraction (name, kind, line numbers)
- Better search relevance
- Enables structural queries

---

## Supported Languages

Agent Brain supports AST-aware chunking for 11 programming languages:

| Language | Extensions | Symbol Types Extracted |
|----------|------------|------------------------|
| Python | .py, .pyw, .pyi | functions, classes, methods |
| TypeScript | .ts, .tsx | functions, classes, methods, arrow functions |
| JavaScript | .js, .jsx, .mjs, .cjs | functions, classes, methods, arrow functions |
| Java | .java | classes, methods, interfaces |
| Go | .go | functions, methods, types |
| Rust | .rs | functions, impl blocks, structs, traits |
| C | .c, .h | functions |
| C++ | .cpp, .cc, .hpp | functions, classes, methods |
| C# | .cs, .csx | classes, methods, interfaces, properties, records |
| Kotlin | .kt, .kts | functions, classes |
| Swift | .swift | functions, classes |

### Language Detection

Languages are detected automatically via:

1. **File Extension** (primary): `.py` -> Python, `.ts` -> TypeScript
2. **Content Analysis** (fallback): Pattern matching for language-specific syntax

```python
# From document_loader.py
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    # ... and more
}
```

---

## The Indexing Pipeline

### Overview

```
Source Files --> Document Loader --> Language Detection
       |                                    |
       v                                    v
  LoadedDocument          +----------------+----------------+
       |                  |                                 |
       v                  v                                 v
  Code Files        Documentation Files
       |                  |
       v                  v
  CodeChunker        ContextAwareChunker
  (tree-sitter)      (sentence/paragraph)
       |                  |
       v                  v
  CodeChunk[]         TextChunk[]
       |                  |
       +--------+---------+
                |
                v
        EmbeddingGenerator
                |
                v
        Vector Store + BM25 Index + Graph Index
```

### Step 1: Document Loading

The `DocumentLoader` identifies code files and extracts initial metadata:

```python
loaded_doc = LoadedDocument(
    text=file_content,
    source=file_path,
    file_name="auth.py",
    metadata={
        "source_type": "code",
        "language": "python",
        "file_size": 2048,
    }
)
```

### Step 2: Code Chunking

The `CodeChunker` uses LlamaIndex's `CodeSplitter` with tree-sitter parsing:

```python
# Configuration
code_chunker = CodeChunker(
    language="python",
    chunk_lines=40,           # Target chunk size in lines
    chunk_lines_overlap=15,   # Overlap between chunks
    max_chars=1500,           # Maximum characters per chunk
    generate_summaries=False, # Optional LLM summaries
)
```

**Chunking Strategy**:
1. Parse code into AST using tree-sitter
2. Identify top-level symbols (functions, classes)
3. Split at symbol boundaries
4. Preserve context with configurable overlap

### Step 3: Symbol Extraction

For each chunk, the system extracts symbol metadata:

```python
# Tree-sitter query for Python
query = """
    (function_definition
      name: (identifier) @name) @symbol
    (class_definition
      name: (identifier) @name) @symbol
"""

# Extracted symbols
symbols = [
    {"name": "authenticate_user", "kind": "function_definition",
     "start_line": 10, "end_line": 25},
    {"name": "User", "kind": "class_definition",
     "start_line": 1, "end_line": 8},
]
```

### Step 4: Metadata Enrichment

Each code chunk receives rich metadata:

```python
chunk = CodeChunk(
    chunk_id="chunk_abc123",
    text="def authenticate_user(...): ...",
    source="/path/to/auth.py",
    chunk_index=0,
    total_chunks=5,
    token_count=150,
    metadata=ChunkMetadata(
        source_type="code",
        language="python",
        symbol_name="authenticate_user",
        symbol_kind="function_definition",
        start_line=10,
        end_line=25,
        docstring="Authenticate a user against the database.",
    )
)
```

---

## Chunk Metadata

### Universal Metadata (All Chunks)

| Field | Description | Example |
|-------|-------------|---------|
| `chunk_id` | Unique identifier | `chunk_abc123` |
| `source` | File path | `/project/src/auth.py` |
| `file_name` | File name | `auth.py` |
| `chunk_index` | Position in document | `0` |
| `total_chunks` | Chunks from this file | `5` |
| `source_type` | Content type | `"code"` or `"doc"` |
| `created_at` | Indexing timestamp | `2024-01-15T10:30:00` |

### Code-Specific Metadata

| Field | Description | Example |
|-------|-------------|---------|
| `language` | Programming language | `"python"` |
| `symbol_name` | Function/class name | `"authenticate_user"` |
| `symbol_kind` | Symbol type | `"function_definition"` |
| `start_line` | Starting line number (1-based) | `10` |
| `end_line` | Ending line number | `25` |
| `docstring` | Extracted documentation | `"Authenticate a user..."` |
| `parameters` | Function parameters | `["username", "password"]` |
| `return_type` | Return type annotation | `"User"` |
| `decorators` | Applied decorators | `["@login_required"]` |
| `imports` | Import statements | `["jwt", "bcrypt"]` |

### C# Special Handling

C# files receive special treatment for XML documentation:

```csharp
/// <summary>
/// Authenticates a user against the database.
/// </summary>
/// <param name="username">The username to authenticate.</param>
/// <returns>The authenticated user.</returns>
public User AuthenticateUser(string username, string password)
{
    // Implementation
}
```

Extracted metadata:
```python
{
    "docstring": "Authenticates a user against the database. The username to authenticate. The authenticated user.",
    "symbol_name": "AuthenticateUser",
    "symbol_kind": "method_declaration"
}
```

---

## Code-Specific Queries

### Filtering by Source Type

Search only code or only documentation:

```bash
# Code only
agent-brain query "database connection" --source-types code

# Documentation only
agent-brain query "installation guide" --source-types doc

# Both (default)
agent-brain query "authentication"
```

### Filtering by Language

Search specific programming languages:

```bash
# Python only
agent-brain query "error handling" --languages python

# Multiple languages
agent-brain query "API client" --languages python,typescript

# Combined filters
agent-brain query "dependency injection" --source-types code --languages java,kotlin
```

### Symbol-Aware Queries

Leverage symbol metadata for precise results:

```bash
# Find function definitions
agent-brain query "function authenticate" --mode bm25

# Find class implementations
agent-brain query "class UserController" --mode hybrid

# Find imports
agent-brain query "import jwt" --mode bm25 --source-types code
```

### File Path Filtering

Target specific directories or files:

```bash
# Search in specific directory
agent-brain query "config" --file-paths "src/config/**"

# Multiple patterns
agent-brain query "tests" --file-paths "tests/**/*.py,spec/**/*.ts"
```

---

## Best Practices

### 1. Include Code During Indexing

Always use `--include-code` when indexing codebases:

```bash
agent-brain index /path/to/project --include-code
```

Without this flag, only documentation files are indexed.

### 2. Choose the Right Search Mode

| Query Type | Recommended Mode | Example |
|------------|------------------|---------|
| Function name | `bm25` | `"authenticate_user"` |
| Class with description | `hybrid` | `"authentication class"` |
| Concept explanation | `vector` | `"how does caching work"` |
| Dependencies | `graph` | `"what imports jwt"` |

### 3. Use Language Filters for Precision

When you know the target language, filter to reduce noise:

```bash
# More precise results
agent-brain query "router setup" --languages typescript

# vs. searching all languages (more noise)
agent-brain query "router setup"
```

### 4. Leverage BM25 for Exact Matches

Function and class names work best with BM25:

```bash
# BM25 for exact symbol names
agent-brain query "VectorStoreManager" --mode bm25

# Hybrid for described functionality
agent-brain query "manages vector storage" --mode hybrid
```

### 5. Generate Summaries for Better Semantic Search

Enable LLM summaries for improved concept matching:

```bash
agent-brain index /project --include-code --generate-summaries
```

**Trade-off**: Adds ~50% to indexing time but improves vector search relevance.

### 6. Tune Chunk Sizes for Your Codebase

Adjust chunk parameters for different code styles:

```bash
# Larger chunks for verbose languages (Java, C#)
agent-brain index /project --chunk-size 800 --overlap 100

# Smaller chunks for concise languages (Python, Go)
agent-brain index /project --chunk-size 400 --overlap 50
```

---

## Troubleshooting

### "No results" for Code Queries

**Symptoms**: Queries return empty results despite indexed code.

**Solutions**:
1. Verify code was indexed: `agent-brain status` should show `total_code_chunks > 0`
2. Check language filter: Ensure your language is indexed
3. Lower threshold: Try `--threshold 0.3`
4. Try BM25 mode for exact terms: `--mode bm25`

### Incomplete Function Chunks

**Symptoms**: Functions appear split across multiple chunks.

**Possible Causes**:
1. Very long functions exceed `max_chars`
2. Tree-sitter parser not available for language

**Solutions**:
1. Increase max_chars: Default is 1500, try 3000 for long functions
2. Verify language support: Check `LanguageDetector.get_supported_languages()`

### Wrong Symbol Assigned to Chunk

**Symptoms**: Chunk metadata shows incorrect symbol name.

**Explanation**: When a chunk spans multiple symbols, the system assigns the most specific (deepest nested) symbol that overlaps with the chunk.

**Solutions**:
1. This is expected behavior for boundary chunks
2. Use file path filtering for precision
3. Enable GraphRAG for relationship-based queries

### Language Detection Failures

**Symptoms**: Files indexed with wrong language or as documentation.

**Solutions**:
1. Check file extension matches expected pattern
2. Rename files to use standard extensions
3. Verify content patterns match language (for fallback detection)

### Slow Code Indexing

**Symptoms**: Indexing takes much longer than expected.

**Causes**:
1. LLM summary generation enabled
2. Large files with complex AST
3. Many small files (overhead per file)

**Solutions**:
1. Disable summaries: `--no-generate-summaries`
2. Exclude generated files: Use `.gitignore` patterns
3. Index in batches: Split large codebases

### Memory Issues During Indexing

**Symptoms**: Out of memory errors during code indexing.

**Solutions**:
1. Reduce batch size: Modify `chroma_batch_size` in indexing service
2. Exclude large binary files
3. Index fewer languages at once

---

## Advanced Topics

### Custom Tree-Sitter Queries

Agent Brain uses language-specific tree-sitter queries for symbol extraction. The queries are defined in `chunking.py`:

```python
# Python query
query_str = """
    (function_definition
      name: (identifier) @name) @symbol
    (class_definition
      name: (identifier) @name) @symbol
"""

# TypeScript query
query_str = """
    (function_declaration
      name: (identifier) @name) @symbol
    (class_declaration
      name: (type_identifier) @name) @symbol
    (variable_declarator
      name: (identifier) @name
      value: (arrow_function)) @symbol
"""
```

### Integration with GraphRAG

Code metadata feeds directly into GraphRAG:

1. **Import relationships**: `auth_module --[imports]--> jwt`
2. **Containment**: `UserController --[contains]--> login`
3. **Definition locations**: `authenticate --[defined_in]--> auth.py`

See [GraphRAG Integration Guide](GRAPHRAG_GUIDE.md) for details.

### Extending Language Support

To add a new language:

1. Add extension mapping in `LanguageDetector.EXTENSION_TO_LANGUAGE`
2. Add content patterns in `LanguageDetector.CONTENT_PATTERNS`
3. Add tree-sitter query in `CodeChunker._get_symbols()`
4. Update `CodeChunker._setup_language()` for parser initialization

---

## Next Steps

- [GraphRAG Integration Guide](GRAPHRAG_GUIDE.md) - How code metadata feeds knowledge graphs
- [API Reference](API_REFERENCE.md) - Code indexing API endpoints
- [Configuration Reference](CONFIGURATION.md) - Chunking configuration options
