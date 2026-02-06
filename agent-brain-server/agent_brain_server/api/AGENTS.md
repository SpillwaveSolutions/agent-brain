# FastAPI API Guidelines for AI Agents

This directory contains the FastAPI REST API for Agent Brain. For Claude Code users, the `/mastering-python-skill` skill provides web API guidance.

## Skill Reference

**Claude Code users:** Invoke `/mastering-python-skill` for FastAPI guidance with no approval fatigue.

## Web API References

When developing API endpoints, use these references:

| Reference | Purpose |
|-----------|---------|
| `fastapi-patterns.md` | Routers, dependencies, middleware, errors |
| `pydantic-validation.md` | Request/response models, validators |
| `database-access.md` | SQLAlchemy async, repository pattern |

**Reference paths:** `.claude/skills/mastering-python-skill/references/web-apis/`

## Usage Guidelines

### For FastAPI (fastapi-patterns.md)
- Use APIRouter for endpoint groups
- Implement dependency injection
- Add proper middleware
- Handle errors with HTTPException

### For Pydantic (pydantic-validation.md)
- Define typed request/response models
- Add field validators
- Use Field() for constraints
- Create BaseSettings for config

### For database (database-access.md)
- Use async SQLAlchemy
- Implement repository pattern
- Manage transactions properly

## API Structure

```
api/
├── main.py              # App entry, lifespan
├── routers/             # Endpoint groups
└── dependencies.py      # Shared deps
```

## Running

```bash
poetry run uvicorn agent_brain_server.api.main:app --reload
# Or
poetry run agent-brain-serve
```

## Quality Requirements

- Type hints on all endpoints
- Pydantic models for request/response
- Proper HTTP status codes
- Dependency injection for services
- Accurate OpenAPI docs
