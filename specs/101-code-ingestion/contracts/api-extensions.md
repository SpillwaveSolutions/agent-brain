# API Contracts: Code Ingestion

## Overview

Code ingestion extends the Doc-Serve API with new parameters for indexing source code and filtering search results by content type and programming language.

## Extended Endpoints

### POST /index (Extended)

Index documents and/or source code with language-specific processing.

#### Request Body (Extended)

```json
{
  "paths": ["string"],
  "recursive": true,
  "chunk_size": 512,
  "chunk_overlap": 50,

  // NEW: Code ingestion parameters
  "include_code": false,
  "languages": ["python", "typescript", "javascript"],
  "exclude_patterns": ["string"]
}
```

#### New Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `include_code` | boolean | No | `false` | Enable source code file processing |
| `languages` | string[] | No | `null` | Programming languages to index |
| `exclude_patterns` | string[] | No | `null` | Glob patterns for files to exclude |

#### Parameter Validation

- `include_code`: Must be boolean
- `languages`: Must be subset of `["python", "typescript", "javascript"]`
- `exclude_patterns`: Must be valid glob patterns
- When `include_code=true`, at least one language must be specified

#### Response (Unchanged)

```json
{
  "job_id": "string",
  "status": "started",
  "message": "string",
  "estimated_duration": "string"
}
```

### POST /query (Extended)

Search with content type and language filtering.

#### Request Body (Extended)

```json
{
  "query": "string",
  "mode": "hybrid",
  "alpha": 0.5,
  "top_k": 5,
  "threshold": 0.7,

  // NEW: Content filtering
  "source_type": "all",
  "language": null
}
```

#### New Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source_type` | string | No | `"all"` | Filter by content type |
| `language` | string | No | `null` | Filter by programming language |

#### Valid Values

- `source_type`: `"all"`, `"code"`, `"doc"`, `"test"`
- `language`: `null`, `"python"`, `"typescript"`, `"javascript"`

#### Parameter Validation

- `source_type` must be one of the valid values
- `language` must be `null` or one of the supported languages
- If `language` is specified, `source_type` should be `"code"` or `"all"`

#### Response (Extended)

Results now include code-specific metadata:

```json
{
  "results": [
    {
      "text": "string",
      "source": "string",
      "score": 0.85,
      "vector_score": 0.72,
      "bm25_score": 0.95,
      "chunk_id": "string",
      "metadata": {
        // Universal fields
        "chunk_id": "string",
        "source": "string",
        "file_name": "string",
        "chunk_index": 0,
        "total_chunks": 5,
        "source_type": "code",

        // Code-specific fields (when source_type="code")
        "language": "python",
        "symbol_name": "UserService.authenticate",
        "symbol_kind": "method",
        "start_line": 120,
        "end_line": 145,
        "section_summary": "Authenticates user credentials",
        "prev_section_summary": "Initializes service",

        // Document-specific fields (when source_type="doc")
        "section_title": "Authentication Guide",
        "heading_path": "Security > Authentication"
      }
    }
  ],
  "query_time_ms": 350.5,
  "total_results": 1
}
```

### GET /health/status (Extended)

Includes code chunk counts in health status.

#### Extended Response

```json
{
  "total_documents": 25,
  "total_chunks": 125,
  "indexing_in_progress": false,
  "current_job_id": null,
  "progress_percent": 0.0,
  "last_indexed_at": "2025-12-18T10:00:00Z",

  // NEW: Code-specific metrics
  "code_chunks_count": 75,
  "doc_chunks_count": 50,
  "supported_languages": ["python", "typescript", "javascript", "kotlin", "c", "cpp", "java", "go", "rust", "swift"]
}
```

## OpenAPI Schema Extensions

### IndexRequest Schema

```yaml
IndexRequest:
  type: object
  properties:
    paths:
      type: array
      items:
        type: string
      description: File/directory paths to index
    recursive:
      type: boolean
      default: true
      description: Recursively scan subdirectories
    chunk_size:
      type: integer
      minimum: 128
      maximum: 2048
      default: 512
      description: Token size for text chunks
    chunk_overlap:
      type: integer
      minimum: 0
      maximum: 512
      default: 50
      description: Token overlap between chunks

    # NEW: Code ingestion fields
    include_code:
      type: boolean
      default: false
      description: Enable source code file processing
    languages:
      type: array
      items:
        type: string
        enum: [python, typescript, javascript, kotlin, c, cpp, java, go, rust, swift]
      description: Programming languages to index
    exclude_patterns:
      type: array
      items:
        type: string
      description: Glob patterns for files to exclude
  required: [paths]
```

### QueryRequest Schema

```yaml
QueryRequest:
  type: object
  properties:
    query:
      type: string
      description: Search query text
    mode:
      type: string
      enum: [vector, bm25, hybrid]
      default: hybrid
      description: Search algorithm to use
    alpha:
      type: number
      minimum: 0.0
      maximum: 1.0
      default: 0.5
      description: Hybrid weighting (0.0=BM25, 1.0=vector)
    top_k:
      type: integer
      minimum: 1
      maximum: 50
      default: 5
      description: Maximum results to return
    threshold:
      type: number
      minimum: 0.0
      maximum: 1.0
      default: 0.7
      description: Minimum similarity score

    # NEW: Content filtering
    source_type:
      type: string
      enum: [all, code, doc, test]
      default: all
      description: Filter by content type
    language:
      type: string
      enum: [python, typescript, javascript, kotlin, c, cpp, java, go, rust, swift]
      nullable: true
      description: Filter by programming language
  required: [query]
```

### ChunkMetadata Schema

```yaml
ChunkMetadata:
  type: object
  properties:
    # Universal fields
    chunk_id:
      type: string
      description: Unique chunk identifier
    source:
      type: string
      description: File path
    file_name:
      type: string
      description: Base filename
    chunk_index:
      type: integer
      description: Chunk position in file
    total_chunks:
      type: integer
      description: Total chunks in file
    source_type:
      type: string
      enum: [doc, code, test]
      description: Content classification

    # Code-specific fields
    language:
      type: string
      enum: [python, typescript, javascript]
      description: Programming language
    symbol_name:
      type: string
      description: Function/class/method name
    symbol_kind:
      type: string
      enum: [module, class, function, method, variable]
      description: Symbol type
    start_line:
      type: integer
      description: Starting line number
    end_line:
      type: integer
      description: Ending line number
    section_summary:
      type: string
      description: AI-generated description
    prev_section_summary:
      type: string
      description: Previous chunk description

    # Document-specific fields
    section_title:
      type: string
      description: Section heading
    heading_path:
      type: string
      description: Hierarchical heading path
  required: [chunk_id, source, file_name, chunk_index, total_chunks, source_type]
```

## Backward Compatibility

### API Compatibility
- All existing endpoints work unchanged
- New parameters are optional with sensible defaults
- Existing clients continue to function
- Response format extensions are additive

### Data Compatibility
- Existing document chunks remain searchable
- New code chunks coexist in unified index
- Metadata extensions don't break existing queries
- Can disable code features without data migration

## Error Responses

### Code-Specific Errors

#### 422 Validation Error - Invalid Language
```json
{
  "detail": [
    {
      "loc": ["body", "languages", 0],
      "msg": "value is not a valid enumeration member; permitted: 'python', 'typescript', 'javascript'",
      "type": "enum"
    }
  ]
}
```

#### 503 Service Unavailable - Code Indexing in Progress
```json
{
  "detail": "Code indexing is currently in progress. Try again in a few minutes."
}
```

#### 400 Bad Request - Conflicting Parameters
```json
{
  "detail": "Cannot specify 'language' filter when source_type is 'doc'"
}
```

## Rate Limiting

Code ingestion adds to existing rate limits:

- **Indexing**: Additional 5 requests/hour for code indexing operations
- **Queries**: No change to existing query limits
- **Health**: No change to existing health check limits

## Versioning

- **API Version**: No major version change (additive features)
- **Schema Extensions**: Documented in OpenAPI specification
- **Breaking Changes**: None - all changes are backward compatible

## Testing Contracts

### Unit Test Contracts
- CodeSplitter produces correct AST boundaries
- Metadata extraction includes required fields
- Language detection works for supported extensions
- Summary generation creates meaningful descriptions

### Integration Test Contracts
- Full indexing pipeline processes code files
- Query filtering works by source_type and language
- Cross-reference searches return both docs and code
- Health endpoints report correct chunk counts

### End-to-End Contracts
- CLI tools accept new parameters
- API responses include code metadata
- Performance meets documented expectations
- Error handling provides actionable messages