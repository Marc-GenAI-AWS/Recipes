#!/usr/bin/env bash
# Launches a Cloudflare Quick Tunnel that exposes slurmrestd (127.0.0.1:6820)
# at a public https://*.trycloudflare.com URL, so a SMUS Workflows DAG in AWS
# can reach it without a VPN.
#
# Not for production: the subdomain is ephemeral and rotates every time
# cloudflared restarts. For a stable URL, register a named tunnel against a
# Cloudflare-managed domain (free tier is enough).
#
# Usage:
#   ./run-quick-tunnel.sh                 # runs in the foreground, Ctrl-C to stop
#   ./run-quick-tunnel.sh --background    # nohup + log to ./cloudflared.log

set -euo pipefail

PORT="${SLURMRESTD_PORT:-6820}"
LOG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$LOG_DIR/cloudflared.log"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not installed — installing arm64 .deb from GitHub releases..."
  tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/cloudflared.deb" \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
  sudo dpkg -i "$tmp/cloudflared.deb"
  rm -rf "$tmp"
fi

cmd=(cloudflared tunnel --url "http://127.0.0.1:${PORT}")

if [[ "${1:-}" == "--background" ]]; then
  echo "Launching tunnel in background; logs -> $LOG_FILE"
  nohup "${cmd[@]}" > "$LOG_FILE" 2>&1 &
  pid=$!
  echo "pid=$pid"
  # Wait for the URL to appear
  for _ in {1..20}; do
    sleep 1
    url=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_FILE" | head -1 || true)
    [[ -n "$url" ]] && break
  done
  if [[ -n "${url:-}" ]]; then
    echo "Tunnel URL: $url"
  else
    echo "Did not see a tunnel URL in $LOG_FILE after 20s — check the log."
    exit 1
  fi
else
  echo "Launching tunnel in foreground (Ctrl-C to stop)"
  exec "${cmd[@]}"
fi
