"""Tests for include_types field on IndexRequest and FolderManager integration."""

from __future__ import annotations

import pytest

from agent_brain_server.models.index import IndexRequest
from agent_brain_server.services.file_type_presets import resolve_file_types


class TestIndexRequestIncludeTypes:
    """Tests for include_types field on IndexRequest model."""

    def test_include_types_defaults_to_none(self) -> None:
        """IndexRequest.include_types defaults to None."""
        req = IndexRequest(folder_path="/some/path")
        assert req.include_types is None

    def test_include_types_accepts_valid_presets(self) -> None:
        """IndexRequest accepts valid preset names in include_types."""
        req = IndexRequest(
            folder_path="/some/path",
            include_types=["python", "docs"],
        )
        assert req.include_types == ["python", "docs"]

    def test_include_types_accepts_single_preset(self) -> None:
        """IndexRequest accepts a single preset in include_types."""
        req = IndexRequest(
            folder_path="/some/path",
            include_types=["code"],
        )
        assert req.include_types == ["code"]

    def test_include_types_accepts_empty_list(self) -> None:
        """IndexRequest accepts empty list for include_types (treated as None)."""
        req = IndexRequest(
            folder_path="/some/path",
            include_types=[],
        )
        assert req.include_types == []

    def test_include_types_and_include_patterns_coexist(self) -> None:
        """IndexRequest accepts both include_types and include_patterns."""
        req = IndexRequest(
            folder_path="/some/path",
            include_types=["python"],
            include_patterns=["*.toml", "*.yaml"],
        )
        assert req.include_types == ["python"]
        assert req.include_patterns == ["*.toml", "*.yaml"]

    def test_include_types_none_with_patterns(self) -> None:
        """include_patterns still works when include_types is None."""
        req = IndexRequest(
            folder_path="/some/path",
            include_patterns=["*.md", "*.py"],
        )
        assert req.include_types is None
        assert req.include_patterns == ["*.md", "*.py"]

    def test_index_request_serialization_with_include_types(self) -> None:
        """IndexRequest serializes include_types in model_dump."""
        req = IndexRequest(
            folder_path="/some/path",
            include_types=["typescript", "web"],
        )
        data = req.model_dump()
        assert "include_types" in data
        assert data["include_types"] == ["typescript", "web"]


class TestResolveFileTypes:
    """Tests for resolve_file_types function integration with IndexRequest."""

    def test_resolve_python_preset(self) -> None:
        """Resolving 'python' preset returns Python glob patterns."""
        patterns = resolve_file_types(["python"])
        assert "*.py" in patterns
        assert "*.pyi" in patterns

    def test_resolve_docs_preset(self) -> None:
        """Resolving 'docs' preset returns documentation glob patterns."""
        patterns = resolve_file_types(["docs"])
        assert "*.md" in patterns
        assert "*.txt" in patterns
        assert "*.rst" in patterns

    def test_resolve_multiple_presets_combines(self) -> None:
        """Resolving multiple presets combines patterns (union)."""
        patterns = resolve_file_types(["python", "docs"])
        # Python patterns
        assert "*.py" in patterns
        # Docs patterns
        assert "*.md" in patterns

    def test_resolve_deduplicates_patterns(self) -> None:
        """Resolving overlapping presets deduplicates patterns."""
        # "web" includes *.tsx, "typescript" also includes *.tsx
        patterns = resolve_file_types(["typescript", "web"])
        tsx_count = patterns.count("*.tsx")
        assert tsx_count == 1, f"*.tsx should appear once, got {tsx_count}"

    def test_resolve_unknown_preset_raises_value_error(self) -> None:
        """resolve_file_types raises ValueError for unknown preset names."""
        with pytest.raises(ValueError, match="Unknown file type preset"):
            resolve_file_types(["unknown_preset_xyz"])

    def test_resolve_empty_list_returns_empty(self) -> None:
        """resolve_file_types([]) returns empty list."""
        patterns = resolve_file_types([])
        assert patterns == []


class TestIncludeTypesCombination:
    """Tests for combining include_types and include_patterns."""

    def test_combine_include_types_with_include_patterns(self) -> None:
        """Effective patterns = union of include_types resolution + include_patterns."""
        include_types = ["python"]
        include_patterns = ["*.toml", "*.yaml"]

        # Simulate what IndexingService does
        effective_patterns = list(include_patterns)
        preset_patterns = resolve_file_types(include_types)
        for pattern in preset_patterns:
            if pattern not in effective_patterns:
                effective_patterns.append(pattern)

        # Should contain both explicit and preset patterns
        assert "*.toml" in effective_patterns
        assert "*.yaml" in effective_patterns
        assert "*.py" in effective_patterns
        assert "*.pyi" in effective_patterns

    def test_combine_no_duplicates(self) -> None:
        """Union of patterns has no duplicates."""
        include_types = ["python"]
        # include_patterns already contains a Python pattern
        include_patterns = ["*.py", "*.toml"]

        effective_patterns = list(include_patterns)
        preset_patterns = resolve_file_types(include_types)
        for pattern in preset_patterns:
            if pattern not in effective_patterns:
                effective_patterns.append(pattern)

        # *.py should appear only once
        assert effective_patterns.count("*.py") == 1

    def test_none_include_types_uses_only_include_patterns(self) -> None:
        """When include_types is None, only include_patterns are used."""
        include_types = None
        include_patterns = ["*.md", "*.txt"]

        effective_patterns = list(include_patterns or [])
        if include_types:
            preset_patterns = resolve_file_types(include_types)
            for pattern in preset_patterns:
                if pattern not in effective_patterns:
                    effective_patterns.append(pattern)

        assert effective_patterns == ["*.md", "*.txt"]

    def test_none_include_patterns_uses_only_include_types(self) -> None:
        """When include_patterns is None, only include_types are resolved."""
        include_types = ["python"]
        include_patterns = None

        effective_patterns = list(include_patterns or [])
        if include_types:
            preset_patterns = resolve_file_types(include_types)
            for pattern in preset_patterns:
                if pattern not in effective_patterns:
                    effective_patterns.append(pattern)

        assert "*.py" in effective_patterns
        assert "*.toml" not in effective_patterns


class TestIndexingServiceFolderManagerIntegration:
    """Tests for IndexingService + FolderManager integration."""

    @pytest.mark.asyncio
    async def test_indexing_service_accepts_folder_manager_param(self) -> None:
        """IndexingService can be instantiated with folder_manager parameter."""
        from unittest.mock import AsyncMock, MagicMock

        from agent_brain_server.services.folder_manager import FolderManager
        from agent_brain_server.services.indexing_service import IndexingService

        # Create mock folder manager
        mock_folder_manager = AsyncMock(spec=FolderManager)

        # Create mock storage backend
        mock_backend = MagicMock()
        mock_backend.is_initialized = True

        # Must be able to create IndexingService with folder_manager
        service = IndexingService(
            storage_backend=mock_backend,
            folder_manager=mock_folder_manager,
        )

        assert service.folder_manager is mock_folder_manager

    @pytest.mark.asyncio
    async def test_indexing_service_without_folder_manager(self) -> None:
        """IndexingService works with folder_manager=None (backward compat)."""
        from unittest.mock import MagicMock

        from agent_brain_server.services.indexing_service import IndexingService

        mock_backend = MagicMock()
        mock_backend.is_initialized = True

        service = IndexingService(storage_backend=mock_backend)
        assert service.folder_manager is None

    @pytest.mark.asyncio
    async def test_get_status_without_folder_manager_uses_in_memory_set(
        self,
    ) -> None:
        """get_status uses in-memory _indexed_folders when folder_manager is None."""
        from unittest.mock import AsyncMock, MagicMock

        from agent_brain_server.services.indexing_service import IndexingService

        mock_backend = MagicMock()
        mock_backend.is_initialized = True
        mock_backend.get_count = AsyncMock(return_value=0)

        service = IndexingService(storage_backend=mock_backend)
        # Simulate indexed folder in memory
        service._indexed_folders.add("/some/folder")

        status = await service.get_status()

        assert "/some/folder" in status["indexed_folders"]
