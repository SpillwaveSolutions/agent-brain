---
name: agent-brain-config
description: Configure API keys for Agent Brain (OPENAI_API_KEY, ANTHROPIC_API_KEY)
parameters: []
skills:
  - configuring-agent-brain
---

# Configure Agent Brain API Keys

## Purpose

Guides users through configuring the required API keys for Agent Brain. The OpenAI API key is required for vector and hybrid search modes. The Anthropic API key is optional and enables code summarization features.

## Usage

```
/agent-brain-config
```

## Execution

### Step 1: Check Current Configuration

```bash
echo "OpenAI: ${OPENAI_API_KEY:+SET}"
echo "Anthropic: ${ANTHROPIC_API_KEY:+SET}"
```

### Step 2: Guide API Key Setup

**For OPENAI_API_KEY (Required):**

1. Obtain key from: https://platform.openai.com/account/api-keys
2. Set environment variable:

```bash
# Temporary (current session only)
export OPENAI_API_KEY="sk-proj-..."

# Permanent (add to shell profile)
echo 'export OPENAI_API_KEY="sk-proj-..."' >> ~/.bashrc
source ~/.bashrc

# Or for zsh
echo 'export OPENAI_API_KEY="sk-proj-..."' >> ~/.zshrc
source ~/.zshrc
```

**For ANTHROPIC_API_KEY (Optional):**

1. Obtain key from: https://console.anthropic.com/
2. Set environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Step 3: Verify Configuration

```bash
# Test OpenAI key
curl -s https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -c 100
```

If successful, shows model data. If failed, shows error message.

## Output

```
Agent Brain Configuration
=========================

Checking current configuration...

API Keys Status:
  OPENAI_API_KEY:    SET [OK]
  ANTHROPIC_API_KEY: NOT SET (optional)

OpenAI API Key
--------------
Status: Configured
Test: Connection successful

Anthropic API Key (Optional)
----------------------------
Status: Not configured
Note: Only needed for code summarization features

Configuration complete!

To add Anthropic key later:
  export ANTHROPIC_API_KEY="sk-ant-..."
```

When keys are missing:

```
Agent Brain Configuration
=========================

API Keys Status:
  OPENAI_API_KEY:    NOT SET [REQUIRED]
  ANTHROPIC_API_KEY: NOT SET (optional)

OpenAI API Key Setup (Required)
-------------------------------
The OpenAI API key is required for semantic search.

1. Get your API key:
   https://platform.openai.com/account/api-keys

2. Set the environment variable:

   # For current session:
   export OPENAI_API_KEY="sk-proj-..."

   # To make permanent, add to your shell profile:
   echo 'export OPENAI_API_KEY="your-key"' >> ~/.bashrc
   source ~/.bashrc

3. Verify with: /agent-brain-config

Security Notes:
- Never commit API keys to version control
- Never share keys in chat or logs
- Add .env to .gitignore
```

## Error Handling

### Invalid API Key Format

```
Warning: API key format appears invalid.

OpenAI keys should start with: sk-proj- or sk-
Anthropic keys should start with: sk-ant-

Please verify you copied the complete key.
```

### API Key Test Failed

```
OpenAI API Key Test: FAILED

Error: Invalid API key

Possible issues:
1. Key was copied incorrectly (missing characters)
2. Key has been revoked or expired
3. Key has no API access (check OpenAI dashboard)

Steps to resolve:
1. Visit https://platform.openai.com/account/api-keys
2. Create a new API key
3. Copy the COMPLETE key (it's only shown once)
4. Run: export OPENAI_API_KEY="new-key"
5. Retry: /agent-brain-config
```

### Rate Limit or Quota Issues

```
OpenAI API Key Test: RATE LIMITED

Your API key is valid but rate limited.

This could mean:
1. Free tier limits reached
2. Usage quota exceeded
3. Too many requests

Check your usage: https://platform.openai.com/usage
```

## Security Guidance

**IMPORTANT: Never commit API keys to version control!**

Recommended practices:
1. Use environment variables, not hardcoded values
2. Add `.env` files to `.gitignore`
3. Use secret management for production
4. Rotate keys periodically
5. Use separate keys for development and production

Check your `.gitignore`:

```bash
# Ensure .env is ignored
grep -q "\.env" .gitignore || echo ".env" >> .gitignore
```
