#!/usr/bin/env python3
"""Contact sheets of the finished film (12 frames per sheet, 480x270 each, timestamped): one frame every STEP seconds
plus the review times of the stills (when given).
usage: qa_sheets.py VIDEO OUT_DIR [STEP=10] [times file]"""
import os, subprocess, sys
from PIL import Image, ImageDraw

video, out = sys.argv[1], sys.argv[2]
step = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                           capture_output=True, text=True, check=True).stdout.strip())
T = [round(2 + k * step, 1) for k in range(int((dur - 4) // step) + 1)]
if len(sys.argv) > 4 and os.path.exists(sys.argv[4]):
    T += [float(x) for x in open(sys.argv[4]).read().split() if 0 <= float(x) < dur - 0.2]
T = sorted(set(T))
W, H = 480, 270
tiles = []
for t in T:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1", "-vf", f"scale={W}:{H}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(raw) == W * H * 3: tiles.append((t, Image.frombytes("RGB", (W, H), raw)))
for si in range(0, len(tiles), 12):
    grp = tiles[si:si + 12]
    sheet = Image.new("RGB", (W * 4, H * 3), "black"); d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(grp):
        x, y = (i % 4) * W, (i // 4) * H
        sheet.paste(im, (x, y)); d.rectangle([x, y, x + 70, y + 16], fill="black")
        d.text((x + 3, y + 2), f"{int(t // 60)}:{t % 60:04.1f}", fill="yellow")
    sheet.save(os.path.join(out, f"qa_sheet_{si // 12 + 1:02d}.jpg"), quality=80)
print("frames", len(tiles), "sheets", (len(tiles) + 11) // 12)
