#!/usr/bin/env bash
# Activate a project: copy its modules into the Remotion source tree (the engine imports src/script.ts, src/v2.ts,
# src/names.ts, src/extras.tsx) and its optional data overrides. usage: bash production/ci/use_project.sh NAME
set -e
P=${1:?usage: use_project.sh NAME}
ROOT=$(cd "$(dirname "$0")/../.." && pwd); D=$ROOT/projects/$P
for f in src/script.ts src/v2.ts src/names.ts src/extras.tsx narration.json project.json; do
  test -f "$D/$f" || { echo "project $P incomplete: missing $f"; exit 1; }
done
cp "$D"/src/script.ts "$D"/src/v2.ts "$D"/src/names.ts "$D"/src/extras.tsx "$ROOT/production/remotion/src/"
if [ -d "$D/data" ]; then cp "$D"/data/*.json "$ROOT/production/remotion/src/data/" 2>/dev/null || true; fi
echo "project $P active"
