#!/usr/bin/env bash
# Installs slurm-wlm + munge, places the config files from this directory,
# mints a JWT HS256 signing key, and starts slurmctld + slurmd.
# Idempotent: safe to re-run.
#
# Run as root:  sudo bash on-prem/slurm/install-slurm.sh
#
# Tested on Ubuntu 24.04 aarch64 with a single-node DGX Spark. For a real
# multi-node cluster, edit slurm.conf first and distribute configs + the
# munge key to every node.

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Must run as root (try: sudo bash $0)" >&2
  exit 1
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/6] Installing packages (slurm-wlm, slurmrestd, munge)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq slurm-wlm slurmrestd munge

echo "[2/6] Placing config files from $HERE"
# slurmctld refuses to start unless NodeName/SlurmctldHost match `hostname -s`.
# Templates in this repo use the placeholder `gpu-node-01`; rewrite to the
# real hostname on the way in so a fresh clone just works.
HOSTNAME_SHORT="$(hostname -s)"
echo "    rewriting slurm.conf / gres.conf: gpu-node-01 -> $HOSTNAME_SHORT"
sed "s/\bgpu-node-01\b/$HOSTNAME_SHORT/g" "$HERE/slurm.conf"  > /etc/slurm/slurm.conf
sed "s/\bgpu-node-01\b/$HOSTNAME_SHORT/g" "$HERE/gres.conf"   > /etc/slurm/gres.conf
chmod 644 /etc/slurm/slurm.conf /etc/slurm/gres.conf
install -o root -g root -m 644 "$HERE/cgroup.conf" /etc/slurm/cgroup.conf

echo "[3/6] Creating spool + log directories"
install -d -o slurm -g slurm -m 755 /var/spool/slurmctld
install -d -o slurm -g slurm -m 755 /var/spool/slurm
install -d -o slurm -g slurm -m 755 /var/log/slurm
install -d -o root  -g root  -m 755 /var/spool/slurmd

echo "[4/6] Generating JWT HS256 signing key (if missing)"
if [[ ! -f /var/spool/slurm/jwt_hs256.key ]]; then
  dd if=/dev/urandom of=/var/spool/slurm/jwt_hs256.key bs=32 count=1 status=none
  chown slurm:slurm /var/spool/slurm/jwt_hs256.key
  chmod 600 /var/spool/slurm/jwt_hs256.key
  echo "    new JWT key minted"
else
  echo "    JWT key already exists, leaving alone"
fi

echo "[5/6] Enabling + starting munge, slurmctld, slurmd"
systemctl enable --now munge
sleep 1
munge -n | unmunge >/dev/null && echo "    munge OK"
systemctl restart slurmctld
systemctl restart slurmd
sleep 2

echo "[6/6] Status"
systemctl is-active munge slurmctld slurmd
sinfo
