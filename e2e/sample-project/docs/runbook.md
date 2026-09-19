# Runbook

## Start the service

Run `python -m inventory.api` from the `src` folder. The service listens on
port 8080 by default. Set `INVENTORY_PORT` to change the port.

## Stop the service

Send SIGTERM to the process. The service flushes the SQLite write buffer
before it exits.

## Reset the store

To reset the store, stop the service and delete the file `inventory.sqlite3`.
The service creates a new empty database on the next start. There is no
reset command in the API. Deletion is the only supported reset.

## Check health

Call `GET /health`. The response is `{"status": "ok"}` when the repository
answers within one second.
