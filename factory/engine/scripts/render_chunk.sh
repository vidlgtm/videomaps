#!/bin/bash
# Render frames A..B of composition "Main" into OUT (h264 crf 18, muted).
# W independent browsers x concurrency 1: every tab keeps the full GPU tile budget, so overlay layers
# (cards, flags, labels) are never dropped at high map zoom (the 4-tab run lost them).
# Self-check: frames are compared with fresh-page reference stills; any mismatch -> that sub-range is
# re-rendered frame by frame as stills (fresh page per frame) and checked again.
set -e
A=$1; B=$2; OUT=$3; W=${WORKERS:-3}; SERVE=${SERVE:-build}; P=${PART:-x}
QA=${QA_COMPARE:-$(cd "$(dirname "$0")/../../.." && pwd)/production/pipeline/qa_compare.py}
test -f "$QA" || { echo "qa_compare.py not found: $QA"; exit 1; }
mkdir -p out/sub out/qa out/ref
N=$((B - A + 1)); SZ=$(( (N + W - 1) / W ))

render_sub() { # i a b
  npx remotion render "$SERVE" Main out/sub/s_$1.mp4 --frames=$2-$3 --muted --codec=h264 --crf=18 --jpeg-quality=95 --gl=swangle \
    --concurrency=1 --timeout=600000 --log=error > out/sub/log_$1.txt 2>&1 || { echo "render sub $1 failed"; tail -20 out/sub/log_$1.txt; }
}
stills_sub() { # i a b
  rm -rf out/sub/f_$1; mkdir -p out/sub/f_$1
  node scripts/stills_range.mjs "$SERVE" $2 $3 out/sub/f_$1 > out/sub/slog_$1.txt 2>&1 || { tail -20 out/sub/slog_$1.txt; exit 1; }
  ffmpeg -v error -y -framerate 30 -start_number $2 -i out/sub/f_$1/f_%06d.jpg -frames:v $(( $3 - $2 + 1 )) \
    -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p out/sub/s_$1.mp4
  rm -rf out/sub/f_$1
}

SUBS=()
for i in $(seq 0 $((W - 1))); do
  a=$((A + i * SZ)); b=$((a + SZ - 1)); [ $b -gt $B ] && b=$B; [ $a -gt $B ] && continue
  SUBS+=("$i $a $b")
done
echo "part $P: frames $A-$B in ${#SUBS[@]} sub-ranges"
for s in "${SUBS[@]}"; do render_sub $s & done
wait
echo "video pass done"

for s in "${SUBS[@]}"; do
  read i a b <<< "$s"
  FR=$(python3 -c "print(' '.join(str(f) for f in range($a + 8, $b + 1, 40)))")
  for f in $FR; do
    npx remotion still "$SERVE" Main out/ref/ref_$f.jpg --frame=$f --scale=0.25 --gl=swangle --log=error > /dev/null 2>&1 || true
  done
  NEED=0
  if [ ! -s out/sub/s_$i.mp4 ] || [ "$(ffprobe -v error -count_packets -select_streams v:0 -show_entries stream=nb_read_packets -of csv=p=0 out/sub/s_$i.mp4)" != "$(( b - a + 1 ))" ]; then
    echo "sub $i missing/short" > out/qa/qa_p${P}_s${i}_check1.txt; NEED=1
  elif ! python3 "$QA" out/sub/s_$i.mp4 $a out/ref $FR > out/qa/qa_p${P}_s${i}_check1.txt; then
    NEED=1
  fi
  if [ $NEED = 1 ]; then
    echo "part $P sub $i ($a-$b): mismatch -> stills mode"; cat out/qa/qa_p${P}_s${i}_check1.txt
    echo "fallback part $P sub $i frames $a-$b" > out/qa/qa_p${P}_s${i}_fallback.txt
    stills_sub $i $a $b
    python3 "$QA" out/sub/s_$i.mp4 $a out/ref $FR > out/qa/qa_p${P}_s${i}_check2.txt \
      || echo "STILL MISMATCH part $P sub $i" | tee out/qa/qa_p${P}_s${i}_FAIL.txt
  fi
done

for s in "${SUBS[@]}"; do read i a b <<< "$s"; echo "file '$PWD/out/sub/s_$i.mp4'"; done > out/sub/list.txt
ffmpeg -v error -y -f concat -safe 0 -i out/sub/list.txt -c copy "$OUT"
echo "part $P frames: $(ffprobe -v error -count_packets -select_streams v:0 -show_entries stream=nb_read_packets -of csv=p=0 "$OUT") (expected $N)"
