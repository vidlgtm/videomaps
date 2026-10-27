#!/usr/bin/env python3
"""Review helpers of the production line.
usage:
  python factory/line/review.py times <film.json> <total_s>         review still times (opening, title, every chapter card,
                                                                    every 3D piece and document clip, settled camera views, end)
  python factory/line/review.py key <orderDir> <engineDir> [music.json]
        approval key of the stills: the order's files (without "approved"), film.json (without its build time), the voice
        timeline and the names of every asset -> the film rendered later is exactly the one whose stills were approved
  python factory/line/review.py approved <orderDir> <key>           exit 0 when order.json "approved": {"stills": key}
  python factory/line/review.py parts <total_s> [frames_per_part=900] [max_parts=18]   render matrix -> JSON list"""
import glob, hashlib, json, math, os, sys

ORDER_FILES = ("order.json", "narration.json", "storyboard.json", "sources.json", "scenes.json", "store.json", "objects.json")


def times(film, total):
    F = json.load(open(film))
    T = float(total)
    ts = [1.0, 4.0]
    op = F.get("opening") or {}
    if op.get("mapIn", 0) > 0: ts.append(op["mapIn"] + 1.2)
    if F.get("title"): ts.append(F["title"]["from"] + 3.0)
    ts += [c["from"] + 1.2 for c in F.get("cards", []) if c.get("kind") == "chapter"]
    for c in F.get("clips", []):
        d = c["to"] - c["from"]
        ts.append(c["from"] + min(1.6, d / 2))
        if d > 6: ts.append(c["to"] - 0.8)
    if F.get("credits"): ts.append(F["credits"]["from"] + 2.0)
    ts.append(T - 2.0)
    settled = [k["t"] + k.get("dur", 0) + 0.4 for k in F.get("camera", []) if k.get("dur", 0) > 1.5]
    room = max(0, 36 - len(ts))
    if settled and room:
        step = max(1, len(settled) // room)
        ts += settled[::step][:room]
    out = []
    for t in sorted(x for x in ts if 0 <= x < T - 0.5):
        if not out or t - out[-1] >= 1.2: out.append(round(t, 1))
    return out


def stills_key(odir, edir, music=None):
    h = hashlib.sha256()
    for f in ORDER_FILES:
        p = os.path.join(odir, f)
        if not os.path.exists(p): continue
        if f == "order.json":
            o = json.load(open(p, encoding="utf-8")); o.pop("approved", None)
            h.update(json.dumps(o, sort_keys=True).encode())
        else:
            h.update(open(p, "rb").read())
    F = json.load(open(os.path.join(edir, "src/data/film.json")))
    F.get("meta", {}).pop("generated", None)
    h.update(json.dumps(F, sort_keys=True).encode())
    h.update(open(os.path.join(edir, "src/data/timeline.json"), "rb").read())
    pub = os.path.join(edir, "public")
    for f in sorted(glob.glob(pub + "/**/*", recursive=True)):
        if os.path.isfile(f): h.update(os.path.relpath(f, pub).encode() + b"\n")
    if music and os.path.exists(music):
        M = json.load(open(music))
        h.update(json.dumps({k: [v.get("key"), v.get("take")] for k, v in M.items()}, sort_keys=True).encode())
    return h.hexdigest()[:16]


def main(a):
    if not a: print(__doc__); sys.exit(1)
    c = a[0]
    if c == "times" and len(a) == 3: print(" ".join(str(t) for t in times(a[1], a[2])))
    elif c == "key" and len(a) in (3, 4): print(stills_key(a[1], a[2], a[3] if len(a) == 4 else None))
    elif c == "approved" and len(a) == 3:
        o = json.load(open(os.path.join(a[1], "order.json"), encoding="utf-8"))
        ok = (o.get("approved") or {}).get("stills") == a[2]
        print(f"stills {a[2]}: {'APPROVED' if ok else 'not approved yet'} (order.json \"approved\": {{\"stills\": \"{a[2]}\"}})")
        sys.exit(0 if ok else 1)
    elif c == "parts" and len(a) >= 2:
        frames = math.ceil(float(a[1]) * 30)
        per = int(a[2]) if len(a) > 2 else 900
        mx = int(a[3]) if len(a) > 3 else 18
        print(json.dumps(list(range(min(mx, max(1, math.ceil(frames / per)))))))
    else: print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
