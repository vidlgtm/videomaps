"""QA contact sheets for the tiles5 additions: every new tile in the middle of its 3x3 neighbourhood (existing tiles from
assets3/assets4), so seams against the old tiles are visible at a glance."""
import os, json, zipfile, io
from PIL import Image, ImageDraw

def sheet(cells, get, step, name, px=300):
    mos = []
    for c in cells:
        m = Image.new("RGB", (3 * px, 3 * px), (12, 24, 34))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                im = get(c[0] + dx * step, c[1] + dy * step)
                if im is not None: m.paste(im.resize((px, px), Image.LANCZOS), ((dx + 1) * px, (dy + 1) * px))
        ImageDraw.Draw(m).text((8, 8), str(c), fill=(255, 230, 120))
        mos.append(m)
    cols = 3 if len(mos) > 4 else 2
    out = Image.new("RGB", (cols * 3 * px + (cols - 1) * 12, ((len(mos) + cols - 1) // cols) * (3 * px + 12)), (0, 0, 0))
    for n, m in enumerate(mos): out.paste(m, ((n % cols) * (3 * px + 12), (n // cols) * (3 * px + 12)))
    out.save(name, quality=90); print(name, out.size)

hz = zipfile.ZipFile("/tmp/hd_tiles.zip"); hn = set(hz.namelist())
def hd_get(i, j):
    p = f"out/hd5/hd/t_{i}_{j}.jpg"
    if os.path.exists(p): return Image.open(p).convert("RGB")
    for n in (f"hd/t_{i}_{j}.jpg", f"t_{i}_{j}.jpg"):
        if n in hn: return Image.open(io.BytesIO(hz.read(n))).convert("RGB")
    return None
sheet(json.loads(os.environ["HD_CELLS"]), hd_get, 1, "out/hd5_sheet.jpg")

uz = zipfile.ZipFile("/tmp/uhd.zip"); un = set(uz.namelist())
def uhd_get(x, y):
    p = f"out/terrain3/uhd/u_{x}_{y}.jpg"
    if os.path.exists(p): return Image.open(p).convert("RGB")
    for n in (f"uhd/u_{x}_{y}.jpg", f"u_{x}_{y}.jpg"):
        if n in un: return Image.open(io.BytesIO(uz.read(n))).convert("RGB")
    return None
sheet(json.loads(os.environ["UHD_TILES"]), uhd_get, 256, "out/uhd5_sheet.jpg")
