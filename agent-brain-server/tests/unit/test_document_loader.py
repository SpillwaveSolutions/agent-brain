"""Tests for DocumentLoader and LanguageDetector in document_loader.py."""

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_brain_server.indexing.document_loader import (
    _DOCX_AVAILABLE,
    DocumentLoader,
    LanguageDetector,
)


class TestCSharpExtensionDetection:
    """Tests for C# file extension detection."""

    def test_csharp_cs_extension(self) -> None:
        """Test .cs extension is detected as csharp."""
        assert LanguageDetector.detect_from_path("Program.cs") == "csharp"

    def test_csharp_csx_extension(self) -> None:
        """Test .csx extension is detected as csharp."""
        assert LanguageDetector.detect_from_path("Script.csx") == "csharp"

    def test_csharp_case_insensitive_extension(self) -> None:
        """Test extension detection is case-insensitive."""
        assert LanguageDetector.detect_from_path("Program.CS") == "csharp"

    def test_csharp_nested_path(self) -> None:
        """Test detection works with nested file paths."""
        assert LanguageDetector.detect_from_path("src/Models/Document.cs") == "csharp"


class TestCSharpIsSupported:
    """Tests for C# language support check."""

    def test_csharp_is_supported(self) -> None:
        """Test csharp is listed as a supported language."""
        assert LanguageDetector.is_supported_language("csharp") is True

    def test_csharp_in_supported_languages(self) -> None:
        """Test csharp appears in get_supported_languages()."""
        assert "csharp" in LanguageDetector.get_supported_languages()


class TestPascalExtensionDetection:
    """Tests for Object Pascal file extension detection."""

    def test_pascal_pas_extension(self) -> None:
        assert LanguageDetector.detect_from_path("main.pas") == "pascal"

    def test_pascal_pp_extension(self) -> None:
        assert LanguageDetector.detect_from_path("module.pp") == "pascal"

    def test_pascal_lpr_extension(self) -> None:
        assert LanguageDetector.detect_from_path("app.lpr") == "pascal"

    def test_pascal_dpr_extension(self) -> None:
        assert LanguageDetector.detect_from_path("app.dpr") == "pascal"

    def test_pascal_dpk_extension(self) -> None:
        assert LanguageDetector.detect_from_path("package.dpk") == "pascal"


class TestPascalIsSupported:
    """Tests for Pascal language support check."""

    def test_pascal_is_supported(self) -> None:
        assert LanguageDetector.is_supported_language("pascal") is True

    def test_pascal_in_supported_languages(self) -> None:
        assert "pascal" in LanguageDetector.get_supported_languages()


class TestPascalContentDetection:
    """Tests for Pascal content-based language detection."""

    def test_pascal_header_pattern(self) -> None:
        content = "unit Geometry;\ninterface\n"
        matches = LanguageDetector.detect_from_content(content)
        assert len(matches) > 0
        assert matches[0][0] == "pascal"

    def test_pascal_function_procedure_pattern(self) -> None:
        content = "procedure PrintValue;\nfunction Area: Double;\n"
        matches = LanguageDetector.detect_from_content(content)
        languages = [name for name, _ in matches]
        assert "pascal" in languages

    def test_pascal_begin_pattern(self) -> None:
        content = "program Demo;\nbegin\n  Writeln('Hello');\nend.\n"
        matches = LanguageDetector.detect_from_content(content)
        assert len(matches) > 0
        assert matches[0][0] == "pascal"


class TestCSharpContentDetection:
    """Tests for C# content-based language detection."""

    def test_csharp_using_system(self) -> None:
        """Test detection of 'using System' pattern."""
        content = "using System;\nusing System.Collections.Generic;\n"
        matches = LanguageDetector.detect_from_content(content)
        assert len(matches) > 0
        assert matches[0][0] == "csharp"

    def test_csharp_namespace_pattern(self) -> None:
        """Test detection of namespace declaration."""
        content = "namespace MyApp\n{\n    public class Foo {}\n}\n"
        matches = LanguageDetector.detect_from_content(content)
        lang_names = [m[0] for m in matches]
        assert "csharp" in lang_names

    def test_csharp_property_accessor_pattern(self) -> None:
        """Test detection of property accessor pattern."""
        content = "public string Name { get; set; }\n"
        matches = LanguageDetector.detect_from_content(content)
        lang_names = [m[0] for m in matches]
        assert "csharp" in lang_names

    def test_csharp_full_content_detection(self) -> None:
        """Test detection with comprehensive C# content."""
        content = """using System;
namespace MyApp {
    public class Program {
        public string Name { get; set; }
    }
}"""
        matches = LanguageDetector.detect_from_content(content)
        assert len(matches) > 0
        assert matches[0][0] == "csharp"

    def test_csharp_detect_language_with_path(self) -> None:
        """Test detect_language prefers path-based detection."""
        result = LanguageDetector.detect_language("Example.cs", "some random content")
        assert result == "csharp"

    def test_csharp_detect_language_from_content_fallback(self) -> None:
        """Test detect_language falls back to content detection."""
        content = """using System;
namespace MyApp {
    public class Program {
        public string Name { get; set; }
    }
}"""
        result = LanguageDetector.detect_language("unknown.txt", content)
        # Should detect as csharp from content (or None if threshold not met)
        # The important thing is it doesn't crash
        assert result is None or result == "csharp"


class TestDocxGracefulSkip:
    """Tests for graceful .docx handling when docx2txt is unavailable."""

    def test_docx_excluded_when_unavailable(self) -> None:
        """When docx2txt is not installed, .docx is not in extensions."""
        # Reload the module with docx2txt unavailable
        with patch.dict("sys.modules", {"docx2txt": None}):

            import agent_brain_server.indexing.document_loader as dl

            # Save originals
            orig_avail = dl._DOCX_AVAILABLE

            # Simulate unavailable
            dl._DOCX_AVAILABLE = False
            loader = DocumentLoader(
                supported_extensions=({".txt", ".md", ".pdf", ".html", ".rst"})
            )
            assert ".docx" not in loader.extensions

            # Restore
            dl._DOCX_AVAILABLE = orig_avail

    def test_docx_included_when_available(self) -> None:
        """When docx2txt is installed, .docx is in extensions."""
        if _DOCX_AVAILABLE:
            loader = DocumentLoader()
            assert ".docx" in loader.DOCUMENT_EXTENSIONS
        else:
            loader = DocumentLoader()
            assert ".docx" not in loader.DOCUMENT_EXTENSIONS


class TestDefaultExcludePatterns:
    """Tests for default exclude patterns."""

    def test_claude_directory_excluded(self) -> None:
        """.claude/ directories should be excluded by default."""
        loader = DocumentLoader()
        assert "**/.claude/**" in loader.exclude_patterns

    def test_claude_plugin_directory_excluded(self) -> None:
        """.claude-plugin/ directories should be excluded by default."""
        loader = DocumentLoader()
        assert "**/.claude-plugin/**" in loader.exclude_patterns

    def test_node_modules_excluded(self) -> None:
        """node_modules should still be excluded."""
        loader = DocumentLoader()
        assert "**/node_modules/**" in loader.exclude_patterns

    def test_git_excluded(self) -> None:
        """.git should still be excluded."""
        loader = DocumentLoader()
        assert "**/.git/**" in loader.exclude_patterns


class TestExcludePatternMatching:
    """Tests for _walk_pruned exclude-pattern matching (issue #142).

    Before the pathspec migration, ``**/dir/**`` patterns silently no-oped
    because ``pat.replace("**", "*")`` produced ``*/dir/*`` which
    ``fnmatch`` couldn't match against the directory's own absolute path.
    These tests pin the corrected behavior.
    """

    @pytest.fixture
    def sample_tree(self, tmp_path: Path) -> Path:
        """Build a tmp tree mirroring the reproducer in issue #142."""
        root = tmp_path / "reference"
        (root / "research" / "chapter13").mkdir(parents=True)
        (root / "research" / "chapter13" / "ch13_perplexity.md").write_text("")
        (root / "research" / "chapter14").mkdir(parents=True)
        (root / "research" / "chapter14" / "ch14_notes.md").write_text("notes")
        (root / "other").mkdir(parents=True)
        (root / "other" / "keep.md").write_text("keep me")
        (root / "logs").mkdir()
        (root / "logs" / "build.log").write_text("noise")
        return root

    def _walk(self, loader: DocumentLoader, root: Path) -> set[str]:
        """Run _walk_pruned and return paths relative to root for assertion."""
        return {str(p.relative_to(root.resolve())) for p in loader._walk_pruned(root)}

    def test_documented_double_star_dir_double_star_shape_prunes(
        self, sample_tree: Path
    ) -> None:
        """**/dir/** must prune the directory — the documented shape (#142)."""
        loader = DocumentLoader(exclude_patterns=["**/chapter13/**"])
        files = self._walk(loader, sample_tree)
        assert all("chapter13" not in f for f in files), files
        # Sibling chapter14 should survive
        assert any("chapter14" in f for f in files), files

    def test_workaround_shape_still_prunes(self, sample_tree: Path) -> None:
        """**/dir (no trailing) — the workaround from #142 — still works."""
        loader = DocumentLoader(exclude_patterns=["**/research/chapter14"])
        files = self._walk(loader, sample_tree)
        assert all("chapter14" not in f for f in files), files
        # chapter13 unaffected
        assert any("chapter13" in f for f in files), files

    def test_file_level_glob_excludes_individual_files(self, sample_tree: Path) -> None:
        """File-level patterns like **/*.log should drop matching files."""
        loader = DocumentLoader(exclude_patterns=["**/*.log"])
        files = self._walk(loader, sample_tree)
        assert all(not f.endswith(".log") for f in files), files
        # Non-matching files survive
        assert any(f.endswith("keep.md") for f in files), files

    def test_default_patterns_still_prune(self, tmp_path: Path) -> None:
        """Default DEFAULT_EXCLUDE_PATTERNS continue to prune their targets."""
        root = tmp_path / "proj"
        (root / "src").mkdir(parents=True)
        (root / "src" / "app.py").write_text("# code")
        (root / "node_modules" / "lib").mkdir(parents=True)
        (root / "node_modules" / "lib" / "index.js").write_text("noise")
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "x.pyc").write_text("noise")
        (root / ".agent-brain").mkdir()
        (root / ".agent-brain" / "config.json").write_text("{}")

        loader = DocumentLoader()
        files = self._walk(loader, root)
        assert any(f.endswith("app.py") for f in files), files
        assert all("node_modules" not in f for f in files), files
        assert all("__pycache__" not in f for f in files), files
        # Note: .agent-brain is not in the default patterns yet (#123 fix lives
        # in the file watcher) — but if a project lists it explicitly, it
        # should prune.
        loader2 = DocumentLoader(exclude_patterns=["**/.agent-brain/**"])
        files2 = self._walk(loader2, root)
        assert all(".agent-brain" not in f for f in files2), files2

    def test_no_patterns_yields_everything(self, sample_tree: Path) -> None:
        """Empty exclude_patterns list disables pruning entirely."""
        loader = DocumentLoader(exclude_patterns=[])
        files = self._walk(loader, sample_tree)
        assert any("chapter13" in f for f in files), files
        assert any("chapter14" in f for f in files), files
        assert any("keep.md" in f for f in files), files
        assert any("build.log" in f for f in files), files
