# Runtime parity fixture template

This checked-in project is the source template for disposable runtime parity
workspaces created under `e2e_workdir/<run-id>/<adapter>/<scenario>/<runtime>-runtime/`.

It must stay pristine between test runs and must not contain pre-generated
runtime install directories such as `.codex/`, `.opencode/`, `.gemini/`, or
`.agent-brain/`.

Each disposable runtime workspace also includes sibling `cleanup/` and `logs/`
directories that are generated at runtime and must not be checked in here.
