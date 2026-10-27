#!/usr/bin/env python3
"""HERMETIC CHECK - the factory takes pictures only from the order store (release store_<order>, see
factory/intake/store.py). Every web address in the factory's code and in the files its workflows run must be on the
list below: this repository (releases, API), software and model weights, and the fixed base map (satellite imagery,
relief, boundaries). Anything else - a photo archive, a museum, Wikimedia - stops the run before it starts.
Exit code 1 = a forbidden address (file, line, address)."""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALLOWED = [
    # this repository: releases, API, uploads
    ("github.com", "/vidlgtm/videomaps"), ("github.com", "/${{"), ("github.com", "/{REPO}"),     # (the last two: variables = this repository)
    ("api.github.com", ""), ("uploads.github.com", ""),
    # software and model weights
    ("download.blender.org", ""), ("download.pytorch.org", ""), ("pypi.org", ""), ("registry.npmjs.org", ""),
    ("huggingface.co", ""), ("github.com", "/xinntao/Real-ESRGAN/releases/"), ("github.com", "/opencv/opencv_zoo/"),
    ("github.com", "/VAST-AI-Research/TripoSR"), ("github.com", "/Tencent/Hunyuan3D-2"),
    ("github.com", "/ace-step/ACE-Step-1.5"),
    # fixed base map of every film (same for all films, not chosen per film)
    ("tiles.maps.eox.at", "/wmts/1.0.0/s2cloudless"), ("s3.amazonaws.com", "/elevation-tiles-prod/"),
    ("eoimages.gsfc.nasa.gov", "/images/imagerecords/"), ("raw.githubusercontent.com", "/nvkelso/natural-earth-vector/"),
]
SKIP_DIRS = {"node_modules", ".git", "intake", "media", "out", "cache", "store_files", "__pycache__"}
CODE = (".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".sh", ".yml", ".yaml")
URL = re.compile(r"https?://([A-Za-z0-9.-]+)(/[^\s\"'`)<>]*)?")


def files():
    for d, subs, fs in os.walk(os.path.join(ROOT, "factory")):
        subs[:] = [s for s in subs if s not in SKIP_DIRS]
        for f in fs:
            if f.endswith(CODE): yield os.path.join(d, f)
    wf = os.path.join(ROOT, ".github", "workflows")
    for f in sorted(os.listdir(wf)) if os.path.isdir(wf) else []:
        p = os.path.join(wf, f)
        if f.endswith((".yml", ".yaml")):
            yield p
            for m in set(re.findall(r"(production/[\w./-]+\.(?:py|sh|mjs|js|ts))", open(p, encoding="utf-8").read())):
                if os.path.exists(os.path.join(ROOT, m)): yield os.path.join(ROOT, m)


def allowed(host, path):
    host = host.lower().rstrip(".")
    if host in ("...", "") or set(host) <= {"."}: return True        # placeholder in a comment
    return any(host == h and (path or "/").startswith(p or "/") for h, p in ALLOWED)


def main():
    bad = []
    for p in sorted(set(files())):
        for n, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
            for m in URL.finditer(line):
                if not allowed(m.group(1), m.group(2) or ""):
                    bad.append(f"{os.path.relpath(p, ROOT)}:{n}: {m.group(0)[:120]}")
    if bad:
        print("HERMETIC CHECK FAILED - the factory may take pictures only from the order store:")
        for b in bad: print("  ", b)
        sys.exit(1)
    print("hermetic check ok: every address is this repository, software, model weights or the fixed base map")


if __name__ == "__main__":
    main()
