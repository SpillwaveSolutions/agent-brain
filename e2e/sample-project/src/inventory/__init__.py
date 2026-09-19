"""Inventory service fixture for Agent Brain integration tests."""

from inventory.models import Item
from inventory.service import InventoryService, OutOfStock

__all__ = ["Item", "InventoryService", "OutOfStock"]
