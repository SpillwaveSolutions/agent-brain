---
name: agent-brain-install
description: Install Agent Brain packages using pipx, uv, pip, or conda
parameters: []
skills:
  - configuring-agent-brain
---

# Install Agent Brain Packages

## STOP - READ THIS FIRST

**DO NOT RUN ANY INSTALLATION COMMANDS YET.**

You MUST ask the user which installation method they prefer using the AskUserQuestion tool BEFORE doing anything else.

## Step 1: Ask User for Installation Method

**THIS IS MANDATORY. DO NOT SKIP THIS STEP.**

Use the AskUserQuestion tool with this exact structure:

```json
{
  "questions": [{
    "question": "Which installation method do you prefer for Agent Brain?",
    "header": "Install via",
    "options": [
      {
        "label": "pipx (Recommended)",
        "description": "Install globally in an isolated environment. No activation needed."
      },
      {
        "label": "uv",
        "description": "Fast, modern Python tool installer. Good for power users."
      },
      {
        "label": "pip (venv)",
        "description": "Install into a local virtual environment. Requires activation."
      },
      {
        "label": "conda",
        "description": "For conda users. Creates a conda environment with pip inside."
      }
    ],
    "multiSelect": false
  }]
}
```

**STOP HERE AND WAIT FOR THE USER'S RESPONSE.**

Do not proceed until you have called AskUserQuestion and received the user's selection.

---

## Step 1.5: Resolve Version

After receiving the user's installation method choice, resolve the latest version from PyPI:

```bash
# Get latest version from PyPI
VERSION=$(curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")
echo "Latest available: $VERSION"
```

Then ask user for version preference using AskUserQuestion:

```json
{
  "questions": [{
    "question": "Which version of Agent Brain do you want to install?",
    "header": "Version",
    "options": [
      {
        "label": "Latest ($VERSION) (Recommended)",
        "description": "Install the latest stable release from PyPI."
      },
      {
        "label": "Specific version",
        "description": "I'll show available versions and ask which one."
      }
    ],
    "multiSelect": false
  }]
}
```

If user selects "Specific version", show available versions:

```bash
curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "
import sys,json
releases = list(json.load(sys.stdin)['releases'].keys())
releases.sort(key=lambda v: [int(x) for x in v.split('.')], reverse=True)
print('Available versions:', ', '.join(releases[:8]))
"
```

Then ask the user to enter the specific version they want and store it in `$VERSION`.

---

## Step 2: Check Python Version

Only after receiving the user's installation method choice:

```bash
python --version
```

Requires Python 3.10+. If lower, tell user to upgrade first.

---

## Step 3: Execute Based on User's Selection

### If user selected "pipx (Recommended)"

1. Check/install pipx:
   ```bash
   pipx --version 2>/dev/null || python -m pip install --user pipx && python -m pipx ensurepath
   ```

2. Install Agent Brain with pinned version:
   ```bash
   pipx install agent-brain-cli==$VERSION
   ```

3. Verify (user may need to restart terminal):
   ```bash
   agent-brain --version
   ```

### If user selected "uv"

1. Check/install uv:
   ```bash
   uv --version 2>/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install Agent Brain with pinned version:
   ```bash
   uv tool install agent-brain-cli==$VERSION
   ```

3. Verify:
   ```bash
   agent-brain --version
   ```

### If user selected "pip (venv)"

1. Create virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   ```

2. Install packages with pinned version:
   ```bash
   pip install agent-brain-rag==$VERSION agent-brain-cli==$VERSION
   ```

3. Verify:
   ```bash
   agent-brain --version
   ```

4. **Tell user:** Must run `source .venv/bin/activate` before using agent-brain.

### If user selected "conda"

1. Create conda environment:
   ```bash
   conda create -n agent-brain python=3.12 -y
   conda activate agent-brain
   ```

2. Install packages with pinned version:
   ```bash
   pip install agent-brain-rag==$VERSION agent-brain-cli==$VERSION
   ```

3. Verify:
   ```bash
   agent-brain --version
   ```

4. **Tell user:** Must run `conda activate agent-brain` before using agent-brain.

---

## Success Output

After successful installation, show:

```
Agent Brain Installation Complete
=================================

Install Method: [method user selected]
Installed Version: $VERSION
Resolved from: PyPI (latest) or (user-specified)

Next steps:
  1. Configure: /agent-brain-config
  2. Initialize: /agent-brain-init
  3. Start server: /agent-brain-start
```

---

## Why Ask First?

Different methods have different trade-offs:

| Method | Global? | Isolated? | Needs Activation? |
|--------|---------|-----------|-------------------|
| pipx | Yes | Yes | No |
| uv | Yes | Yes | No |
| pip (venv) | No | Yes | Yes |
| conda | No | Yes | Yes |

- **pipx/uv**: Best for CLI tools - globally available, no activation
- **pip (venv)**: Best for project-specific installs
- **conda**: Best for data science users already using conda
