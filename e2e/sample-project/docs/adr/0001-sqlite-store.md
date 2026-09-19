# ADR 0001: Use SQLite for the persistent store

## Status

Accepted

## Context

The service runs as a single process on one machine. Operators asked for a
store that survives restarts and needs no separate database server.

## Decision

Use SQLite instead of PostgreSQL. The whole store is one file named
`inventory.sqlite3` next to the process.

## Consequences

- No database server to install or operate.
- One writer at a time. This is acceptable for a single-node install.
- A move to PostgreSQL needs a new `Repository` implementation and nothing
  else, because the service layer depends only on the repository contract.
