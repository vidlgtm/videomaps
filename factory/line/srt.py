#!/usr/bin/env python3
"""Subtitles from a voice timeline (same line rules as factory/line/voice.py).
usage: python factory/line/srt.py <timeline.json> <out.srt>"""
import json, re, sys


def ts(x):
    h, r = divmod(x, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


def main(a):
    if len(a) != 2: print(__doc__); sys.exit(1)
    words = json.load(open(a[0]))["words"]
    lines, cur = [], []
    for w in words:
        cur.append(w)
        txt = " ".join(x["w"] for x in cur)
        if len(txt) > 38 or re.search(r"[.?!]$", w["w"]) or (re.search(r"[,;:]$", w["w"]) and len(txt) > 24):
            lines.append(cur); cur = []
    if cur: lines.append(cur)
    with open(a[1], "w") as fh:
        for i, L in enumerate(lines, 1):
            fh.write(f"{i}\n{ts(L[0]['t0'])} --> {ts(L[-1]['t1'])}\n{' '.join(x['w'] for x in L)}\n\n")
    print(f"subtitles: {len(lines)} lines")


if __name__ == "__main__":
    main(sys.argv[1:])
