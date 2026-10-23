#!/usr/bin/env bash
# apt-get install that cannot stall a job for half an hour (kit 2.0, 06 T38). On the first kit run a GitHub runner sat
# 33 min after "Reading package lists..." (voice job 35 min instead of 2; the Manim job likewise). Here: no man-db
# rebuild, network timeouts and retries, dpkg lock wait, every try capped (update 5 min, install 15 min), 3 tries,
# then a clear error.   usage: bash production/ci/apt.sh <package> [<package> ...]
set -u
sudo rm -f /etc/apt/sources.list.d/microsoft* /var/lib/man-db/auto-update
O=(-o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 -o DPkg::Lock::Timeout=120 -o Dpkg::Use-Pty=0)
for i in 1 2 3; do
  T0=$(date +%s)
  timeout 300 sudo DEBIAN_FRONTEND=noninteractive apt-get "${O[@]}" update -qq || echo "::warning::apt update try $i failed or timed out"
  if timeout 900 sudo DEBIAN_FRONTEND=noninteractive apt-get "${O[@]}" install -y -qq "$@" > /dev/null; then
    echo "apt: $* installed in $(( $(date +%s) - T0 )) s (try $i)"; exit 0
  fi
  echo "::warning::apt install try $i failed or timed out after $(( $(date +%s) - T0 )) s - retrying"
  sudo dpkg --configure -a > /dev/null 2>&1 || true; sleep 20
done
echo "::error::apt could not install: $* (3 tries; 06 T38: cancel and dispatch again later)"; exit 1
