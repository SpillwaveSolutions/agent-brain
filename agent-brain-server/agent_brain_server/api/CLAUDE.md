# FastAPI API Guidelines for Claude Code

This directory contains the FastAPI REST API for Agent Brain. Use the `/mastering-python-skill` skill for Python web API best practices.

## Required Skill

**Invoke:** `/mastering-python-skill`

This skill is bound to the `senior-python-engineer` agent with pre-authorized tools (no approval fatigue).

## Specific References for Web APIs

When developing FastAPI endpoints in this directory, refer to these skill references:

| Reference | Use For | Path |
|-----------|---------|------|
| **fastapi-patterns.md** | Routers, dependencies, middleware, error handling | `.claude/skills/mastering-python-skill/references/web-apis/fastapi-patterns.md` |
| **pydantic-validation.md** | Request/response models, validators, settings | `.claude/skills/mastering-python-skill/references/web-apis/pydantic-validation.md` |
| **database-access.md** | SQLAlchemy async, repository pattern, transactions | `.claude/skills/mastering-python-skill/references/web-apis/database-access.md` |

## When to Use Each Reference

### fastapi-patterns.md
- Creating new API routers
- Implementing dependency injection
- Adding middleware (CORS, logging, auth)
- Structured error handling with `HTTPException`
- Background tasks and lifespan events

### pydantic-validation.md
- Defining request/response models
- Adding field validators
- Using `Field()` for constraints
- Creating settings classes with `BaseSettings`
- Model serialization and aliases

### database-access.md
- Async database operations with SQLAlchemy
- Repository pattern implementation
- Transaction management
- Connection pooling

## API Structure

```
api/
├── main.py              # FastAPI app, lifespan, middleware
├── routers/
│   ├── health.py        # Health check endpoints
│   ├── index.py         # Indexing endpoints
│   └── query.py         # Search/query endpoints
└── dependencies.py      # Shared dependencies
```

## FastAPI Patterns

```python
# Router with dependencies
router = APIRouter(prefix="/query", tags=["query"])

@router.post("/", response_model=QueryResponse)
async def search(
    request: QueryRequest,
    service: QueryService = Depends(get_query_service)
) -> QueryResponse:
    return await service.search(request.query)
```

## Running the Server

```bash
# Development
poetry run uvicorn agent_brain_server.api.main:app --reload

# Or via CLI
poetry run agent-brain-serve
```

## Quality Standards

Before committing API changes:
- [ ] Endpoints have proper type hints
- [ ] Request/response models use Pydantic
- [ ] Errors return appropriate HTTP status codes
- [ ] Dependencies are properly injected
- [ ] OpenAPI docs are accurate (`/docs`)
