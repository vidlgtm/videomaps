#!/usr/bin/env bash
# apt-get install that cannot stall a job (kit 2.3, 06 T38 / T42). GitHub runners sometimes crawl for 30+ min inside
# apt (first kit run: voice and Manim jobs 35 min instead of 2; later the Manim job failed 3 x 15 min). Here:
# packages already installed are skipped; IPv4 only; network timeouts and retries; visible progress (to see where a
# stall happens); no recommends; no man-db rebuild; each try capped (update 5 min, install 25 min); tries 2 and 3
# switch from the Azure mirror to the main Ubuntu archive.   usage: bash production/ci/apt.sh <package> [<package> ...]
set -u
need=(); for p in "$@"; do dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || need+=("$p"); done
if [ ${#need[@]} -eq 0 ]; then echo "apt: already installed: $*"; exit 0; fi
sudo rm -f /etc/apt/sources.list.d/microsoft* /var/lib/man-db/auto-update
O=(-o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30
   -o DPkg::Lock::Timeout=120 -o Dpkg::Use-Pty=0)
for i in 1 2 3; do
  T0=$(date +%s)
  if [ "$i" -gt 1 ]; then
    sudo sed -i 's#azure\.archive\.ubuntu\.com#archive.ubuntu.com#g' /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list 2>/dev/null || true
  fi
  timeout 300 sudo DEBIAN_FRONTEND=noninteractive apt-get "${O[@]}" update -q || echo "::warning::apt update try $i failed or timed out"
  if timeout 1500 sudo DEBIAN_FRONTEND=noninteractive apt-get "${O[@]}" install -y -q --no-install-recommends "${need[@]}"; then
    echo "apt: ${need[*]} installed in $(( $(date +%s) - T0 )) s (try $i)"; exit 0
  fi
  echo "::warning::apt install try $i failed or timed out after $(( $(date +%s) - T0 )) s - next try on the main Ubuntu archive"
  sudo dpkg --configure -a > /dev/null 2>&1 || true; sleep 20
done
echo "::error::apt could not install: ${need[*]} (3 tries; 06 T38)"; exit 1
