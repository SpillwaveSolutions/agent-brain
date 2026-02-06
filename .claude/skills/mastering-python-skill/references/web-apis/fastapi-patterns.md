# FastAPI Patterns

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Dependency Injection Pattern](#example-1-dependency-injection-pattern)
  - [Example 2: Request Validation with Pydantic](#example-2-request-validation-with-pydantic)
  - [Example 3: Background Tasks and Middleware](#example-3-background-tasks-and-middleware)
  - [Example 4: API Versioning and Router Organization](#example-4-api-versioning-and-router-organization)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code |
|------|------|
| Create app | `app = FastAPI(title="My API")` |
| GET endpoint | `@app.get("/items/{id}")` |
| POST endpoint | `@app.post("/items", status_code=201)` |
| Dependency | `def get_db(): yield db` |
| Use dependency | `db: Session = Depends(get_db)` |
| Path param | `item_id: int` |
| Query param | `skip: int = 0, limit: int = 10` |
| Body param | `item: ItemCreate` |
| Response model | `response_model=ItemResponse` |
| Background task | `background_tasks.add_task(send_email, email)` |

---

## Core Concepts

FastAPI is a modern, high-performance web framework built on Starlette and Pydantic. Key features:

- **Type-Driven Development**: Leverages Python type hints for validation, serialization, and documentation
- **Dependency Injection**: Built-in DI system for managing database connections, authentication, etc.
- **Async Support**: First-class async/await support with both sync and async endpoints
- **Auto Documentation**: Generates OpenAPI (Swagger) and ReDoc documentation automatically

FastAPI achieves performance comparable to Node.js and Go through ASGI and async I/O while maintaining Python's developer experience.

---

## Production Examples

### Example 1: Dependency Injection Pattern

**Use case**: Manage database sessions, authentication, and shared services across endpoints.

```python
#!/usr/bin/env python3
"""Dependency injection patterns for FastAPI."""

from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


# Database setup
DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/dbname"

engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=10)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan events."""
    # Startup: create tables, warm up connections
    print("Starting up...")
    yield
    # Shutdown: close connections
    await engine.dispose()
    print("Shutting down...")


app = FastAPI(title="My API", lifespan=lifespan)


# Database dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session, ensuring cleanup."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Type alias for cleaner annotations
DbSession = Annotated[AsyncSession, Depends(get_db)]


# Authentication dependency
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Validate token and return current user."""
    user = await validate_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# Using dependencies in endpoints
@app.get("/users/me")
async def read_current_user(
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    """Get current user profile."""
    return UserResponse.model_validate(current_user)


@app.get("/items")
async def list_items(
    db: DbSession,
    skip: int = 0,
    limit: int = 100,
) -> list[ItemResponse]:
    """List all items with pagination."""
    result = await db.execute(
        select(Item).offset(skip).limit(limit)
    )
    return [ItemResponse.model_validate(item) for item in result.scalars()]
```

**Key points**:
- Use `Annotated` type aliases for cleaner, reusable dependency annotations
- The `lifespan` context manager replaces deprecated `on_event` decorators
- Dependencies automatically handle setup and cleanup (database commits/rollbacks)
- Chain dependencies for complex auth flows (user → permissions → resources)

---

### Example 2: Request Validation with Pydantic

**Use case**: Validate and transform request/response data with automatic error handling.

```python
#!/usr/bin/env python3
"""Request validation and response models with Pydantic."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator


app = FastAPI()


class ItemStatus(str, Enum):
    """Item status enumeration."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# Request models (for input)
class ItemCreate(BaseModel):
    """Schema for creating an item."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    price: float = Field(..., gt=0, description="Price must be positive")
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Validate name is not just whitespace."""
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v.strip()


class ItemUpdate(BaseModel):
    """Schema for updating an item (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    price: float | None = Field(None, gt=0)
    status: ItemStatus | None = None
    tags: list[str] | None = None


# Response models (for output)
class ItemResponse(BaseModel):
    """Schema for item responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price: float
    status: ItemStatus
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class ItemListResponse(BaseModel):
    """Paginated list of items."""

    items: list[ItemResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# Endpoints with validation
@app.post(
    "/items",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_item(item: ItemCreate) -> ItemResponse:
    """Create a new item with validated data."""
    # Pydantic validates the request body automatically
    db_item = await save_to_database(item)
    return ItemResponse.model_validate(db_item)


@app.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: Annotated[int, Path(ge=1, description="The item ID")],
) -> ItemResponse:
    """Get item by ID with path parameter validation."""
    item = await fetch_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found",
        )
    return ItemResponse.model_validate(item)


@app.get("/items", response_model=ItemListResponse)
async def list_items(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: ItemStatus | None = None,
    search: Annotated[str | None, Query(min_length=2)] = None,
) -> ItemListResponse:
    """List items with query parameter validation."""
    items, total = await query_items(
        page=page,
        page_size=page_size,
        status=status,
        search=search,
    )
    return ItemListResponse(
        items=[ItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@app.patch("/items/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: Annotated[int, Path(ge=1)],
    item_update: ItemUpdate,
) -> ItemResponse:
    """Partial update with only provided fields."""
    # exclude_unset=True ignores fields not in the request
    update_data = item_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    updated = await update_in_database(item_id, update_data)
    return ItemResponse.model_validate(updated)
```

**Key points**:
- Use separate models for Create/Update/Response to control what's accepted and returned
- `Field()` provides validation constraints and OpenAPI documentation
- `model_dump(exclude_unset=True)` enables proper PATCH semantics
- `ConfigDict(from_attributes=True)` allows ORM model → Pydantic conversion

---

### Example 3: Background Tasks and Middleware

**Use case**: Handle async operations and cross-cutting concerns like logging and timing.

```python
#!/usr/bin/env python3
"""Background tasks and middleware patterns."""

import time
import uuid
from typing import Callable

from fastapi import BackgroundTasks, FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


app = FastAPI()


# Background task functions
async def send_email_notification(email: str, subject: str, body: str) -> None:
    """Send email asynchronously (non-blocking)."""
    # Simulate email sending
    await asyncio.sleep(2)
    print(f"Email sent to {email}: {subject}")


async def log_analytics_event(event_type: str, data: dict) -> None:
    """Log analytics event to external service."""
    # Simulate API call
    await asyncio.sleep(0.5)
    print(f"Analytics logged: {event_type} - {data}")


# Using background tasks in endpoints
@app.post("/orders")
async def create_order(
    order: OrderCreate,
    background_tasks: BackgroundTasks,
) -> OrderResponse:
    """Create order and send confirmation email."""
    # Create order synchronously
    db_order = await save_order(order)

    # Queue background tasks (non-blocking)
    background_tasks.add_task(
        send_email_notification,
        email=order.customer_email,
        subject="Order Confirmation",
        body=f"Your order #{db_order.id} has been placed.",
    )
    background_tasks.add_task(
        log_analytics_event,
        event_type="order_created",
        data={"order_id": db_order.id, "total": order.total},
    )

    return OrderResponse.model_validate(db_order)


# Request ID middleware
class RequestIdMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# Timing middleware
class TimingMiddleware(BaseHTTPMiddleware):
    """Log request timing."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Log slow requests
        if duration_ms > 500:
            print(
                f"Slow request: {request.method} {request.url.path} "
                f"took {duration_ms:.2f}ms"
            )

        return response


# Register middleware (order matters - first added = outermost)
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIdMiddleware)


# Exception handler middleware
@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle uncaught exceptions with request context."""
    request_id = getattr(request.state, "request_id", "unknown")
    print(f"Error in request {request_id}: {exc}")

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
    )
```

**Key points**:
- Background tasks run after the response is sent (fire-and-forget)
- Middleware executes for every request—use for cross-cutting concerns
- Middleware order matters: first added wraps outermost
- Use `request.state` to pass data between middleware and handlers

---

### Example 4: API Versioning and Router Organization

**Use case**: Structure large APIs with versioning and modular routers.

```python
#!/usr/bin/env python3
"""API versioning and router organization."""

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute


# Custom route class for operation IDs
class CustomRoute(APIRoute):
    """Generate cleaner operation IDs for OpenAPI."""

    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def custom_handler(request):
            return await original_route_handler(request)

        return custom_handler


# Version 1 routers
v1_users_router = APIRouter(
    prefix="/users",
    tags=["users"],
    route_class=CustomRoute,
)

v1_items_router = APIRouter(
    prefix="/items",
    tags=["items"],
)


@v1_users_router.get("")
async def list_users_v1() -> list[UserResponseV1]:
    """List users (v1 format)."""
    return await get_all_users_v1()


@v1_users_router.get("/{user_id}")
async def get_user_v1(user_id: int) -> UserResponseV1:
    """Get user by ID (v1 format)."""
    return await fetch_user_v1(user_id)


@v1_items_router.get("")
async def list_items_v1() -> list[ItemResponseV1]:
    """List items (v1 format)."""
    return await get_all_items_v1()


# Version 2 routers with breaking changes
v2_users_router = APIRouter(
    prefix="/users",
    tags=["users-v2"],
)


@v2_users_router.get("")
async def list_users_v2() -> list[UserResponseV2]:
    """List users (v2 format with additional fields)."""
    return await get_all_users_v2()


@v2_users_router.get("/{user_id}")
async def get_user_v2(user_id: int) -> UserResponseV2:
    """Get user by ID (v2 format)."""
    return await fetch_user_v2(user_id)


# Combine routers into version groups
v1_router = APIRouter(prefix="/v1")
v1_router.include_router(v1_users_router)
v1_router.include_router(v1_items_router)

v2_router = APIRouter(prefix="/v2")
v2_router.include_router(v2_users_router)


# Main application
app = FastAPI(
    title="My API",
    description="API with multiple versions",
    version="2.0.0",
)

# Mount versioned routers
app.include_router(v1_router)
app.include_router(v2_router)


# Health check (unversioned)
@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}


# Redirect root to docs
@app.get("/", include_in_schema=False)
async def root():
    """Redirect to API documentation."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
```

**Typical project structure**:
```
src/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app creation
│   ├── config.py            # Settings with pydantic-settings
│   ├── dependencies.py      # Shared dependencies
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py    # V1 router aggregation
│   │   │   ├── users.py     # User endpoints
│   │   │   └── items.py     # Item endpoints
│   │   └── v2/
│   │       └── ...
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   └── services/            # Business logic
```

**Key points**:
- Use URL path versioning (`/v1/`, `/v2/`) for clear API evolution
- Group related endpoints with `APIRouter` and tags
- Separate schemas per version to allow independent evolution
- Keep health checks unversioned and always available

---

## Common Patterns

### Pattern: Settings with pydantic-settings
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    debug: bool = False

    model_config = ConfigDict(env_file=".env")

settings = Settings()
```

### Pattern: Custom Exception Handler
```python
class AppException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
```

### Pattern: Rate Limiting Dependency
```python
from fastapi import HTTPException
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests: int, window: timedelta):
        self.max_requests = max_requests
        self.window = window
        self.requests: dict[str, list[datetime]] = {}

    async def __call__(self, request: Request):
        client_ip = request.client.host
        now = datetime.utcnow()
        # Clean old requests and check limit
        # ... implementation
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Blocking call in async endpoint
@app.get("/data")
async def get_data():
    data = requests.get("http://api.example.com")  # Blocks event loop!
    return data.json()
```

**Do this instead:**
```python
# Use async HTTP client
import httpx

@app.get("/data")
async def get_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://api.example.com")
        return response.json()
```

---

**Don't do this:**
```python
# Global mutable state
items_cache = {}  # Shared across requests - race conditions!

@app.get("/items/{id}")
async def get_item(id: int):
    if id not in items_cache:
        items_cache[id] = await fetch_item(id)
    return items_cache[id]
```

**Do this instead:**
```python
# Use proper caching with Redis or dependency injection
from functools import lru_cache

@lru_cache
def get_settings():
    return Settings()

# Or use Redis for distributed caching
```

---

## See Also

- [pydantic-validation.md](pydantic-validation.md) - Detailed Pydantic patterns
- [database-access.md](database-access.md) - SQLAlchemy async with FastAPI
- [async-programming.md](../patterns/async-programming.md) - Async patterns
