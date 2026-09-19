"""Business rules. The API layer must not duplicate these."""

from inventory.models import Item
from inventory.repository import Repository


class OutOfStock(Exception):
    """Raised when a reservation exceeds the on-hand quantity."""


class InventoryService:
    """Stock rules on top of a repository."""

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def add_item(self, sku: str, name: str, on_hand: int = 0) -> Item:
        item = Item(sku=sku, name=name, on_hand=on_hand)
        self._repo.save(item)
        return item

    def reserve_stock(self, sku: str, quantity: int) -> Item:
        """Reserve quantity of sku.

        Raises:
            KeyError: The sku does not exist.
            OutOfStock: quantity exceeds on_hand. Nothing changes.
        """
        item = self._repo.get(sku)
        if item is None:
            raise KeyError(sku)
        if quantity > item.on_hand:
            raise OutOfStock(f"{sku}: requested {quantity}, on hand {item.on_hand}")
        item.on_hand -= quantity
        self._repo.save(item)
        return item

    def restock(self, sku: str, quantity: int) -> Item:
        """Add quantity to sku. Zero or negative quantity raises ValueError."""
        if quantity <= 0:
            raise ValueError("restock quantity must be positive")
        item = self._repo.get(sku)
        if item is None:
            raise KeyError(sku)
        item.on_hand += quantity
        self._repo.save(item)
        return item
