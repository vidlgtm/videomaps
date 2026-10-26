"""Workshop template 'cloth' - fetches the flag picture (Wikimedia Commons file, rendered to PNG by Commons, or a
direct PNG/JPG url) + its licence for the credits.  usage: python3 cloth_prep.py <params.json> <out_dir>"""
import json, os, sys, time, io, re
import numpy as np, requests
from PIL import Image

P = json.load(open(sys.argv[1])); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
F = P["flag"]; H = {"User-Agent": "videomaps-workshop/1.0 (map history films)"}


def get(url, **kw):
    for i in range(6):
        try:
            r = requests.get(url, timeout=60, headers=H, **kw); r.raise_for_status(); return r
        except Exception:
            time.sleep(2 + 3 * i)
    raise RuntimeError(url)


meta = {}
if F.get("commons"):
    t = F["commons"] if F["commons"].startswith("File:") else "File:" + F["commons"]
    d = get("https://commons.wikimedia.org/w/api.php", params={"action": "query", "titles": t, "prop": "imageinfo",
            "iiprop": "url|size|extmetadata", "iiurlwidth": 2560, "format": "json"}).json()
    ii = next(iter(d["query"]["pages"].values()))["imageinfo"][0]
    em = ii.get("extmetadata", {})
    lic = em.get("LicenseShortName", {}).get("value", "")
    if not re.search(r"public domain|^pd|cc0|cc by(-sa)? ", lic.lower() + " "):
        raise SystemExit(f"licence not allowed for {t}: {lic}")
    art = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", "")).strip()
    url = ii.get("thumburl") or ii["url"]
    meta = {"what": t[5:].rsplit(".", 1)[0], "license": "Public domain" if "public domain" in lic.lower() or lic.lower().startswith("pd") else lic,
            "author": art, "page": ii.get("descriptionurl", "")}
else:
    url = F["url"]
im = Image.open(io.BytesIO(get(url).content)).convert("RGB")
if im.width < 2000: im = im.resize((2000, round(im.height * 2000 / im.width)), Image.LANCZOS)
im.save(f"{OUT}/flag.png")
a = np.asarray(im, np.float32) / 255
meta.update({"aspect": im.width / im.height, "size": im.size,
             "luma": round(float((0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]).mean()), 4)})
json.dump(meta, open(f"{OUT}/meta.json", "w"))
print("flag", im.size, meta.get("license", ""), flush=True)
