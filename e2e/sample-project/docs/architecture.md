# Architecture

The inventory service has three layers. Each layer calls only the layer
below it.

| Layer | Module | Responsibility |
| --- | --- | --- |
| API | `src/inventory/api.py` | Parse requests, call the service, shape responses |
| Service | `src/inventory/service.py` | Business rules such as stock reservation |
| Repository | `src/inventory/repository.py` | Persist items in memory or in SQLite |

## Stock reservation rule

`InventoryService.reserve_stock` checks the on-hand quantity before it
reserves. If the requested quantity exceeds the on-hand quantity, the service
raises `OutOfStock` and changes nothing. Partial reservations are not allowed.

## Restock rule

`InventoryService.restock` adds quantity to an item. A restock of zero or a
negative quantity raises `ValueError`.

## Repository contract

Both repositories implement `get`, `save`, and `list_all`. The SQLite
repository stores items in one table named `items` with columns `sku`,
`name`, and `on_hand`.
