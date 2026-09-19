"""HTTP-style handlers. Thin wrappers that call the service."""

from inventory.repository import SqliteRepository
from inventory.service import InventoryService, OutOfStock

service = InventoryService(SqliteRepository())


def health() -> dict[str, str]:
    """GET /health."""
    return {"status": "ok"}


def reserve(sku: str, quantity: int) -> tuple[int, dict[str, object]]:
    """POST /items/{sku}/reserve. Returns (status, body)."""
    try:
        item = service.reserve_stock(sku, quantity)
    except KeyError:
        return 404, {"error": "unknown sku"}
    except OutOfStock as exc:
        return 409, {"error": str(exc)}
    return 200, {"sku": item.sku, "on_hand": item.on_hand}


def restock(sku: str, quantity: int) -> tuple[int, dict[str, object]]:
    """POST /items/{sku}/restock."""
    try:
        item = service.restock(sku, quantity)
    except (KeyError, ValueError) as exc:
        return 400, {"error": str(exc)}
    return 200, {"sku": item.sku, "on_hand": item.on_hand}
