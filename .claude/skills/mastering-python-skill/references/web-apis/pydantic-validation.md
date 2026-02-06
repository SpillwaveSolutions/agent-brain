# Pydantic Validation and Data Modeling

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Model Definition and Validation](#example-1-model-definition-and-validation)
  - [Example 2: Custom Validators and Field Types](#example-2-custom-validators-and-field-types)
  - [Example 3: Settings Management with pydantic-settings](#example-3-settings-management-with-pydantic-settings)
  - [Example 4: Nested Models and Discriminated Unions](#example-4-nested-models-and-discriminated-unions)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code |
|------|------|
| Define model | `class User(BaseModel): name: str` |
| Optional field | `email: str \| None = None` |
| Field constraint | `age: int = Field(ge=0, le=150)` |
| Custom validator | `@field_validator("email")` |
| Model validator | `@model_validator(mode="after")` |
| From dict | `User.model_validate(data)` |
| To dict | `user.model_dump()` |
| From ORM | `User.model_validate(orm_obj)` |
| JSON schema | `User.model_json_schema()` |
| Strict mode | `model_config = ConfigDict(strict=True)` |

---

## Core Concepts

Pydantic is Python's most popular data validation library, leveraging type hints for:

- **Runtime Validation**: Validate data at runtime, catching errors early
- **Type Coercion**: Automatically convert compatible types (e.g., `"123"` → `123`)
- **Serialization**: Convert models to/from JSON, dicts, and other formats
- **Schema Generation**: Auto-generate JSON Schema for API documentation

Pydantic v2 (2023+) was rewritten in Rust for 5-50x performance improvement while maintaining Python API compatibility.

---

## Production Examples

### Example 1: Model Definition and Validation

**Use case**: Define data models with automatic validation and documentation.

```python
#!/usr/bin/env python3
"""Basic Pydantic model definition and validation."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, EmailStr


class UserRole(str, Enum):
    """User role enumeration."""

    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class Address(BaseModel):
    """Nested address model."""

    street: str
    city: str
    country: str = "USA"
    postal_code: str = Field(..., pattern=r"^\d{5}(-\d{4})?$")


class UserCreate(BaseModel):
    """Schema for creating a user."""

    # Required fields
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Alphanumeric username",
    )
    email: EmailStr  # Built-in email validation
    password: str = Field(..., min_length=8)

    # Optional fields with defaults
    full_name: str | None = None
    role: UserRole = UserRole.USER
    age: int | None = Field(None, ge=0, le=150)
    tags: list[str] = Field(default_factory=list)
    address: Address | None = None

    # Model configuration
    model_config = ConfigDict(
        str_strip_whitespace=True,  # Strip whitespace from strings
        validate_default=True,  # Validate default values
        extra="forbid",  # Raise error on extra fields
    )


class UserResponse(BaseModel):
    """Schema for user responses (excludes password)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str | None
    role: UserRole
    created_at: datetime
    is_active: bool = True


# Usage examples
def main():
    # Valid data - automatic validation
    user_data = {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "securepassword123",
        "full_name": "John Doe",
        "age": 30,
        "address": {
            "street": "123 Main St",
            "city": "New York",
            "postal_code": "10001",
        },
    }
    user = UserCreate.model_validate(user_data)
    print(f"Created user: {user.username}")

    # Type coercion - "30" becomes 30
    user2 = UserCreate(
        username="jane_doe",
        email="jane@example.com",
        password="anotherpassword",
        age="30",  # String coerced to int
    )
    print(f"Age type: {type(user2.age)}")  # <class 'int'>

    # Serialization
    user_dict = user.model_dump(exclude={"password"})
    user_json = user.model_dump_json(indent=2)

    # Validation errors
    try:
        bad_user = UserCreate(
            username="ab",  # Too short
            email="not-an-email",  # Invalid email
            password="short",  # Too short
        )
    except ValidationError as e:
        print(f"Validation errors: {e.error_count()}")
        for error in e.errors():
            print(f"  - {error['loc']}: {error['msg']}")


if __name__ == "__main__":
    main()
```

**Key points**:
- Use `Field()` for constraints, defaults, and documentation
- `ConfigDict` controls model behavior (strict mode, extra fields, etc.)
- `model_validate()` creates from dict, `model_dump()` exports to dict
- Validation errors provide detailed location and message info

---

### Example 2: Custom Validators and Field Types

**Use case**: Implement complex validation logic and custom types.

```python
#!/usr/bin/env python3
"""Custom validators and computed fields."""

from datetime import date, datetime
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    Field,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)


# Custom type with Annotated
PositiveInt = Annotated[int, Field(gt=0)]
Percentage = Annotated[float, Field(ge=0, le=100)]


class Product(BaseModel):
    """Product with custom validation."""

    name: str
    sku: str
    price: PositiveInt
    discount_percent: Percentage = 0
    quantity: int = Field(ge=0)
    tags: list[str] = Field(default_factory=list)

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        """Validate SKU format: ABC-12345."""
        import re
        if not re.match(r"^[A-Z]{3}-\d{5}$", v.upper()):
            raise ValueError("SKU must be format ABC-12345")
        return v.upper()

    @field_validator("tags", mode="before")
    @classmethod
    def split_tags(cls, v: Any) -> list[str]:
        """Accept comma-separated string or list."""
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(",") if tag.strip()]
        return v

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        """Clean and validate product name."""
        cleaned = " ".join(v.split())  # Normalize whitespace
        if len(cleaned) < 2:
            raise ValueError("Name must be at least 2 characters")
        return cleaned.title()

    @computed_field
    @property
    def discounted_price(self) -> int:
        """Calculate discounted price."""
        return int(self.price * (1 - self.discount_percent / 100))

    @field_serializer("price", "discounted_price")
    def format_price(self, v: int) -> str:
        """Format price as currency string."""
        return f"${v / 100:.2f}"


class DateRange(BaseModel):
    """Date range with cross-field validation."""

    start_date: date
    end_date: date
    description: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        """Ensure end_date is after start_date."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self

    @computed_field
    @property
    def duration_days(self) -> int:
        """Calculate duration in days."""
        return (self.end_date - self.start_date).days


class Order(BaseModel):
    """Order with model-level validation."""

    order_id: str
    customer_email: str
    items: list[Product]
    shipping_address: str
    billing_address: str | None = None
    use_shipping_for_billing: bool = True

    @model_validator(mode="before")
    @classmethod
    def set_billing_address(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Pre-validation: copy shipping to billing if needed."""
        if data.get("use_shipping_for_billing") and not data.get("billing_address"):
            data["billing_address"] = data.get("shipping_address")
        return data

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        """Post-validation: ensure order is valid."""
        if not self.items:
            raise ValueError("Order must have at least one item")
        if self.total_amount > 10000_00:  # $10,000 in cents
            raise ValueError("Order exceeds maximum amount")
        return self

    @computed_field
    @property
    def total_amount(self) -> int:
        """Calculate order total in cents."""
        return sum(item.discounted_price * item.quantity for item in self.items)

    @computed_field
    @property
    def item_count(self) -> int:
        """Total number of items."""
        return sum(item.quantity for item in self.items)


# Usage
def main():
    # Product with custom validation
    product = Product(
        name="  wireless   mouse  ",  # Normalized to "Wireless Mouse"
        sku="abc-12345",  # Uppercased to "ABC-12345"
        price=2999,  # $29.99 in cents
        discount_percent=10,
        tags="electronics, computer, peripherals",  # Split to list
    )
    print(f"Product: {product.name}")
    print(f"SKU: {product.sku}")
    print(f"Price: {product.price}")  # Serialized as "$29.99"
    print(f"Discounted: {product.discounted_price}")  # Computed

    # Date range validation
    try:
        invalid_range = DateRange(
            start_date=date(2024, 12, 31),
            end_date=date(2024, 1, 1),  # Before start!
        )
    except ValidationError as e:
        print(f"Date error: {e.errors()[0]['msg']}")


if __name__ == "__main__":
    main()
```

**Key points**:
- `@field_validator` validates individual fields (use `mode="before"` for pre-processing)
- `@model_validator` validates relationships between fields
- `@computed_field` creates derived fields included in serialization
- `@field_serializer` customizes output format
- Use `Annotated` to create reusable custom types

---

### Example 3: Settings Management with pydantic-settings

**Use case**: Load configuration from environment variables with validation.

```python
#!/usr/bin/env python3
"""Configuration management with pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DB_",  # DB_HOST, DB_PORT, etc.
    )

    host: str = "localhost"
    port: int = 5432
    name: str = Field(..., alias="database")  # DB_DATABASE
    user: str
    password: SecretStr  # Masked in logs/repr

    @property
    def url(self) -> str:
        """Build database URL."""
        return (
            f"postgresql+asyncpg://{self.user}:"
            f"{self.password.get_secret_value()}@"
            f"{self.host}:{self.port}/{self.name}"
        )


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: SecretStr | None = None

    @property
    def url(self) -> str:
        """Build Redis URL."""
        auth = f":{self.password.get_secret_value()}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class Settings(BaseSettings):
    """Application settings with nested configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # APP__DEBUG for nested
        extra="ignore",
    )

    # Application settings
    app_name: str = "My Application"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"
    secret_key: SecretStr
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]

    # API settings
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Nested settings
    database: DatabaseSettings
    redis: RedisSettings | None = None

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v):
        """Parse comma-separated hosts."""
        if isinstance(v, str):
            return [h.strip() for h in v.split(",")]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse comma-separated origins."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"


# Singleton pattern with caching
@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Example .env file content:
"""
# Application
APP_NAME="My Production App"
DEBUG=false
ENVIRONMENT=production
SECRET_KEY=super-secret-key-here
ALLOWED_HOSTS=api.example.com,www.example.com

# Database (nested with prefix)
DB_HOST=db.example.com
DB_PORT=5432
DB_DATABASE=myapp
DB_USER=myapp_user
DB_PASSWORD=db-password-here

# Redis
REDIS_HOST=redis.example.com
REDIS_PORT=6379
REDIS_PASSWORD=redis-password

# Logging
LOG_LEVEL=INFO
"""


# Usage in FastAPI
def main():
    settings = get_settings()

    print(f"App: {settings.app_name}")
    print(f"Environment: {settings.environment}")
    print(f"Debug: {settings.debug}")

    # SecretStr is masked in output
    print(f"Secret Key: {settings.secret_key}")  # Shows "**********"

    # Access the actual value when needed
    actual_secret = settings.secret_key.get_secret_value()

    # Database URL (password exposed only when needed)
    print(f"DB URL: {settings.database.url}")

    # Production check
    if settings.is_production():
        print("Running in production mode")


if __name__ == "__main__":
    main()
```

**Key points**:
- `pydantic-settings` loads from environment variables and `.env` files
- `SecretStr` masks sensitive values in logs and repr
- Use `env_prefix` for namespaced environment variables
- `@lru_cache` ensures settings are loaded once
- Nested settings allow organized configuration groups

---

### Example 4: Nested Models and Discriminated Unions

**Use case**: Handle complex data structures with polymorphic types.

```python
#!/usr/bin/env python3
"""Nested models and discriminated unions."""

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


# Discriminated union for payment methods
class CreditCardPayment(BaseModel):
    """Credit card payment details."""

    type: Literal["credit_card"] = "credit_card"
    card_last_four: str = Field(..., pattern=r"^\d{4}$")
    card_brand: Literal["visa", "mastercard", "amex"]
    exp_month: int = Field(..., ge=1, le=12)
    exp_year: int = Field(..., ge=2024)


class BankTransferPayment(BaseModel):
    """Bank transfer payment details."""

    type: Literal["bank_transfer"] = "bank_transfer"
    bank_name: str
    account_last_four: str = Field(..., pattern=r"^\d{4}$")
    routing_number: str


class CryptoPayment(BaseModel):
    """Cryptocurrency payment details."""

    type: Literal["crypto"] = "crypto"
    currency: Literal["BTC", "ETH", "USDC"]
    wallet_address: str
    network: str


# Discriminated union - Pydantic uses 'type' field to determine model
PaymentMethod = Annotated[
    Union[CreditCardPayment, BankTransferPayment, CryptoPayment],
    Field(discriminator="type"),
]


# Nested model structure
class LineItem(BaseModel):
    """Order line item."""

    product_id: str
    name: str
    quantity: int = Field(..., ge=1)
    unit_price: int  # cents
    discount: int = 0

    @property
    def total(self) -> int:
        """Calculate line total."""
        return (self.unit_price - self.discount) * self.quantity


class ShippingAddress(BaseModel):
    """Shipping address."""

    recipient_name: str
    street_line_1: str
    street_line_2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str = "US"
    phone: str | None = None


class OrderStatus(BaseModel):
    """Order status tracking."""

    status: Literal["pending", "processing", "shipped", "delivered", "cancelled"]
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    notes: str | None = None


class Order(BaseModel):
    """Complete order with nested structures."""

    model_config = ConfigDict(from_attributes=True)

    order_id: str
    customer_id: str
    items: list[LineItem]
    shipping_address: ShippingAddress
    billing_address: ShippingAddress | None = None
    payment: PaymentMethod
    status_history: list[OrderStatus] = Field(default_factory=list)

    @property
    def subtotal(self) -> int:
        """Calculate order subtotal."""
        return sum(item.total for item in self.items)

    @property
    def current_status(self) -> str:
        """Get current order status."""
        if self.status_history:
            return self.status_history[-1].status
        return "pending"


# API response with generic wrapper
class ApiResponse[T](BaseModel):
    """Generic API response wrapper."""

    success: bool = True
    data: T
    meta: dict | None = None


class PaginatedResponse[T](BaseModel):
    """Paginated API response."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        """Check if there are previous pages."""
        return self.page > 1


# Usage
def main():
    # Create order with credit card payment
    order_data = {
        "order_id": "ORD-12345",
        "customer_id": "CUST-001",
        "items": [
            {
                "product_id": "PROD-001",
                "name": "Wireless Mouse",
                "quantity": 2,
                "unit_price": 2999,
            },
            {
                "product_id": "PROD-002",
                "name": "USB Cable",
                "quantity": 1,
                "unit_price": 999,
                "discount": 100,
            },
        ],
        "shipping_address": {
            "recipient_name": "John Doe",
            "street_line_1": "123 Main St",
            "city": "New York",
            "state": "NY",
            "postal_code": "10001",
        },
        "payment": {
            "type": "credit_card",  # Discriminator field
            "card_last_four": "4242",
            "card_brand": "visa",
            "exp_month": 12,
            "exp_year": 2025,
        },
    }

    order = Order.model_validate(order_data)
    print(f"Order: {order.order_id}")
    print(f"Subtotal: ${order.subtotal / 100:.2f}")
    print(f"Payment type: {order.payment.type}")

    # Discriminated union picks correct type
    if isinstance(order.payment, CreditCardPayment):
        print(f"Card: {order.payment.card_brand} ****{order.payment.card_last_four}")

    # Create with bank transfer instead
    bank_order_data = order_data.copy()
    bank_order_data["payment"] = {
        "type": "bank_transfer",
        "bank_name": "Chase",
        "account_last_four": "1234",
        "routing_number": "021000021",
    }

    bank_order = Order.model_validate(bank_order_data)
    print(f"Bank payment: {bank_order.payment.type}")

    # Generic response wrapper
    response = ApiResponse[Order](
        data=order,
        meta={"generated_at": datetime.utcnow().isoformat()},
    )
    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
```

**Key points**:
- Use `Literal` with `discriminator` for type-safe unions
- Pydantic automatically selects correct model based on discriminator field
- Generic models (`ApiResponse[T]`) create reusable wrappers
- Nested models validate at all levels automatically

---

## Common Patterns

### Pattern: Partial Update Model
```python
from pydantic import BaseModel

def create_partial_model(model: type[BaseModel]) -> type[BaseModel]:
    """Create a model where all fields are optional."""
    return create_model(
        f"Partial{model.__name__}",
        **{
            name: (field.annotation | None, None)
            for name, field in model.model_fields.items()
        },
    )
```

### Pattern: Immutable Models
```python
class ImmutableUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str

user = ImmutableUser(id=1, name="Alice")
# user.name = "Bob"  # Raises error - model is frozen
```

### Pattern: JSON Schema Customization
```python
class CustomSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"name": "Alice", "age": 30}
            ]
        }
    )
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Mutable default argument
class Bad(BaseModel):
    items: list = []  # Shared between instances!
```

**Do this instead:**
```python
class Good(BaseModel):
    items: list = Field(default_factory=list)  # Fresh list per instance
```

---

**Don't do this:**
```python
# Forgetting from_attributes for ORM
class UserResponse(BaseModel):
    id: int
    name: str

user_orm = session.query(User).first()
UserResponse.model_validate(user_orm)  # Fails!
```

**Do this instead:**
```python
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str

UserResponse.model_validate(user_orm)  # Works!
```

---

## See Also

- [type-systems.md](../foundations/type-systems.md) - Python type hints
- [fastapi-patterns.md](fastapi-patterns.md) - Using Pydantic with FastAPI
- [database-access.md](database-access.md) - Pydantic with SQLAlchemy
