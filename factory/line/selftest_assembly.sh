#!/bin/bash
# Self-test of the final assembly: the same script (assemble.sh) and the same ffmpeg as the final job, on three small
# parts made here with three time bases (mp4 default, 1/1000, 1/90000), plus a mix of the exact length. It runs in the
# first minute of every film run, so an assembly error shows before anything renders, never after the render.
# usage: bash factory/line/selftest_assembly.sh        (needs ffmpeg/ffprobe, python3 + pillow)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
mkdir -p "$W/parts"
mk() { ffmpeg -v error -y -f lavfi -i "testsrc2=size=1920x1080:rate=30" -frames:v "$2" -c:v libx264 -preset ultrafast \
         -pix_fmt yuv420p $3 "$W/parts/$1"; }
mk part_00.mp4 151 ""
mk part_01.mp4 149 "-video_track_timescale 1000"
mk part_02.mp4 137 "-video_track_timescale 90000"
TOTAL=437
ffmpeg -v error -y -f lavfi -i "sine=frequency=220:sample_rate=48000:duration=$(python3 -c "print($TOTAL / 30)")" -ac 2 "$W/mix.wav"
cd "$W"
if ! ASSEMBLE_TEST=1 X264_PRESET=ultrafast FILM_SLUG=selftest FILM_TITLE="Assembly self-test" \
     bash "$HERE/assemble.sh" parts mix.wav $TOTAL film_selftest > log.txt 2>&1; then
  cat log.txt; echo "::error::assembly self-test failed: the final step would fail after the render"; exit 1
fi
grep -E "^(frames in parts|video|video rate|== final): " log.txt || true
test -s selftest_final_1080p.mp4 && test -s selftest_preview_720p.mp4 && ls qa_sheet_*.jpg > /dev/null
echo "assembly self-test ok: $TOTAL frames from 3 parts with 3 time bases -> final, preview, QA sheets, report"
