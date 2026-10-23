#!/usr/bin/env bash
# Blender 4.5 LTS (official build) into $HOME/blender
set -e
bash "$(dirname "$0")/apt.sh" libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libxkbcommon0 libsm6 libice6 ffmpeg || true
F=$(curl -s https://download.blender.org/release/Blender4.5/ | grep -oE 'blender-4\.5\.[0-9]+-linux-x64\.tar\.xz' | sort -V | uniq | tail -1)
echo "Blender: $F"
curl -sL -o /tmp/b.tar.xz "https://download.blender.org/release/Blender4.5/$F"
mkdir -p $HOME/blender && tar -xf /tmp/b.tar.xz -C $HOME/blender --strip-components=1 && rm /tmp/b.tar.xz
