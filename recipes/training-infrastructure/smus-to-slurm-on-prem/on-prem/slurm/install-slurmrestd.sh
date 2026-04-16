#!/usr/bin/env bash
# Configures slurmrestd to run as an unprivileged user with JWT auth on TCP 6820.
# Idempotent: safe to re-run. Must be run AFTER install-slurm.sh.
#
# Run as root:  sudo bash on-prem/slurm/install-slurmrestd.sh

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Must run as root (try: sudo bash $0)" >&2
  exit 1
fi

echo "[1/5] Ensuring slurmrest system user exists + is in the slurm group"
if ! id slurmrest >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin slurmrest
fi
usermod -aG slurm slurmrest

echo "[2/5] Relaxing JWT key group-read so slurmrest can verify tokens"
chgrp slurm /var/spool/slurm/jwt_hs256.key
chmod 640   /var/spool/slurm/jwt_hs256.key

echo "[3/5] Writing systemd drop-in"
mkdir -p /etc/systemd/system/slurmrestd.service.d
cat > /etc/systemd/system/slurmrestd.service.d/override.conf <<'EOF'
[Service]
User=slurmrest
Group=slurmrest
# Load only the current slurmctld OpenAPI plugin; avoid slurmdbd plugin that
# fatals without a configured accounting DB. Bind TCP only (no unix socket,
# which the unprivileged user cannot create in /run).
Environment="SLURMRESTD_OPTIONS=-s openapi/slurmctld"
ExecStart=
ExecStart=/usr/sbin/slurmrestd $SLURMRESTD_OPTIONS 0.0.0.0:6820
EOF

systemctl daemon-reload

echo "[4/5] Starting slurmrestd"
systemctl enable --now slurmrestd
sleep 2
systemctl is-active slurmrestd

echo "[5/5] Minting a 1h test token + pinging /slurm/v0.0.40/ping"
TOKEN=$(sudo -u slurm scontrol token lifespan=3600 | sed 's/^SLURM_JWT=//')
echo "    token length: ${#TOKEN}"
curl -sS -o /tmp/slurmrestd-ping.out -w "    HTTP %{http_code}\n" \
  -H "X-SLURM-USER-NAME: slurm" -H "X-SLURM-USER-TOKEN: $TOKEN" \
  http://127.0.0.1:6820/slurm/v0.0.40/ping
head -c 200 /tmp/slurmrestd-ping.out; echo
echo
echo "Mint a fresh token any time with:  sudo -u slurm scontrol token lifespan=3600"
