"""Tests for FileTypePresetResolver (file_type_presets module)."""

from __future__ import annotations

import pytest

from agent_brain_server.services.file_type_presets import (
    FILE_TYPE_PRESETS,
    list_presets,
    resolve_file_types,
)


class TestResolveFileTypes:
    """Tests for resolve_file_types()."""

    def test_single_preset_python(self) -> None:
        """Test resolving the 'python' preset returns its patterns."""
        result = resolve_file_types(["python"])
        assert result == ["*.py", "*.pyi", "*.pyw"]

    def test_single_preset_go(self) -> None:
        """Test resolving single-pattern presets."""
        result = resolve_file_types(["go"])
        assert result == ["*.go"]

    def test_single_preset_rust(self) -> None:
        """Test resolving the 'rust' preset."""
        result = resolve_file_types(["rust"])
        assert result == ["*.rs"]

    def test_single_preset_typescript(self) -> None:
        """Test resolving the 'typescript' preset."""
        result = resolve_file_types(["typescript"])
        assert result == ["*.ts", "*.tsx"]

    def test_multiple_presets_combined(self) -> None:
        """Test combining multiple presets returns all patterns."""
        result = resolve_file_types(["python", "go"])
        assert "*.py" in result
        assert "*.pyi" in result
        assert "*.pyw" in result
        assert "*.go" in result

    def test_multiple_presets_deduplicated(self) -> None:
        """Test overlapping presets produce deduplicated patterns."""
        # Both 'web' and 'typescript' have *.tsx and *.jsx
        result = resolve_file_types(["typescript", "web"])
        assert result.count("*.tsx") == 1
        assert result.count("*.jsx") == 1

    def test_python_and_docs_combined(self) -> None:
        """Test combining python and docs presets."""
        result = resolve_file_types(["python", "docs"])
        expected_patterns = ["*.py", "*.pyi", "*.pyw", "*.md", "*.txt", "*.rst", "*.pdf"]
        assert result == expected_patterns

    def test_unknown_preset_raises_value_error(self) -> None:
        """Test that unknown preset name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown file type preset 'foobar'"):
            resolve_file_types(["foobar"])

    def test_unknown_preset_message_lists_valid_presets(self) -> None:
        """Test that ValueError message includes list of valid presets."""
        with pytest.raises(ValueError) as exc_info:
            resolve_file_types(["not_a_preset"])

        error_msg = str(exc_info.value)
        assert "Valid presets:" in error_msg
        # All preset names should appear in the error message
        for preset_name in FILE_TYPE_PRESETS:
            assert preset_name in error_msg

    def test_unknown_preset_mixed_with_valid(self) -> None:
        """Test that unknown preset in a list raises ValueError."""
        with pytest.raises(ValueError, match="Unknown file type preset 'invalid'"):
            resolve_file_types(["python", "invalid"])

    def test_empty_list_returns_empty(self) -> None:
        """Test that empty input returns empty list."""
        result = resolve_file_types([])
        assert result == []

    def test_code_preset_includes_all_languages(self) -> None:
        """Test that 'code' preset contains patterns from all language presets."""
        code_patterns = resolve_file_types(["code"])

        # Should include patterns from each language preset
        language_presets = [
            "python",
            "javascript",
            "typescript",
            "go",
            "rust",
            "java",
            "csharp",
            "c",
            "cpp",
        ]
        for lang in language_presets:
            lang_patterns = resolve_file_types([lang])
            for pattern in lang_patterns:
                assert pattern in code_patterns, (
                    f"Pattern '{pattern}' from preset '{lang}' "
                    f"not found in 'code' preset"
                )

    def test_code_preset_deduplicated(self) -> None:
        """Test that 'code' preset has no duplicate patterns."""
        code_patterns = resolve_file_types(["code"])
        assert len(code_patterns) == len(set(code_patterns)), (
            "Code preset contains duplicate patterns"
        )

    def test_text_preset_patterns(self) -> None:
        """Test the 'text' preset patterns."""
        result = resolve_file_types(["text"])
        assert result == ["*.md", "*.txt", "*.rst"]

    def test_pdf_preset_patterns(self) -> None:
        """Test the 'pdf' preset patterns."""
        result = resolve_file_types(["pdf"])
        assert result == ["*.pdf"]

    def test_docs_vs_text_difference(self) -> None:
        """Test that 'docs' includes *.pdf but 'text' does not."""
        docs_patterns = resolve_file_types(["docs"])
        text_patterns = resolve_file_types(["text"])

        assert "*.pdf" in docs_patterns
        assert "*.pdf" not in text_patterns

    def test_order_preserved_first_occurrence(self) -> None:
        """Test that pattern order follows first occurrence across presets."""
        # python comes first, so python patterns should appear first
        result = resolve_file_types(["python", "go"])
        py_index = result.index("*.py")
        go_index = result.index("*.go")
        assert py_index < go_index

    def test_web_preset_patterns(self) -> None:
        """Test the 'web' preset contains expected patterns."""
        result = resolve_file_types(["web"])
        assert "*.html" in result
        assert "*.css" in result
        assert "*.scss" in result
        assert "*.jsx" in result
        assert "*.tsx" in result

    def test_cpp_preset_patterns(self) -> None:
        """Test the 'cpp' preset patterns."""
        result = resolve_file_types(["cpp"])
        assert result == ["*.cpp", "*.hpp", "*.cc", "*.hh"]

    def test_csharp_preset_patterns(self) -> None:
        """Test the 'csharp' preset patterns."""
        result = resolve_file_types(["csharp"])
        assert result == ["*.cs"]

    def test_java_preset_patterns(self) -> None:
        """Test the 'java' preset patterns."""
        result = resolve_file_types(["java"])
        assert result == ["*.java"]

    def test_c_preset_patterns(self) -> None:
        """Test the 'c' preset patterns."""
        result = resolve_file_types(["c"])
        assert result == ["*.c", "*.h"]

    def test_all_14_presets_exist(self) -> None:
        """Test that all 14 expected presets are defined."""
        expected_presets = {
            "python",
            "javascript",
            "typescript",
            "go",
            "rust",
            "java",
            "csharp",
            "c",
            "cpp",
            "web",
            "docs",
            "code",
            "text",
            "pdf",
        }
        assert set(FILE_TYPE_PRESETS.keys()) == expected_presets


class TestListPresets:
    """Tests for list_presets()."""

    def test_returns_all_presets(self) -> None:
        """Test that list_presets returns all preset names."""
        presets = list_presets()
        assert len(presets) == len(FILE_TYPE_PRESETS)
        for name in FILE_TYPE_PRESETS:
            assert name in presets

    def test_returns_copy(self) -> None:
        """Test that list_presets returns a copy (mutations don't affect original)."""
        presets = list_presets()
        presets["new_preset"] = ["*.xyz"]
        # Original should be unchanged
        assert "new_preset" not in FILE_TYPE_PRESETS

    def test_preset_values_are_lists(self) -> None:
        """Test that all preset values are lists of strings."""
        presets = list_presets()
        for name, patterns in presets.items():
            assert isinstance(patterns, list), f"Preset '{name}' value is not a list"
            for pattern in patterns:
                assert isinstance(pattern, str), (
                    f"Pattern '{pattern}' in preset '{name}' is not a string"
                )
