# Dev Environment Setup

How to set up and use the development environment for the window-project constraint engine.

## How it works

The entire development environment lives inside a Docker container. You do not need to clone the repo or install Python, Node, or any tooling on your local machine. The dev container includes everything: Python 3.14, test runners, linters, AI coding tools, and the GitHub CLI.

The project source code lives at `/workspaces/window-project` inside the container.

## Opening the project in VS Code

**Prerequisites:** [VS Code](https://code.visualstudio.com/) with the **Dev Containers** extension (`ms-vscode-remote.remote-containers`).

1. Open VS Code.
2. `Ctrl+Shift+P` -> **Dev Containers: Attach to Running Container...**
3. Select the container from the list.

VS Code opens with the workspace at `/workspaces/window-project`. The integrated terminal, Python interpreter, linters, and extensions all run inside the container rather than on your host. This means code execution uses the container's Python 3.14, installed packages, and tooling -- even though the files themselves are bind-mounted from your local machine.

You can still use your host tools (git, editors, CLI utilities) directly on the same files. The container is a convenience that provides a consistent, pre-configured environment -- it does not replace your local workflow.

### GitHub Codespaces

If the repo is hosted on GitHub, click **Code -> Codespaces -> New codespace**. GitHub builds the same dev container in the cloud -- no local Docker required.

## Running AI tools from the terminal

Once inside the container, run Claude Code or Codex directly:

```bash
claude    # Launch Claude Code
codex     # Launch Codex CLI
```

Both tools are pre-installed as global npm packages in the container image.

## Running the project

```bash
# Install/update dependencies
pip install -r requirements.txt

# Run all V1 tests
pytest engine_v1/tests/test_engine.py -v

# Run all V2 tests
pytest engine_v2/tests/ -v

# Launch web demo
python -m uvicorn demo.app:app --reload
```

## What the container provides

| Component | Detail |
|-----------|--------|
| Base image | `mcr.microsoft.com/devcontainers/python:3.14` |
| Python tooling | pip, uv, black, ruff, ipykernel, pytest |
| Node.js 20 | Required for Claude Code and Codex CLI |
| GitHub CLI | `gh` for pull requests, issues, and auth |
| Claude Code | `@anthropic-ai/claude-code` (global npm package) |
| Codex CLI | `@openai/codex` (global npm package) |

### VS Code extensions (auto-installed)

- Python (`ms-python.python`)
- Jupyter (`ms-toolsai.jupyter`, `ms-toolsai.vscode-jupyter-cell-tags`)
- Ruff (`charliermarsh.ruff`)
- Black Formatter (`ms-python.black-formatter`)

## Launching AI tools from Windows PowerShell (without VS Code)

If you have a local clone and have built the container at least once via VS Code, you can launch Claude Code or Codex from a Windows PowerShell terminal without VS Code open.

Add the PowerShell profile functions to your `$PROFILE`:

```powershell
. .devcontainer/Microsoft.PowerShell_profile.ps1
```

Then run:

```powershell
claude-wsl-window   # Launch Claude Code inside the dev container
codex-wsl-window    # Launch Codex CLI inside the dev container
```

These functions find the dev container by Docker label, start it if stopped, exec in as the `vscode` user, inject a `GH_TOKEN` from `gh auth` if available, and launch the tool.

## File reference

| File | Purpose |
|------|---------|
| `.devcontainer/devcontainer.json` | Dev container configuration |
| `.devcontainer/Dockerfile` | Container image definition |
| `.devcontainer/claude-entry.sh` | Entry script for Claude Code |
| `.devcontainer/codex-entry.sh` | Entry script for Codex CLI |
| `.devcontainer/Microsoft.PowerShell_profile.ps1` | PowerShell functions for launching AI tools from Windows |

## Related

- [CLAUDE.md](../../CLAUDE.md) -- project context and key commands
