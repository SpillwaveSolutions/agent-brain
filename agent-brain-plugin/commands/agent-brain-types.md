---
name: agent-brain-types
description: List available file type presets for indexing
parameters: []
skills:
  - using-agent-brain
---

# File Type Presets

## Purpose

Show all available file type presets that can be used with the `--include-type`
flag during indexing. Presets are named groups of glob patterns that make it
easy to index specific categories of files without writing individual patterns.

## Usage

```
/agent-brain-types
```

### Examples

```
/agent-brain-types
```

## Execution

Display all available file type presets:

```bash
agent-brain types list
```

### Expected Output

```
Preset       Extensions
python       *.py, *.pyi, *.pyw
javascript   *.js, *.jsx, *.mjs, *.cjs
typescript   *.ts, *.tsx
go           *.go
rust         *.rs
java         *.java
csharp       *.cs
c            *.c, *.h
cpp          *.cpp, *.hpp, *.cc, *.hh
web          *.html, *.css, *.scss, *.jsx, *.tsx
docs         *.md, *.txt, *.rst, *.pdf
text         *.md, *.txt, *.rst
pdf          *.pdf
code         *.py, *.pyi, *.pyw, *.js, *.jsx, ...

Use with: agent-brain index <path> --include-type <preset>
```

## Output

Show the preset table and explain how to use presets with the index command.
Provide examples of combining presets:

```bash
# Index only Python files
agent-brain index ./src --include-type python

# Index Python and documentation files
agent-brain index ./project --include-type python,docs

# Index all code files
agent-brain index ./repo --include-type code

# Combine presets with custom patterns
agent-brain index ./project --include-type typescript --include-patterns "*.json"
```

## Notes

- Presets can be combined with commas: `--include-type python,docs`
- Presets can be combined with `--include-patterns` for custom patterns
- The `code` preset is a union of all language presets
- These presets are local (no server connection required)
- Use `agent-brain index --help` to see all indexing options
