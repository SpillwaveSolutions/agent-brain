---
name: agent-brain-graph
description: Search using GraphRAG for relationship and dependency queries
parameters:
  - name: query
    description: The search query about relationships or dependencies
    required: true
  - name: traversal-depth
    description: How deep to traverse relationships (1-5)
    required: false
    default: 2
  - name: top-k
    description: Number of results to return (1-20)
    required: false
    default: 5
  - name: include-relationships
    description: Include relationship details in output
    required: false
    default: true
skills:
  - using-agent-brain
---

# Agent Brain Graph Search

## Purpose

Performs GraphRAG-powered search for relationship and dependency queries. This mode queries the knowledge graph to find entities (functions, classes, modules) and their relationships (calls, imports, inherits).

Graph search is ideal for:
- Finding what calls a specific function
- Exploring class inheritance hierarchies
- Understanding module dependencies
- Tracing data flow through code

## Usage

```
/agent-brain-graph <query> [--traversal-depth <n>] [--top-k <n>] [--include-relationships]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| query | Yes | - | The relationship or dependency query |
| --traversal-depth | No | 2 | How many relationship hops (1-5) |
| --top-k | No | 5 | Number of results (1-20) |
| --include-relationships | No | true | Show relationship details |

### Traversal Depth Guide

| Depth | Use Case | Example |
|-------|----------|---------|
| 1 | Direct relationships | "what directly calls X" |
| 2 | Two-hop relationships | "what calls functions that call X" |
| 3 | Complex chains | "trace the call chain to X" |
| 4-5 | Deep exploration | "full dependency tree" |

## Prerequisites

GraphRAG must be enabled before using graph search:

```bash
# Enable graph indexing
export ENABLE_GRAPH_INDEX=true

# Start server
agent-brain start --daemon

# Index with graph extraction
agent-brain index /path/to/code
```

### Check Graph Status

```bash
agent-brain status
# Look for: Graph Index: enabled (X entities, Y relationships)
```

## Execution

### Pre-flight Check

```bash
# Verify server is running and graph is enabled
agent-brain status
```

If graph index shows as disabled:
```bash
# Enable and restart
export ENABLE_GRAPH_INDEX=true
agent-brain stop
agent-brain start --daemon
agent-brain reset --yes
agent-brain index /path/to/code
```

### Search Command

```bash
agent-brain query "<query>" --mode graph --traversal-depth <depth> --top-k <k> --include-relationships
```

### Example Queries

```bash
# What calls a specific function
agent-brain query "what functions call process_payment" --mode graph

# Class inheritance
agent-brain query "classes that inherit from BaseService" --mode graph --traversal-depth 3

# Module dependencies
agent-brain query "modules that import authentication" --mode graph

# Find all callers (deep)
agent-brain query "complete call chain to validate_token" --mode graph --traversal-depth 4

# Relationship exploration
agent-brain query "dependencies of UserController" --mode graph --include-relationships
```

## Output

### Result Format

For each result, present:

1. **Entity**: The matched entity (function, class, module)
2. **Type**: Entity type (function, class, module, etc.)
3. **Relationships**: Connected entities and relationship types
4. **Source**: File path and location

### Example Output

```
## Graph Search Results for "what functions call process_payment"

### 1. process_payment (function in src/payments/processor.py)

**Callers (incoming):**
- checkout_handler() in src/api/checkout.py [CALLS]
- process_order() in src/orders/service.py [CALLS]
- handle_webhook() in src/webhooks/stripe.py [CALLS]

**Dependencies (outgoing):**
- validate_payment_method() in src/payments/validator.py [CALLS]
- charge_card() in src/payments/gateway.py [CALLS]
- log_transaction() in src/payments/logger.py [CALLS]

**File:** src/payments/processor.py:45-78

---

### 2. PaymentProcessor.process (method in src/payments/processor.py)

**Callers (incoming):**
- PaymentService.execute() in src/services/payment.py [CALLS]

**Inherits from:**
- BaseProcessor in src/payments/base.py [INHERITS]

**File:** src/payments/processor.py:120-145

---
Found 2 entities with relationships to "process_payment"
Graph traversal depth: 2
```

### Relationship Types

| Type | Description | Example |
|------|-------------|---------|
| CALLS | Function/method invocation | `A() CALLS B()` |
| IMPORTS | Module import | `module A IMPORTS module B` |
| INHERITS | Class inheritance | `ClassA INHERITS ClassB` |
| IMPLEMENTS | Interface implementation | `Class IMPLEMENTS Interface` |
| CONTAINS | Containment relationship | `Module CONTAINS Class` |
| USES | Variable/type usage | `Function USES Type` |

## Error Handling

### Graph Index Not Enabled

```
Error: Graph index is not enabled
```

**Resolution:**
```bash
export ENABLE_GRAPH_INDEX=true
agent-brain stop && agent-brain start --daemon
agent-brain reset --yes
agent-brain index /path/to/code
```

### No Graph Data

```
Warning: Graph index is empty. Index documents first.
```

**Resolution:**
```bash
agent-brain index /path/to/code
```

### Entity Not Found

```
No entities found matching "nonexistent_function"
```

**Resolution:**
- Verify the function/class name is correct
- Check if the file containing it was indexed
- Try a broader search term

### Server Not Running

```
Error: Could not connect to Agent Brain server
```

**Resolution:**
```bash
agent-brain start --daemon
```

## Performance Notes

| Metric | Typical Value |
|--------|---------------|
| Latency | 500-1200ms |
| Memory | Higher than BM25/vector (graph storage) |
| Best for | Relationship queries, dependency analysis |

### When to Use Graph vs Other Modes

| Query Type | Recommended Mode |
|------------|------------------|
| "what calls X" | Graph |
| "dependencies of X" | Graph |
| "classes that inherit from X" | Graph |
| "how does X work" | Vector or Hybrid |
| "find error message X" | BM25 |
| "complete implementation of X" | Multi |

## Related Commands

- `/agent-brain-multi` - Multi-mode search including graph
- `/agent-brain-hybrid` - Hybrid BM25 + semantic search
- `/agent-brain-search` - Default hybrid search
