import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from inventory.repository import InMemoryRepository  # noqa: E402
from inventory.service import InventoryService, OutOfStock  # noqa: E402


def make_service() -> InventoryService:
    svc = InventoryService(InMemoryRepository())
    svc.add_item("A1", "Widget", on_hand=5)
    return svc


def test_reserve_within_stock() -> None:
    assert make_service().reserve_stock("A1", 3).on_hand == 2


def test_reserve_over_stock_raises_and_changes_nothing() -> None:
    svc = make_service()
    with pytest.raises(OutOfStock):
        svc.reserve_stock("A1", 6)
    assert svc.reserve_stock("A1", 0).on_hand == 5


def test_restock_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        make_service().restock("A1", 0)
