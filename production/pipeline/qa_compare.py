#!/usr/bin/env python3
"""Compare frames of a rendered chunk with fresh-page reference stills (rendered at scale 0.25).
usage: qa_compare.py VIDEO FIRST_FRAME REFDIR f1 f2 ...   -> exit 1 if any 15x15 block (at 480x270) differs strongly
(a dropped card / flag / label gives block differences far above the threshold; encoding noise stays well below)."""
import sys, subprocess, numpy as np
from PIL import Image
video, a, refdir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
frames = [int(x) for x in sys.argv[4:]]
TH = 28.0
bad, n = [], 0
for f in frames:
    try:
        r = np.asarray(Image.open(f'{refdir}/ref_{f}.jpg').convert('L').resize((480, 270)), np.float32)
    except Exception:
        print(f, 'no reference'); continue
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vf', f'select=eq(n\\,{f - a}),scale=480:270', '-frames:v', '1',
                          '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True).stdout
    if len(raw) != 480 * 270:
        bad.append((f, 'no frame')); continue
    v = np.frombuffer(raw, np.uint8).reshape(270, 480).astype(np.float32)
    blk = np.abs(v - r).reshape(18, 15, 32, 15).mean(axis=(1, 3))
    m = float(blk.max()); n += 1
    print(f, round(m, 1))
    if m > TH: bad.append((f, round(m, 1)))
print('checked', n, 'flagged', bad)
sys.exit(1 if bad else 0)
