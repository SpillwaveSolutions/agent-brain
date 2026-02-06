#!/usr/bin/env python3
"""
Database CLI with SQLAlchemy Async

Demonstrates SQLAlchemy 2.0 async patterns:
- Async engine and session setup
- Repository pattern
- CRUD operations
- Transaction management

Usage:
    python db_cli.py init                    # Initialize database
    python db_cli.py list                    # List all users
    python db_cli.py add "Name" email@ex.com # Add user
    python db_cli.py get 1                   # Get user by ID
    python db_cli.py update 1 --name "New"   # Update user
    python db_cli.py delete 1                # Delete user

See: ../references/web-apis/database-access.md
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

try:
    from sqlalchemy import String, select, func
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
except ImportError:
    print("Error: sqlalchemy not installed.")
    print("Run: pip install sqlalchemy aiosqlite")
    sys.exit(1)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_URL = "sqlite+aiosqlite:///./sample_cli.db"


# ============================================================
# MODELS
# ============================================================

class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, name={self.name!r}, email={self.email!r})"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ============================================================
# DATABASE SETUP
# ============================================================

def get_engine():
    """Create async engine."""
    return create_async_engine(
        DATABASE_URL,
        echo=False,  # Set True for SQL logging
    )


def get_session_factory(engine):
    """Create session factory."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# ============================================================
# REPOSITORY PATTERN
# ============================================================

class UserRepository:
    """Repository for User CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name: str, email: str) -> User:
        """Create a new user."""
        user = User(name=name, email=email)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: int) -> User | None:
        """Get user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100, offset: int = 0) -> Sequence[User]:
        """List all users with pagination."""
        stmt = (
            select(User)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        """Count total users."""
        stmt = select(func.count()).select_from(User)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def update(
        self,
        user_id: int,
        name: str | None = None,
        email: str | None = None,
    ) -> User | None:
        """Update a user."""
        user = await self.get_by_id(user_id)
        if user is None:
            return None

        if name is not None:
            user.name = name
        if email is not None:
            user.email = email

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user_id: int) -> bool:
        """Delete a user."""
        user = await self.get_by_id(user_id)
        if user is None:
            return False

        await self.session.delete(user)
        await self.session.commit()
        return True


# ============================================================
# CLI COMMANDS
# ============================================================

async def cmd_init(args: argparse.Namespace) -> int:
    """Initialize database and optionally add sample data."""
    engine = get_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Database initialized successfully.")

    if args.sample_data:
        session_factory = get_session_factory(engine)
        async with session_factory() as session:
            repo = UserRepository(session)

            # Check if data already exists
            if await repo.count() > 0:
                print("Sample data already exists, skipping.")
            else:
                sample_users = [
                    ("Alice Johnson", "alice@example.com"),
                    ("Bob Smith", "bob@example.com"),
                    ("Charlie Brown", "charlie@example.com"),
                ]

                for name, email in sample_users:
                    await repo.create(name, email)

                print(f"Added {len(sample_users)} sample users.")

    await engine.dispose()
    return 0


async def cmd_list(args: argparse.Namespace) -> int:
    """List all users."""
    engine = get_engine()
    session_factory = get_session_factory(engine)

    async with session_factory() as session:
        repo = UserRepository(session)

        total = await repo.count()
        users = await repo.list_all(limit=args.limit, offset=args.offset)

        if not users:
            print("No users found.")
            await engine.dispose()
            return 0

        print(f"\nUsers ({len(users)} of {total}):")
        print("-" * 60)
        print(f"{'ID':<5} {'Name':<25} {'Email':<30}")
        print("-" * 60)

        for user in users:
            print(f"{user.id:<5} {user.name:<25} {user.email:<30}")

        print("-" * 60)

    await engine.dispose()
    return 0


async def cmd_add(args: argparse.Namespace) -> int:
    """Add a new user."""
    engine = get_engine()
    session_factory = get_session_factory(engine)

    async with session_factory() as session:
        repo = UserRepository(session)

        # Check if email already exists
        existing = await repo.get_by_email(args.email)
        if existing:
            print(f"Error: User with email {args.email!r} already exists.")
            await engine.dispose()
            return 1

        try:
            user = await repo.create(args.name, args.email)
            print(f"Created user: {user}")
        except Exception as e:
            print(f"Error creating user: {e}")
            await engine.dispose()
            return 1

    await engine.dispose()
    return 0


async def cmd_get(args: argparse.Namespace) -> int:
    """Get user by ID."""
    engine = get_engine()
    session_factory = get_session_factory(engine)

    async with session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_id(args.user_id)

        if user is None:
            print(f"User with ID {args.user_id} not found.")
            await engine.dispose()
            return 1

        print(f"\nUser Details:")
        print("-" * 40)
        for key, value in user.to_dict().items():
            print(f"  {key}: {value}")
        print("-" * 40)

    await engine.dispose()
    return 0


async def cmd_update(args: argparse.Namespace) -> int:
    """Update a user."""
    if args.name is None and args.email is None:
        print("Error: Specify --name or --email to update.")
        return 1

    engine = get_engine()
    session_factory = get_session_factory(engine)

    async with session_factory() as session:
        repo = UserRepository(session)

        user = await repo.update(
            args.user_id,
            name=args.name,
            email=args.email,
        )

        if user is None:
            print(f"User with ID {args.user_id} not found.")
            await engine.dispose()
            return 1

        print(f"Updated user: {user}")

    await engine.dispose()
    return 0


async def cmd_delete(args: argparse.Namespace) -> int:
    """Delete a user."""
    if not args.force:
        confirm = input(f"Delete user {args.user_id}? [y/N]: ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return 0

    engine = get_engine()
    session_factory = get_session_factory(engine)

    async with session_factory() as session:
        repo = UserRepository(session)
        deleted = await repo.delete(args.user_id)

        if not deleted:
            print(f"User with ID {args.user_id} not found.")
            await engine.dispose()
            return 1

        print(f"Deleted user {args.user_id}.")

    await engine.dispose()
    return 0


# ============================================================
# CLI SETUP
# ============================================================

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SQLAlchemy async database CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s init                         # Initialize database
  %(prog)s init --sample-data           # Initialize with sample data
  %(prog)s list                         # List all users
  %(prog)s list --limit 10              # List with pagination
  %(prog)s add "John Doe" john@ex.com   # Add user
  %(prog)s get 1                        # Get user by ID
  %(prog)s update 1 --name "Jane"       # Update name
  %(prog)s update 1 --email new@ex.com  # Update email
  %(prog)s delete 1                     # Delete user (with confirm)
  %(prog)s delete 1 --force             # Delete without confirm
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize database")
    init_parser.add_argument(
        "--sample-data",
        action="store_true",
        help="Add sample data",
    )
    init_parser.set_defaults(func=cmd_init)

    # list command
    list_parser = subparsers.add_parser("list", help="List all users")
    list_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of users to list",
    )
    list_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Number of users to skip",
    )
    list_parser.set_defaults(func=cmd_list)

    # add command
    add_parser = subparsers.add_parser("add", help="Add a new user")
    add_parser.add_argument("name", help="User name")
    add_parser.add_argument("email", help="User email")
    add_parser.set_defaults(func=cmd_add)

    # get command
    get_parser = subparsers.add_parser("get", help="Get user by ID")
    get_parser.add_argument("user_id", type=int, help="User ID")
    get_parser.set_defaults(func=cmd_get)

    # update command
    update_parser = subparsers.add_parser("update", help="Update a user")
    update_parser.add_argument("user_id", type=int, help="User ID")
    update_parser.add_argument("--name", help="New name")
    update_parser.add_argument("--email", help="New email")
    update_parser.set_defaults(func=cmd_update)

    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a user")
    delete_parser.add_argument("user_id", type=int, help="User ID")
    delete_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Skip confirmation",
    )
    delete_parser.set_defaults(func=cmd_delete)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Check database file exists for non-init commands
    if args.command != "init" and not Path("sample_cli.db").exists():
        print("Error: Database not initialized. Run: python db_cli.py init")
        return 1

    return asyncio.run(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
