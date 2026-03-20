FROM mcr.microsoft.com/devcontainers/python:3.14

RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
    && pip install uv black ruff ipykernel pytest

    # Install GitHub CLI
RUN wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y gh

# Install Claude Code
RUN npm install -g @anthropic-ai/claude-code
# Install Codex CLI
RUN npm install -g @openai/codex