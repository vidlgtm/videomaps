"""Equirectangular overlay of the USSR (1991 borders) for the Three.js globe intro."""
import sys
import geopandas as gpd
from shapely.geometry import MultiPolygon
from shapely.ops import unary_union
from PIL import Image, ImageDraw, ImageFilter

out = sys.argv[1] if len(sys.argv) > 1 else "ussr_overlay.png"
W, H = 4096, 2048
a0 = gpd.read_file("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries_lakes.geojson")
ISO = ["RUS", "UKR", "BLR", "KAZ", "UZB", "TKM", "KGZ", "TJK", "GEO", "ARM", "AZE", "MDA", "EST", "LVA", "LTU"]
U = unary_union(a0[a0["ADM0_A3"].isin(ISO)].geometry.values)
P = lambda lon, lat: ((lon + 180) / 360 * W, (90 - lat) / 180 * H)
fill = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(fill)
edge = Image.new("RGBA", (W, H), (0, 0, 0, 0)); e = ImageDraw.Draw(edge)
for p in (U.geoms if isinstance(U, MultiPolygon) else [U]):
    pts = [P(x, y) for x, y in p.exterior.coords]
    d.polygon(pts, fill=(196, 48, 58, 120))
    e.line(pts + [pts[0]], fill=(255, 214, 140, 255), width=4)
glow = edge.filter(ImageFilter.GaussianBlur(6))
Image.alpha_composite(Image.alpha_composite(fill, glow), edge).save(out)
print("overlay", out)
