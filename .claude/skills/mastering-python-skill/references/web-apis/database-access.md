# Database Access with SQLAlchemy 2.0

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Async SQLAlchemy Setup](#example-1-async-sqlalchemy-setup)
  - [Example 2: Repository Pattern with CRUD Operations](#example-2-repository-pattern-with-crud-operations)
  - [Example 3: Transactions and Error Handling](#example-3-transactions-and-error-handling)
  - [Example 4: Alembic Migrations](#example-4-alembic-migrations)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code |
|------|------|
| Create async engine | `create_async_engine(url, pool_size=5)` |
| Async session | `async_sessionmaker(engine, class_=AsyncSession)` |
| Select query | `select(User).where(User.id == 1)` |
| Insert | `session.add(user)` |
| Update | `await session.execute(update(User).where(...).values(...))` |
| Delete | `await session.delete(user)` |
| Commit | `await session.commit()` |
| Rollback | `await session.rollback()` |
| Join | `select(User).join(User.posts)` |
| Eager load | `selectinload(User.posts)` |

---

## Core Concepts

SQLAlchemy 2.0 introduces a modernized API with first-class async support:

- **Async Engine**: Non-blocking database operations with asyncpg, aiosqlite
- **Type-Safe Queries**: The `select()` construct replaces legacy `Query` API
- **Connection Pooling**: Built-in pool management for production workloads
- **Unit of Work**: Session tracks changes and commits atomically

**Driver Options**:
| Database | Async Driver | Sync Driver |
|----------|--------------|-------------|
| PostgreSQL | `asyncpg` | `psycopg2` |
| MySQL | `aiomysql` | `pymysql` |
| SQLite | `aiosqlite` | `sqlite3` |

---

## Production Examples

### Example 1: Async SQLAlchemy Setup

**Use case**: Configure SQLAlchemy for async FastAPI applications.

```python
#!/usr/bin/env python3
"""Async SQLAlchemy 2.0 configuration."""

from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import String, Text, func
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# Database URL for async PostgreSQL
DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/mydb"


# Create async engine with connection pooling
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set True for SQL logging
    pool_size=5,  # Connections to keep open
    max_overflow=10,  # Additional connections when pool is full
    pool_timeout=30,  # Seconds to wait for connection
    pool_recycle=1800,  # Recycle connections after 30 min
    pool_pre_ping=True,  # Verify connections before use
)


# Async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
    autoflush=False,  # Manual flush control
)


# Base class for models
class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models with async support."""

    pass


# Timestamp mixin for created_at/updated_at
class TimestampMixin:
    """Add timestamp columns to models."""

    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )


# Model definitions
class User(TimestampMixin, Base):
    """User model with relationships."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationship to posts
    posts: Mapped[list["Post"]] = relationship(
        back_populates="author",
        lazy="selectin",  # Async-compatible loading
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class Post(TimestampMixin, Base):
    """Blog post model."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(default=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Relationship to author
    author: Mapped["User"] = relationship(back_populates="posts")

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, title={self.title[:20]}...)>"


# Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield database session with automatic cleanup."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Startup/shutdown for FastAPI lifespan
async def init_db() -> None:
    """Initialize database (create tables)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


# Usage example
async def main():
    # Initialize tables
    await init_db()

    # Use session
    async with async_session() as session:
        # Create user
        user = User(
            email="john@example.com",
            username="john_doe",
            hashed_password="hashed_secret",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)  # Get auto-generated ID

        print(f"Created: {user}")

    # Cleanup
    await close_db()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**Key points**:
- Use `create_async_engine` with async driver (`asyncpg`, `aiosqlite`)
- `AsyncAttrs` enables async access to lazy-loaded relationships
- `expire_on_commit=False` prevents detached instance errors
- Pool settings are critical for production performance

---

### Example 2: Repository Pattern with CRUD Operations

**Use case**: Encapsulate database operations with type-safe repository classes.

```python
#!/usr/bin/env python3
"""Repository pattern for SQLAlchemy CRUD operations."""

from typing import Generic, Sequence, TypeVar

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Base, User, Post


# Generic type for models
ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[ModelT]):
        self.session = session
        self.model = model

    async def get(self, id: int) -> ModelT | None:
        """Get single record by ID."""
        return await self.session.get(self.model, id)

    async def get_many(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ModelT]:
        """Get paginated list of records."""
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, **kwargs) -> ModelT:
        """Create new record."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()  # Get ID without committing
        await self.session.refresh(instance)
        return instance

    async def update(self, id: int, **kwargs) -> ModelT | None:
        """Update record by ID."""
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, id: int) -> bool:
        """Delete record by ID."""
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def count(self) -> int:
        """Count total records."""
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()


class UserRepository(BaseRepository[User]):
    """User-specific repository operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email address."""
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username."""
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_posts(self, user_id: int) -> User | None:
        """Get user with eagerly loaded posts."""
        stmt = (
            select(User)
            .options(selectinload(User.posts))
            .where(User.id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_users(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[User]:
        """Get only active users."""
        stmt = (
            select(User)
            .where(User.is_active == True)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def deactivate(self, user_id: int) -> User | None:
        """Deactivate a user."""
        return await self.update(user_id, is_active=False)


class PostRepository(BaseRepository[Post]):
    """Post-specific repository operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Post)

    async def get_published(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Post]:
        """Get published posts."""
        stmt = (
            select(Post)
            .where(Post.published == True)
            .order_by(Post.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_author(
        self,
        author_id: int,
        *,
        include_drafts: bool = False,
    ) -> Sequence[Post]:
        """Get posts by author."""
        stmt = select(Post).where(Post.author_id == author_id)
        if not include_drafts:
            stmt = stmt.where(Post.published == True)
        stmt = stmt.order_by(Post.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def publish(self, post_id: int) -> Post | None:
        """Publish a post."""
        return await self.update(post_id, published=True)

    async def search(self, query: str, limit: int = 20) -> Sequence[Post]:
        """Search posts by title or content."""
        stmt = (
            select(Post)
            .where(
                Post.published == True,
                (Post.title.ilike(f"%{query}%"))
                | (Post.content.ilike(f"%{query}%")),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


# Usage with FastAPI dependency injection
async def get_user_repo(db: AsyncSession = Depends(get_db)) -> UserRepository:
    """Provide UserRepository instance."""
    return UserRepository(db)


async def get_post_repo(db: AsyncSession = Depends(get_db)) -> PostRepository:
    """Provide PostRepository instance."""
    return PostRepository(db)


# FastAPI endpoint example
@app.get("/users/{user_id}/posts")
async def get_user_posts(
    user_id: int,
    user_repo: UserRepository = Depends(get_user_repo),
    post_repo: PostRepository = Depends(get_post_repo),
) -> list[PostResponse]:
    """Get all posts by a user."""
    user = await user_repo.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    posts = await post_repo.get_by_author(user_id)
    return [PostResponse.model_validate(p) for p in posts]
```

**Key points**:
- Generic `BaseRepository` provides reusable CRUD operations
- Specialized repositories add domain-specific queries
- `selectinload` efficiently loads relationships in async context
- FastAPI dependencies inject repositories for clean separation

---

### Example 3: Transactions and Error Handling

**Use case**: Handle complex operations with proper transaction management.

```python
#!/usr/bin/env python3
"""Transaction management and error handling."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base database error."""

    pass


class DuplicateError(DatabaseError):
    """Record already exists."""

    pass


class NotFoundError(DatabaseError):
    """Record not found."""

    pass


class TransactionError(DatabaseError):
    """Transaction failed."""

    pass


# Transaction context manager
@asynccontextmanager
async def transaction(
    session: AsyncSession,
) -> AsyncGenerator[AsyncSession, None]:
    """Manage database transaction with automatic rollback on error."""
    try:
        yield session
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Integrity error: {e}")
        if "unique constraint" in str(e).lower():
            raise DuplicateError("Record already exists") from e
        raise DatabaseError(f"Database integrity error: {e}") from e
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error: {e}")
        raise DatabaseError(f"Database operation failed: {e}") from e
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error in transaction: {e}")
        raise


# Nested transaction (savepoint)
@asynccontextmanager
async def savepoint(
    session: AsyncSession,
) -> AsyncGenerator[AsyncSession, None]:
    """Create a savepoint for nested transactions."""
    async with session.begin_nested():
        try:
            yield session
        except Exception:
            # Savepoint automatically rolled back
            raise


# Service layer with transaction handling
class UserService:
    """User service with business logic and transactions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.post_repo = PostRepository(session)

    async def register_user(
        self,
        email: str,
        username: str,
        password: str,
    ) -> User:
        """Register new user with validation."""
        async with transaction(self.session):
            # Check existing email
            existing = await self.user_repo.get_by_email(email)
            if existing:
                raise DuplicateError(f"Email {email} already registered")

            # Check existing username
            existing = await self.user_repo.get_by_username(username)
            if existing:
                raise DuplicateError(f"Username {username} already taken")

            # Create user
            hashed = hash_password(password)
            user = await self.user_repo.create(
                email=email,
                username=username,
                hashed_password=hashed,
            )
            return user

    async def transfer_posts(
        self,
        from_user_id: int,
        to_user_id: int,
    ) -> int:
        """Transfer all posts from one user to another."""
        async with transaction(self.session):
            # Verify both users exist
            from_user = await self.user_repo.get(from_user_id)
            if not from_user:
                raise NotFoundError(f"Source user {from_user_id} not found")

            to_user = await self.user_repo.get(to_user_id)
            if not to_user:
                raise NotFoundError(f"Target user {to_user_id} not found")

            # Update all posts
            stmt = (
                update(Post)
                .where(Post.author_id == from_user_id)
                .values(author_id=to_user_id)
            )
            result = await self.session.execute(stmt)
            return result.rowcount

    async def delete_user_cascade(self, user_id: int) -> bool:
        """Delete user and all their posts."""
        async with transaction(self.session):
            user = await self.user_repo.get(user_id)
            if not user:
                raise NotFoundError(f"User {user_id} not found")

            # Delete posts first (or use ON DELETE CASCADE)
            stmt = delete(Post).where(Post.author_id == user_id)
            await self.session.execute(stmt)

            # Delete user
            await self.user_repo.delete(user_id)
            return True

    async def create_user_with_welcome_post(
        self,
        email: str,
        username: str,
        password: str,
    ) -> tuple[User, Post]:
        """Create user and welcome post atomically."""
        async with transaction(self.session):
            # Create user
            user = await self.register_user(email, username, password)

            # Create welcome post
            post = await self.post_repo.create(
                title=f"Welcome, {username}!",
                content="Thanks for joining our platform.",
                author_id=user.id,
                published=True,
            )

            return user, post


# Retry decorator for transient failures
def retry_on_deadlock(max_retries: int = 3, delay: float = 0.1):
    """Retry operation on database deadlock."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except SQLAlchemyError as e:
                    if "deadlock" in str(e).lower():
                        last_error = e
                        logger.warning(
                            f"Deadlock detected, retry {attempt + 1}/{max_retries}"
                        )
                        await asyncio.sleep(delay * (2 ** attempt))
                    else:
                        raise
            raise TransactionError(
                f"Operation failed after {max_retries} retries"
            ) from last_error

        return wrapper

    return decorator


# FastAPI error handlers
@app.exception_handler(DuplicateError)
async def duplicate_handler(request: Request, exc: DuplicateError):
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


@app.exception_handler(DatabaseError)
async def database_handler(request: Request, exc: DatabaseError):
    return JSONResponse(
        status_code=500,
        content={"detail": "Database operation failed"},
    )
```

**Key points**:
- Use context managers for transaction boundaries
- Convert SQLAlchemy exceptions to domain errors
- Savepoints enable nested transactions (partial rollback)
- Retry logic handles transient failures (deadlocks)

---

### Example 4: Alembic Migrations

**Use case**: Manage database schema changes with version control.

```python
#!/usr/bin/env python3
"""Alembic migration configuration and examples."""

# alembic/env.py
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.models import Base
from app.config import settings


# Alembic Config object
config = context.config

# Set database URL from settings
config.set_main_option("sqlalchemy.url", settings.database.url)

# Interpret the config file for logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Example migration file** (`alembic/versions/001_create_users_table.py`):

```python
"""Create users table

Revision ID: 001
Revises:
Create Date: 2024-01-15 10:00:00.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create users table."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    """Drop users table."""
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
```

**Zero-downtime migration pattern** (expand-contract):

```python
"""Add new column with default (expand phase)

Revision ID: 003
"""

def upgrade() -> None:
    """Add status column with default value."""
    # Step 1: Add nullable column
    op.add_column(
        "users",
        sa.Column("status", sa.String(20), nullable=True),
    )

    # Step 2: Backfill existing data
    op.execute(
        "UPDATE users SET status = 'active' WHERE status IS NULL"
    )

    # Step 3: Make non-nullable (in separate migration after deploy)
    # op.alter_column("users", "status", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "status")
```

**Common Alembic commands**:
```bash
# Initialize Alembic
alembic init alembic

# Create migration from model changes
alembic revision --autogenerate -m "Add posts table"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Show current version
alembic current

# Show migration history
alembic history

# Generate SQL without applying
alembic upgrade head --sql
```

**Key points**:
- Use autogenerate for simple changes, manual for complex migrations
- Expand-contract pattern for zero-downtime deployments
- Always test migrations in staging before production
- Keep migrations small and focused

---

## Common Patterns

### Pattern: Bulk Insert
```python
async def bulk_insert_users(users: list[dict]) -> int:
    """Efficiently insert many records."""
    stmt = insert(User).values(users)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount
```

### Pattern: Upsert (Insert or Update)
```python
from sqlalchemy.dialects.postgresql import insert

async def upsert_user(user_data: dict) -> User:
    """Insert or update user."""
    stmt = insert(User).values(**user_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["email"],
        set_={"username": stmt.excluded.username},
    )
    await session.execute(stmt)
    await session.commit()
```

### Pattern: Pagination with Total Count
```python
async def paginate(
    query,
    page: int,
    page_size: int,
) -> tuple[Sequence[ModelT], int]:
    """Return page of results with total count."""
    # Get total
    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    # Get page
    stmt = query.offset((page - 1) * page_size).limit(page_size)
    items = (await session.execute(stmt)).scalars().all()

    return items, total
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# N+1 query problem
users = await session.execute(select(User))
for user in users.scalars():
    # Each iteration runs a new query!
    print(user.posts)  # Lazy load
```

**Do this instead:**
```python
# Eager load relationships
stmt = select(User).options(selectinload(User.posts))
users = await session.execute(stmt)
for user in users.scalars():
    print(user.posts)  # Already loaded
```

---

**Don't do this:**
```python
# Session used after close
async with async_session() as session:
    user = await session.get(User, 1)

# Session closed, user is detached!
print(user.posts)  # Error: detached instance
```

**Do this instead:**
```python
# Load everything needed before session closes
async with async_session() as session:
    stmt = select(User).options(selectinload(User.posts)).where(User.id == 1)
    user = (await session.execute(stmt)).scalar_one()
    posts = user.posts  # Loaded while session open

print(posts)  # Safe to use
```

---

## See Also

- [fastapi-patterns.md](fastapi-patterns.md) - FastAPI with SQLAlchemy
- [async-programming.md](../patterns/async-programming.md) - Async patterns
- [error-handling.md](../patterns/error-handling.md) - Exception handling
