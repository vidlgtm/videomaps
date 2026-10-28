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

# Frame-exact join. The parts hold sub-ranges from two encoders joined by stream copy, so their timestamps and edit lists
# are not trusted at all: every part is decoded on its own with its edit list ignored (an edit list of a stream-copied
# join can hide frames) and re-timed to its frame order, the raw frames go in order into ONE encoder at exactly 30 fps.
# Before the long encode every part must decode to exactly its packets with no decode error; after it the film must
# have TOTAL frames, TOTAL/30 s and 30 fps. (Joins that trusted the timestamps lost 15-32 frames or squeezed 9.7 min of
# frames into 129 s.)
read -r WID HEI <<< "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=x "$(head -n1 parts.txt)" | head -n1 | tr 'x' ' ' | tr -cd '0-9 ')"
FS=$(( WID * HEI * 3 / 2 ))                          # bytes of one yuv420p frame
# (rawvideo has no timestamps: the muxer only logs "non monotonically increasing dts" at the sub-range joins of a part
#  and writes every frame - fps_mode passthrough never drops one; that line is not a decode error)
dec() { ffmpeg -v error -nostdin -ignore_editlist 1 -i "$1" -map 0:v:0 -fps_mode passthrough -pix_fmt yuv420p -f rawvideo -; }
BAD=0
for f in $(cat parts.txt); do
  wh=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=x "$f" | head -n1 | tr -cd '0-9x')
  p=$(frames "$f"); by=$(dec "$f" 2> "$f.err" | wc -c); e=$(grep -v "non monotonically increasing dts to muxer" "$f.err" | grep -c . || true)
  echo "$(basename "$f"): ${wh}, packets $p, decoded frames $(( by / FS )) (+$(( by % FS )) bytes), decode errors $e"
  [ "$wh" = "${WID}x${HEI}" ] && [ $(( by % FS )) -eq 0 ] && [ $(( by / FS )) -eq "$p" ] && [ "$e" -eq 0 ] \
    || { BAD=1; grep -v "non monotonically increasing dts to muxer" "$f.err" | head -5; }
done
[ $BAD = 0 ] || { echo "refused: a part does not decode to exactly its frames (see above)"; exit 1; }
for f in $(cat parts.txt); do dec "$f"; done | ffmpeg -v error -nostdin -y -f rawvideo -pix_fmt yuv420p -s "${WID}x${HEI}" -framerate 30 -i - \
  -c:v libx264 -crf 17 -preset "${X264_PRESET:-medium}" -pix_fmt yuv420p -movflags +faststart video.mp4
FR=$(frames video.mp4)
VINFO=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration,avg_frame_rate,r_frame_rate -of default=noprint_wrappers=1 video.mp4 | tr '\n' ' ')
echo "video: $FR frames | $VINFO"
python3 - "$FR" "$TOTAL" "$VINFO" <<'PY'
import sys
fr, total, info = int(sys.argv[1]), int(sys.argv[2]), dict(kv.split("=", 1) for kv in sys.argv[3].split() if "=" in kv)
rate = lambda s: (lambda n, d: float(n) / float(d) if float(d) else 0.0)(*(s.split("/") + ["1"])[:2])
dur, avg = float(info.get("duration", "0")), rate(info.get("avg_frame_rate", "0/1"))
bad = [m for ok, m in ((fr == total, f"{fr} frames, expected {total}"),
                       (abs(dur - total / 30) <= 1.5 / 30, f"{dur:.3f} s, expected {total / 30:.3f} s"),
                       (abs(avg - 30) < 0.01, f"{avg:.4f} fps, expected 30")) if not ok]
if bad: print("refused: the joined video is wrong - " + "; ".join(bad)); sys.exit(1)
print(f"video ok: {fr} frames, {dur:.3f} s, {avg:g} fps")
PY
echo "video: $FR frames"; test "$FR" -eq "$TOTAL"

ffmpeg -v error -y -i video.mp4 -i $MIX -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -ar 48000 -movflags +faststart \
  -metadata title="$TITLE" ${SLUG}_final_1080p.mp4
ffmpeg -v error -y -i ${SLUG}_final_1080p.mp4 -vf scale=1280:-2 -c:v libx264 -crf 23 -preset veryfast -c:a aac -b:a 160k \
  -movflags +faststart ${SLUG}_preview_720p.mp4
python3 $HERE/qa_sheets.py ${SLUG}_final_1080p.mp4 . 10 ${REVIEW_TIMES:-}
{
  echo "== $TITLE"
  echo "== final: $(ffprobe -v error -show_entries stream=codec_type,duration,nb_frames,r_frame_rate -of compact ${SLUG}_final_1080p.mp4 | tr '\n' ' ')"
  echo "== video frames: $FR (expected $TOTAL) = $(python3 -c "print(f'{$TOTAL / 30 / 60:.2f}')") min | $VINFO"
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
