# Security Best Practices

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Input Validation and Sanitization](#example-1-input-validation-and-sanitization)
  - [Example 2: Secure Authentication](#example-2-secure-authentication)
  - [Example 3: Dependency Security Scanning](#example-3-dependency-security-scanning)
  - [Example 4: Secure Configuration and Secrets](#example-4-secure-configuration-and-secrets)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code |
|------|------|
| Hash password | `pwd_context.hash(password)` |
| Verify password | `pwd_context.verify(password, hashed)` |
| Generate token | `secrets.token_urlsafe(32)` |
| Validate input | `pydantic.BaseModel` with validators |
| Parameterized SQL | `select(User).where(User.id == :id)` |
| Scan deps | `pip-audit --strict` |
| SAST scan | `bandit -r src/ -f json` |

---

## Core Concepts

**OWASP Top 10 for Python**:

| Risk | Mitigation |
|------|------------|
| **Injection** | Parameterized queries, input validation |
| **Broken Auth** | Argon2/bcrypt, secure sessions, MFA |
| **Sensitive Data** | Encryption at rest/transit, secret management |
| **XXE** | Disable XML external entities |
| **Broken Access** | RBAC, resource ownership checks |
| **Misconfiguration** | Secure defaults, environment separation |
| **XSS** | Output encoding, CSP headers |
| **Deserialization** | Use JSON, validate schemas (avoid unsafe serialization) |
| **Components** | Dependency scanning, updates |
| **Logging** | Audit trails, no sensitive data in logs |

**Security Principles**:
- **Defense in Depth**: Multiple layers of protection
- **Least Privilege**: Minimum necessary permissions
- **Fail Secure**: Deny by default on errors
- **Input Validation**: Validate at boundaries

---

## Production Examples

### Example 1: Input Validation and Sanitization

**Use case**: Secure input validation with Pydantic to prevent injection attacks.

```python
#!/usr/bin/env python3
"""Secure input validation patterns with Pydantic."""

import html
import re
from typing import Annotated, Any
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    SecretStr,
    field_validator,
    model_validator,
)


# ============================================================
# CUSTOM VALIDATORS
# ============================================================

def sanitize_string(value: str) -> str:
    """Remove potentially dangerous characters."""
    # Remove null bytes
    value = value.replace("\x00", "")
    # Normalize unicode
    value = value.strip()
    return value


def validate_no_sql_injection(value: str) -> str:
    """Check for common SQL injection patterns."""
    dangerous_patterns = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)",
        r"(--|;|/\*|\*/)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"('\s*OR\s+')",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValueError("Potentially dangerous input detected")

    return value


def validate_no_path_traversal(value: str) -> str:
    """Prevent path traversal attacks."""
    if ".." in value or value.startswith("/"):
        raise ValueError("Path traversal not allowed")
    return value


# ============================================================
# SECURE INPUT MODELS
# ============================================================

class SecureUserInput(BaseModel):
    """User input with comprehensive validation."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_min_length=1,
        extra="forbid",  # Reject unknown fields
    )

    username: Annotated[
        str,
        Field(
            min_length=3,
            max_length=32,
            pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$",
            description="Alphanumeric username starting with letter",
        ),
    ]

    email: EmailStr

    password: Annotated[
        SecretStr,
        Field(min_length=12, description="Minimum 12 characters"),
    ]

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Additional username validation."""
        # Check reserved words
        reserved = {"admin", "root", "system", "null", "undefined"}
        if v.lower() in reserved:
            raise ValueError("Username is reserved")
        return sanitize_string(v)


class SearchQuery(BaseModel):
    """Safe search query input."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: Annotated[str, Field(min_length=1, max_length=200)]
    page: Annotated[int, Field(ge=1, le=1000)] = 1
    per_page: Annotated[int, Field(ge=1, le=100)] = 20

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Sanitize search query."""
        v = sanitize_string(v)
        v = validate_no_sql_injection(v)
        # HTML escape for display
        v = html.escape(v)
        return v


class FileUploadRequest(BaseModel):
    """Secure file upload validation."""

    filename: Annotated[str, Field(max_length=255)]
    content_type: str
    size_bytes: Annotated[int, Field(gt=0, le=10_485_760)]  # Max 10MB

    ALLOWED_TYPES: set[str] = {"image/jpeg", "image/png", "application/pdf"}
    ALLOWED_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".pdf"}

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename is safe."""
        v = sanitize_string(v)
        v = validate_no_path_traversal(v)

        # Check extension
        ext = "." + v.rsplit(".", 1)[-1].lower() if "." in v else ""
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise ValueError(f"File extension not allowed: {ext}")

        # Remove any remaining dangerous characters
        v = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", v)

        return v

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        """Validate content type."""
        if v not in cls.ALLOWED_TYPES:
            raise ValueError(f"Content type not allowed: {v}")
        return v


class WebhookPayload(BaseModel):
    """Validate external webhook data."""

    event_type: Annotated[str, Field(pattern=r"^[a-z_]+$")]
    timestamp: int
    data: dict[str, Any]
    callback_url: HttpUrl | None = None

    @field_validator("callback_url")
    @classmethod
    def validate_callback_url(cls, v: HttpUrl | None) -> HttpUrl | None:
        """Prevent SSRF by validating callback URLs."""
        if v is None:
            return None

        parsed = urlparse(str(v))

        # Block internal IPs
        blocked_hosts = {
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "169.254.169.254",  # AWS metadata
            "metadata.google.internal",  # GCP metadata
        }

        if parsed.hostname and parsed.hostname.lower() in blocked_hosts:
            raise ValueError("Internal URLs not allowed")

        # Block private IP ranges
        if parsed.hostname:
            import ipaddress
            try:
                ip = ipaddress.ip_address(parsed.hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    raise ValueError("Private IP addresses not allowed")
            except ValueError:
                pass  # Not an IP address, hostname is fine

        return v


# ============================================================
# USAGE
# ============================================================

if __name__ == "__main__":
    # Valid input
    user = SecureUserInput(
        username="john_doe",
        email="john@example.com",
        password="SecurePass123!@#",  # type: ignore
    )
    print(f"Valid user: {user.username}")

    # Invalid inputs will raise ValidationError
    try:
        bad_user = SecureUserInput(
            username="admin",  # Reserved
            email="john@example.com",
            password="short",  # type: ignore
        )
    except Exception as e:
        print(f"Validation error: {e}")

    # Search query sanitization
    search = SearchQuery(query="<script>alert('xss')</script>")
    print(f"Sanitized query: {search.query}")  # HTML escaped
```

**Key points**:
- `extra="forbid"` prevents mass assignment attacks
- Custom validators catch injection patterns
- SSRF prevention for callback URLs
- SecretStr masks passwords in logs

---

### Example 2: Secure Authentication

**Use case**: Password hashing with Argon2 and JWT token management.

```python
#!/usr/bin/env python3
"""Secure authentication with Argon2 and JWT."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, SecretStr

# ============================================================
# PASSWORD HASHING (Argon2id recommended)
# ============================================================

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__memory_cost=65536,  # 64 MB
    argon2__time_cost=3,        # 3 iterations
    argon2__parallelism=4,      # 4 threads
)


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def check_needs_rehash(hashed_password: str) -> bool:
    """Check if password needs rehashing (e.g., algorithm upgrade)."""
    return pwd_context.needs_update(hashed_password)


# ============================================================
# JWT TOKEN MANAGEMENT
# ============================================================

class TokenSettings(BaseModel):
    """JWT configuration."""

    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    issuer: str = "myapp"


class TokenPayload(BaseModel):
    """JWT payload structure."""

    sub: str  # Subject (user ID)
    exp: datetime
    iat: datetime
    jti: str  # JWT ID for revocation
    type: str  # "access" or "refresh"
    roles: list[str] = []


class TokenManager:
    """Secure JWT token management."""

    def __init__(self, settings: TokenSettings):
        self.settings = settings
        self._revoked_tokens: set[str] = set()  # In production, use Redis

    def create_access_token(
        self,
        user_id: str,
        roles: list[str] | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create short-lived access token."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=self.settings.access_token_expire_minutes)

        payload = {
            "sub": user_id,
            "exp": expires,
            "iat": now,
            "jti": secrets.token_urlsafe(16),
            "type": "access",
            "roles": roles or [],
            "iss": self.settings.issuer,
            **(extra_claims or {}),
        }

        return jwt.encode(
            payload,
            self.settings.secret_key.get_secret_value(),
            algorithm=self.settings.algorithm,
        )

    def create_refresh_token(self, user_id: str) -> str:
        """Create long-lived refresh token."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=self.settings.refresh_token_expire_days)

        payload = {
            "sub": user_id,
            "exp": expires,
            "iat": now,
            "jti": secrets.token_urlsafe(16),
            "type": "refresh",
            "iss": self.settings.issuer,
        }

        return jwt.encode(
            payload,
            self.settings.secret_key.get_secret_value(),
            algorithm=self.settings.algorithm,
        )

    def verify_token(self, token: str, expected_type: str = "access") -> TokenPayload:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.settings.secret_key.get_secret_value(),
                algorithms=[self.settings.algorithm],
                issuer=self.settings.issuer,
                options={
                    "require": ["exp", "iat", "sub", "jti", "type"],
                },
            )

            # Check token type
            if payload.get("type") != expected_type:
                raise jwt.InvalidTokenError(f"Expected {expected_type} token")

            # Check if revoked
            if payload.get("jti") in self._revoked_tokens:
                raise jwt.InvalidTokenError("Token has been revoked")

            return TokenPayload(**payload)

        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}")

    def revoke_token(self, token: str) -> None:
        """Revoke a token by its JTI."""
        try:
            payload = jwt.decode(
                token,
                self.settings.secret_key.get_secret_value(),
                algorithms=[self.settings.algorithm],
                options={"verify_exp": False},
            )
            self._revoked_tokens.add(payload["jti"])
        except jwt.InvalidTokenError:
            pass  # Already invalid


# ============================================================
# SECURE TOKEN GENERATION
# ============================================================

def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(32)


def generate_verification_token() -> str:
    """Generate email verification token."""
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> tuple[str, str]:
    """Generate password reset token and selector.

    Returns:
        Tuple of (selector, validator) - store hash of validator
    """
    selector = secrets.token_urlsafe(12)
    validator = secrets.token_urlsafe(32)
    return selector, validator


# ============================================================
# USAGE
# ============================================================

if __name__ == "__main__":
    # Password hashing
    password = "MySecurePassword123!"
    hashed = hash_password(password)
    print(f"Hashed: {hashed[:50]}...")

    assert verify_password(password, hashed)
    assert not verify_password("wrong", hashed)

    # JWT tokens
    settings = TokenSettings(secret_key=SecretStr(secrets.token_urlsafe(32)))
    token_manager = TokenManager(settings)

    # Create tokens
    access_token = token_manager.create_access_token(
        user_id="user-123",
        roles=["user", "admin"],
    )
    print(f"Access token: {access_token[:50]}...")

    # Verify token
    payload = token_manager.verify_token(access_token)
    print(f"User ID: {payload.sub}, Roles: {payload.roles}")

    # Revoke token
    token_manager.revoke_token(access_token)
    try:
        token_manager.verify_token(access_token)
    except ValueError as e:
        print(f"Token revoked: {e}")
```

**Key points**:
- Argon2id is the recommended password hashing algorithm
- Short-lived access tokens (15 min), longer refresh tokens
- JTI enables token revocation
- secrets module for cryptographically secure randomness

---

### Example 3: Dependency Security Scanning

**Use case**: Automated vulnerability scanning in CI/CD pipelines.

```yaml
# .github/workflows/security.yml
name: Security Scan

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM

jobs:
  # ============================================================
  # DEPENDENCY SCANNING
  # ============================================================
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install pip-audit safety

      - name: Run pip-audit
        run: |
          pip-audit --strict --desc on -r requirements.txt
        continue-on-error: true

      - name: Run safety check
        run: |
          safety check -r requirements.txt --full-report
        continue-on-error: true

      - name: Check for known vulnerabilities
        run: |
          pip install -r requirements.txt
          pip-audit --strict

  # ============================================================
  # STATIC APPLICATION SECURITY TESTING (SAST)
  # ============================================================
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Bandit
        run: pip install bandit[toml]

      - name: Run Bandit security scan
        run: |
          bandit -r src/ \
            -f json \
            -o bandit-report.json \
            --severity-level medium \
            --confidence-level medium
        continue-on-error: true

      - name: Upload Bandit report
        uses: actions/upload-artifact@v4
        with:
          name: bandit-report
          path: bandit-report.json

      - name: Check for high severity issues
        run: |
          bandit -r src/ \
            --severity-level high \
            --confidence-level high \
            -f txt

  # ============================================================
  # SECRET SCANNING
  # ============================================================
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Detect secrets with TruffleHog
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          extra_args: --only-verified

      - name: Detect secrets with Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  # ============================================================
  # LICENSE COMPLIANCE
  # ============================================================
  license-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install pip-licenses
        run: pip install pip-licenses

      - name: Check licenses
        run: |
          pip install -r requirements.txt
          pip-licenses --format=markdown --order=license

      - name: Check for problematic licenses
        run: |
          pip-licenses --fail-on="GPL;AGPL" || echo "Check licenses manually"
```

**Python script for local scanning**:

```python
#!/usr/bin/env python3
"""Security scanning utilities."""

import subprocess
import sys
from pathlib import Path


def run_pip_audit(requirements_file: str = "requirements.txt") -> int:
    """Run pip-audit for dependency vulnerabilities."""
    print("Running pip-audit...")
    result = subprocess.run(
        ["pip-audit", "--strict", "-r", requirements_file],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def run_bandit(source_dir: str = "src") -> int:
    """Run Bandit SAST scanner."""
    print("Running Bandit...")
    result = subprocess.run(
        [
            "bandit",
            "-r", source_dir,
            "-f", "txt",
            "--severity-level", "medium",
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def run_safety(requirements_file: str = "requirements.txt") -> int:
    """Run Safety dependency check."""
    print("Running Safety...")
    result = subprocess.run(
        ["safety", "check", "-r", requirements_file],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def main() -> int:
    """Run all security scans."""
    results = []

    # Check if tools are installed
    for tool in ["pip-audit", "bandit", "safety"]:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
        except FileNotFoundError:
            print(f"Installing {tool}...")
            subprocess.run([sys.executable, "-m", "pip", "install", tool])

    # Run scans
    if Path("requirements.txt").exists():
        results.append(run_pip_audit())
        results.append(run_safety())

    if Path("src").is_dir():
        results.append(run_bandit("src"))

    # Return non-zero if any scan failed
    return max(results) if results else 0


if __name__ == "__main__":
    sys.exit(main())
```

**Key points**:
- pip-audit checks PyPI for known vulnerabilities
- Bandit performs static analysis for security issues
- TruffleHog/Gitleaks detect committed secrets
- Schedule daily scans for new vulnerabilities

---

### Example 4: Secure Configuration and Secrets

**Use case**: Secure secrets management with environment variables and vaults.

```python
#!/usr/bin/env python3
"""Secure configuration and secrets management."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import (
    Field,
    PostgresDsn,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# SECURE SETTINGS MODEL
# ============================================================

class SecuritySettings(BaseSettings):
    """Security-related configuration."""

    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Don't allow secrets in __repr__
        json_schema_extra={"hide_input_in_errors": True},
    )

    # Secrets (never logged or exposed)
    jwt_secret_key: SecretStr = Field(
        ...,
        description="Secret key for JWT signing",
        min_length=32,
    )
    encryption_key: SecretStr = Field(
        ...,
        description="Key for data encryption",
        min_length=32,
    )

    # Database with credentials
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection string",
    )

    # API keys
    stripe_api_key: SecretStr | None = Field(
        default=None,
        description="Stripe API key",
    )

    # Security settings
    allowed_hosts: list[str] = Field(
        default=["localhost"],
        description="Allowed host headers",
    )
    cors_origins: list[str] = Field(
        default=[],
        description="Allowed CORS origins",
    )

    # Rate limiting
    rate_limit_requests: int = Field(
        default=100,
        ge=1,
        description="Requests per window",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        description="Rate limit window",
    )

    @field_validator("jwt_secret_key", "encryption_key")
    @classmethod
    def validate_secret_strength(cls, v: SecretStr) -> SecretStr:
        """Ensure secrets meet minimum requirements."""
        secret = v.get_secret_value()
        if len(secret) < 32:
            raise ValueError("Secret must be at least 32 characters")
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> "SecuritySettings":
        """Validate settings are appropriate for production."""
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            if "localhost" in self.allowed_hosts:
                raise ValueError("localhost not allowed in production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS not allowed in production")
        return self


class AppSettings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    environment: str = Field(
        default="development",
        pattern="^(development|staging|production)$",
    )
    debug: bool = Field(
        default=False,
        description="Debug mode (never True in production)",
    )
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    )

    @model_validator(mode="after")
    def validate_debug_mode(self) -> "AppSettings":
        """Ensure debug is off in production."""
        if self.environment == "production" and self.debug:
            raise ValueError("Debug mode must be disabled in production")
        return self


# ============================================================
# SETTINGS FACTORY
# ============================================================

@lru_cache
def get_security_settings() -> SecuritySettings:
    """Get cached security settings."""
    return SecuritySettings()


@lru_cache
def get_app_settings() -> AppSettings:
    """Get cached app settings."""
    return AppSettings()


# ============================================================
# SECRETS FROM VAULT (Example with HashiCorp Vault)
# ============================================================

class VaultClient:
    """Simple Vault client for secrets retrieval."""

    def __init__(self, vault_addr: str, vault_token: SecretStr):
        self.vault_addr = vault_addr
        self.vault_token = vault_token

    def get_secret(self, path: str) -> dict[str, Any]:
        """Retrieve secret from Vault."""
        import httpx

        response = httpx.get(
            f"{self.vault_addr}/v1/{path}",
            headers={"X-Vault-Token": self.vault_token.get_secret_value()},
        )
        response.raise_for_status()
        return response.json()["data"]["data"]


# ============================================================
# SECURE FILE HANDLING
# ============================================================

def load_secret_file(path: str | Path) -> SecretStr:
    """Load secret from file with proper permissions check."""
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Secret file not found: {path}")

    # Check file permissions (Unix only)
    if os.name == "posix":
        mode = path.stat().st_mode & 0o777
        if mode & 0o077:  # Check if group/other has any permissions
            raise PermissionError(
                f"Secret file {path} has unsafe permissions: {oct(mode)}. "
                "Run: chmod 600 {path}"
            )

    return SecretStr(path.read_text().strip())


# ============================================================
# USAGE
# ============================================================

if __name__ == "__main__":
    # Example .env file content:
    # SECURITY_JWT_SECRET_KEY=your-super-secret-key-at-least-32-chars
    # SECURITY_ENCRYPTION_KEY=another-secret-key-at-least-32-characters
    # SECURITY_DATABASE_URL=postgresql://user:pass@localhost/db
    # APP_ENVIRONMENT=development
    # APP_DEBUG=false

    # Load settings
    try:
        security = get_security_settings()
        app = get_app_settings()

        print(f"Environment: {app.environment}")
        print(f"Debug: {app.debug}")
        print(f"Allowed hosts: {security.allowed_hosts}")

        # SecretStr prevents accidental exposure
        print(f"JWT Key: {security.jwt_secret_key}")  # Shows: SecretStr('**********')

        # Access secret value explicitly when needed
        # jwt_key = security.jwt_secret_key.get_secret_value()

    except Exception as e:
        print(f"Configuration error: {e}")
```

**Key points**:
- SecretStr prevents accidental logging of secrets
- Validators enforce security requirements per environment
- File permissions checked for secret files
- Settings cached to avoid repeated parsing

---

## Common Patterns

### Pattern: Parameterized Queries (Prevent SQL Injection)
```python
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# SAFE: Parameterized query
async def get_user_safe(session: AsyncSession, user_id: str):
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

# SAFE: Named parameters with text()
async def search_users_safe(session: AsyncSession, query: str):
    stmt = text("SELECT * FROM users WHERE name LIKE :query")
    result = await session.execute(stmt, {"query": f"%{query}%"})
    return result.fetchall()

# DANGEROUS: String concatenation
# async def get_user_unsafe(session, user_id: str):
#     stmt = text(f"SELECT * FROM users WHERE id = '{user_id}'")  # NEVER DO THIS
```

### Pattern: Rate Limiting
```python
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import HTTPException, Request

class RateLimiter:
    def __init__(self, requests: int, window: timedelta):
        self.requests = requests
        self.window = window
        self.clients: dict[str, list[datetime]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = datetime.now()
        cutoff = now - self.window

        # Clean old requests
        self.clients[client_id] = [
            t for t in self.clients[client_id] if t > cutoff
        ]

        if len(self.clients[client_id]) >= self.requests:
            return False

        self.clients[client_id].append(now)
        return True

limiter = RateLimiter(requests=100, window=timedelta(minutes=1))

async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    return await call_next(request)
```

### Pattern: Content Security Policy
```python
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

app = FastAPI()
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["example.com"])
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Hardcoded secrets
DATABASE_URL = "postgresql://admin:password123@localhost/db"
API_KEY = "sk-1234567890abcdef"
```

**Do this instead:**
```python
# Environment variables with validation
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: PostgresDsn
    api_key: SecretStr

settings = Settings()  # Loads from environment
```

---

**Don't do this:**
```python
# Storing plaintext passwords
user.password = request.password  # NEVER!
```

**Do this instead:**
```python
# Hash passwords with Argon2
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["argon2"])
user.password_hash = pwd_context.hash(request.password)
```

---

**Don't do this:**
```python
# Exposing stack traces in production
@app.exception_handler(Exception)
async def handle_error(request, exc):
    return JSONResponse({"error": str(exc), "trace": traceback.format_exc()})
```

**Do this instead:**
```python
# Generic error messages in production
@app.exception_handler(Exception)
async def handle_error(request, exc):
    logger.exception("Unhandled error", request_id=request.state.request_id)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "request_id": request.state.request_id},
    )
```

---

## See Also

- [ci-cd-pipelines.md](ci-cd-pipelines.md) - Security scanning in CI
- [monitoring.md](monitoring.md) - Security logging
- [pydantic-validation.md](../web-apis/pydantic-validation.md) - Input validation
