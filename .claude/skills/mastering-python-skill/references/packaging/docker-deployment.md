# Docker Deployment for Python

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Basic Flask/FastAPI Dockerfile](#example-1-basic-flaskfastapi-dockerfile)
  - [Example 2: Multi-Stage Build](#example-2-multi-stage-build)
  - [Example 3: Docker Compose for Development](#example-3-docker-compose-for-development)
  - [Example 4: Production Kubernetes Deployment](#example-4-production-kubernetes-deployment)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Command |
|------|---------|
| Build image | `docker build -t myapp .` |
| Run container | `docker run -p 8000:8000 myapp` |
| Run detached | `docker run -d -p 8000:8000 myapp` |
| View logs | `docker logs -f <container>` |
| Shell access | `docker exec -it <container> bash` |
| List images | `docker images` |
| List containers | `docker ps -a` |
| Remove image | `docker rmi myapp` |
| Compose up | `docker compose up -d` |
| Compose down | `docker compose down` |

---

## Core Concepts

Docker containerization solves the "works on my machine" problem:

- **Consistency**: Same environment from dev to production
- **Isolation**: No dependency conflicts between applications
- **Portability**: Run anywhere Docker is installed
- **Reproducibility**: Versioned images for reliable deployments

**Base Image Options**:
| Image | Size | Use Case |
|-------|------|----------|
| `python:3.12` | ~900MB | Full stdlib, dev tools |
| `python:3.12-slim` | ~115MB | Most production apps |
| `python:3.12-alpine` | ~40MB | Minimal, but musl libc issues |

**Recommendation**: Use `slim` for most apps—good balance of size and compatibility.

---

## Production Examples

### Example 1: Basic Flask/FastAPI Dockerfile

**Use case**: Simple web application containerization.

```dockerfile
# Dockerfile
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run with production server
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

**.dockerignore**:

```text
# Version control
.git
.gitignore

# Python
__pycache__
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
.venv/
.env

# Testing
tests/
pytest_cache/
.coverage
htmlcov/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Docker
Dockerfile
docker-compose*.yml
.dockerignore

# Documentation
docs/
*.md
!README.md

# Local config
.env.local
.env.development
*.log
```

**Build and run**:

```bash
# Build the image
docker build -t myapp:latest .

# Run the container
docker run -d \
    --name myapp \
    -p 8000:8000 \
    -e DATABASE_URL="postgresql://user:pass@db:5432/mydb" \
    myapp:latest

# View logs
docker logs -f myapp

# Stop and remove
docker stop myapp && docker rm myapp
```

**Key points**:
- Layer ordering matters—copy requirements.txt first for caching
- Use non-root user for security
- `PYTHONUNBUFFERED=1` ensures logs are visible immediately
- Health checks enable orchestrator monitoring

---

### Example 2: Multi-Stage Build

**Use case**: Minimize image size by separating build and runtime.

```dockerfile
# Stage 1: Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Production stage
FROM python:3.12-slim AS production

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["gunicorn", "src.main:app", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker"]
```

**With Poetry**:

```dockerfile
# Multi-stage build with Poetry
FROM python:3.12-slim AS builder

WORKDIR /app

# Install Poetry
RUN pip install poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Export to requirements.txt (no dev dependencies)
RUN poetry export -f requirements.txt --without-hashes --only main > requirements.txt

# Create virtual environment and install
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS production

WORKDIR /app

# Copy virtual environment
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application
COPY src/ ./src/

# Non-root user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Size comparison**:
```bash
# Single stage (full image)
myapp:single    1.2GB

# Multi-stage (slim runtime)
myapp:multi     180MB
```

**Key points**:
- Builder stage has compilers and dev tools
- Production stage only has runtime dependencies
- Virtual environment copied intact between stages
- Final image is much smaller and more secure

---

### Example 3: Docker Compose for Development

**Use case**: Local development with database, cache, and hot reload.

```yaml
# docker-compose.yml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ./src:/app/src:cached
      - ./tests:/app/tests:cached
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/myapp
      - REDIS_URL=redis://redis:6379/0
      - DEBUG=true
      - LOG_LEVEL=DEBUG
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=myapp
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # Database admin UI
  adminer:
    image: adminer
    ports:
      - "8080:8080"
    depends_on:
      - db

volumes:
  postgres_data:
  redis_data:
```

**Development Dockerfile** (`Dockerfile.dev`):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dev dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# Copy application
COPY . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Development server with hot reload
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

**Development workflow**:

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f app

# Run tests in container
docker compose exec app pytest

# Run migrations
docker compose exec app alembic upgrade head

# Access database shell
docker compose exec db psql -U postgres -d myapp

# Rebuild after dependency changes
docker compose build app
docker compose up -d app

# Stop everything
docker compose down

# Stop and remove volumes (reset data)
docker compose down -v
```

**Production compose** (`docker-compose.prod.yml`):

```yaml
# docker-compose.prod.yml
services:
  app:
    image: myregistry.com/myapp:${VERSION:-latest}
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SECRET_KEY=${SECRET_KEY}
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

**Key points**:
- Use volumes to mount source code for hot reload
- `depends_on` with health checks ensures startup order
- Separate dev and prod compose files
- Use environment variables for configuration

---

### Example 4: Production Kubernetes Deployment

**Use case**: Deploy to Kubernetes with proper health checks and scaling.

**Deployment manifest** (`k8s/deployment.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  labels:
    app: myapp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      # Non-root security context
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000

      containers:
        - name: myapp
          image: myregistry.com/myapp:1.0.0
          ports:
            - containerPort: 8000
              name: http

          # Environment from ConfigMap and Secret
          envFrom:
            - configMapRef:
                name: myapp-config
            - secretRef:
                name: myapp-secrets

          # Resource limits
          resources:
            requests:
              cpu: 250m
              memory: 256Mi
            limits:
              cpu: 1000m
              memory: 512Mi

          # Probes
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 30
            timeoutSeconds: 5
            failureThreshold: 3

          readinessProbe:
            httpGet:
              path: /ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3

          startupProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 30  # 5 * 30 = 150s max startup time

          # Security settings
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL

          # Mount for tmp files if needed
          volumeMounts:
            - name: tmp
              mountPath: /tmp

      volumes:
        - name: tmp
          emptyDir: {}

      # Pod anti-affinity for high availability
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    app: myapp
                topologyKey: kubernetes.io/hostname
```

**Service and Ingress**:

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 8000
      name: http
  selector:
    app: myapp
---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - api.example.com
      secretName: myapp-tls
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: myapp
                port:
                  number: 80
```

**ConfigMap and Secrets**:

```yaml
# k8s/config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: myapp-config
data:
  LOG_LEVEL: "INFO"
  WORKERS: "4"
  ENVIRONMENT: "production"
---
apiVersion: v1
kind: Secret
metadata:
  name: myapp-secrets
type: Opaque
stringData:
  DATABASE_URL: "postgresql://user:password@db:5432/myapp"
  SECRET_KEY: "your-secret-key-here"
```

**Health check endpoints in FastAPI**:

```python
# src/health.py
from fastapi import APIRouter, Response
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Liveness probe - is the app alive?"""
    return {"status": "healthy"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    """Readiness probe - can the app serve traffic?"""
    try:
        # Check database connection
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "checks": {"database": "ok"}}
    except Exception as e:
        return Response(
            content=f'{{"status": "not ready", "error": "{str(e)}"}}',
            status_code=503,
            media_type="application/json",
        )
```

**Key points**:
- Use all three probe types: liveness, readiness, startup
- Set appropriate resource requests and limits
- Run as non-root with read-only filesystem
- Use pod anti-affinity for high availability
- Separate ConfigMaps (non-sensitive) from Secrets (sensitive)

---

## Common Patterns

### Pattern: Graceful Shutdown
```python
# main.py
import signal
import asyncio

shutdown_event = asyncio.Event()

def handle_sigterm(*args):
    shutdown_event.set()

signal.signal(signal.SIGTERM, handle_sigterm)

@app.on_event("shutdown")
async def shutdown():
    # Finish in-flight requests
    await asyncio.sleep(5)
```

### Pattern: Build Args for Versioning
```dockerfile
ARG VERSION=unknown
ARG BUILD_DATE=unknown
ARG GIT_SHA=unknown

LABEL version=$VERSION
LABEL build-date=$BUILD_DATE
LABEL git-sha=$GIT_SHA

ENV APP_VERSION=$VERSION
```

```bash
docker build \
    --build-arg VERSION=1.0.0 \
    --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
    --build-arg GIT_SHA=$(git rev-parse HEAD) \
    -t myapp:1.0.0 .
```

### Pattern: Multi-Platform Builds
```bash
# Build for multiple architectures
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t myapp:latest \
    --push .
```

---

## Pitfalls to Avoid

**Don't do this:**
```dockerfile
# Running as root
FROM python:3.12-slim
COPY . /app
CMD ["python", "app.py"]
# Runs as root - security risk!
```

**Do this instead:**
```dockerfile
FROM python:3.12-slim
RUN useradd --create-home appuser
WORKDIR /app
COPY --chown=appuser:appuser . .
USER appuser
CMD ["python", "app.py"]
```

---

**Don't do this:**
```dockerfile
# Poor layer caching
COPY . .
RUN pip install -r requirements.txt
# Every code change rebuilds dependencies!
```

**Do this instead:**
```dockerfile
# Requirements first, code second
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Code changes don't rebuild deps
```

---

**Don't do this:**
```dockerfile
# Using latest tag
FROM python:latest
# Unpredictable, breaks builds randomly
```

**Do this instead:**
```dockerfile
# Pin exact version
FROM python:3.12.2-slim
# Reproducible, predictable builds
```

---

## See Also

- [poetry-workflow.md](poetry-workflow.md) - Managing dependencies with Poetry
- [pyproject-config.md](pyproject-config.md) - Project configuration
- [async-programming.md](../patterns/async-programming.md) - Async patterns for web apps
