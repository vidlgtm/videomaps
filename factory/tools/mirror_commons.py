#!/usr/bin/env python3
"""Keeps a copy of Wikimedia Commons pictures in the factory cache release, for runners that Wikimedia rate-limits.
The copy is the standard 1920 px rendering (or the original when it is smaller) - the same bytes the preps download -
stored as cm_<sha1(title)[:16]>.  Existing copies are kept.
usage: GH_TOKEN=... python3 factory/tools/mirror_commons.py "File:..." ["File:..." ...]"""
import hashlib, os, sys, time
import requests

REPO = os.environ.get("REPO", "vidlgtm/videomaps"); TAG = "factory_ws_cache"
H = {"User-Agent": "videomaps-workshop-bot/1.0 (https://github.com/vidlgtm/videomaps)"}
GH = {"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"}
API = f"https://api.github.com/repos/{REPO}"

rel = requests.get(f"{API}/releases/tags/{TAG}", headers=GH, timeout=60); rel.raise_for_status(); rel = rel.json()
have, page = set(), 1
while True:
    r = requests.get(f"{API}/releases/{rel['id']}/assets", params={"per_page": 100, "page": page}, headers=GH, timeout=60)
    r.raise_for_status(); got = r.json(); have |= {x["name"] for x in got}
    if len(got) < 100: break
    page += 1

bad = 0
for t in sys.argv[1:]:
    t = t if t.startswith("File:") else "File:" + t
    name = "cm_" + hashlib.sha1(t.encode()).hexdigest()[:16]
    if name in have: print(f"kept    {name}  {t}"); continue
    d = requests.get("https://commons.wikimedia.org/w/api.php", headers=H, timeout=60, params={
        "action": "query", "titles": t, "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": 1920, "format": "json"}).json()
    pg = next(iter(d["query"]["pages"].values()))
    if "imageinfo" not in pg: print(f"MISSING {t}"); bad += 1; continue
    ii = pg["imageinfo"][0]
    b = requests.get(ii.get("thumburl") or ii["url"], headers=H, timeout=120)
    if b.status_code != 200: print(f"HTTP {b.status_code} {t}"); bad += 1; continue
    up = requests.post(rel["upload_url"].split("{")[0], params={"name": name}, data=b.content, timeout=300,
                       headers=dict(GH, **{"Content-Type": "application/octet-stream"}))
    print(f"{'stored ' if up.status_code == 201 else 'FAILED ' + str(up.status_code)} {name}  {t}  {len(b.content)} B")
    bad += up.status_code != 201
    time.sleep(1)
sys.exit(1 if bad else 0)
