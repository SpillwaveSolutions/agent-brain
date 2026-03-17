---
last_validated: 2026-03-16
---

# Deployment Guide

This guide covers deploying Agent Brain in various environments, from local development to production deployments.

## Table of Contents

- [Local Development](#local-development)
- [Production Considerations](#production-considerations)
- [Docker Deployment](#docker-deployment)
- [Resource Requirements](#resource-requirements)
- [Monitoring and Observability](#monitoring-and-observability)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

---

## Local Development

### Quick Start

```bash
# 1. Install packages
pip install agent-brain-rag agent-brain-cli

# 2. Set API keys
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."  # Optional

# 3. Initialize project
cd /path/to/your/project
agent-brain init

# 4. Start server
agent-brain start --daemon

# 5. Index documents
agent-brain index ./docs --include-code

# 6. Verify
agent-brain status
```

### Development Server Options

```bash
# Start with auto-reload for development
agent-brain start --reload

# Start with debug logging
DEBUG=true agent-brain start

# Start on specific port
agent-brain start --port 8080

# Start in foreground (see logs)
agent-brain start
```

### Virtual Environment Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install packages
pip install agent-brain-rag agent-brain-cli

# Verify installation
agent-brain --version
agent-brain-serve --version
```

---

## Production Considerations

### Checklist

Before deploying to production:

- [ ] API keys stored securely (environment variables or secrets manager)
- [ ] Storage paths point to persistent volumes
- [ ] Appropriate resource limits configured
- [ ] Health endpoints monitored
- [ ] Backup strategy for indexed data
- [ ] Security: bind to localhost or use reverse proxy

### Environment Configuration

Create a production `.env` file:

```bash
# Required
OPENAI_API_KEY=sk-proj-...

# Optional (for GraphRAG)
ANTHROPIC_API_KEY=sk-ant-...

# Server Configuration
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=false

# Embedding
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=3072

# Storage - point to persistent volumes
CHROMA_PERSIST_DIR=/data/agent-brain/vectors
BM25_INDEX_PATH=/data/agent-brain/bm25

# GraphRAG (optional)
ENABLE_GRAPH_INDEX=true
GRAPH_STORE_TYPE=kuzu
GRAPH_INDEX_PATH=/data/agent-brain/graph
```

### Persistent Storage

Agent Brain stores data in three locations:

| Storage | Purpose | Size Estimate |
|---------|---------|---------------|
| ChromaDB | Vector embeddings | ~1GB per 100K chunks |
| BM25 Index | Keyword index | ~100MB per 100K chunks |
| Graph Index | Knowledge graph | ~200MB per 50K entities |

**Recommendation**: Use SSD storage for best performance.

### systemd Service

Create `/etc/systemd/system/agent-brain.service`:

```ini
[Unit]
Description=Agent Brain RAG Server
After=network.target

[Service]
Type=simple
User=agent-brain
Group=agent-brain
WorkingDirectory=/opt/agent-brain
Environment=OPENAI_API_KEY=sk-proj-...
Environment=CHROMA_PERSIST_DIR=/data/agent-brain/vectors
Environment=BM25_INDEX_PATH=/data/agent-brain/bm25
ExecStart=/opt/agent-brain/venv/bin/agent-brain-serve --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable agent-brain
sudo systemctl start agent-brain
sudo systemctl status agent-brain
```

---

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir \
    agent-brain-rag \
    agent-brain-cli

# Create data directories
RUN mkdir -p /data/vectors /data/bm25 /data/graph

# Set environment defaults
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV CHROMA_PERSIST_DIR=/data/vectors
ENV BM25_INDEX_PATH=/data/bm25
ENV GRAPH_INDEX_PATH=/data/graph

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run server
CMD ["agent-brain-serve", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  agent-brain:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ENABLE_GRAPH_INDEX=true
      - GRAPH_STORE_TYPE=simple
    volumes:
      - agent-brain-data:/data
      - ./docs:/docs:ro  # Mount documents to index
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  agent-brain-data:
```

### Running with Docker

```bash
# Build image
docker build -t agent-brain .

# Run container
docker run -d \
  --name agent-brain \
  -p 8000:8000 \
  -e OPENAI_API_KEY="sk-proj-..." \
  -v agent-brain-data:/data \
  -v /path/to/docs:/docs:ro \
  agent-brain

# Index documents
docker exec agent-brain agent-brain index /docs

# Check status
docker exec agent-brain agent-brain status
```

### Docker Compose Deployment

```bash
# Set environment
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Start services
docker-compose up -d

# Index documents
docker-compose exec agent-brain agent-brain index /docs

# View logs
docker-compose logs -f agent-brain
```

---

## Resource Requirements

### Minimum Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 2GB | 8GB |
| Storage | 10GB | 50GB SSD |
| Python | 3.10+ | 3.11+ |

### Memory Sizing

Memory usage scales with:

1. **Number of chunks**: ~1KB per chunk in memory during indexing
2. **Vector dimensions**: 3072 dimensions = ~12KB per vector
3. **Graph size**: ~1MB per 1000 entities

**Guidelines**:

| Project Size | Documents | Chunks | RAM Needed |
|--------------|-----------|--------|------------|
| Small | < 1,000 | < 10,000 | 2GB |
| Medium | 1,000-10,000 | 10,000-100,000 | 4-8GB |
| Large | 10,000+ | 100,000+ | 8-16GB |

### CPU Considerations

- **Indexing**: CPU-intensive during embedding generation
- **Queries**: Mostly I/O-bound, scales with concurrent requests
- **GraphRAG**: LLM extraction is API-bound, not CPU-bound

---

## Monitoring and Observability

### Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Basic health check (for load balancers) |
| `GET /health/status` | Detailed status (indexing progress, counts) |

### Prometheus Metrics (Future)

Agent Brain will support Prometheus metrics in a future release. For now, use log-based monitoring.

### Logging

Agent Brain logs to stdout/stderr with configurable levels:

```bash
# Enable debug logging
DEBUG=true agent-brain-serve

# Log format
# 2024-01-15 10:30:00 [INFO] agent_brain_server.api.main: Starting Agent Brain RAG server...
```

### Log Aggregation

For production, use a log aggregator:

```yaml
# docker-compose with logging
services:
  agent-brain:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Alerting Suggestions

Set up alerts for:

- Health endpoint returns non-healthy status
- Query latency exceeds threshold (e.g., > 5 seconds)
- Indexing fails repeatedly
- Disk usage exceeds 80%

---

## Security Considerations

### Network Security

By default, Agent Brain binds to `127.0.0.1`, accessible only from localhost.

**For network access**, use a reverse proxy:

```nginx
# nginx configuration
server {
    listen 443 ssl;
    server_name agent-brain.example.com;

    ssl_certificate /etc/ssl/certs/agent-brain.crt;
    ssl_certificate_key /etc/ssl/private/agent-brain.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # Basic auth
        auth_basic "Agent Brain";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
}
```

### API Key Security

**Never commit API keys to version control.**

Options for secure storage:

1. **Environment variables**: Set in systemd or Docker
2. **Secrets manager**: AWS Secrets Manager, HashiCorp Vault
3. **.env files**: Keep out of version control with `.gitignore`

```bash
# .gitignore
.env
.env.local
.env.production
```

### Data Security

- Indexed content is stored locally in unencrypted format
- Consider disk encryption for sensitive codebases
- Limit file permissions on storage directories

```bash
# Secure storage directory
chmod 700 /data/agent-brain
chown agent-brain:agent-brain /data/agent-brain
```

### CORS Configuration

The default CORS configuration allows all origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production!
)
```

For production, restrict to specific origins.

---

## Troubleshooting

### Common Issues

#### Server Won't Start

**Symptoms**: `Address already in use` or server exits immediately.

**Solutions**:
```bash
# Check what's using the port
lsof -i :8000

# Kill existing process
kill -9 $(lsof -t -i :8000)

# Or use a different port
agent-brain start --port 8080
```

#### Out of Memory During Indexing

**Symptoms**: Process killed or OOM errors during indexing.

**Solutions**:
1. Index in smaller batches
2. Increase available memory
3. Reduce chunk overlap
4. Disable LLM summaries

```bash
# Index specific folders instead of entire project
agent-brain index ./docs
agent-brain index ./src/module1
agent-brain index ./src/module2
```

#### Slow Query Performance

**Symptoms**: Queries take > 5 seconds.

**Causes and Solutions**:

| Cause | Solution |
|-------|----------|
| Large result sets | Reduce `top_k` |
| Complex graph queries | Reduce `traversal_depth` |
| Cold start | First query after restart is slow |
| Slow disk | Use SSD storage |

#### ChromaDB Corruption

**Symptoms**: Errors about corrupted database or missing files.

**Solution**:
```bash
# Reset and re-index
agent-brain reset --yes
agent-brain index /path/to/documents
```

#### API Key Errors

**Symptoms**: `AuthenticationError` or `Invalid API key`.

**Solutions**:
```bash
# Verify key is set
echo $OPENAI_API_KEY

# Check key format (should start with sk-proj-)
# Regenerate key if needed at platform.openai.com
```

### Debug Mode

Enable debug mode for detailed logging:

```bash
DEBUG=true agent-brain start
```

This enables:
- Detailed request/response logging
- Stack traces for errors
- Auto-reload on code changes

### Getting Help

1. Check logs: `docker-compose logs agent-brain`
2. Verify health: `curl http://localhost:8000/health`
3. Check status: `agent-brain status`
4. GitHub Issues: Report bugs with logs and reproduction steps

---

## Backup and Recovery

### Backup Strategy

Back up these directories regularly:

```bash
# Backup locations
CHROMA_PERSIST_DIR=/data/agent-brain/vectors
BM25_INDEX_PATH=/data/agent-brain/bm25
GRAPH_INDEX_PATH=/data/agent-brain/graph
```

**Backup script**:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR=/backups/agent-brain

mkdir -p $BACKUP_DIR

# Stop server for consistent backup
agent-brain stop

# Create backup
tar -czf $BACKUP_DIR/agent-brain-$DATE.tar.gz \
    /data/agent-brain/vectors \
    /data/agent-brain/bm25 \
    /data/agent-brain/graph

# Restart server
agent-brain start --daemon

# Cleanup old backups (keep 7 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

### Recovery

```bash
# Stop server
agent-brain stop

# Restore from backup
tar -xzf /backups/agent-brain/agent-brain-20240115.tar.gz -C /

# Restart server
agent-brain start --daemon
```

### Re-indexing

If indexes are corrupted beyond recovery:

```bash
# Reset all indexes
agent-brain reset --yes

# Re-index from source documents
agent-brain index /path/to/documents --include-code
```

---

## Next Steps

- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Configuration Reference](CONFIGURATION.md) - All configuration options
- [Architecture Overview](ARCHITECTURE.md) - System design
