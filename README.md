Phase 1

1. Build System: Use Poetry for dependency and environment management.
2. REST API: Use FastAPI to create the RESTful interface. This will expose endpoints for querying the indexed documents.
3. Indexing and Vector Store: Use LlamaIndex for indexing the documents, applying context-aware chunking via RecursiveCharacterTextSplitter. Use Chroma as the vector store, which is thread-safe and suited for concurrent requests.
4. Embedding Model: Use OpenAI’s latest embedding model, which as of now is “text-embedding-3-large” (or whichever the latest model is at the time). This model will convert text chunks into embeddings for indexing and querying.
5. LLM for Summarization: Use Claude 4.5 Haiku for generating summaries of documents and surrounding chunks. This helps enable context-aware chunking and enhances the quality of the retrieval.
6. Tokenizer/Embedding Generation: Use OpenAI’s tokenizer (such as tiktoken) for tokenization, which is thread-safe for concurrent use. The embedding model will use this tokenization under the hood when generating vectors.
7. Claude Skill Integration: Add a Claude skill that interfaces with the REST API, allowing you to query the vector store during generation tasks. This enables dynamic look-ups from the indexed corpus while generating content.
8. Chunk Sizes: For context-aware chunking, consider a base chunk size of around 512 to 1024 tokens, with overlap of around 50 to 100 tokens. You can adjust these sizes after testing with your specific documents.

This combination gives you a powerful, scalable stack for indexing, embedding, querying, and generating context-aware results via a REST API.

Mono repo 

```markdown
/
   docs/ 
   doc-serve-skill/
   doc-serve-server/
   doc-svr-ctl/ (Command line interface to doc-server)
   
   
```

1. command-line tool, called something like "docserver," that takes a path to a folder containing documents and a port number to run on. This launches folder.
2. When it starts, it indexes all the documents in that folder, using OpenAI embeddings and stores them in the Chroma vector store.
3. The tool will expose health endpoints—likely something like a /health or /status route—to indicate if it's up, if indexing is in progress, or if it's finished and ready for querying.
4. The skill will know how to check this health endpoint to see whether the docserver is running. If not, it can spin it up with the proper folder path and port.
5. Once indexing is complete and the server is ready, the skill can query the vector store over HTTP, sending text queries and getting back relevant document chunks or summaries.
6. Everything will be running locally, so it stays efficient and fast.
7. There is a doc-svr-cli to query the DB and test it easily, and turn it off. Add dirs to index, etc. 
8. Doc-serve-server exposes OpenAPI schema 

It is a fully self-contained system that the skill can start, check, and query as needed. This design gives you flexibility and scalability.

Phase 2

Yes, you can add BM25-style keyword search alongside vector search, and LlamaIndex actually has first-class support for that plus hybrid retrieval.[developers.llamaindex+1](https://developers.llamaindex.ai/python/examples/retrievers/bm25_retriever/)

## BM25 and hybrid in LlamaIndex

- LlamaIndex ships a `BM25Retriever` that runs classic sparse retrieval (BM25) over your corpus.[llamaindexxx.readthedocs+1](https://llamaindexxx.readthedocs.io/en/latest/examples/retrievers/bm25_retriever.html)
- You can pair that with a standard vector retriever (your Chroma-backed index) and either:
    - Expose them as separate modes (keyword vs semantic), or
    - Wrap them in a “hybrid” or “fusion” retriever that merges BM25 and vector results (often via reciprocal rank fusion or weighted scores).[llamaindex+2](https://www.llamaindex.ai/blog/llamaindex-enhancing-retrieval-performance-with-alpha-tuning-in-hybrid-search-in-rag-135d0c9b8a00)

Conceptually you end up with:

- Dense retriever: semantic similarity over embeddings (your current Chroma + OpenAI embeddings).
- Sparse retriever: BM25 over raw text.
- Hybrid retriever: calls both, merges ranked lists, returns a unified set of nodes.[trulens+2](https://www.trulens.org/cookbook/frameworks/llamaindex/llama_index_hybrid_retriever/)

## Where BM25 actually lives

- LlamaIndex can do BM25 internally with `BM25Retriever` over its document store (no external search engine required).[developers.llamaindex+1](https://developers.llamaindex.ai/python/examples/retrievers/bm25_retriever/)
- Some vector backends (e.g., Milvus, Qdrant) and newer Chroma “sparse search” features also expose BM25-like sparse vectors or full-text/BM25 integrations, which LlamaIndex can use via their hybrid vector store integrations.[milvus+2](https://milvus.io/docs/llamaindex_milvus_full_text_search.md)

With your current design (LlamaIndex + Chroma):

- Keep Chroma for dense vectors.
- Add a `BM25Retriever` over the same `Document`/`Node` objects (LlamaIndex’s internal store).
- Create a hybrid retriever that combines:
    - `VectorIndexRetriever` (Chroma-backed)
    - `BM25Retriever` (keyword/BM25)[stackoverflow+1](https://stackoverflow.com/questions/77027805/how-to-add-fulltext-search-to-llamaindex)

## How you’d expose it in your REST API

You could define something like:

- `mode=vector` → only dense retrieval
- `mode=bm25` → pure keyword/BM25
- `mode=hybrid` (default) → fusion of both lists, N results per type then merged and reranked.[llamaindex+1](https://www.llamaindex.ai/blog/llamaindex-enhancing-retrieval-performance-with-alpha-tuning-in-hybrid-search-in-rag-135d0c9b8a00)

This gives your Claude skill three knobs:

- “Fuzzy semantic” (vector)
- “Exact keyword” (BM25)
- “Best of both” (hybrid)

All backed by the same underlying indexed corpus and context-aware chunking.

1. https://developers.llamaindex.ai/python/examples/retrievers/bm25_retriever/
2. https://stackoverflow.com/questions/77027805/how-to-add-fulltext-search-to-llamaindex
3. https://llamaindexxx.readthedocs.io/en/latest/examples/retrievers/bm25_retriever.html
4. https://www.llamaindex.ai/blog/llamaindex-enhancing-retrieval-performance-with-alpha-tuning-in-hybrid-search-in-rag-135d0c9b8a00
5. https://www.trulens.org/cookbook/frameworks/llamaindex/llama_index_hybrid_retriever/
6. https://www.trulens.org/examples/frameworks/llama_index/llama_index_hybrid_retriever/
7. https://milvus.io/docs/llamaindex_milvus_full_text_search.md
8. https://www.trychroma.com/project/sparse-vector-search
9. https://developers.llamaindex.ai/python/examples/vector_stores/qdrant_hybrid/
10. https://github.com/run-llama/llama_index/discussions/9837
11. https://www.linkedin.com/posts/trychroma_chroma-now-supports-sparse-vector-search-activity-7389395636674232320-JVgi
12. https://builder.aws.com/content/2vMeX91f1Cb4rcDm4tBPzYJmRtl/building-an-enterprise-knowledge-rag-platform-with-llamaindex-and-amazon-bedrock
13. https://www.linkedin.com/learning/hands-on-ai-rag-using-llamaindex/hybrid-retrieval
14. https://docs.haystack.deepset.ai/docs/retrievers
15. https://github.com/run-llama/llama_index/issues/8083
16. https://interestingengineering.substack.com/p/from-bm25-to-agentic-rag-the-evolution
17. https://docs.llamaindex.ai/en/v0.10.34/examples/retrievers/bm25_retriever/
18. https://milvus.io/docs/llamaindex_milvus_hybrid_search.md
19. https://github.com/chroma-core/chroma/issues/2633
20. https://docs.llamaindex.ai/en/v0.9.48/examples/retrievers/bm25_retriever.html
