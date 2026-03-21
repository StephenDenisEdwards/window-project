#!/usr/bin/env bash
set -e

cd /workspaces/window-project || exit 1

# Inject GH token if available
if command -v gh >/dev/null 2>&1; then
    TOKEN=$(gh auth token 2>/dev/null || true)
    if [ -n "$TOKEN" ]; then
        export GH_TOKEN="$TOKEN"
    fi
fi

exec claude