---
created: 2026-03-19T05:03:29.874Z
title: Fix indexing jobs failing with Broken pipe under concurrent Ollama load
area: tooling
files:
  - agent-brain-server/agent_brain_server/services/indexing_service.py
  - agent-brain-server/agent_brain_server/api/routers/
---

## Problem

When 4 indexing jobs are queued and run concurrently (or even sequentially with Ollama still busy),
all jobs fail at exactly 50% progress with `[Errno 32] Broken pipe`. Despite the failure, all data
is actually queryable — the chunks were indexed successfully. This means the Broken pipe hits the
**job status reporting mechanism** (HTTP connection back to client), not the embedding pipeline.

Observed behavior:
- 4 jobs started: agent-brain source, rulez_plugin, agent-memory, articles/
- All 4 reported FAILED at ~50% with Broken pipe
- After "failure": 34,439 chunks indexed, all 4 sources return real search results
- Server is HEALTHY/IDLE after all jobs report FAILED
- `agent-brain jobs <job_id>` fails with traceback (job status endpoint broken?)

Root cause hypothesis: Ollama has a default concurrent request limit. With 4 simultaneous heavy
embedding streams, Ollama drops the HTTP connection mid-stream. The indexing worker doesn't retry
the connection and marks the job as FAILED even though embedding completed.

Secondary issue: `agent-brain jobs --watch` always times out after 30s ("Request timed out after
30.0s"). The --watch flag keeps a persistent HTTP connection that Ollama/server drops, making
live monitoring impossible.

## Solution

1. Add retry logic in the embedding client when Ollama drops the connection (BrokenPipeError /
   ConnectionResetError) — retry with exponential backoff rather than failing the job
2. Separate job progress reporting from the embedding HTTP stream so a dropped Ollama connection
   doesn't propagate as a job failure
3. Fix `agent-brain jobs --watch` streaming endpoint to not use a persistent connection that times out
4. Consider: limit concurrent Ollama embedding threads (configurable `ollama_concurrent_requests`)
   to prevent overload at the source rather than at retry time
5. After a "failed" job, verify chunk count to detect false failures vs real failures
