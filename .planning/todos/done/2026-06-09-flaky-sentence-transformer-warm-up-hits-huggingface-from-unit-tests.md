---
created: 2026-06-09T05:30:00.000Z
title: TestSentenceTransformerWarmUp.test_warm_up_success is a flaky network test misclassified as unit
area: testing
files:
  - agent-brain-server/tests/unit/providers/test_reranker_providers.py:533-552
---

## Problem

`agent-brain-server/tests/unit/providers/test_reranker_providers.py::TestSentenceTransformerWarmUp::test_warm_up_success`
lives under `tests/unit/` but calls a real `provider.warm_up()` that downloads
`cross-encoder/ms-marco-MiniLM-L-6-v2` (~80 MB) from huggingface.co. Same goes
for the sibling `test_availability_caching` (same class, same model, real
`is_available()` call).

Symptom on PR #197 second CI run:
```
WARNING  CrossEncoder warm-up failed: We couldn't connect to 'https://huggingface.co'
to load this file, couldn't find it in the cached files and it looks like
cross-encoder/ms-marco-MiniLM-L-6-v2 is not the path to a directory containing
a file named config.json.
FAILED tests/unit/providers/test_reranker_providers.py::TestSentenceTransformerWarmUp::test_warm_up_success
  - assert False is True
```

The third CI run passed (HF cache warm) — confirming this is purely
network/cache-state dependent, not a real regression. But the failure mode
silently torpedoes unrelated PRs. PR #197 burned a CI iteration on this.

## Solution

Two options (recommended: A):

**Option A — Mock `SentenceTransformer` in the unit test.** Keep the test as a
unit test by patching the cross-encoder class so no network call is made. This
is the right test layer: we're verifying `warm_up()`'s state-machine behavior
(`_model_loaded`, `_availability_checked`, `_is_available_cached`), not that
HuggingFace serves models.

```python
from unittest.mock import patch, MagicMock

def test_warm_up_success(self) -> None:
    config = RerankerConfig(
        provider=RerankerProviderType.SENTENCE_TRANSFORMERS,
        model="cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    provider = SentenceTransformerRerankerProvider(config)
    assert provider._model_loaded is False

    with patch(
        "agent_brain_server.providers.reranker.sentence_transformers.CrossEncoder",
        return_value=MagicMock(),
    ):
        result = provider.warm_up()

    assert result is True
    assert provider._model_loaded is True
    # ... etc
```

Apply the same pattern to `test_availability_caching`.

**Option B — Move + mark as integration.** Move both tests to
`agent-brain-server/tests/integration/providers/` and add
`@pytest.mark.network`. Then teach CI to skip `network` tests when offline
(or accept that integration tests can be flaky and run them in a separate job
that doesn't gate the QA Gate). Heavier change.

## Acceptance

- Both tests in `TestSentenceTransformerWarmUp` run with zero network calls
  (verify with `pytest --disable-socket` or by inspection)
- Tests still cover the state-machine semantics: `_model_loaded`,
  `_availability_checked`, `_is_available_cached` transitions
- CI runs no longer flake on HuggingFace connectivity for this class

---

## Resolution (2026-06-11)

**Fixed via Option A** (mock `CrossEncoder`). `TestSentenceTransformerWarmUp` in
`agent-brain-server/tests/unit/providers/test_reranker_providers.py` rewritten to
7 fully-mocked tests patching
`agent_brain_server.providers.reranker.sentence_transformers.CrossEncoder`
(patched where used, not where defined). Covers the state-machine flags
(`_cross_encoder`, `_model_loaded`, `_availability_checked`,
`_is_available_cached`), idempotent lazy-load (`assert_called_once`), and the
failure path. Verified zero network calls under `HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1`; 51/51 in-file pass. Branch
`fix/maintenance-todos-flaky-test-and-scope-guard`.
