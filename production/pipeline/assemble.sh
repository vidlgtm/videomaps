#!/bin/bash
# Frame-exact assembly of the final film: chunk videos + mastered mix -> final 1080p, 720p preview, QA sheets, report, release.
# usage: assemble.sh PARTS_DIR MIX_WAV TOTAL_FRAMES TAG
# Chunks can contain sub-ranges from different encoders (Remotion / per-frame fallback) whose container time bases differ,
# so timestamps are regenerated from frame order (setpts=N) and the whole film is encoded in one continuous pass.
set -e
D=$1; MIX=$2; TOTAL=$3; TAG=$4
ls $D/part_*.mp4 | sort > parts.txt; N=$(wc -l < parts.txt); echo "parts: $N"
SUM=0
for f in $(cat parts.txt); do
  c=$(ffprobe -v error -count_packets -select_streams v:0 -show_entries stream=nb_read_packets -of csv=p=0 $f); SUM=$((SUM + c))
done
echo "frames in parts: $SUM (expected $TOTAL)"; test $SUM -eq $TOTAL

IN=""; F=""; C=""; i=0
for f in $(cat parts.txt); do IN="$IN -i $f"; F="$F[$i:v]setpts=N/(30*TB)[v$i];"; C="$C[v$i]"; i=$((i + 1)); done
ffmpeg -v error -y $IN -filter_complex "${F}${C}concat=n=$N:v=1:a=0,setpts=N/(30*TB),fps=30[out]" -map "[out]" -fps_mode passthrough \
  -c:v libx264 -crf 17 -preset medium -pix_fmt yuv420p -movflags +faststart video.mp4
FR=$(ffprobe -v error -count_packets -select_streams v:0 -show_entries stream=nb_read_packets -of csv=p=0 video.mp4)
VD=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 video.mp4)
echo "video: $FR frames, $VD s"; test $FR -eq $TOTAL

ffmpeg -v error -y -i video.mp4 -i $MIX -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -ar 48000 -movflags +faststart \
  -metadata title="Why the Soviet Union Broke Into Exactly 15 Countries" USSR15_final_1080p.mp4
ffmpeg -v error -y -i USSR15_final_1080p.mp4 -vf scale=1280:-2 -c:v libx264 -crf 23 -preset veryfast -c:a aac -b:a 160k \
  -movflags +faststart USSR15_preview_720p.mp4
python3 production/pipeline/qa_sheets.py USSR15_final_1080p.mp4 .
{
  echo "== final: $(ffprobe -v error -show_entries stream=codec_type,duration,nb_frames,r_frame_rate -of compact USSR15_final_1080p.mp4 | tr '\n' ' ')"
  echo "== video frames: $FR (expected $TOTAL)"
  echo "== final loudness"; ffmpeg -hide_banner -nostats -i USSR15_final_1080p.mp4 -vn -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|LRA|Peak):"
  [ -f $(dirname $MIX)/audio_report.txt ] && { echo "== audio master"; cat $(dirname $MIX)/audio_report.txt; }
  echo "== sub-ranges re-rendered frame by frame (fresh page per frame)"; cat $D/qa/*fallback* 2>/dev/null || echo none
  echo "== self-check (max 15x15 block diff vs fresh-page reference; ~30-40 = scale-rendering baseline, >90 = missing layer)"
  for f in $D/qa/*check*; do echo "$(basename $f): $(tail -1 $f)"; done
} > qa_report.txt
cat qa_report.txt; ls -la *.mp4 *.jpg
gh release delete $TAG --repo $GITHUB_REPOSITORY -y --cleanup-tag || true
gh release create $TAG --repo $GITHUB_REPOSITORY --title "Final film" --notes "Why the Soviet Union Broke Into Exactly 15 Countries" \
  USSR15_final_1080p.mp4 USSR15_preview_720p.mp4 qa_sheet_*.jpg qa_report.txt
