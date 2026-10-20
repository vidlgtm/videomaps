#!/usr/bin/env python3
"""Contact sheets of the finished film at key moments (12 frames per sheet, 480x270 each, timestamped).
usage: qa_sheets.py VIDEO OUT_DIR"""
import subprocess, sys, os
from PIL import Image, ImageDraw
video, out = sys.argv[1], sys.argv[2]
T = [3, 8, 14, 18, 33, 39, 47, 58, 61, 75, 90, 112, 128, 137, 150, 166, 192, 210, 230, 244.9, 267, 285, 306, 320,
     331.5, 333.5, 343, 347, 354.5, 358, 362, 380, 396, 416, 420, 428.9, 430.2, 431.6, 440, 453, 466, 480, 503, 520,
     535, 544, 549, 552, 556, 559.5]
W, H = 480, 270
tiles = []
for t in T:
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', video, '-frames:v', '1', '-vf', f'scale={W}:{H}',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    if len(raw) == W * H * 3: tiles.append((t, Image.frombytes('RGB', (W, H), raw)))
for si in range(0, len(tiles), 12):
    grp = tiles[si:si + 12]
    sheet = Image.new('RGB', (W * 4, H * 3), 'black'); d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(grp):
        x, y = (i % 4) * W, (i // 4) * H
        sheet.paste(im, (x, y)); d.rectangle([x, y, x + 62, y + 16], fill='black'); d.text((x + 3, y + 2), f'{t}s', fill='yellow')
    sheet.save(os.path.join(out, f'qa_sheet_{si // 12 + 1}.jpg'), quality=80)
print('sheets', (len(tiles) + 11) // 12)
