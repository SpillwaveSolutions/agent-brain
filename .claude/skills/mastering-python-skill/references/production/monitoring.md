# Monitoring and Observability

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Structured Logging](#example-1-structured-logging)
  - [Example 2: Prometheus Metrics](#example-2-prometheus-metrics)
  - [Example 3: OpenTelemetry Distributed Tracing](#example-3-opentelemetry-distributed-tracing)
  - [Example 4: FastAPI Observability Integration](#example-4-fastapi-observability-integration)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code |
|------|------|
| Structured log | `structlog.get_logger().info("event", user_id=123)` |
| Counter metric | `requests_total.labels(method="GET").inc()` |
| Histogram | `request_duration.observe(elapsed_time)` |
| Create span | `with tracer.start_as_current_span("op"):` |
| Add span attribute | `span.set_attribute("user.id", user_id)` |
| Record exception | `span.record_exception(e)` |

---

## Core Concepts

The **Three Pillars of Observability**:

| Pillar | Purpose | Tools |
|--------|---------|-------|
| **Logs** | Discrete events, debugging | structlog, Python logging |
| **Metrics** | Aggregated measurements, alerting | Prometheus, StatsD |
| **Traces** | Request flow across services | OpenTelemetry, Jaeger |

**Key Principles**:
- **Logs** tell you *what* happened
- **Metrics** tell you *how much* and *how often*
- **Traces** tell you *where* time was spent

**Metric Types**:
| Type | Use Case | Example |
|------|----------|---------|
| Counter | Cumulative values | Total requests, errors |
| Gauge | Point-in-time values | Active connections, queue size |
| Histogram | Distributions | Request latency, response sizes |
| Summary | Percentiles | P50, P95, P99 latencies |

---

## Production Examples

### Example 1: Structured Logging

**Use case**: Production-ready logging with JSON output and context propagation.

```python
#!/usr/bin/env python3
"""Structured logging configuration with structlog."""

import logging
import sys
from typing import Any

import structlog


def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
    add_timestamp: bool = True,
) -> None:
    """Configure structured logging for production use.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: Output JSON format (True for production)
        add_timestamp: Add ISO timestamp to logs
    """
    # Shared processors for all loggers
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso") if add_timestamp else lambda *a, **k: None,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        # Production: JSON format
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: colored console output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )


# Create logger
logger = structlog.get_logger()


def process_order(order_id: str, user_id: int, amount: float) -> dict[str, Any]:
    """Process an order with comprehensive logging."""
    # Bind context that persists across log calls
    log = logger.bind(order_id=order_id, user_id=user_id)

    log.info("order_processing_started", amount=amount)

    try:
        # Simulate processing
        if amount <= 0:
            raise ValueError("Invalid amount")

        result = {"status": "completed", "transaction_id": "txn_123"}

        log.info(
            "order_processing_completed",
            transaction_id=result["transaction_id"],
            amount=amount,
        )
        return result

    except Exception as e:
        log.exception(
            "order_processing_failed",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise


# Context variables for request-scoped data
def set_request_context(request_id: str, user_id: int | None = None) -> None:
    """Set request context that appears in all subsequent logs."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        user_id=user_id,
    )


if __name__ == "__main__":
    # Development mode
    configure_logging(level="DEBUG", json_output=False)

    # Set request context
    set_request_context(request_id="req-abc-123", user_id=42)

    # All logs now include request_id and user_id
    logger.info("application_started", version="1.0.0")
    process_order("order-456", user_id=42, amount=99.99)
```

**Output (JSON mode)**:
```json
{"request_id": "req-abc-123", "user_id": 42, "event": "order_processing_started", "order_id": "order-456", "amount": 99.99, "level": "info", "timestamp": "2024-01-15T10:30:00Z"}
```

**Key points**:
- Context variables propagate through async code
- JSON format enables log aggregation (ELK, CloudWatch)
- Structured data enables querying and alerting

---

### Example 2: Prometheus Metrics

**Use case**: Expose application metrics for Prometheus scraping.

```python
#!/usr/bin/env python3
"""Prometheus metrics for Python applications."""

import random
import time
from contextlib import contextmanager
from typing import Iterator

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    start_http_server,
    CONTENT_TYPE_LATEST,
)


# ============================================================
# METRIC DEFINITIONS
# ============================================================

# Counter: cumulative, only increases
requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

# Gauge: can go up or down
active_connections = Gauge(
    "active_connections",
    "Number of active connections",
)

in_progress_requests = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently in progress",
    ["method"],
)

# Histogram: distribution of values
request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Info: static key-value pairs
app_info = Info(
    "app",
    "Application information",
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

@contextmanager
def track_request_duration(method: str, endpoint: str) -> Iterator[None]:
    """Context manager to track request duration."""
    start_time = time.perf_counter()
    in_progress_requests.labels(method=method).inc()

    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        in_progress_requests.labels(method=method).dec()


def record_request(method: str, endpoint: str, status: int) -> None:
    """Record a completed request."""
    requests_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()


# ============================================================
# BUSINESS METRICS
# ============================================================

orders_processed = Counter(
    "orders_processed_total",
    "Total orders processed",
    ["status", "payment_method"],
)

order_value = Histogram(
    "order_value_dollars",
    "Order values in dollars",
    buckets=[10, 25, 50, 100, 250, 500, 1000, 5000],
)

inventory_level = Gauge(
    "inventory_level",
    "Current inventory level",
    ["product_id", "warehouse"],
)


def process_order(order_id: str, amount: float, payment_method: str) -> None:
    """Process order and record metrics."""
    try:
        # Business logic here
        orders_processed.labels(status="success", payment_method=payment_method).inc()
        order_value.observe(amount)
    except Exception:
        orders_processed.labels(status="failure", payment_method=payment_method).inc()
        raise


# ============================================================
# METRICS ENDPOINT
# ============================================================

def get_metrics() -> bytes:
    """Generate metrics in Prometheus format."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get content type for metrics response."""
    return CONTENT_TYPE_LATEST


# FastAPI integration
def create_metrics_endpoint():
    """Create FastAPI metrics endpoint."""
    from fastapi import FastAPI, Response

    app = FastAPI()

    @app.get("/metrics")
    def metrics():
        return Response(
            content=get_metrics(),
            media_type=get_metrics_content_type(),
        )

    return app


if __name__ == "__main__":
    # Set static info
    app_info.info({
        "version": "1.0.0",
        "environment": "production",
    })

    # Start metrics server on port 8000
    start_http_server(8000)
    print("Metrics server started on :8000/metrics")

    # Simulate activity
    while True:
        with track_request_duration("GET", "/api/orders"):
            time.sleep(random.uniform(0.01, 0.5))

        record_request("GET", "/api/orders", status=200)
        active_connections.set(random.randint(10, 100))
        time.sleep(0.1)
```

**Prometheus scrape config**:
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'python-app'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 15s
```

**Key points**:
- Use labels for dimensionality (method, endpoint, status)
- Choose appropriate metric types (counter vs gauge vs histogram)
- Buckets should match expected value distributions

---

### Example 3: OpenTelemetry Distributed Tracing

**Use case**: Trace requests across microservices with OpenTelemetry.

```python
#!/usr/bin/env python3
"""OpenTelemetry distributed tracing setup."""

from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode


def configure_tracing(
    service_name: str,
    service_version: str = "1.0.0",
    otlp_endpoint: str | None = None,
    console_export: bool = False,
) -> trace.Tracer:
    """Configure OpenTelemetry tracing.

    Args:
        service_name: Name of this service
        service_version: Version of this service
        otlp_endpoint: OTLP collector endpoint (e.g., "localhost:4317")
        console_export: Also export to console (for debugging)

    Returns:
        Configured tracer
    """
    # Resource identifies this service
    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
        "deployment.environment": "production",
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add OTLP exporter if endpoint provided
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Add console exporter for debugging
    if console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Auto-instrument common libraries
    RequestsInstrumentor().instrument()
    # SQLAlchemyInstrumentor().instrument()  # If using SQLAlchemy

    return trace.get_tracer(service_name)


# ============================================================
# TRACING HELPERS
# ============================================================

def get_tracer(name: str = __name__) -> trace.Tracer:
    """Get a tracer instance."""
    return trace.get_tracer(name)


class TracingContext:
    """Context manager for tracing operations."""

    def __init__(
        self,
        operation_name: str,
        attributes: dict[str, Any] | None = None,
        tracer: trace.Tracer | None = None,
    ):
        self.operation_name = operation_name
        self.attributes = attributes or {}
        self.tracer = tracer or get_tracer()
        self.span: trace.Span | None = None

    def __enter__(self) -> trace.Span:
        self.span = self.tracer.start_span(self.operation_name)
        self.span.__enter__()

        for key, value in self.attributes.items():
            self.span.set_attribute(key, value)

        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self.span.record_exception(exc_val)
            self.span.set_status(Status(StatusCode.ERROR, str(exc_val)))
        else:
            self.span.set_status(Status(StatusCode.OK))

        self.span.__exit__(exc_type, exc_val, exc_tb)
        return False


# ============================================================
# USAGE EXAMPLE
# ============================================================

def process_order(order_id: str, items: list[dict]) -> dict[str, Any]:
    """Process an order with distributed tracing."""
    tracer = get_tracer()

    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("order.item_count", len(items))

        # Validate order
        with tracer.start_as_current_span("validate_order") as validate_span:
            validate_span.set_attribute("validation.type", "schema")
            # Validation logic
            is_valid = True
            validate_span.set_attribute("validation.result", is_valid)

        # Check inventory (might call another service)
        with tracer.start_as_current_span("check_inventory") as inv_span:
            inv_span.set_attribute("inventory.items_checked", len(items))
            # Inventory check logic
            available = True
            inv_span.set_attribute("inventory.all_available", available)

        # Process payment (might call external API)
        with tracer.start_as_current_span("process_payment") as payment_span:
            payment_span.set_attribute("payment.method", "credit_card")
            try:
                # Payment logic
                transaction_id = "txn_12345"
                payment_span.set_attribute("payment.transaction_id", transaction_id)
            except Exception as e:
                payment_span.record_exception(e)
                payment_span.set_status(Status(StatusCode.ERROR))
                raise

        # Add event for audit
        span.add_event(
            "order_completed",
            attributes={"transaction_id": transaction_id},
        )

        return {
            "order_id": order_id,
            "status": "completed",
            "transaction_id": transaction_id,
        }


if __name__ == "__main__":
    # Configure tracing
    tracer = configure_tracing(
        service_name="order-service",
        service_version="1.0.0",
        console_export=True,  # Print spans to console
    )

    # Process a sample order
    result = process_order(
        order_id="order-123",
        items=[{"sku": "ITEM-1", "qty": 2}],
    )
    print(f"Result: {result}")
```

**Key points**:
- Spans create parent-child relationships automatically
- Attributes provide searchable context
- Events mark points in time within a span
- Exceptions are recorded with stack traces

---

### Example 4: FastAPI Observability Integration

**Use case**: Complete observability setup for a FastAPI application.

```python
#!/usr/bin/env python3
"""FastAPI with complete observability: logs, metrics, traces."""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# ============================================================
# CONFIGURATION
# ============================================================

# Structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()

# Prometheus metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Tracer
tracer = trace.get_tracer(__name__)


# ============================================================
# MIDDLEWARE
# ============================================================

async def observability_middleware(request: Request, call_next) -> Response:
    """Middleware that adds logging, metrics, and trace context."""
    # Generate request ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Set logging context
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    # Start timing
    start_time = time.perf_counter()

    # Log request
    logger.info("request_started", client_ip=request.client.host if request.client else None)

    try:
        response = await call_next(request)

        # Calculate duration
        duration = time.perf_counter() - start_time

        # Record metrics
        endpoint = request.url.path
        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code,
        ).inc()
        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)

        # Log response
        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response

    except Exception as e:
        duration = time.perf_counter() - start_time

        logger.exception(
            "request_failed",
            error_type=type(e).__name__,
            duration_ms=round(duration * 1000, 2),
        )

        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=500,
        ).inc()

        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "request_id": request_id},
        )


# ============================================================
# APPLICATION
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    logger.info("application_starting", version="1.0.0")
    yield
    logger.info("application_shutting_down")


app = FastAPI(
    title="Observable API",
    version="1.0.0",
    lifespan=lifespan,
)

# Add middleware
app.middleware("http")(observability_middleware)

# Instrument with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/api/orders/{order_id}")
async def get_order(order_id: str) -> dict[str, Any]:
    """Get order by ID with tracing."""
    with tracer.start_as_current_span("get_order") as span:
        span.set_attribute("order.id", order_id)

        # Simulate database lookup
        log = logger.bind(order_id=order_id)
        log.info("fetching_order")

        # Your business logic here
        order = {
            "id": order_id,
            "status": "completed",
            "total": 99.99,
        }

        span.set_attribute("order.status", order["status"])
        return order


@app.post("/api/orders")
async def create_order(request: Request) -> dict[str, Any]:
    """Create new order with full observability."""
    body = await request.json()

    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("order.item_count", len(body.get("items", [])))

        log = logger.bind(item_count=len(body.get("items", [])))
        log.info("creating_order")

        # Your business logic here
        order_id = str(uuid.uuid4())

        span.set_attribute("order.id", order_id)
        log.info("order_created", order_id=order_id)

        return {"id": order_id, "status": "created"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Key points**:
- Middleware captures all requests consistently
- Request ID propagates through logs and headers
- Metrics exposed at `/metrics` for Prometheus
- Auto-instrumentation adds spans for all endpoints

---

## Common Patterns

### Pattern: Custom Metric Decorator
```python
from functools import wraps
from prometheus_client import Histogram
import time

operation_duration = Histogram(
    "operation_duration_seconds",
    "Duration of operations",
    ["operation"],
)

def timed(operation_name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                operation_duration.labels(operation=operation_name).observe(duration)
        return wrapper
    return decorator

@timed("process_payment")
def process_payment(amount: float) -> str:
    # Implementation
    return "success"
```

### Pattern: Trace Context Propagation
```python
from opentelemetry import trace
from opentelemetry.propagate import inject, extract

def call_downstream_service(url: str, data: dict) -> dict:
    """Call another service with trace context."""
    headers = {}
    inject(headers)  # Adds traceparent header

    response = requests.post(url, json=data, headers=headers)
    return response.json()

def handle_incoming_request(headers: dict) -> None:
    """Extract trace context from incoming request."""
    context = extract(headers)
    with trace.get_tracer(__name__).start_as_current_span(
        "handle_request",
        context=context,
    ):
        # Processing with linked trace
        pass
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# High-cardinality labels cause metric explosion
requests_total.labels(
    user_id=user.id,  # Millions of users = millions of metrics!
    endpoint=path,
).inc()
```

**Do this instead:**
```python
# Use bounded labels
requests_total.labels(
    user_tier=user.tier,  # "free", "pro", "enterprise"
    endpoint=path,
).inc()

# Track user-specific data in traces/logs instead
span.set_attribute("user.id", user.id)
```

---

**Don't do this:**
```python
# Logging sensitive data
logger.info("user_login", password=password, credit_card=card)
```

**Do this instead:**
```python
# Redact sensitive fields
logger.info("user_login", user_id=user.id, card_last_four=card[-4:])
```

---

## See Also

- [ci-cd-pipelines.md](ci-cd-pipelines.md) - Deployment pipelines
- [security.md](security.md) - Security logging
- [fastapi-patterns.md](../web-apis/fastapi-patterns.md) - FastAPI setup
