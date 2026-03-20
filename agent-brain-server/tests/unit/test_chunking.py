from pathlib import Path

import pytest

from agent_brain_server.indexing.chunking import CodeChunker, LoadedDocument

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.mark.asyncio
async def test_code_chunker_python_ast():
    # Make code longer to force splitting
    code = (
        """def hello(name):
    \"\"\"Greet someone.\"\"\"
    return f"Hello, {name}!"

# Some padding to force a split
# """
        + ("# padding\n" * 20)
        + """

class Greeter:
    def __init__(self, greeting):
        self.greeting = greeting

    def greet(self, name):
        return f"{self.greeting}, {name}!"
"""
    )
    doc = LoadedDocument(
        text=code,
        source="test.py",
        file_name="test.py",
        file_path="test.py",
        file_size=len(code),
        metadata={"source_type": "code", "language": "python"},
    )

    chunker = CodeChunker(
        language="python", chunk_lines=2, max_chars=100
    )  # Very small to force splitting
    chunks = await chunker.chunk_code_document(doc)

    assert len(chunks) > 0

    # Check symbols found in any chunk
    symbol_names = [c.metadata.symbol_name for c in chunks if c.metadata.symbol_name]
    assert "hello" in symbol_names
    assert "Greeter" in symbol_names


@pytest.mark.asyncio
async def test_code_chunker_typescript_ast():
    # Make code longer to force splitting
    code = (
        """function add(a: number, b: number): number {
    return a + b;
}

// Padding
"""
        + ("// padding\n" * 20)
        + """

export class Calculator {
    multiply(a: number, b: number): number {
        return a * b;
    }
}

const subtract = (a: number, b: number) => a - b;
"""
    )
    doc = LoadedDocument(
        text=code,
        source="test.ts",
        file_name="test.ts",
        file_path="test.ts",
        file_size=len(code),
        metadata={"source_type": "code", "language": "typescript"},
    )

    chunker = CodeChunker(language="typescript", chunk_lines=5, max_chars=100)
    chunks = await chunker.chunk_code_document(doc)

    assert len(chunks) > 0

    # Check symbols
    symbol_names = [c.metadata.symbol_name for c in chunks if c.metadata.symbol_name]
    assert "add" in symbol_names
    # Calculator might be shadowed by multiply if they start in the same chunk
    assert "Calculator" in symbol_names or "multiply" in symbol_names
    assert "subtract" in symbol_names


@pytest.mark.asyncio
async def test_code_chunker_fallback_on_error():
    # Invalid python code (syntax error)
    code = "def hello(name"
    doc = LoadedDocument(
        text=code,
        source="test.py",
        file_name="test.py",
        file_path="test.py",
        file_size=len(code),
        metadata={"source_type": "code", "language": "python"},
    )

    chunker = CodeChunker(language="python")
    chunks = await chunker.chunk_code_document(doc)

    # Should still produce chunks even if AST parsing is limited
    assert len(chunks) > 0
    assert chunks[0].text == code


# --- C# Code Chunker Tests ---


def test_csharp_code_chunker_initialization() -> None:
    """Test CodeChunker can be initialized for csharp."""
    chunker = CodeChunker(language="csharp")
    assert chunker.language == "csharp"
    assert chunker.ts_language is not None


def test_csharp_symbol_extraction_basic() -> None:
    """Test symbol extraction from basic C# code."""
    chunker = CodeChunker(language="csharp")
    code = """using System;
namespace MyApp {
    public class Calculator {
        public int Add(int a, int b) {
            return a + b;
        }
    }
}"""
    symbols = chunker._get_symbols(code)
    symbol_names = [s["name"] for s in symbols]
    assert "Calculator" in symbol_names
    assert "Add" in symbol_names
    assert "MyApp" in symbol_names


def test_csharp_symbol_extraction_all_types() -> None:
    """Test symbol extraction detects all C# declaration types."""
    chunker = CodeChunker(language="csharp")
    code = """namespace TestNs {
    public interface IService {
        void Run();
    }
    public class Service : IService {
        public string Name { get; set; }
        public Service(string name) { Name = name; }
        public void Run() { }
    }
    public enum Status { Active, Inactive }
    public struct Point { public int X; }
    public record Person(string Name, int Age);
}"""
    symbols = chunker._get_symbols(code)
    symbol_names = [s["name"] for s in symbols]
    symbol_kinds = [s["kind"] for s in symbols]

    assert "TestNs" in symbol_names
    assert "IService" in symbol_names
    assert "Service" in symbol_names
    assert "Name" in symbol_names  # Property
    assert "Run" in symbol_names  # Method
    assert "Status" in symbol_names
    assert "Point" in symbol_names
    assert "Person" in symbol_names

    assert "namespace_declaration" in symbol_kinds
    assert "interface_declaration" in symbol_kinds
    assert "class_declaration" in symbol_kinds
    assert "enum_declaration" in symbol_kinds
    assert "struct_declaration" in symbol_kinds
    assert "record_declaration" in symbol_kinds
    assert "property_declaration" in symbol_kinds


def test_csharp_xml_doc_comment_extraction() -> None:
    """Test XML doc comment extraction for C# symbols."""
    chunker = CodeChunker(language="csharp")
    code = """/// <summary>
/// A simple calculator class.
/// </summary>
public class Calculator {
    /// <summary>Adds two numbers.</summary>
    public int Add(int a, int b) {
        return a + b;
    }
}"""
    symbols = chunker._get_symbols(code)

    # Find the Calculator class symbol
    calc_symbol = next(s for s in symbols if s["name"] == "Calculator")
    assert "docstring" in calc_symbol
    assert "simple calculator class" in calc_symbol["docstring"].lower()

    # Find the Add method symbol
    add_symbol = next(s for s in symbols if s["name"] == "Add")
    assert "docstring" in add_symbol
    assert "adds two numbers" in add_symbol["docstring"].lower()


def test_csharp_xml_doc_comment_with_attribute() -> None:
    """Test XML doc comment extraction skips attributes."""
    chunker = CodeChunker(language="csharp")
    code = """/// <summary>
/// A serializable document.
/// </summary>
[Serializable]
public class Document {
}"""
    symbols = chunker._get_symbols(code)
    doc_symbol = next(s for s in symbols if s["name"] == "Document")
    assert "docstring" in doc_symbol
    assert "serializable document" in doc_symbol["docstring"].lower()


def test_csharp_symbol_without_doc_comment() -> None:
    """Test symbols without doc comments have no docstring."""
    chunker = CodeChunker(language="csharp")
    code = """public class Simple {
    public void DoWork() { }
}"""
    symbols = chunker._get_symbols(code)
    simple_symbol = next(s for s in symbols if s["name"] == "Simple")
    assert "docstring" not in simple_symbol


def test_csharp_fixture_file_symbols() -> None:
    """Test symbol extraction from the sample.cs fixture file."""
    fixture_path = FIXTURES_DIR / "sample.cs"
    if not fixture_path.exists():
        pytest.skip("sample.cs fixture not found")

    code = fixture_path.read_text()
    chunker = CodeChunker(language="csharp")
    symbols = chunker._get_symbols(code)
    symbol_names = [s["name"] for s in symbols]

    # Verify key declarations from sample.cs
    assert "IDocument" in symbol_names
    assert "DocumentType" in symbol_names
    assert "Position" in symbol_names
    assert "DocumentMetadata" in symbol_names
    assert "SearchableDocument" in symbol_names
    assert "GetContent" in symbol_names
    assert "ChunkContent" in symbol_names
    assert "Search" in symbol_names


@pytest.mark.asyncio
async def test_csharp_code_chunker_chunking() -> None:
    """Test full chunking pipeline for C# code."""
    code = (
        """using System;
namespace MyApp {
    /// <summary>
    /// A calculator class.
    /// </summary>
    public class Calculator {
        public int Add(int a, int b) {
            return a + b;
        }
    }
}

// padding
"""
        + ("// padding line\n" * 30)
        + """
namespace MyApp {
    public class Logger {
        public void Log(string message) {
            Console.WriteLine(message);
        }
    }
}
"""
    )
    doc = LoadedDocument(
        text=code,
        source="test.cs",
        file_name="test.cs",
        file_path="test.cs",
        file_size=len(code),
        metadata={"source_type": "code", "language": "csharp"},
    )

    chunker = CodeChunker(language="csharp", chunk_lines=5, max_chars=200)
    chunks = await chunker.chunk_code_document(doc)

    assert len(chunks) > 0

    # Check that symbols are found across chunks
    symbol_names = [c.metadata.symbol_name for c in chunks if c.metadata.symbol_name]
    assert "Calculator" in symbol_names or "Add" in symbol_names


def test_pascal_code_chunker_initialization() -> None:
    """Test CodeChunker can be initialized for pascal."""
    chunker = CodeChunker(language="pascal")
    assert chunker.language == "pascal"
    assert chunker.ts_language is not None


def test_pascal_symbol_extraction_basic() -> None:
    """Test standalone Pascal procedure/function extraction."""
    chunker = CodeChunker(language="pascal")
    code = """unit Demo;

interface

procedure PrintValue;
function Area: Double;

implementation

procedure PrintValue;
begin
end;

function Area: Double;
begin
  Result := 42.0;
end;

end.
"""
    symbols = chunker._get_symbols(code)
    names = [s["name"] for s in symbols]

    assert "PrintValue" in names
    assert "Area" in names


def test_pascal_symbol_extraction_class() -> None:
    """Test Pascal class and qualified method extraction."""
    chunker = CodeChunker(language="pascal")
    code = """unit Shapes;

interface

type
  TShape = class
  public
    procedure Draw; virtual;
  end;

  TCircle = class(TShape)
  public
    procedure TCircle.SetRadius(const Value: Double);
    function TCircle.GetDiameter: Double;
  end;

implementation
end.
"""
    symbols = chunker._get_symbols(code)
    names = [s["name"] for s in symbols]

    assert "TShape" in names
    assert "TCircle" in names
    assert "TCircle.SetRadius" in names
    assert "TCircle.GetDiameter" in names


def test_pascal_fixture_file_symbols() -> None:
    """Test symbol extraction from the sample.pas fixture file."""
    fixture_path = FIXTURES_DIR / "sample.pas"
    if not fixture_path.exists():
        pytest.skip("sample.pas fixture not found")

    code = fixture_path.read_text()
    chunker = CodeChunker(language="pascal")
    symbols = chunker._get_symbols(code)
    names = [s["name"] for s in symbols]

    assert "TPoint" in names
    assert "TShape" in names
    assert "TCircle" in names
    assert "TRectangle" in names
    assert "TCircle.SetRadius" in names
    assert "TCircle.GetDiameter" in names
    assert "ClampValue" in names
    assert "PrintShapeInfo" in names


@pytest.mark.asyncio
async def test_pascal_code_chunker_chunking() -> None:
    """Test full chunking pipeline for Pascal code."""
    fixture_path = FIXTURES_DIR / "sample.pas"
    if not fixture_path.exists():
        pytest.skip("sample.pas fixture not found")

    code = fixture_path.read_text()
    doc = LoadedDocument(
        text=code,
        source="sample.pas",
        file_name="sample.pas",
        file_path="sample.pas",
        file_size=len(code),
        metadata={"source_type": "code", "language": "pascal"},
    )

    chunker = CodeChunker(language="pascal", chunk_lines=8, max_chars=220)
    chunks = await chunker.chunk_code_document(doc)

    assert len(chunks) > 0
    names = [c.metadata.symbol_name for c in chunks if c.metadata.symbol_name]
    assert any(name in names for name in ["TCircle", "TCircle.SetRadius", "ClampValue"])
