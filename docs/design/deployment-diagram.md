# Agent Brain Deployment Diagram

This document contains PlantUML deployment diagrams showing how Agent Brain components are deployed across different environments.

## System Deployment Overview

```plantuml
@startuml Agent Brain Deployment Overview
!theme plain
skinparam backgroundColor #FEFEFE
skinparam componentStyle rectangle

title Agent Brain - System Deployment Architecture

' Define colors
skinparam node {
    BackgroundColor<<workstation>> #E3F2FD
    BackgroundColor<<server>> #E8F5E9
    BackgroundColor<<storage>> #FFF3E0
    BackgroundColor<<external>> #FCE4EC
    BackgroundColor<<container>> #F3E5F5
}

' External Services Cloud
cloud "External Services" {
    node "OpenAI API" <<external>> as openai {
        component [Embeddings API] as embed_api
        component [text-embedding-3-large] as embed_model
    }

    node "Anthropic API" <<external>> as anthropic {
        component [Claude API] as claude_api
        component [claude-haiku-4-5] as haiku_model
    }
}

' Developer Workstation
node "Developer Workstation" <<workstation>> as workstation {

    node "Python Virtual Environment" as venv {
        component [agent-brain-cli] as cli
        component [agent-brain-server] as server

        frame "Dependencies" {
            component [FastAPI + Uvicorn] as fastapi
            component [LlamaIndex] as llamaindex
            component [ChromaDB Client] as chroma_client
            component [httpx] as httpx
            component [Click + Rich] as click
        }
    }

    node "Claude Code" <<workstation>> as claude_code {
        component [agent-brain-plugin] as plugin

        frame "Plugin Components" {
            component [15 Slash Commands] as commands
            component [2 Agents] as agents
            component [2 Skills] as skills
        }
    }

    folder ".claude/agent-brain/" as state_dir {
        file "runtime.json" as runtime
        file "config.json" as config
        file "server.lock" as lock

        folder "chroma_db/" as chroma_dir {
            database "ChromaDB\n(SQLite + Parquet)" as chromadb
        }

        folder "bm25_index/" as bm25_dir {
            file "retriever.json" as bm25_json
            file "docstore.json" as docstore
        }

        folder "graph_index/" as graph_dir {
            file "graph_store.json" as graph_json
            file "graph_metadata.json" as graph_meta
        }
    }
}

' Connections
cli --> server : HTTP REST\n(localhost:8000+)
plugin --> cli : subprocess\ncalls
server --> fastapi
fastapi --> llamaindex
llamaindex --> chroma_client
chroma_client --> chromadb

server --> openai : HTTPS\n(embeddings)
server --> anthropic : HTTPS\n(summaries)

server ..> runtime : writes
server ..> lock : acquires
server ..> chromadb : persists
server ..> bm25_json : persists
server ..> graph_json : persists

@enduml
```

### Deployment Overview Description

The Agent Brain system is deployed primarily as a local development tool with the following key components:

1. **Developer Workstation**: The primary deployment target where all components run
2. **Python Virtual Environment**: Isolates dependencies for agent-brain-cli and agent-brain-server
3. **Claude Code**: The IDE integration point via the agent-brain-plugin
4. **State Directory**: Project-specific state stored in `.claude/agent-brain/`
5. **External Services**: Cloud APIs for embeddings (OpenAI) and summarization (Anthropic)

---

## Local Development Environment

```plantuml
@startuml Local Development Deployment
!theme plain
skinparam backgroundColor #FEFEFE

title Agent Brain - Local Development Environment

skinparam node {
    BackgroundColor<<app>> #E3F2FD
    BackgroundColor<<storage>> #FFF3E0
    BackgroundColor<<config>> #E8F5E9
}

node "Developer Machine" {

    ' Application Layer
    node "Application Layer" <<app>> as app_layer {

        frame "CLI Process" {
            component [agent-brain] as cli_main
            component [Click Commands] as click_cmds
            component [Rich Console] as rich
            component [API Client\n(httpx)] as api_client
        }

        frame "Server Process (Uvicorn)" {
            component [FastAPI App] as fastapi
            component [QueryService] as query_svc
            component [IndexingService] as index_svc
            component [BM25IndexManager] as bm25_mgr
            component [VectorStoreManager] as vector_mgr
            component [GraphStoreManager] as graph_mgr
        }

        cli_main --> click_cmds
        click_cmds --> api_client
        api_client --> fastapi : HTTP/REST\nport 8000+

        fastapi --> query_svc
        fastapi --> index_svc
        index_svc --> bm25_mgr
        index_svc --> vector_mgr
        index_svc --> graph_mgr
        query_svc --> bm25_mgr
        query_svc --> vector_mgr
        query_svc --> graph_mgr
    }

    ' Storage Layer
    node "Storage Layer" <<storage>> as storage_layer {

        database "ChromaDB\n(Persistent Client)" as chromadb {
            collections "doc_serve_collection" as collection
            file "chroma.sqlite3" as sqlite
            folder "embeddings/" as embeddings
        }

        folder "BM25 Index" as bm25_store {
            file "retriever.json\n(index data)" as retriever_json
            file "docstore.json\n(document cache)" as docstore_json
        }

        folder "Graph Store" as graph_store {
            file "graph_store.json\n(triplets)" as triplets
            file "graph_metadata.json\n(counts)" as metadata
        }
    }

    ' Configuration Layer
    node "Configuration Layer" <<config>> as config_layer {

        file ".env" as env_file
        file "runtime.json" as runtime_file
        file "config.json" as config_file
        file "server.lock" as lock_file

        note right of env_file
            OPENAI_API_KEY=sk-...
            ANTHROPIC_API_KEY=sk-ant-...
            API_PORT=8000
            ENABLE_GRAPH_INDEX=false
        end note
    }

    ' Connections
    vector_mgr --> chromadb
    bm25_mgr --> bm25_store
    graph_mgr --> graph_store

    fastapi ..> env_file : reads
    fastapi ..> runtime_file : writes on start
    fastapi ..> lock_file : acquires/releases
}

@enduml
```

### Local Development Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **CLI Process** | User interaction and server management | Click, Rich, httpx |
| **Server Process** | REST API and RAG pipeline | FastAPI, Uvicorn |
| **ChromaDB** | Vector storage with HNSW indexing | SQLite + Parquet files |
| **BM25 Index** | Keyword search index | JSON-serialized LlamaIndex BM25Retriever |
| **Graph Store** | Knowledge graph for GraphRAG | JSON-serialized triplets |

---

## Multi-Instance Architecture

```plantuml
@startuml Multi-Instance Deployment
!theme plain
skinparam backgroundColor #FEFEFE

title Agent Brain - Multi-Instance Architecture

skinparam node {
    BackgroundColor<<project>> #E3F2FD
    BackgroundColor<<shared>> #E8F5E9
}

node "Developer Machine" {

    ' Project A
    node "Project A\n(/home/dev/project-a)" <<project>> as proj_a {
        folder ".claude/agent-brain/" as state_a {
            file "runtime.json\nport: 8001" as runtime_a
            database "ChromaDB\n(project-a data)" as chroma_a
            file "BM25 Index" as bm25_a
        }

        component [Server Instance\n:8001] as server_a
        server_a --> state_a
    }

    ' Project B
    node "Project B\n(/home/dev/project-b)" <<project>> as proj_b {
        folder ".claude/agent-brain/" as state_b {
            file "runtime.json\nport: 8002" as runtime_b
            database "ChromaDB\n(project-b data)" as chroma_b
            file "BM25 Index" as bm25_b
        }

        component [Server Instance\n:8002] as server_b
        server_b --> state_b
    }

    ' Project C
    node "Project C\n(/home/dev/project-c)" <<project>> as proj_c {
        folder ".claude/agent-brain/" as state_c {
            file "runtime.json\nport: 8003" as runtime_c
            database "ChromaDB\n(project-c data)" as chroma_c
            file "BM25 Index" as bm25_c
        }

        component [Server Instance\n:8003] as server_c
        server_c --> state_c
    }

    ' CLI
    component [agent-brain CLI] as cli

    cli --> server_a : "agent-brain --project /project-a"
    cli --> server_b : "agent-brain --project /project-b"
    cli --> server_c : "agent-brain --project /project-c"

    note bottom of cli
        CLI auto-discovers active instances
        via runtime.json files in each project
    end note
}

' Instance Discovery Flow
note right of proj_a
    **Instance Isolation**
    - Each project has dedicated state
    - Ports auto-assigned (0 = find free)
    - Lock files prevent conflicts
    - Data never shared between projects
end note

@enduml
```

### Multi-Instance Features

| Feature | Description |
|---------|-------------|
| **Project Isolation** | Each project gets its own state directory, database, and server instance |
| **Auto Port Assignment** | Use `--port 0` to auto-assign an available port |
| **Lock Files** | Prevent multiple servers from running for the same project |
| **Instance Discovery** | CLI can list and manage all running instances via `agent-brain list` |

---

## Docker Deployment

```plantuml
@startuml Docker Deployment
!theme plain
skinparam backgroundColor #FEFEFE

title Agent Brain - Docker Deployment

skinparam node {
    BackgroundColor<<container>> #F3E5F5
    BackgroundColor<<volume>> #FFF3E0
    BackgroundColor<<network>> #E3F2FD
}

node "Docker Host" {

    ' Docker Network
    node "Docker Network: agent-brain-net" <<network>> as network {

        ' Container
        node "Container: agent-brain-server" <<container>> as container {

            component [Python 3.11 Runtime] as python
            component [agent-brain-serve] as server
            component [Uvicorn ASGI] as uvicorn

            frame "Exposed Ports" {
                portin "8000/tcp" as port8000
            }

            python --> server
            server --> uvicorn
            uvicorn --> port8000
        }
    }

    ' Volumes
    node "Docker Volumes" <<volume>> as volumes {

        folder "agent-brain-data" as data_vol {
            database "ChromaDB" as chroma_vol
            file "BM25 Index" as bm25_vol
            file "Graph Store" as graph_vol
        }

        folder "agent-brain-config" as config_vol {
            file ".env" as env_vol
        }
    }

    ' Volume Mounts
    container ..> data_vol : /app/data
    container ..> config_vol : /app/.env

    ' External Access
    actor "Client" as client
    client --> port8000 : HTTP REST API
}

note right of container
    **Docker Run Command**
    docker run -d \\
      --name agent-brain \\
      -p 8000:8000 \\
      -v agent-brain-data:/app/data \\
      -v $(pwd)/.env:/app/.env:ro \\
      -e OPENAI_API_KEY=$OPENAI_API_KEY \\
      agent-brain-server:latest
end note

@enduml
```

### Docker Configuration

```yaml
# docker-compose.yml example
version: '3.8'
services:
  agent-brain-server:
    image: agent-brain-server:latest
    container_name: agent-brain
    ports:
      - "8000:8000"
    volumes:
      - agent-brain-data:/app/data
      - ./.env:/app/.env:ro
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - CHROMA_PERSIST_DIR=/app/data/chroma_db
      - BM25_INDEX_PATH=/app/data/bm25_index
      - GRAPH_INDEX_PATH=/app/data/graph_index
    restart: unless-stopped

volumes:
  agent-brain-data:
```

---

## Environment Configuration

```plantuml
@startuml Environment Configuration
!theme plain
skinparam backgroundColor #FEFEFE

title Agent Brain - Environment Configuration Flow

skinparam note {
    BackgroundColor #FFFDE7
}

' Configuration Sources
rectangle "Configuration Sources" {
    file "CLI Arguments\n(--port, --host)" as cli_args
    file "Environment Variables\n(OPENAI_API_KEY, etc.)" as env_vars
    file ".env File\n(project root)" as env_file
    file "config.json\n(.claude/agent-brain/)" as config_json
    file "Default Values\n(settings.py)" as defaults
}

' Configuration Loading
rectangle "Pydantic Settings" as pydantic {
    component [Settings Class] as settings
}

' Precedence Flow
cli_args --> settings : "Highest Priority"
env_vars --> settings : "High Priority"
env_file --> settings : "Medium Priority"
config_json --> settings : "Low Priority"
defaults --> settings : "Lowest Priority"

' Configuration Categories
rectangle "Configuration Categories" {

    frame "API Configuration" {
        component [API_HOST: 127.0.0.1] as api_host
        component [API_PORT: 8000] as api_port
        component [DEBUG: false] as debug
    }

    frame "External Services" {
        component [OPENAI_API_KEY] as openai_key
        component [ANTHROPIC_API_KEY] as anthropic_key
        component [EMBEDDING_MODEL:\ntext-embedding-3-large] as embed_model
        component [CLAUDE_MODEL:\nclaude-haiku-4-5] as claude_model
    }

    frame "Storage Paths" {
        component [CHROMA_PERSIST_DIR:\n./chroma_db] as chroma_path
        component [BM25_INDEX_PATH:\n./bm25_index] as bm25_path
        component [GRAPH_INDEX_PATH:\n./graph_index] as graph_path
    }

    frame "Feature Flags" {
        component [ENABLE_GRAPH_INDEX: false] as graph_flag
        component [GRAPH_STORE_TYPE: simple] as graph_type
    }
}

settings --> api_host
settings --> api_port
settings --> openai_key
settings --> chroma_path
settings --> graph_flag

note bottom of pydantic
    **Configuration Precedence**
    1. CLI arguments (highest)
    2. Environment variables
    3. .env file
    4. config.json (project-specific)
    5. Default values (lowest)
end note

@enduml
```

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key for embeddings |
| `ANTHROPIC_API_KEY` | No | - | Anthropic API key for code summarization |
| `API_HOST` | No | `127.0.0.1` | Server bind address |
| `API_PORT` | No | `8000` | Server port (0 = auto-assign) |
| `DEBUG` | No | `false` | Enable debug logging |
| `EMBEDDING_MODEL` | No | `text-embedding-3-large` | OpenAI embedding model |
| `CLAUDE_MODEL` | No | `claude-haiku-4-5-20251001` | Claude model for summaries |
| `CHROMA_PERSIST_DIR` | No | `./chroma_db` | ChromaDB storage path |
| `BM25_INDEX_PATH` | No | `./bm25_index` | BM25 index storage path |
| `ENABLE_GRAPH_INDEX` | No | `false` | Enable GraphRAG feature |
| `DOC_SERVE_STATE_DIR` | No | - | Override state directory |
| `DOC_SERVE_MODE` | No | `project` | Instance mode: project or shared |

---

## Deployment Benefits

### Local Development Mode
- **Zero Configuration**: Works out of the box with minimal setup
- **Project Isolation**: Each project has independent state and data
- **Fast Iteration**: Hot reload in debug mode for rapid development

### Docker Mode
- **Reproducibility**: Consistent environment across machines
- **Persistence**: Volume mounts preserve data across container restarts
- **Portability**: Easy deployment to any Docker-capable host

### Multi-Instance Mode
- **Parallel Projects**: Work on multiple projects simultaneously
- **Resource Isolation**: Each instance has dedicated resources
- **Auto-Discovery**: CLI automatically finds and manages instances
