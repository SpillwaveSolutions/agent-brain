# PyPI Trusted Publisher Setup Guide

This document describes how to configure PyPI Trusted Publisher (OIDC) authentication for Agent Brain packages.

## Overview

PyPI Trusted Publisher uses OpenID Connect (OIDC) to authenticate GitHub Actions workflows without requiring API tokens. This is more secure and easier to maintain than traditional token-based authentication.

## Prerequisites

1. PyPI account with owner access to both packages:
   - https://pypi.org/project/agent-brain-rag/
   - https://pypi.org/project/agent-brain-cli/

2. GitHub repository owner access to:
   - https://github.com/SpillwaveSolutions/agent-brain

## Step 1: Configure agent-brain-rag on PyPI

1. **Log in to PyPI**: https://pypi.org/account/login/

2. **Navigate to publishing settings**:
   - Go to: https://pypi.org/manage/project/agent-brain-rag/settings/publishing/
   - Or: Your Projects → agent-brain-rag → Settings → Publishing

3. **Add a new trusted publisher**:
   - Click "Add a new publisher"
   - Select "GitHub Actions"

4. **Fill in the form**:

   | Field | Value |
   |-------|-------|
   | Owner | `SpillwaveSolutions` |
   | Repository name | `agent-brain` |
   | Workflow name | `publish-to-pypi.yml` |
   | Environment name | `pypi` |

5. **Click "Add"** to save

## Step 2: Configure agent-brain-cli on PyPI

1. **Navigate to publishing settings**:
   - Go to: https://pypi.org/manage/project/agent-brain-cli/settings/publishing/

2. **Add a new trusted publisher** with the same values:

   | Field | Value |
   |-------|-------|
   | Owner | `SpillwaveSolutions` |
   | Repository name | `agent-brain` |
   | Workflow name | `publish-to-pypi.yml` |
   | Environment name | `pypi` |

3. **Click "Add"** to save

## Step 3: Create GitHub Environment

1. **Go to repository settings**:
   - https://github.com/SpillwaveSolutions/agent-brain/settings/environments

2. **Create new environment**:
   - Click "New environment"
   - Name: `pypi`
   - Click "Configure environment"

3. **Optional protections** (recommended):
   - Enable "Required reviewers" - add maintainers
   - Enable "Deployment branches" - select "main" only
   - This prevents accidental releases from feature branches

4. **Click "Save protection rules"**

## Verification

After setup, verify the configuration:

### PyPI Side
1. Go to each package's publishing settings
2. Confirm "Trusted Publishers" shows your GitHub Actions configuration
3. Look for entry with `SpillwaveSolutions/agent-brain` and `publish-to-pypi.yml`

### GitHub Side
1. Go to repository Settings → Environments
2. Confirm `pypi` environment exists
3. Check protection rules if configured

### Test Release
1. Create a test release on GitHub
2. Watch the Actions tab for the `publish-to-pypi` workflow
3. Verify both packages published successfully
4. Check PyPI for new versions

## Troubleshooting

### Error: "Token request failed"

**Symptoms:**
```
Error: Token request failed: ...
```

**Solutions:**
1. Verify workflow name matches exactly: `publish-to-pypi.yml`
2. Check environment name is `pypi` (case-sensitive)
3. Ensure repository name is correct: `agent-brain`

### Error: "Publisher not configured"

**Symptoms:**
```
Error: The server could not find a trusted publisher for this upload
```

**Solutions:**
1. Double-check trusted publisher configuration on PyPI
2. Verify the GitHub organization/owner is `SpillwaveSolutions`
3. Make sure the workflow has `id-token: write` permission

### Error: "Environment not found"

**Symptoms:**
```
Error: Environment 'pypi' was not found
```

**Solutions:**
1. Create the `pypi` environment in GitHub repository settings
2. Ensure the environment name matches exactly (case-sensitive)

## Workflow Requirements

The GitHub Action workflow must include these elements:

```yaml
permissions:
  contents: read
  id-token: write  # Required for OIDC

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi  # Must match PyPI configuration

    steps:
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: path/to/dist/
```

## Security Notes

- **No API tokens needed**: OIDC eliminates the need for long-lived secrets
- **Environment protection**: Use deployment rules to require approvals
- **Branch restrictions**: Limit deployments to `main` branch only
- **Audit trail**: All releases are linked to specific GitHub Actions runs

## References

- [PyPI Trusted Publishers Documentation](https://docs.pypi.org/trusted-publishers/)
- [GitHub Actions OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [PyPI Publishing Action](https://github.com/pypa/gh-action-pypi-publish)
