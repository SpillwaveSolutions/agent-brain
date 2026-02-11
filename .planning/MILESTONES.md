# Milestones

## v3.0 Advanced RAG (Shipped: 2026-02-10)

**Phases completed:** 4 phases, 15 plans, 20 tasks
**Tests:** 505 passing (70% coverage)
**Server LOC:** 12,858 Python | **Test LOC:** 13,171 Python

**Key accomplishments:**
1. Two-stage reranking with SentenceTransformers CrossEncoder + Ollama providers (+3-4% precision)
2. Pluggable provider system — YAML-driven config for embeddings (OpenAI/Ollama/Cohere), summarization (Anthropic/OpenAI/Gemini/Grok/Ollama), and reranking
3. Schema-based GraphRAG with 17 entity types, 8 relationship predicates, and type-filtered queries
4. Dimension mismatch prevention and strict startup validation for provider configs
5. Comprehensive E2E test suites for all providers with graceful API key skipping
6. GitHub Actions CI workflow with matrix strategy for provider testing

**Archive:** [v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md) | [v3.0-REQUIREMENTS.md](milestones/v3.0-REQUIREMENTS.md)

---

