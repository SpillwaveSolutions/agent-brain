"""HTTP client for Doc-Serve API communication."""

from dataclasses import dataclass
from types import TracebackType
from typing import Any

import httpx


class DocServeError(Exception):
    """Base exception for Doc-Serve client errors."""

    pass


class ConnectionError(DocServeError):
    """Raised when unable to connect to the server."""

    pass


class ServerError(DocServeError):
    """Raised when server returns an error response."""

    def __init__(self, message: str, status_code: int, detail: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


@dataclass
class HealthStatus:
    """Server health status."""

    status: str
    message: str | None
    version: str
    timestamp: str


@dataclass
class IndexingStatus:
    """Detailed indexing status."""

    total_documents: int
    total_chunks: int
    indexing_in_progress: bool
    current_job_id: str | None
    progress_percent: float
    last_indexed_at: str | None
    indexed_folders: list[str]
    file_watcher: dict[str, Any] | None = None
    embedding_cache: dict[str, Any] | None = None


@dataclass
class ResultExplanation:
    """Structured per-result explanation (issue #159).

    Populated only when the request set `explain=true`. All fields are
    optional because their relevance depends on retrieval mode.
    """

    reason: str
    matched_terms: list[str] | None = None
    fusion: dict[str, float] | None = None
    graph_path: list[str] | None = None
    rerank_movement: int | None = None
    graph_fallback: bool | None = None


@dataclass
class QueryResult:
    """Single query result."""

    text: str
    source: str
    score: float
    chunk_id: str
    metadata: dict[str, Any]
    vector_score: float | None = None
    bm25_score: float | None = None
    graph_score: float | None = None
    rerank_score: float | None = None
    original_rank: int | None = None
    relationship_path: list[str] | None = None
    related_entities: list[str] | None = None
    source_type: str = "doc"
    language: str | None = None
    explanation: ResultExplanation | None = None


@dataclass
class QueryResponse:
    """Query response with results."""

    results: list[QueryResult]
    query_time_ms: float
    total_results: int


@dataclass
class FolderInfo:
    """Indexed folder information."""

    folder_path: str
    chunk_count: int
    last_indexed: str
    watch_mode: str = "off"
    watch_debounce_seconds: int | None = None


@dataclass
class IndexResponse:
    """Indexing operation response."""

    job_id: str
    status: str
    message: str | None


def _parse_query_result(payload: dict[str, Any]) -> QueryResult:
    """Build a QueryResult from a server response dict, including optional
    explanation block (issue #159)."""
    explanation_data = payload.get("explanation")
    explanation: ResultExplanation | None = None
    if explanation_data is not None:
        explanation = ResultExplanation(
            reason=explanation_data.get("reason", ""),
            matched_terms=explanation_data.get("matched_terms"),
            fusion=explanation_data.get("fusion"),
            graph_path=explanation_data.get("graph_path"),
            rerank_movement=explanation_data.get("rerank_movement"),
            graph_fallback=explanation_data.get("graph_fallback"),
        )
    return QueryResult(
        text=payload["text"],
        source=payload["source"],
        score=payload["score"],
        chunk_id=payload["chunk_id"],
        metadata=payload.get("metadata", {}),
        vector_score=payload.get("vector_score"),
        bm25_score=payload.get("bm25_score"),
        graph_score=payload.get("graph_score"),
        rerank_score=payload.get("rerank_score"),
        original_rank=payload.get("original_rank"),
        relationship_path=payload.get("relationship_path"),
        related_entities=payload.get("related_entities"),
        source_type=payload.get("source_type", "doc"),
        language=payload.get("language"),
        explanation=explanation,
    )


class DocServeClient:
    """HTTP client for Doc-Serve API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        timeout: float = 30.0,
        api_key: str | None = None,
    ):
        """
        Initialize the client.

        Args:
            base_url: Server base URL.
            timeout: Request timeout in seconds.
            api_key: Optional bearer token (Issues #179, #199). When supplied,
                every outbound request carries an ``Authorization: Bearer``
                header per RFC 6750. ``None`` means no auth header (server
                must be in ``INSECURE_NO_AUTH=true`` mode to accept the
                request).
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self._client = httpx.Client(timeout=timeout, headers=headers)

    @classmethod
    def from_httpx(
        cls,
        client: httpx.Client,
        api_key: str | None = None,
    ) -> "DocServeClient":
        """Build a DocServeClient that uses a pre-constructed httpx.Client.

        Used by the transport selector to inject a UDS-backed client
        (see ``agent_brain_cli.client.transport.open_backend``). The
        inner client's ``base_url`` is preserved; this wrapper sends
        relative paths only.

        Args:
            client: An already-configured ``httpx.Client``. The wrapper
                takes ownership and will close it on ``__exit__``.
            api_key: Optional bearer token to merge into the client's
                default headers as ``Authorization: Bearer <token>``
                (Issues #179, #199). Caller may also have set the
                header on ``client`` directly; both paths work.

        Returns:
            A DocServeClient backed by ``client``.
        """
        instance = cls.__new__(cls)
        instance.base_url = ""  # inner client carries the real base_url
        timeout = client.timeout
        instance.timeout = timeout.read or 30.0
        if api_key:
            client.headers["Authorization"] = f"Bearer {api_key}"
        instance._client = client
        return instance

    def __enter__(self) -> "DocServeClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make an HTTP request to the server.

        Args:
            method: HTTP method (GET, POST, DELETE).
            path: API path.
            json: Optional JSON body.
            params: Optional query parameters.

        Returns:
            Response JSON data.

        Raises:
            ConnectionError: If unable to connect.
            ServerError: If server returns an error.
        """
        url = f"{self.base_url}{path}"

        try:
            response = self._client.request(method, url, json=json, params=params)
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Unable to connect to server at {self.base_url}. "
                f"Is the server running? Error: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise ConnectionError(
                f"Request timed out after {self.timeout}s. "
                "The server may be overloaded or unresponsive."
            ) from e

        if response.status_code >= 400:
            detail = None
            try:
                error_data = response.json()
                detail = error_data.get("detail", str(error_data))
            except Exception:
                detail = response.text

            raise ServerError(
                f"Server returned {response.status_code}",
                status_code=response.status_code,
                detail=detail,
            )

        result: dict[str, Any] = response.json()
        return result

    def health(self) -> HealthStatus:
        """
        Get server health status.

        Returns:
            HealthStatus with current status.
        """
        data = self._request("GET", "/health/")
        return HealthStatus(
            status=data["status"],
            message=data.get("message"),
            version=data.get("version", "unknown"),
            timestamp=data.get("timestamp", ""),
        )

    def status(self) -> IndexingStatus:
        """
        Get detailed indexing status.

        Returns:
            IndexingStatus with document counts and progress.
        """
        data = self._request("GET", "/health/status")
        return IndexingStatus(
            total_documents=data.get("total_documents", 0),
            total_chunks=data.get("total_chunks", 0),
            indexing_in_progress=data.get("indexing_in_progress", False),
            current_job_id=data.get("current_job_id"),
            progress_percent=data.get("progress_percent", 0.0),
            last_indexed_at=data.get("last_indexed_at"),
            indexed_folders=data.get("indexed_folders", []),
            file_watcher=data.get("file_watcher"),
            embedding_cache=data.get("embedding_cache"),
        )

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        mode: str = "hybrid",
        alpha: float = 0.5,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
        file_paths: list[str] | None = None,
        explain: bool = False,
    ) -> QueryResponse:
        """
        Query indexed documents.

        Args:
            query_text: Search query.
            top_k: Number of results to return.
            similarity_threshold: Minimum similarity score.
            mode: Retrieval mode (vector, bm25, hybrid).
            alpha: Hybrid search weighting (1.0=vector, 0.0=bm25).
            source_types: Filter by source types (doc, code, test).
            languages: Filter by programming languages.
            file_paths: Filter by file path patterns.
            explain: When True, include structured per-result explanations
                (matched terms, fusion breakdown, graph path, rerank movement,
                and a 'why this rank' summary). See issue #159.

        Returns:
            QueryResponse with matching results.
        """
        request_data: dict[str, Any] = {
            "query": query_text,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold,
            "mode": mode,
            "alpha": alpha,
        }
        if source_types is not None:
            request_data["source_types"] = source_types
        if languages is not None:
            request_data["languages"] = languages
        if file_paths is not None:
            request_data["file_paths"] = file_paths
        if explain:
            request_data["explain"] = True

        data = self._request("POST", "/query/", json=request_data)

        results = [_parse_query_result(r) for r in data.get("results", [])]

        return QueryResponse(
            results=results,
            query_time_ms=data.get("query_time_ms", 0.0),
            total_results=data.get("total_results", len(results)),
        )

    def index(
        self,
        folder_path: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        recursive: bool = True,
        include_code: bool = False,
        supported_languages: list[str] | None = None,
        code_chunk_strategy: str = "ast_aware",
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        include_types: list[str] | None = None,
        generate_summaries: bool = False,
        force: bool = False,
        injector_script: str | None = None,
        folder_metadata_file: str | None = None,
        dry_run: bool = False,
        watch_mode: str | None = None,
        watch_debounce_seconds: int | None = None,
    ) -> IndexResponse:
        """
        Enqueue an indexing job for documents and optionally code from a folder.

        Args:
            folder_path: Path to folder with documents.
            chunk_size: Target chunk size in tokens.
            chunk_overlap: Overlap between chunks.
            recursive: Whether to scan recursively.
            include_code: Whether to index source code files.
            supported_languages: Languages to index (defaults to all).
            code_chunk_strategy: Strategy for code chunking.
            include_patterns: Additional include patterns.
            exclude_patterns: Additional exclude patterns.
            include_types: File type preset names (e.g., ["python", "docs"]).
            generate_summaries: Generate LLM summaries for code chunks.
            force: Bypass deduplication and force a new job.
            injector_script: Path to Python script exporting process_chunk().
            folder_metadata_file: Path to JSON file with static metadata.
            dry_run: Validate injector against sample chunks without indexing.
            watch_mode: Watch mode for auto-reindex: 'auto' or 'off'.
            watch_debounce_seconds: Per-folder debounce in seconds.

        Returns:
            IndexResponse with job ID and queue status.
        """
        body: dict[str, Any] = {
            "folder_path": folder_path,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "recursive": recursive,
            "include_code": include_code,
            "supported_languages": supported_languages,
            "code_chunk_strategy": code_chunk_strategy,
            "include_patterns": include_patterns,
            "exclude_patterns": exclude_patterns,
            "generate_summaries": generate_summaries,
            "force": force,
        }
        if include_types is not None:
            body["include_types"] = include_types
        if injector_script is not None:
            body["injector_script"] = injector_script
        if folder_metadata_file is not None:
            body["folder_metadata_file"] = folder_metadata_file
        if dry_run:
            body["dry_run"] = True
        if watch_mode is not None:
            body["watch_mode"] = watch_mode
        if watch_debounce_seconds is not None:
            body["watch_debounce_seconds"] = watch_debounce_seconds

        data = self._request(
            "POST",
            "/index/",
            json=body,
            params={"force": force},
        )

        return IndexResponse(
            job_id=data["job_id"],
            status=data["status"],
            message=data.get("message"),
        )

    def list_folders(self) -> list[FolderInfo]:
        """
        List all indexed folders.

        Returns:
            List of FolderInfo objects sorted by folder path.
        """
        data = self._request("GET", "/index/folders/")
        folders: list[FolderInfo] = [
            FolderInfo(
                folder_path=f["folder_path"],
                chunk_count=f["chunk_count"],
                last_indexed=f["last_indexed"],
                watch_mode=f.get("watch_mode", "off"),
                watch_debounce_seconds=f.get("watch_debounce_seconds"),
            )
            for f in data.get("folders", [])
        ]
        return folders

    def delete_folder(self, folder_path: str) -> dict[str, Any]:
        """
        Delete all indexed chunks for a folder.

        Args:
            folder_path: Absolute path to the folder to remove.

        Returns:
            Response dict with folder_path, chunks_deleted, and message.
        """
        result: dict[str, Any] = self._request(
            "DELETE",
            "/index/folders/",
            json={"folder_path": folder_path},
        )
        return result

    def reset(self) -> IndexResponse:
        """
        Reset the index by deleting all documents.

        Returns:
            IndexResponse confirming reset.
        """
        data = self._request("DELETE", "/index/")

        return IndexResponse(
            job_id=data.get("job_id", "reset"),
            status=data["status"],
            message=data.get("message"),
        )

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        List jobs in the queue.

        Args:
            limit: Maximum number of jobs to return.

        Returns:
            List of job dictionaries.
        """
        data = self._request("GET", f"/index/jobs/?limit={limit}")
        jobs: list[dict[str, Any]] = data.get("jobs", [])
        return jobs

    def get_job(self, job_id: str) -> dict[str, Any]:
        """
        Get details for a specific job.

        Args:
            job_id: The job ID to look up.

        Returns:
            Job detail dictionary.
        """
        return self._request("GET", f"/index/jobs/{job_id}")

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """
        Cancel a specific job.

        Args:
            job_id: The job ID to cancel.

        Returns:
            Cancellation result dictionary.
        """
        return self._request("DELETE", f"/index/jobs/{job_id}")

    def cache_status(self) -> dict[str, Any]:
        """
        Get embedding cache status.

        Returns:
            Dict with hits, misses, hit_rate, mem_entries, entry_count, size_bytes.

        Raises:
            ConnectionError: If unable to connect.
            ServerError: If server returns an error.
        """
        return self._request("GET", "/index/cache/")

    def clear_cache(self) -> dict[str, Any]:
        """
        Clear the embedding cache.

        Returns:
            Dict with count, size_bytes, size_mb of cleared entries.

        Raises:
            ConnectionError: If unable to connect.
            ServerError: If server returns an error.
        """
        return self._request("DELETE", "/index/cache/")
