"""Manim overlays (transparent, 1080p30). Each scene builds, then holds, so Remotion can trim to the narration.
Palette matches the map: ink #0E1A24, parchment text #F2EEE6, gold #D9B45A, crimson #B3363F, teal #3E8E8A."""
from manim import *

INK, TXT, GOLD, RED, TEAL, MUTED = "#0E1A24", "#F2EEE6", "#D9B45A", "#C2414B", "#4FA39E", "#9AA6AE"
HEAD, BODY = "Cinzel", "Inter"
HOLD = 9


def panel(w, h, op=0.86):
    return RoundedRectangle(width=w, height=h, corner_radius=0.18, fill_color=INK, fill_opacity=op,
                            stroke_color=GOLD, stroke_width=1.6, stroke_opacity=0.8)


def T(s, size=34, color=TXT, font=BODY, weight=NORMAL):
    return Text(s, font=font, font_size=size, color=color, weight=weight)


class ThreeRules(Scene):
    """Stalin, 1936: three conditions for a union republic."""
    def construct(self):
        p = panel(10.6, 6.2).shift(RIGHT * 1.2)
        title = T("STALIN'S THREE RULES  ·  1936", 40, GOLD, HEAD, BOLD).next_to(p.get_top(), DOWN, 0.45)
        line = Line(LEFT * 4.2, RIGHT * 4.2, color=GOLD, stroke_width=1.2).next_to(title, DOWN, 0.22)
        self.play(FadeIn(p, scale=0.97), run_time=0.6)
        self.play(Write(title), Create(line), run_time=1.0)
        rules = [("1", "On the outer border of the USSR", "so it could, in theory, leave"),
                 ("2", "A compact titular majority", "its namesake nation forms the core"),
                 ("3", "At least about 1 million people", "large enough to stand alone")]
        rows = VGroup()
        for i, (n, a, b) in enumerate(rules):
            badge = VGroup(Circle(0.36, color=GOLD, fill_color=RED, fill_opacity=1, stroke_width=2),
                           T(n, 30, TXT, HEAD, BOLD))
            txt = VGroup(T(a, 34, TXT, BODY, BOLD), T(b, 24, MUTED)).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
            row = VGroup(badge, txt).arrange(RIGHT, buff=0.45)
            rows.add(row)
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.55).next_to(line, DOWN, 0.55).align_to(line, LEFT).shift(RIGHT * 0.2)
        for row in rows:
            self.play(FadeIn(row[0], scale=0.6), FadeIn(row[1], shift=RIGHT * 0.3), run_time=0.7)
            self.wait(1.6)
        self.play(Indicate(rows[0], color=GOLD, scale_factor=1.04), run_time=1.2)
        self.wait(HOLD)


class TatarstanEstonia(Scene):
    """1989 comparison: only the border rule separates them."""
    def construct(self):
        p = panel(12.6, 6.4)
        self.play(FadeIn(p, scale=0.97), run_time=0.5)
        hdr = VGroup(T("", 30), T("TATARSTAN", 38, GOLD, HEAD, BOLD), T("ESTONIA", 38, GOLD, HEAD, BOLD))
        rows = [("Population (1989)", "3.64 million", "1.57 million"),
                ("Titular nation", "48.5% Tatar", "61.5% Estonian"),
                ("On the outer border", "✗", "✓"),
                ("Status", "Autonomous republic", "Union republic")]
        grid = VGroup(*hdr)
        for a, b, c in rows:
            col_b = RED if b == "✗" else TXT
            col_c = TEAL if c == "✓" else TXT
            sz_b = 52 if b in "✗✓" else 32
            sz_c = 52 if c in "✗✓" else 32
            grid.add(T(a, 28, MUTED), T(b, sz_b, col_b, BODY, BOLD), T(c, sz_c, col_c, BODY, BOLD))
        grid.arrange_in_grid(rows=5, cols=3, buff=(0.9, 0.42), col_alignments="lcc").move_to(p)
        self.play(FadeIn(grid[1], shift=DOWN * 0.2), FadeIn(grid[2], shift=DOWN * 0.2), run_time=0.7)
        for i in range(4):
            r = grid[3 + 3 * i: 6 + 3 * i]
            self.play(FadeIn(r[0], shift=RIGHT * 0.2), FadeIn(r[1]), FadeIn(r[2]), run_time=0.6)
            if i == 2:
                self.play(Circumscribe(VGroup(*r), color=GOLD, time_width=1.5), run_time=1.2)
            self.wait(1.2)
        self.wait(HOLD)


class Timeline(Scene):
    """Number of union republics, 1922-1991."""
    def construct(self):
        pts = [("1922", 4), ("1924", 6), ("1929", 7), ("1936", 11), ("1940", 16), ("1956", 15), ("1991", 15)]
        bar = Line(LEFT * 6, RIGHT * 6, color=TXT, stroke_width=3).shift(DOWN * 1.2)
        base = panel(13.4, 4.6).shift(DOWN * 0.4)
        self.play(FadeIn(base, scale=0.98), Create(bar), run_time=0.9)
        cnt = Integer(0, font_size=110, color=GOLD, mob_class=Text).shift(UP * 0.9)
        cap = T("union republics", 30, MUTED).next_to(cnt, DOWN, 0.1)
        self.play(FadeIn(cnt), FadeIn(cap), run_time=0.4)
        for i, (y, n) in enumerate(pts):
            x = -6 + 12 * i / (len(pts) - 1)
            dot = Dot([x, -1.2, 0], radius=0.11, color=RED if y in ("1940", "1956") else GOLD)
            yl = T(y, 30, TXT, HEAD, BOLD).next_to(dot, DOWN, 0.25)
            nl = T(str(n), 26, MUTED).next_to(dot, UP, 0.25)
            self.play(FadeIn(dot, scale=0.4), FadeIn(yl, shift=UP * 0.1), FadeIn(nl),
                      ChangeDecimalToValue(cnt, n), run_time=0.8)
            if y == "1991":
                self.play(cnt.animate.set_color(TXT), Flash(dot, color=GOLD), run_time=0.6)
            self.wait(0.5)
        self.wait(HOLD)


class SecessionLaw(Scene):
    """April 1990 law: the exit door made deliberately narrow."""
    def construct(self):
        p = panel(13.0, 5.2)
        title = T("THE 1990 SECESSION LAW", 40, GOLD, HEAD, BOLD).next_to(p.get_top(), DOWN, 0.4)
        self.play(FadeIn(p, scale=0.97), Write(title), run_time=0.9)
        steps = [("Referendum", "a vote in the republic"), ("Two-thirds", "of all registered voters"),
                 ("Up to 5 years", "of transition, then approval")]
        cards = VGroup()
        for a, b in steps:
            box = RoundedRectangle(width=3.5, height=2.0, corner_radius=0.15, stroke_color=GOLD, stroke_width=1.5,
                                   fill_color="#13232F", fill_opacity=1)
            txt = VGroup(T(a, 34, TXT, BODY, BOLD), T(b, 22, MUTED)).arrange(DOWN, buff=0.18).move_to(box)
            cards.add(VGroup(box, txt))
        cards.arrange(RIGHT, buff=0.85).next_to(title, DOWN, 0.55)
        arrows = VGroup(*[Arrow(cards[i].get_right(), cards[i + 1].get_left(), buff=0.12, color=GOLD, stroke_width=4)
                          for i in range(2)])
        for i, cd in enumerate(cards):
            self.play(FadeIn(cd, shift=UP * 0.25), run_time=0.6)
            if i < 2: self.play(GrowArrow(arrows[i]), run_time=0.4)
            self.wait(0.9)
        self.wait(HOLD)


class UtiPossidetis(Scene):
    """uti possidetis juris: internal lines become international borders."""
    def construct(self):
        p = panel(12.4, 6.2)
        self.play(FadeIn(p, scale=0.97), run_time=0.5)
        lat = T("uti possidetis juris", 64, GOLD, "Cormorant Garamond", BOLD).next_to(p.get_top(), DOWN, 0.5)
        tr = T("\u201cas you possess under law, so you shall possess\u201d", 28, MUTED).next_to(lat, DOWN, 0.2)
        self.play(Write(lat), run_time=1.4); self.play(FadeIn(tr, shift=UP * 0.1), run_time=0.7)
        a = Polygon([-4.6, -0.6, 0], [-1.2, -0.3, 0], [-0.9, -2.5, 0], [-4.4, -2.6, 0], stroke_width=0, fill_color=RED, fill_opacity=0.55)
        b = Polygon([-1.2, -0.3, 0], [2.2, -0.7, 0], [2.0, -2.6, 0], [-0.9, -2.5, 0], stroke_width=0, fill_color=TEAL, fill_opacity=0.55)
        dash = DashedLine([-1.2, -0.3, 0], [-0.9, -2.5, 0], color=TXT, dash_length=0.12, stroke_width=3)
        lab1 = T("internal line, 1990", 24, TXT).next_to(dash, RIGHT, 0.2).shift(UP * 0.8 + RIGHT * 0.2)
        self.play(FadeIn(a), FadeIn(b), Create(dash), FadeIn(lab1), run_time=1.0)
        self.wait(1.0)
        solid = Line([-1.2, -0.3, 0], [-0.9, -2.5, 0], color=GOLD, stroke_width=9)
        lab2 = T("international border, 1991", 24, GOLD, BODY, BOLD).move_to(lab1)
        self.play(Transform(dash, solid), Transform(lab1, lab2), run_time=1.2)
        side = VGroup(T("Union republics", 28, TXT, BODY, BOLD), T("legal borders  +  right to leave  \u2713", 24, TEAL),
                      T("Autonomous units", 28, TXT, BODY, BOLD), T("no right to leave  \u2717", 24, RED)
                      ).arrange(DOWN, aligned_edge=LEFT, buff=0.16).move_to([4.2, -1.5, 0])
        self.play(LaggedStart(*[FadeIn(s, shift=LEFT * 0.2) for s in side], lag_ratio=0.35), run_time=1.6)
        self.wait(HOLD)


class Hierarchy(Scene):
    """The nested system in 1989 - only the outer shell had the right to leave."""
    def construct(self):
        tiers = [("15", "Union republics", "constitutional right to leave", GOLD),
                 ("20", "Autonomous republics", "inside union republics", TXT),
                 ("8", "Autonomous regions", "", TXT), ("10", "Autonomous districts", "", TXT)]
        p = panel(9.6, 6.4).shift(RIGHT * 2.4)
        self.play(FadeIn(p, scale=0.97), run_time=0.5)
        rows = VGroup()
        for i, (n, a, b, col) in enumerate(tiers):
            num = T(n, 64 - 6 * i, col, HEAD, BOLD)
            lab = VGroup(T(a, 32 - 2 * i, TXT, BODY, BOLD), T(b, 22, TEAL if i == 0 else MUTED)) if b else VGroup(T(a, 32 - 2 * i, TXT, BODY, BOLD))
            lab.arrange(DOWN, aligned_edge=LEFT, buff=0.08)
            rows.add(VGroup(num, lab).arrange(RIGHT, buff=0.4))
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.42).move_to(p).shift(RIGHT * 0.2)
        for i, r in enumerate(rows):
            r.shift(RIGHT * 0.35 * i)
            self.play(FadeIn(r, shift=DOWN * 0.15), run_time=0.6); self.wait(0.9)
        key = SurroundingRectangle(rows[0], color=GOLD, buff=0.15, corner_radius=0.1)
        self.play(Create(key), run_time=0.8)
        self.wait(HOLD)
