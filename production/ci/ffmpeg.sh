#!/usr/bin/env bash
# ffmpeg + ffprobe without the Ubuntu mirror: the mirror of the GitHub runners can stall apt for 30+ minutes (seen again
# in October 2026). A pinned static build (BtbN/FFmpeg-Builds, GPL with libx264 and libmp3lame, n8.1.3; month-end
# releases are kept for two years) comes from GitHub's release storage, checked by sha256; apt only if that fails.
# usage: bash production/ci/ffmpeg.sh
set -u
if command -v ffmpeg > /dev/null && command -v ffprobe > /dev/null; then echo "ffmpeg: already present - $(ffmpeg -version | head -1)"; exit 0; fi
TAG=autobuild-2026-09-30-13-08
F=ffmpeg-n8.1.3-9-g29e619e767-linux64-gpl-8.1
SHA=97ce978979194b5cf7e06a5e68020dbdaa7a4f3294c5452b6a1bc347100dbb79
D=/opt/ffmpeg-static
for i in 1 2 3; do
  T0=$(date +%s)
  if timeout 480 curl -sfL --retry 3 -o /tmp/ffmpeg.tar.xz "https://github.com/BtbN/FFmpeg-Builds/releases/download/$TAG/$F.tar.xz" \
      && echo "$SHA  /tmp/ffmpeg.tar.xz" | sha256sum -c --quiet; then
    sudo mkdir -p "$D" && sudo tar -xJf /tmp/ffmpeg.tar.xz -C "$D" --strip-components=2 "$F/bin/ffmpeg" "$F/bin/ffprobe" && rm -f /tmp/ffmpeg.tar.xz
    sudo ln -sf "$D/ffmpeg" /usr/local/bin/ffmpeg && sudo ln -sf "$D/ffprobe" /usr/local/bin/ffprobe
    echo "ffmpeg: static build in $(( $(date +%s) - T0 )) s - $(ffmpeg -version | head -1)"; exit 0
  fi
  echo "::warning::static ffmpeg download try $i failed"; rm -f /tmp/ffmpeg.tar.xz; sleep 10
done
echo "::warning::static ffmpeg unavailable - apt instead"
exec bash "$(dirname "$0")/apt.sh" ffmpeg
