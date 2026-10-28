#!/bin/bash
# Frame-exact assembly of a factory film: render parts + mastered mix -> final 1080p, 720p preview, QA sheets, report,
# release TAG (must start with film_; earlier releases are never touched).
# usage: assemble.sh PARTS_DIR MIX_WAV TOTAL_FRAMES TAG      env: FILM_SLUG FILM_TITLE EXTRA_ASSETS REVIEW_TIMES
#        ASSEMBLE_TEST=1 (+ X264_PRESET): the self-test of selftest_assembly.sh - any length, nothing published
# Parts can hold sub-ranges from different encoders (video pass / per-frame fallback) whose time bases differ, so
# timestamps are regenerated from frame order (time base 1/30, pts = frame number) and the film is encoded in one pass.
set -e
# frame count of a video (digits only: newer ffprobe prints "967," with -of csv)
frames() { ffprobe -v error -count_packets -select_streams v:0 -show_entries stream=nb_read_packets -of default=noprint_wrappers=1:nokey=1 "$1" | head -n1 | tr -cd '0-9'; }
D=$1; MIX=$2; TOTAL=$3; TAG=$4
case "$TAG" in film_*) ;; *) echo "refused: release tag '$TAG' must start with film_"; exit 1;; esac
SLUG=${FILM_SLUG:-film}; TITLE=${FILM_TITLE:-Film}
HERE=$(cd "$(dirname "$0")" && pwd)
ls $D/part_*.mp4 | sort > parts.txt; N=$(wc -l < parts.txt); echo "parts: $N"
SUM=0
for f in $(cat parts.txt); do
  c=$(frames "$f"); SUM=$((SUM + c))
done
echo "frames in parts: $SUM (expected $TOTAL)"; test $SUM -eq $TOTAL
[ -n "${ASSEMBLE_TEST:-}" ] || test $TOTAL -ge 12600 || { echo "refused: $TOTAL frames is shorter than 7 minutes"; exit 1; }

# Re-timing: settb=1/30,setpts=N gives every frame its own tick (its frame number) in a 1/30 s time base; in a time base
# that does not divide 1/30 s two frames can round onto one tick and a rate conversion drops one (ffmpeg 8: 32 frames
# lost in a 9.7 min film). -fps_mode passthrough then hands the frames to the encoder as they are (none dropped or
# doubled). No -r with it: ffmpeg 6 and later refuse -r together with a non-CFR -fps_mode ("contradictory"); the 1/30
# timestamps carry the 30 fps rate, checked below.
X264="-c:v libx264 -crf 17 -preset ${X264_PRESET:-medium} -pix_fmt yuv420p -movflags +faststart"
IN=""; F=""; C=""; i=0
for f in $(cat parts.txt); do IN="$IN -i $f"; F="${F}[$i:v]settb=1/30,setpts=N[v$i];"; C="${C}[v$i]"; i=$((i + 1)); done
ffmpeg -v error -y $IN -filter_complex "${F}${C}concat=n=$N:v=1:a=0,settb=1/30,setpts=N[out]" -map "[out]" -fps_mode passthrough \
  $X264 video.mp4
FR=$(frames video.mp4)
if [ "$FR" != "$TOTAL" ]; then                        # second way: the concat demuxer, the same exact re-timing
  echo "video: $FR frames (expected $TOTAL) - joining again with the concat demuxer"
  for f in $(cat parts.txt); do echo "file '$PWD/$f'"; done > parts_list.txt
  ffmpeg -v error -y -f concat -safe 0 -i parts_list.txt -vf "settb=1/30,setpts=N" -fps_mode passthrough $X264 video.mp4
  FR=$(frames video.mp4)
fi
RATE=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 video.mp4 | head -n1 | tr -cd '0-9/')
echo "video rate: $RATE"; [ "$RATE" = "30/1" ] || { echo "refused: video rate $RATE (expected 30/1)"; exit 1; }
echo "video: $FR frames"; test "$FR" -eq "$TOTAL"

ffmpeg -v error -y -i video.mp4 -i $MIX -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -ar 48000 -movflags +faststart \
  -metadata title="$TITLE" ${SLUG}_final_1080p.mp4
ffmpeg -v error -y -i ${SLUG}_final_1080p.mp4 -vf scale=1280:-2 -c:v libx264 -crf 23 -preset veryfast -c:a aac -b:a 160k \
  -movflags +faststart ${SLUG}_preview_720p.mp4
python3 $HERE/qa_sheets.py ${SLUG}_final_1080p.mp4 . 10 ${REVIEW_TIMES:-}
{
  echo "== $TITLE"
  echo "== final: $(ffprobe -v error -show_entries stream=codec_type,duration,nb_frames,r_frame_rate -of compact ${SLUG}_final_1080p.mp4 | tr '\n' ' ')"
  echo "== video frames: $FR (expected $TOTAL) = $(python3 -c "print(f'{$TOTAL / 30 / 60:.2f}')") min"
  echo "== final loudness"; ffmpeg -hide_banner -nostats -i ${SLUG}_final_1080p.mp4 -vn -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|LRA|Peak):"
  [ -f "$(dirname "$MIX")/audio_report.txt" ] && { echo "== audio master"; cat "$(dirname "$MIX")/audio_report.txt"; }
  echo "== sub-ranges re-rendered frame by frame (fresh page per frame)"; cat $D/qa/*fallback* 2>/dev/null || echo none
  echo "== self-check (max 15x15 block diff vs fresh-page reference; ~30-40 = scale-rendering baseline, >90 = missing layer)"
  for f in $D/qa/*check*; do [ -f "$f" ] && echo "$(basename $f): $(tail -1 $f)"; done
  echo "== still mismatches"; cat $D/qa/*FAIL* 2>/dev/null || echo none
} > qa_report.txt
cat qa_report.txt; ls -la *.mp4 *.jpg
[ -n "${ASSEMBLE_TEST:-}" ] && { echo "self-test: nothing published"; exit 0; }
gh release delete $TAG --repo $GITHUB_REPOSITORY -y --cleanup-tag 2>/dev/null || true
gh release create $TAG --repo $GITHUB_REPOSITORY --title "$TITLE" --notes "$TITLE" \
  ${SLUG}_final_1080p.mp4 ${SLUG}_preview_720p.mp4 qa_sheet_*.jpg qa_report.txt ${EXTRA_ASSETS:-}
