import pytest

from doc_serve_server.indexing.chunking import CodeChunker, LoadedDocument


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
