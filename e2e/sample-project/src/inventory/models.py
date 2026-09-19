"""Domain models."""

from dataclasses import dataclass


@dataclass
class Item:
    """One stock keeping unit.

    Attributes:
        sku: Unique product code.
        name: Display name.
        on_hand: Quantity in the warehouse.
    """

    sku: str
    name: str
    on_hand: int = 0
