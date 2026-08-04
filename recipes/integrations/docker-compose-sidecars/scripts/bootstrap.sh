#!/usr/bin/env bash
# Bootstrap the compose stack from inside a SageMaker AI Code Editor space.
# Idempotent: safe to re-run.
set -euo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "==> [1/5] docker CLI check"
if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker CLI not found in this space. Enable local docker on the space and relaunch." >&2
    exit 1
fi
docker version --format 'client={{.Client.Version}} server={{.Server.Version}}'

echo "==> [2/5] docker compose plugin check"
if ! docker compose version >/dev/null 2>&1; then
    echo "compose plugin missing; installing into ~/.docker/cli-plugins"
    mkdir -p "$HOME/.docker/cli-plugins"
    ARCH="$(uname -m)"
    COMPOSE_VERSION="v2.29.7"
    curl -fsSL \
        "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-${ARCH}" \
        -o "$HOME/.docker/cli-plugins/docker-compose"
    chmod +x "$HOME/.docker/cli-plugins/docker-compose"
fi
docker compose version

echo "==> [3/5] building images"
docker compose -f compose.yaml build

echo "==> [4/5] starting stack"
docker compose -f compose.yaml up -d

echo "==> [5/5] attaching this Code Editor container to agents-net"
bash "$REPO_DIR/scripts/attach-editor.sh"

echo
docker compose -f compose.yaml ps
echo
echo "Network members:"
docker network inspect agents-net --format '{{range .Containers}}  - {{.Name}}{{"\n"}}{{end}}'
echo "Done. Try: curl -s http://svc-a:8080/ && echo && curl -s http://svc-b:8080/"
