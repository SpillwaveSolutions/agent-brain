# Quickstart: C# Code Indexing

## Index a C# Project

### 1. Start doc-serve

```bash
cd /path/to/my-csharp-project
doc-serve start
```

### 2. Index with code support

```bash
doc-serve index /path/to/my-csharp-project/src --include-code
```

The system automatically detects `.cs` and `.csx` files and parses them using AST-aware chunking.

### 3. Query C# code

```bash
# Search for a specific method
doc-serve query "GetUserById method"

# Filter to C# results only
doc-serve query "authentication" --language csharp
```

### 4. Verify C# indexing

```bash
doc-serve status
# → Indexed: 1,234 chunks from 56 files
# → Languages: python (20), csharp (15), typescript (21)
```

## What Gets Extracted

For a C# file like:

```csharp
/// <summary>
/// Manages user authentication and session handling.
/// </summary>
public class AuthService
{
    /// <summary>
    /// Authenticates a user by email and password.
    /// </summary>
    /// <param name="email">User's email address</param>
    /// <returns>Authentication result with session token</returns>
    public async Task<AuthResult> LoginAsync(string email, string password)
    {
        // ...
    }
}
```

Doc-serve extracts:
- **Symbol name**: `LoginAsync`
- **Symbol kind**: `method_declaration`
- **Parameters**: `string email, string password`
- **Return type**: `Task<AuthResult>`
- **Docstring**: "Authenticates a user by email and password."
- **Line numbers**: start/end line of the method

## Supported C# Constructs

| Construct | Extracted As |
|-----------|-------------|
| Classes | `class_declaration` |
| Methods | `method_declaration` |
| Constructors | `constructor_declaration` |
| Interfaces | `interface_declaration` |
| Properties | `property_declaration` |
| Enums | `enum_declaration` |
| Structs | `struct_declaration` |
| Records | `record_declaration` |
| Namespaces | `namespace_declaration` |

## Verification Checklist

- [ ] `.cs` files are detected and loaded during indexing
- [ ] `.csx` files are also detected and loaded
- [ ] C# code is chunked at class/method boundaries (not arbitrary line splits)
- [ ] Symbol metadata (name, kind, parameters, return type) is present in query results
- [ ] XML doc comments (`///`) are extracted as docstring metadata
- [ ] `--language csharp` filter returns only C# results
- [ ] C# files with syntax errors fall back to text-based chunking (not skipped)
