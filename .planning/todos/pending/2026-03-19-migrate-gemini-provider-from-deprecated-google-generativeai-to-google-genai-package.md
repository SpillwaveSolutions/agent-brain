---
created: 2026-03-19T03:23:23.194Z
title: Migrate gemini provider from deprecated google-generativeai to google-genai package
area: tooling
files:
  - agent-brain-server/agent_brain_server/providers/summarization/gemini.py:6
  - agent-brain-server/pyproject.toml
---

## Problem

Every server startup (regardless of whether Gemini is the active provider) logs:

```
FutureWarning: All support for the `google.generativeai` package has ended.
It will no longer be receiving updates or bug fixes. Please switch to the
`google.genai` package as soon as possible.
  import google.generativeai as genai
```

The Gemini provider at `agent_brain_server/providers/summarization/gemini.py:6`
imports the deprecated `google.generativeai` package. Google has ended all support
for this package. It fires on import, meaning it appears even when Ollama or OpenAI
is the active provider.

## Solution

Migrate `gemini.py` to use `google.genai` (the new Google AI Python SDK):

**Step 1: Update dependency in pyproject.toml**
```toml
# Remove:
google-generativeai = "..."
# Add:
google-genai = ">=0.8.0"
```

**Step 2: Update import and API calls in gemini.py**
```python
# Before:
import google.generativeai as genai
genai.configure(api_key=api_key)
model = genai.GenerativeModel(model_name)

# After:
from google import genai
client = genai.Client(api_key=api_key)
```

The new `google.genai` SDK has a different client-based API. Review the migration
guide: https://github.com/google-gemini/deprecated-generative-ai-python/blob/main/README.md

**Step 3: Update embedding provider too**
Check if `agent_brain_server/providers/embedding/` has a Gemini provider with the
same import — migrate both together.

## Notes

- This fires even when Gemini is not the active provider (import-time warning)
- Low risk change — only affects Gemini provider, isolated module
- Run `task before-push` after migration to verify no regressions
