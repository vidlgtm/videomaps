#!/bin/bash
# Self-test of the final assembly: the same script (assemble.sh) and the same ffmpeg as the final job, on three small
# parts built like the render parts (scripts/render_chunk.sh): each part = three sub-ranges from the two ways a part is
# made - a video pass (h264 with B-frames, two different time bases) and the stills mode (JPEG frames numbered from the
# sub-range start, -framerate 30) - joined by the concat demuxer with stream copy. The assembly must give every frame
# exactly once at 30 fps. It runs in the first minute of every film run, so an assembly error shows before anything
# renders, never after the render.
# usage: bash factory/line/selftest_assembly.sh        (needs ffmpeg/ffprobe, python3 + pillow)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
mkdir -p "$W/parts" "$W/sub"
SRC="testsrc2=size=1920x1080:rate=30"
video_sub() {   # out start frames [timescale]: like a video pass (h264 crf 18, B-frames)
  ffmpeg -v error -nostdin -y -f lavfi -i "$SRC" -vf "trim=start_frame=$2,setpts=PTS-STARTPTS" -frames:v "$3" \
    -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p ${4:+-video_track_timescale $4} "$1"
}
stills_sub() {  # out start frames: like the stills mode (JPEG frames numbered from the start, -framerate 30)
  rm -rf "$W/f"; mkdir -p "$W/f"
  ffmpeg -v error -nostdin -y -f lavfi -i "$SRC" -vf "trim=start_frame=$2,setpts=PTS-STARTPTS" -frames:v "$3" -q:v 3 \
    -start_number "$2" "$W/f/f_%06d.jpg"
  ffmpeg -v error -nostdin -y -framerate 30 -start_number "$2" -i "$W/f/f_%06d.jpg" -frames:v "$3" \
    -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p "$1"
}
part() {        # name "kind:frames ..." - sub-ranges joined like render_chunk.sh (concat demuxer, stream copy)
  local n=$1 start=$2 i=0 list="$W/sub/list_$1.txt"; shift 2; : > "$list"
  for s in "$@"; do
    k=${s%%:*}; c=${s##*:}; o="$W/sub/${n}_$i.mp4"
    case $k in v) video_sub "$o" "$start" "$c";; t) video_sub "$o" "$start" "$c" 90000;; s) stills_sub "$o" "$start" "$c";; esac
    echo "file '$o'" >> "$list"; start=$((start + c)); i=$((i + 1))
  done
  ffmpeg -v error -nostdin -y -f concat -safe 0 -i "$list" -c copy "$W/parts/$n.mp4"
}
part part_00 0   v:50 s:50 v:51
part part_01 151 s:49 v:50 t:50
part part_02 300 v:48 s:49 s:40
TOTAL=437
ffmpeg -v error -nostdin -y -f lavfi -i "sine=frequency=220:sample_rate=48000:duration=$(python3 -c "print($TOTAL / 30)")" -ac 2 "$W/mix.wav"
cd "$W"
if ! ASSEMBLE_TEST=1 X264_PRESET=ultrafast FILM_SLUG=selftest FILM_TITLE="Assembly self-test" \
     bash "$HERE/assemble.sh" parts mix.wav $TOTAL film_selftest > log.txt 2>&1; then
  cat log.txt; echo "::error::assembly self-test failed: the final step would fail after the render"; exit 1
fi
grep -E "^(frames in parts|part_0|video|== final)" log.txt || true
test -s selftest_final_1080p.mp4 && test -s selftest_preview_720p.mp4 && ls qa_sheet_*.jpg > /dev/null
echo "assembly self-test ok: $TOTAL frames from 3 parts (video-pass and stills sub-ranges joined by stream copy) -> one 30 fps film, preview, QA sheets, report"
