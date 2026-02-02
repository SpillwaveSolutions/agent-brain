---
name: agent-brain-install
description: Install Agent Brain packages (agent-brain-rag and agent-brain-cli)
parameters: []
skills:
  - configuring-agent-brain
---

# Install Agent Brain Packages

## Purpose

Installs the Agent Brain Python packages required for document indexing and semantic search. This command installs both `agent-brain-rag` (the server component) and `agent-brain-cli` (the command-line interface).

## Usage

```
/agent-brain-install
```

## Execution

### Step 1: Check Python Version

```bash
python --version
```

Python 3.10 or higher is required. If the version is lower, guide the user to upgrade Python first.

### Step 2: Install Packages

```bash
pip install agent-brain-rag agent-brain-cli
```

**Virtual Environment Recommended:**

For isolated installations, recommend using a virtual environment:

```bash
# Create virtual environment
python -m venv .venv

# Activate (macOS/Linux)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install packages
pip install agent-brain-rag agent-brain-cli
```

### Step 3: Verify Installation

```bash
agent-brain --version
```

Expected output shows the installed version number.

## Output

Format the results as follows:

```
Agent Brain Installation
========================

Python Version: 3.11.4 [OK]
Installing packages...

Installed:
  - agent-brain-rag: 1.2.0
  - agent-brain-cli: 1.2.0

Verification: agent-brain --version
  Version: 1.2.0 [OK]

Installation complete!

Next steps:
  1. Configure API keys: /agent-brain-config
  2. Initialize project: /agent-brain-init
  3. Start server: /agent-brain-start
```

## Error Handling

### Python Version Too Low

```
Python version 3.8 detected. Agent Brain requires Python 3.10+.

Solutions:
1. Install Python 3.10+ from https://python.org/downloads/
2. Use pyenv: pyenv install 3.11 && pyenv local 3.11
3. Use conda: conda create -n agent-brain python=3.11
```

### Permission Denied

```
Permission denied during installation.

Solutions:
1. Use --user flag: pip install --user agent-brain-rag agent-brain-cli
2. Use virtual environment (recommended)
3. On Linux/macOS, avoid using sudo with pip
```

### pip Not Found

```
pip command not found.

Solutions:
1. Ensure pip: python -m ensurepip
2. Install pip: python -m pip install --upgrade pip
3. Use python -m pip instead of pip
```

### Module Not Found After Install

```
Cannot find agent-brain command after installation.

Solutions:
1. Restart your terminal
2. Check PATH includes pip bin directory
3. Use: python -m agent_brain_cli instead
4. Reinstall: pip install --force-reinstall agent-brain-cli
```

### Upgrade Existing Installation

If already installed, upgrade with:

```bash
pip install --upgrade agent-brain-rag agent-brain-cli
```
