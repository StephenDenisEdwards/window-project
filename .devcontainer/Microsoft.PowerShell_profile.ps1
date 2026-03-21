function Get-WindowProjectDevContainer {
    $workspace = "c:\Users\steph\source\repos\window-project"

    $running = docker ps `
        --filter "label=devcontainer.local_folder=$workspace" `
        --format "{{.Names}}" | Select-Object -First 1

    if ($running) {
        return $running
    }

    $stopped = docker ps -a `
        --filter "label=devcontainer.local_folder=$workspace" `
        --format "{{.Names}}" | Select-Object -First 1

    if ($stopped) {
        docker start $stopped | Out-Null
        return $stopped
    }

    Write-Host "No dev container found for $workspace"
    Write-Host "Open the project once in VS Code with Dev Containers first."
    return $null
}

function claude-wsl-window {
    $container = Get-WindowProjectDevContainer
    if (-not $container) { return }

    docker exec -u vscode -it $container bash -lc "/workspaces/window-project/.devcontainer/claude-entry.sh"
}

function codex-wsl-window {
    $container = Get-WindowProjectDevContainer
    if (-not $container) { return }

    docker exec -u vscode -it $container bash -lc "/workspaces/window-project/.devcontainer/codex-entry.sh"
}