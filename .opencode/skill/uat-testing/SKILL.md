# Agent Brain UAT Testing

Run end-to-end User Acceptance Tests for Agent Brain features. Builds wheels, installs packages, starts a test server, runs tests, and reports results — all without permission prompts.

## Usage

Invoke via: `/uat-testing [test description or phase number]`

## How It Works

This skill delegates to the **uat-tester** agent which has pre-granted permissions for all operations needed during UAT: building, installing, starting servers, running curl, killing processes, etc.

## Running UAT Tests

When invoked, spawn the `uat-tester` agent with the test context:

```
Task(
  subagent_type="uat-tester",
  description="UAT: [test description]",
  prompt="[full test instructions]"
)
```

### Example: Single Test

```
/uat-testing cache clear should complete in < 10s during active indexing
```

This will:
1. Build and install the server wheel
2. Start a test server on port 8111
3. Kick off indexing
4. Run `cache clear` and time it
5. Report PASS/FAIL
6. Clean up

### Example: Phase UAT

```
/uat-testing phase 16
```

This will read the UAT test plan from `.planning/phases/16-embedding-cache/16-UAT.md` and run all tests.

## Test Server Configuration

The agent uses an isolated test server to avoid interfering with any running instances:
- **Port**: 8111
- **State dir**: `/tmp/uat-test/.claude/agent-brain`
- **Mode**: project
- **API keys**: sourced from `agent-brain-server/.env`

## What the Agent Can Do (No Prompts Needed)

- Build wheels (`poetry build`)
- Install packages (`uv pip install`)
- Start/stop servers (`agent-brain-serve`, `pkill`)
- HTTP requests (`curl`)
- Process management (`ps`, `lsof`, `kill`)
- File operations (read, write, glob, grep)
- Timing operations
- Run quality checks (`task before-push`)
- Git operations (read-only)
