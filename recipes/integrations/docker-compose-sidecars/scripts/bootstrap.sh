#!/usr/bin/env bash
# Bootstrap the compose stack from inside a SageMaker AI Code Editor space.
# Idempotent: safe to re-run.
set -euo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "==> [1/4] docker CLI check"
if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker CLI not found in this space. Enable local docker on the space and relaunch." >&2
    exit 1
fi
docker version --format 'client={{.Client.Version}} server={{.Server.Version}}'

echo "==> [2/4] docker compose plugin check"
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

echo "==> [3/4] building images"
docker compose -f compose.yaml build

echo "==> [4/4] starting stack"
docker compose -f compose.yaml up -d

echo
docker compose -f compose.yaml ps
echo
echo "Done. Services share the editor's network namespace, so try:"
echo "  curl -s http://127.0.0.1:8080/   # svc-a"
echo "  curl -s http://127.0.0.1:8081/   # svc-b (fetches svc-a via 127.0.0.1:8080)"
