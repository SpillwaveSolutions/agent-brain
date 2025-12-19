"""HTTP client for Doc-Serve API communication."""

from dataclasses import dataclass
from types import TracebackType
from typing import Any, Optional

import httpx


class DocServeError(Exception):
    """Base exception for Doc-Serve client errors."""

    pass


class ConnectionError(DocServeError):
    """Raised when unable to connect to the server."""

    pass


class ServerError(DocServeError):
    """Raised when server returns an error response."""

    def __init__(self, message: str, status_code: int, detail: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


@dataclass
class HealthStatus:
    """Server health status."""

    status: str
    message: Optional[str]
    version: str
    timestamp: str


@dataclass
class IndexingStatus:
    """Detailed indexing status."""

    total_documents: int
    total_chunks: int
    indexing_in_progress: bool
    current_job_id: Optional[str]
    progress_percent: float
    last_indexed_at: Optional[str]
    indexed_folders: list[str]


@dataclass
class QueryResult:
    """Single query result."""

    text: str
    source: str
    score: float
    chunk_id: str
    metadata: dict[str, Any]
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None


@dataclass
class QueryResponse:
    """Query response with results."""

    results: list[QueryResult]
    query_time_ms: float
    total_results: int


@dataclass
class IndexResponse:
    """Indexing operation response."""

    job_id: str
    status: str
    message: Optional[str]


class DocServeClient:
    """HTTP client for Doc-Serve API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        timeout: float = 30.0,
    ):
        """
        Initialize the client.

        Args:
            base_url: Server base URL.
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def __enter__(self) -> "DocServeClient":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Make an HTTP request to the server.

        Args:
            method: HTTP method (GET, POST, DELETE).
            path: API path.
            json: Optional JSON body.

        Returns:
            Response JSON data.

        Raises:
            ConnectionError: If unable to connect.
            ServerError: If server returns an error.
        """
        url = f"{self.base_url}{path}"

        try:
            response = self._client.request(method, url, json=json)
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
        )

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        mode: str = "hybrid",
        alpha: float = 0.5,
        source_types: Optional[list[str]] = None,
        languages: Optional[list[str]] = None,
        file_paths: Optional[list[str]] = None,
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

        Returns:
            QueryResponse with matching results.
        """
        request_data = {
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

        data = self._request("POST", "/query/", json=request_data)

        results = [
            QueryResult(
                text=r["text"],
                source=r["source"],
                score=r["score"],
                chunk_id=r["chunk_id"],
                metadata=r.get("metadata", {}),
                vector_score=r.get("vector_score"),
                bm25_score=r.get("bm25_score"),
            )
            for r in data.get("results", [])
        ]

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
        supported_languages: Optional[list[str]] = None,
        code_chunk_strategy: str = "ast_aware",
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
        generate_summaries: bool = False,
    ) -> IndexResponse:
        """
        Start indexing documents and optionally code from a folder.

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
            generate_summaries: Generate LLM summaries for code chunks.

        Returns:
            IndexResponse with job ID.
        """
        data = self._request(
            "POST",
            "/index/",
            json={
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
            },
        )

        return IndexResponse(
            job_id=data["job_id"],
            status=data["status"],
            message=data.get("message"),
        )

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
