"""Generic Manim parchment document of our films (no charts): a hand-written reveal on aged paper, full frame,
used in the film as a full-frame clip (script.ts CLIPS kind 'cauc', src 'clips/<name>.mp4').
One JSON per document (projects/<p>/manim/<name>.json):
  {"head": "TREATY OF NON-AGGRESSION  ·  MOSCOW, 23 AUGUST 1939", "title": "Secret Additional Protocol",
   "title_font": "Cormorant Garamond" | "Great Vibes", "body": ["line 1", "line 2", "line 3"], "underline": 1 | null,
   "seal": "1939" | null, "hold": 2.2}
render: DOC_JSON=path manim render -qh --fps 30 -r 1920,1080 doc_scene.py Doc   (fonts: repo fonts/ installed to ~/.local/share/fonts)"""
import json, os
import numpy as np
from manim import *
from scipy.ndimage import gaussian_filter, zoom

INK, RED, BROWN = "#2A1D12", "#8E1B1B", "#5A4026"


def parchment(w=1920, h=1080, seed=3):
    rng = np.random.default_rng(seed)
    base = np.array([234, 222, 192], np.float32)
    n = gaussian_filter(rng.standard_normal((h // 4, w // 4)).astype(np.float32), 7) * 16 + \
        gaussian_filter(rng.standard_normal((h // 4, w // 4)).astype(np.float32), 1.0) * 4
    n = zoom(n, 4, order=1)[:h, :w]
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    vign = np.clip(1 - 0.55 * np.clip(r - 0.5, 0, 1) ** 1.4, 0.55, 1)
    img = (base[None, None, :] + n[..., None]) * vign[..., None]
    img[..., 2] *= 0.96
    return np.clip(img, 0, 255).astype(np.uint8)


def seal(label):
    edge = Star(n=28, outer_radius=1.05, inner_radius=0.94, color=RED, fill_color=RED, fill_opacity=1, stroke_width=0)
    disc = Circle(radius=0.86, color="#6E1212", stroke_width=5, fill_color="#9A2020", fill_opacity=1)
    ring = Circle(radius=0.70, color="#C9665E", stroke_width=2)
    t = Text(label, font="Cormorant Garamond", weight=BOLD, color="#F6DDB8").scale(0.62)
    return VGroup(edge, disc, ring, t)


class Doc(Scene):
    def construct(self):
        d = json.load(open(os.environ["DOC_JSON"]))
        im = ImageMobject(parchment()); im.stretch_to_fit_width(config.frame_width); im.stretch_to_fit_height(config.frame_height)
        self.add(im)
        head = Text(d["head"], font="Cormorant Garamond", weight=BOLD, color=BROWN).scale(0.62).to_edge(UP, buff=1.05)
        rule = Line(LEFT * 3.2, RIGHT * 3.2, color=BROWN, stroke_width=2).next_to(head, DOWN, buff=0.28)
        script = d.get("title_font", "Cormorant Garamond") == "Great Vibes"
        title = (Text(d["title"], font="Great Vibes", color=INK).scale(1.7) if script else
                 Text(d["title"], font="Cormorant Garamond", slant=ITALIC, weight=BOLD, color=RED).scale(1.0)).next_to(rule, DOWN, buff=0.55)
        # A document may request a narrower body to preserve a clear safe area for a seal.
        # This prevents long treaty lines from reaching, or being cropped by, the frame edge.
        body = Paragraph(*d["body"], font="Cormorant Garamond", alignment="center", line_spacing=0.85, color=INK).scale(d.get("body_scale", 1.05))
        max_body_width = d.get("body_max_width")
        if max_body_width and body.width > max_body_width:
            body.scale(max_body_width / body.width)
        body.next_to(title, DOWN, buff=d.get("body_buff", 0.6))
        self.play(FadeIn(head, shift=DOWN * 0.15), Create(rule), run_time=0.8)
        self.play(Write(title), run_time=0.7 if not script else 1.4)
        self.play(Write(body), run_time=max(1.2, 0.7 * len(d["body"])), rate_func=linear)
        if d.get("underline") is not None:
            self.play(Create(Underline(body[d["underline"]], color=RED, stroke_width=7, buff=0.08)), run_time=0.5)
        if d.get("seal"):
            sl = seal(d["seal"]).scale(d.get("seal_scale", 0.95))
            # Optional document-specific placement keeps a date seal in its own blank area.
            if d.get("seal_placement") == "below_body_right":
                sl.next_to(body, DOWN, buff=d.get("seal_buff", 0.35)).align_to(body, RIGHT)
            else:
                sl.to_corner(DR, buff=1.0)
            self.play(FadeIn(sl, scale=1.6), run_time=0.35, rate_func=rush_into)
            self.play(sl.animate.scale(1.04), run_time=0.12, rate_func=there_and_back)
        self.wait(d.get("hold", 2.2))
