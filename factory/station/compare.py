#!/usr/bin/env python3
"""Station result against a reference result (same order): every file of the reference pack, pixel by pixel.
usage: python compare.py <new pack dir> <reference pack dir>
same   = identical bytes
noise  = same size, mean difference <= 0.5 and 99.9 % of pixels within 8 levels (model arithmetic, invisible)
DIFF   = anything else (listed). pack.json: placement data (aspect, focus) and credits compared too."""
import json, os, sys


def img_diff(a, b):
    import numpy as np
    from PIL import Image
    A, B = Image.open(a), Image.open(b)
    if A.size != B.size or A.mode != B.mode: return f"size/mode {A.size} {A.mode} vs {B.size} {B.mode}", False
    x = np.abs(np.asarray(A, np.int16) - np.asarray(B, np.int16))
    mean, p999 = float(x.mean()), float(np.percentile(x, 99.9))
    return f"mean {mean:.3f} p99.9 {p999:.0f} max {int(x.max())}", mean <= 0.5 and p999 <= 8


def main(new, ref):
    rows, diff = [], 0
    for d, _, fs in os.walk(ref):
        for f in sorted(fs):
            r = os.path.join(d, f); rel = os.path.relpath(r, ref); n = os.path.join(new, rel)
            if rel in ("pack.json", "station_report.txt") or rel.startswith(("sheets/", "clips/")): continue
            if not os.path.exists(n): rows.append(f"DIFF  {rel}: missing in the new pack"); diff += 1; continue
            if open(r, "rb").read() == open(n, "rb").read(): rows.append(f"same  {rel}"); continue
            if rel.lower().endswith((".jpg", ".png")):
                msg, ok = img_diff(n, r)
                rows.append(f"{'noise' if ok else 'DIFF '} {rel}: {msg}"); diff += 0 if ok else 1
            else: rows.append(f"DIFF  {rel}: bytes differ"); diff += 1
    P, Q = json.load(open(os.path.join(new, "pack.json"))), json.load(open(os.path.join(ref, "pack.json")))
    for sect in ("archive", "cutouts", "docs", "sig", "flags"):
        for k in sorted(set(P.get(sect, {})) | set(Q.get(sect, {}))):
            a, b = P.get(sect, {}).get(k), Q.get(sect, {}).get(k)
            if a != b: rows.append(f"DIFF  pack.{sect}.{k}: {a} vs {b}"); diff += 1
    ca = {c["id"]: c for c in P.get("credits", [])}; cb = {c["id"]: c for c in Q.get("credits", [])}
    for k in sorted(set(ca) | set(cb)):
        a, b = ca.get(k), cb.get(k)
        if a != b: rows.append(f"DIFF  credits.{k}: {json.dumps(a, ensure_ascii=False)} vs {json.dumps(b, ensure_ascii=False)}"); diff += 1
    print("\n".join(rows))
    same = sum(r.startswith("same") for r in rows); noise = sum(r.startswith("noise") for r in rows)
    print(f"\nSTATION COMPARISON: {same} identical, {noise} within model noise, {diff} different")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
