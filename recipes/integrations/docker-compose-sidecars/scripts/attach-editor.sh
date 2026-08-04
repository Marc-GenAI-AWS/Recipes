#!/usr/bin/env bash
# Attach the currently-running Code Editor container to the agents-net network
# so that DNS names like svc-a / svc-b resolve from inside the editor.
set -euo pipefail

NET="agents-net"

# Discover this container's ID. Try cgroup v1/v2 first, then fall back to hostname.
CID="$(grep -oE '[0-9a-f]{64}' /proc/self/cgroup 2>/dev/null | head -n1 || true)"
if [ -z "$CID" ]; then
    CID="$(grep -oE '[0-9a-f]{64}' /proc/self/mountinfo 2>/dev/null | head -n1 || true)"
fi
if [ -z "$CID" ]; then
    CID="$(hostname)"
fi

if ! docker network inspect "$NET" >/dev/null 2>&1; then
    echo "Network '$NET' does not exist yet. Run docker compose up first." >&2
    exit 1
fi

if docker network connect "$NET" "$CID" 2>/dev/null; then
    echo "Attached container '$CID' to network '$NET'."
else
    echo "Container '$CID' is already on '$NET' (or attach failed — check with: docker network inspect $NET)."
fi
