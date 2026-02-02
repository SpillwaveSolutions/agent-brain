# Indexing Sequence Diagrams

This document contains PlantUML sequence diagrams for all indexing operations in Agent Brain.
Each diagram shows the complete flow from request to completion.

## Table of Contents

1. [Document Indexing Sequence](#1-document-indexing-sequence)
2. [Code Indexing Sequence](#2-code-indexing-sequence)
3. [Graph Building Sequence](#3-graph-building-sequence)

---

## 1. Document Indexing Sequence

### Diagram

```plantuml
@startuml Document Indexing Sequence
!theme plain
skinparam sequenceMessageAlign center
skinparam responseMessageBelowArrow true

title Document Indexing Sequence - Full Pipeline

actor Client
participant "FastAPI\n/index" as API
participant "IndexingService" as IS
participant "DocumentLoader" as DL
participant "ContextAwareChunker" as CAC
participant "EmbeddingGenerator" as EG
participant "OpenAI API" as OpenAI
participant "VectorStoreManager" as VS
participant "BM25IndexManager" as BM25
database "ChromaDB" as Chroma
database "BM25 Index\n(disk)" as BM25Disk

== Request Validation ==

Client -> API : POST /index\n{folder_path, chunk_size, chunk_overlap, recursive}
activate API

API -> API : Validate folder_path exists
API -> API : Validate is directory
API -> API : Validate read permissions

alt Validation Failed
    API --> Client : 400 Bad Request\n"Folder not found / not directory / cannot read"
end

API -> IS : Check is_indexing
activate IS

alt Already Indexing
    IS --> API : is_indexing = true
    API --> Client : 409 Conflict\n"Indexing already in progress"
end

deactivate IS

== Start Background Job ==

API -> IS : start_indexing(request)
activate IS

IS -> IS : Generate job_id\n"job_{uuid[:12]}"
IS -> IS : Set state to INDEXING
IS -> IS : Record started_at timestamp

IS -> IS : asyncio.create_task(\n  _run_indexing_pipeline)

IS --> API : job_id
deactivate IS

API --> Client : 202 Accepted\n{job_id, status: "started"}
deactivate API

== Background Indexing Pipeline ==

note over IS: Pipeline runs asynchronously\nUse /health/status to monitor

activate IS

group Initialize Vector Store
    IS -> VS : initialize()
    activate VS
    VS -> Chroma : Create/load collection
    Chroma --> VS : collection handle
    VS --> IS : initialized
    deactivate VS
end

group Step 1: Load Documents
    IS -> IS : progress_callback(0, 100, "Loading documents...")

    IS -> DL : load_files(\n  folder_path,\n  recursive=True,\n  include_code=True)
    activate DL

    DL -> DL : Walk directory tree

    loop For each file
        DL -> DL : Check file extension\n(.md, .txt, .rst, .py, .ts, etc.)
        DL -> DL : Read file content
        DL -> DL : Detect source_type\n(doc vs code)
        DL -> DL : Detect language\n(python, typescript, etc.)
        DL -> DL : Create Document with metadata
    end

    DL --> IS : documents[]
    deactivate DL

    IS -> IS : Set total_documents = len(documents)

    alt No Documents Found
        IS -> IS : Set status = COMPLETED
        IS -> IS : Return early
    end
end

group Step 2: Chunk Documents
    IS -> IS : progress_callback(20, 100, "Chunking documents...")
    IS -> IS : Separate doc_documents and code_documents

    group Chunk Text Documents
        IS -> CAC : Create chunker(\n  chunk_size=1000,\n  chunk_overlap=200)
        activate CAC

        IS -> CAC : chunk_documents(\n  doc_documents,\n  progress_callback)

        loop For each document
            CAC -> CAC : Split by headers/sections
            CAC -> CAC : Split long sections\nby chunk_size
            CAC -> CAC : Add overlap text
            CAC -> CAC : Generate chunk_id (UUID)
            CAC -> CAC : Create TextChunk with\n  text, chunk_id, metadata
        end

        CAC --> IS : doc_chunks[]
        deactivate CAC
    end

    note right of IS
        Code documents are handled
        separately with AST parsing
        (see Code Indexing Sequence)
    end note
end

group Step 3: Generate Embeddings
    IS -> IS : progress_callback(50, 100, "Generating embeddings...")

    IS -> EG : embed_chunks(\n  chunks[],\n  progress_callback)
    activate EG

    EG -> EG : Batch chunks (100 per batch)

    loop For each batch
        EG -> OpenAI : embeddings.create(\n  model="text-embedding-3-large",\n  input=batch_texts)
        activate OpenAI
        OpenAI --> EG : embeddings[3072 dims each]
        deactivate OpenAI

        EG -> EG : Report progress
    end

    EG --> IS : all_embeddings[]
    deactivate EG
end

group Step 4: Store in Vector Database
    IS -> IS : progress_callback(90, 100, "Storing in vector database...")

    IS -> IS : chroma_batch_size = 40000

    loop For each batch of 40000 chunks
        IS -> VS : upsert_documents(\n  ids, embeddings,\n  documents, metadatas)
        activate VS

        VS -> Chroma : upsert(\n  ids, embeddings,\n  documents, metadatas)
        activate Chroma
        Chroma --> VS : success
        deactivate Chroma

        VS --> IS : count upserted
        deactivate VS
    end
end

group Step 5: Build BM25 Index
    IS -> IS : progress_callback(95, 100, "Building BM25 index...")

    IS -> IS : Convert chunks to\nLlamaIndex TextNode[]

    IS -> BM25 : build_index(nodes)
    activate BM25

    BM25 -> BM25 : Create BM25Retriever\nfrom nodes

    BM25 -> BM25Disk : persist(persist_dir)
    activate BM25Disk
    BM25Disk --> BM25 : saved
    deactivate BM25Disk

    BM25 --> IS : index built
    deactivate BM25
end

group Complete
    IS -> IS : Set status = COMPLETED
    IS -> IS : Set completed_at = now()
    IS -> IS : Add folder to indexed_folders
    IS -> IS : progress_callback(100, 100, "Complete!")
end

deactivate IS

@enduml
```

### Walkthrough

1. **Request Validation Phase**
   - Client sends POST to `/index` with folder_path and optional parameters
   - API validates: folder exists, is a directory, has read permissions
   - Returns 400 if validation fails
   - Returns 409 if indexing already in progress

2. **Start Background Job Phase**
   - IndexingService generates a unique job_id using UUID
   - Sets state to INDEXING with started_at timestamp
   - Creates async task for the pipeline
   - **Returns immediately** with 202 Accepted (non-blocking)

3. **Document Loading Phase**
   - DocumentLoader walks the directory tree
   - Identifies files by extension (.md, .txt, .py, .ts, etc.)
   - Reads content and detects source_type (doc vs code)
   - For code files, detects programming language
   - Returns list of Document objects with metadata

4. **Chunking Phase**
   - ContextAwareChunker splits documents into chunks
   - Respects section boundaries (headers, paragraphs)
   - Configurable chunk_size (default 1000 chars)
   - Adds chunk_overlap (default 200 chars) for context
   - Each chunk gets a unique UUID-based chunk_id

5. **Embedding Generation Phase**
   - EmbeddingGenerator batches chunks (100 per batch)
   - Calls OpenAI API with text-embedding-3-large model
   - Returns 3072-dimensional vectors
   - **Performance**: ~1-2 seconds per 100 chunks (API latency)

6. **Vector Storage Phase**
   - VectorStoreManager upserts to ChromaDB
   - Batched at 40,000 chunks (ChromaDB limit)
   - Uses cosine distance metric
   - HNSW index is updated automatically

7. **BM25 Index Building Phase**
   - Chunks are converted to LlamaIndex TextNode format
   - BM25Retriever is built from nodes
   - Index is persisted to disk for durability

8. **Completion Phase**
   - State is set to COMPLETED
   - Folder path is added to indexed_folders set
   - Progress callback reports 100%

### Error Handling

| Error | HTTP Status | Message |
|-------|-------------|---------|
| Folder not found | 400 | "Folder not found: {path}" |
| Not a directory | 400 | "Path is not a directory" |
| Permission denied | 400 | "Cannot read folder" |
| Already indexing | 409 | "Indexing already in progress" |
| Pipeline failure | 500 | "Failed to start indexing: {error}" |

### Performance Considerations

- **Embedding generation** is the bottleneck (API calls)
- Consider rate limiting for large corpora
- BM25 index building is CPU-bound but fast
- ChromaDB persistence is automatic but disk I/O bound

---

## 2. Code Indexing Sequence

### Diagram

```plantuml
@startuml Code Indexing Sequence
!theme plain
skinparam sequenceMessageAlign center
skinparam responseMessageBelowArrow true

title Code Indexing Sequence - AST-Aware Chunking

participant "IndexingService" as IS
participant "DocumentLoader" as DL
participant "CodeChunker" as CC
participant "tree-sitter\nParser" as TS
participant "SummaryExtractor\n(Optional)" as SE
participant "Anthropic API" as Claude

== Language Detection ==

IS -> DL : load_files(folder_path, include_code=True)
activate DL

loop For each file
    DL -> DL : Get file extension

    DL -> DL : Map extension to language
    note right of DL
        Extension mappings:
        .py -> python
        .ts -> typescript
        .js -> javascript
        .java -> java
        .go -> go
        .rs -> rust
        .c -> c
        .cpp -> cpp
        .h -> c
    end note

    DL -> DL : Set source_type = "code"
    DL -> DL : Set language in metadata
end

DL --> IS : documents[] with language metadata
deactivate DL

== Code Chunking by Language ==

IS -> IS : Group code_documents by language

loop For each language (python, typescript, etc.)

    IS -> CC : Create CodeChunker(\n  language=lang,\n  generate_summaries=True)
    activate CC

    CC -> CC : Load tree-sitter parser\nfor language
    note right of CC
        Supported languages:
        - Python (functions, classes, methods)
        - TypeScript (functions, classes, interfaces)
        - JavaScript (functions, classes, methods)
        - Java (methods, classes)
        - Go (functions, types)
        - Rust (functions, impl blocks)
        - C/C++ (functions)
    end note

    loop For each code document

        CC -> CC : chunk_code_document(doc)

        group AST Parsing
            CC -> TS : Parse source code
            activate TS

            TS -> TS : Build AST

            TS --> CC : syntax tree
            deactivate TS
        end

        group Symbol Extraction
            CC -> CC : Walk AST for code symbols
            note right of CC
                Extract:
                - Function definitions
                - Class definitions
                - Method definitions
                - Type/Interface definitions

                For each symbol:
                - name
                - start_line, end_line
                - docstring (if present)
                - parent class (for methods)
            end note

            CC -> CC : Create CodeChunk for each symbol
            note right of CC
                CodeChunk contains:
                - chunk_id (UUID)
                - text (source code)
                - metadata:
                  - source_type: "code"
                  - language: "python"
                  - symbol_name: "function_name"
                  - symbol_type: "function"
                  - start_line, end_line
                  - file_path
            end note
        end

        group Summary Generation (Optional)
            alt generate_summaries = true
                CC -> SE : Create SummaryExtractor
                activate SE

                loop For each code chunk
                    SE -> Claude : Summarize code chunk
                    activate Claude
                    note right of Claude
                        Model: claude-haiku-4-5
                        Prompt: "Summarize this code..."
                    end note
                    Claude --> SE : summary text
                    deactivate Claude

                    SE -> SE : Add summary to\nchunk metadata
                end

                SE --> CC : chunks with summaries
                deactivate SE
            end
        end

        CC --> IS : code_chunks[] for document
    end

    deactivate CC

    IS -> IS : Track supported_languages set
    IS -> IS : Accumulate total_code_chunks
end

== Fallback Handling ==

alt AST Parsing Fails
    IS -> IS : Fall back to\nContextAwareChunker
    note right of IS
        Treats code as plain text:
        - Splits by lines/paragraphs
        - No symbol extraction
        - Still gets embeddings
    end note
end

== Continue to Embedding/Storage ==

note over IS
    Code chunks continue through
    the same pipeline as documents:
    1. Generate embeddings
    2. Store in ChromaDB
    3. Build BM25 index
end note

@enduml
```

### Walkthrough

1. **Language Detection Phase**
   - DocumentLoader identifies code files by extension
   - Maps extensions to programming languages
   - Sets `source_type: "code"` and `language` in metadata

2. **Code Chunking by Language Phase**
   - Documents are grouped by programming language
   - Each language uses a specialized CodeChunker
   - Loads the appropriate tree-sitter parser

3. **AST Parsing Phase**
   - tree-sitter parses source code into an AST
   - Provides accurate code structure recognition
   - Handles syntax variations and edge cases

4. **Symbol Extraction Phase**
   - AST is walked to find code symbols:
     - Functions and methods
     - Classes and types
     - Interfaces (TypeScript)
     - Impl blocks (Rust)
   - Each symbol becomes a separate CodeChunk
   - Metadata includes: name, type, line numbers, parent class

5. **Summary Generation Phase (Optional)**
   - If `generate_summaries=True`, chunks are summarized
   - Uses Claude Haiku for fast, cheap summaries
   - Summaries are added to chunk metadata
   - Useful for improving semantic search quality

6. **Fallback Handling**
   - If AST parsing fails, falls back to text chunking
   - Code is treated as plain text
   - Still gets embedded and indexed

### Supported Languages

| Language | Parser | Extracted Symbols |
|----------|--------|-------------------|
| Python | tree-sitter-python | functions, classes, methods |
| TypeScript | tree-sitter-typescript | functions, classes, interfaces, methods |
| JavaScript | tree-sitter-javascript | functions, classes, methods |
| Java | tree-sitter-java | classes, methods |
| Go | tree-sitter-go | functions, types |
| Rust | tree-sitter-rust | functions, impl blocks |
| C | tree-sitter-c | functions |
| C++ | tree-sitter-cpp | functions, classes |

### CodeChunk Metadata

```python
{
    "chunk_id": "abc123...",
    "source_type": "code",
    "language": "python",
    "symbol_name": "process_data",
    "symbol_type": "function",
    "start_line": 45,
    "end_line": 78,
    "file_path": "/src/processor.py",
    "parent_class": null,  # or "DataProcessor" for methods
    "docstring": "Process input data...",
    "summary": "This function processes..."  # if generate_summaries
}
```

### Performance Considerations

- tree-sitter parsing is very fast (~1ms per file)
- Summary generation adds significant latency (Claude API calls)
- Consider disabling summaries for large codebases
- Batch summary generation where possible

---

## 3. Graph Building Sequence

### Diagram

```plantuml
@startuml Graph Building Sequence
!theme plain
skinparam sequenceMessageAlign center
skinparam responseMessageBelowArrow true

title Graph Building Sequence - Entity Extraction and Relationship Discovery

participant "IndexingService" as IS
participant "GraphIndexManager" as GIM
participant "CodeMetadataExtractor" as CME
participant "LLMEntityExtractor" as LLM
participant "Anthropic API" as Claude
participant "GraphStoreManager" as GSM
database "Property Graph\n(Kuzu/Memory)" as Graph

== Feature Check ==

IS -> IS : Check ENABLE_GRAPH_INDEX setting

alt GraphRAG Disabled
    IS -> IS : Skip graph building
    note right of IS: No-op when disabled
end

== Build Graph from Documents ==

IS -> GIM : build_from_documents(\n  chunks[],\n  progress_callback)
activate GIM

group Initialize Graph Store
    GIM -> GSM : Check is_initialized
    activate GSM
    GSM --> GIM : initialized = false

    GIM -> GSM : initialize()
    GSM -> Graph : Create/load graph
    activate Graph
    Graph --> GSM : graph handle
    deactivate Graph
    GSM --> GIM : initialized
    deactivate GSM
end

loop For each document chunk

    GIM -> GIM : Report progress:\n"Extracting entities: {idx}/{total}"

    GIM -> GIM : _extract_from_document(doc)

    group Get Document Properties
        GIM -> GIM : text = doc.text or doc.get_content()
        GIM -> GIM : metadata = doc.metadata.to_dict()
        GIM -> GIM : chunk_id = doc.chunk_id or doc.id_
        GIM -> GIM : source_type = metadata.source_type
        GIM -> GIM : language = metadata.language
    end

    == Code Metadata Extraction (Fast) ==

    alt source_type == "code" AND GRAPH_USE_CODE_METADATA
        GIM -> CME : extract_from_metadata(\n  metadata, chunk_id)
        activate CME

        CME -> CME : Extract symbol triplets
        note right of CME
            From metadata:
            - symbol_name DEFINED_IN file_path
            - symbol_name HAS_TYPE symbol_type
            - symbol_name BELONGS_TO parent_class
            - file_path USES_LANGUAGE language
        end note

        CME --> GIM : code_triplets[]
        deactivate CME

        GIM -> CME : extract_from_text(\n  text, language, chunk_id)
        activate CME

        CME -> CME : Pattern-based extraction
        note right of CME
            Regex patterns detect:
            - import statements
            - function calls
            - class inheritance
            - type references
        end note

        CME --> GIM : text_triplets[]
        deactivate CME
    end

    == LLM Entity Extraction (Comprehensive) ==

    alt GRAPH_USE_LLM_EXTRACTION AND text not empty
        GIM -> LLM : extract_triplets(\n  text, chunk_id)
        activate LLM

        LLM -> Claude : Extract entities and relationships
        activate Claude
        note right of Claude
            Model: claude-haiku-4-5
            Prompt: "Extract knowledge graph
            triplets from this text.
            Return as JSON:
            [{subject, predicate, object,
              subject_type, object_type}]"
        end note

        Claude --> LLM : JSON triplets
        deactivate Claude

        LLM -> LLM : Parse and validate response
        LLM -> LLM : Create GraphTriple objects

        LLM --> GIM : llm_triplets[]
        deactivate LLM
    end

    == Store Triplets ==

    loop For each triplet in all_triplets

        GIM -> GSM : add_triplet(\n  subject, predicate, object,\n  subject_type, object_type,\n  source_chunk_id)
        activate GSM

        GSM -> Graph : Create/update nodes\nfor subject and object
        activate Graph
        Graph --> GSM : node handles
        deactivate Graph

        GSM -> Graph : Create relationship\nbetween nodes
        activate Graph
        Graph --> GSM : success
        deactivate Graph

        GSM --> GIM : added = true
        deactivate GSM

        GIM -> GIM : Increment total_triplets
    end

end

== Persist Graph ==

GIM -> GSM : persist()
activate GSM
GSM -> Graph : Save to disk
activate Graph
Graph --> GSM : saved
deactivate Graph
GSM --> GIM : persisted
deactivate GSM

GIM -> GIM : Record last_build_time
GIM -> GIM : Record last_triplet_count

GIM --> IS : total_triplets extracted
deactivate GIM

@enduml
```

### Walkthrough

1. **Feature Check Phase**
   - Verifies ENABLE_GRAPH_INDEX environment variable
   - Graph building is a no-op when disabled
   - Allows Agent Brain to run without GraphRAG overhead

2. **Graph Store Initialization Phase**
   - GraphStoreManager initializes if not already done
   - Creates or loads the property graph database
   - Supports in-memory or Kuzu persistent storage

3. **Document Iteration Phase**
   - Processes each document chunk from the indexing pipeline
   - Extracts document properties (text, metadata, chunk_id)
   - Reports progress via callback

4. **Code Metadata Extraction Phase** (Fast, Deterministic)
   - Uses CodeMetadataExtractor for structured extraction
   - Creates triplets from code metadata:
     - `function_name DEFINED_IN file.py`
     - `ClassName HAS_TYPE class`
     - `method BELONGS_TO ClassName`
     - `file.py USES_LANGUAGE python`
   - Pattern-based extraction from code text:
     - Import statements
     - Function calls
     - Class inheritance
     - Type references

5. **LLM Entity Extraction Phase** (Comprehensive, Slower)
   - Uses Claude Haiku for intelligent extraction
   - Discovers conceptual relationships not visible in syntax
   - Returns structured JSON triplets
   - Validates and converts to GraphTriple objects

6. **Triplet Storage Phase**
   - Each triplet is added to the property graph
   - Creates nodes for subject and object entities
   - Creates typed relationship between nodes
   - Links triplet to source_chunk_id for retrieval

7. **Persistence Phase**
   - Graph is saved to disk for durability
   - Records build timestamp and triplet count

### GraphTriple Structure

```python
class GraphTriple:
    subject: str           # "QueryService"
    predicate: str         # "uses"
    object: str            # "VectorStoreManager"
    subject_type: str      # "class"
    object_type: str       # "class"
    source_chunk_id: str   # "abc123..."
```

### Extraction Examples

**Code Metadata Extraction**:
```
# From: def process_data(input: DataFrame) -> Result:
Triplets:
- process_data DEFINED_IN utils.py
- process_data HAS_TYPE function
- process_data ACCEPTS DataFrame
- process_data RETURNS Result
```

**LLM Entity Extraction**:
```
# From: "The QueryService orchestrates search operations
#        by coordinating between the embedding generator
#        and vector store for semantic retrieval."
Triplets:
- QueryService orchestrates search_operations
- QueryService coordinates embedding_generator
- QueryService coordinates vector_store
- embedding_generator enables semantic_retrieval
```

### Configuration Settings

| Setting | Default | Description |
|---------|---------|-------------|
| ENABLE_GRAPH_INDEX | false | Enable/disable GraphRAG |
| GRAPH_USE_CODE_METADATA | true | Extract from code metadata |
| GRAPH_USE_LLM_EXTRACTION | true | Use LLM for extraction |
| GRAPH_STORE_TYPE | "memory" | Storage backend |

### Performance Considerations

- Code metadata extraction is fast (~1ms per chunk)
- LLM extraction adds ~200-500ms per chunk (Claude API)
- Consider disabling LLM extraction for large codebases
- Memory graph store is faster but not persistent
- Kuzu provides persistence but adds I/O overhead

---

## Index Status Monitoring

The `/health/status` endpoint provides real-time indexing status:

```json
{
    "status": "indexing",
    "is_indexing": true,
    "current_job_id": "job_a1b2c3d4e5f6",
    "folder_path": "/path/to/docs",
    "total_documents": 150,
    "processed_documents": 75,
    "total_chunks": 450,
    "total_doc_chunks": 300,
    "total_code_chunks": 150,
    "supported_languages": ["python", "typescript"],
    "progress_percent": 50,
    "started_at": "2024-01-15T10:30:00Z",
    "completed_at": null,
    "error": null,
    "indexed_folders": ["/path/to/docs"],
    "graph_index": {
        "enabled": true,
        "initialized": true,
        "entity_count": 234,
        "relationship_count": 567,
        "store_type": "memory"
    }
}
```

---

## Complete Indexing Flow Summary

```plantuml
@startuml Indexing Overview
!theme plain

start

:Receive POST /index request;

if (Validation passes?) then (yes)
    :Generate job_id;
    :Return 202 Accepted;

    fork
        :Load documents;
        :Separate doc vs code;

        fork
            :Chunk text documents;
        fork again
            :AST-parse code files;
            :Extract symbols;
            :Generate summaries;
        end fork

        :Generate embeddings\n(OpenAI API);

        :Store in ChromaDB;

        :Build BM25 index;

        if (GraphRAG enabled?) then (yes)
            :Extract code metadata triplets;
            :Extract LLM triplets;
            :Store in property graph;
        else (no)
        endif

        :Set status = COMPLETED;
    end fork

else (no)
    :Return 400/409 error;
endif

stop

@enduml
```
