from manim import *


class Smoke(Scene):
    def construct(self):
        title = Text("Stalin's 3 Criteria (1936)", font_size=60, weight=BOLD, color="#F1E9D2")
        self.play(Write(title), run_time=1.0)
        self.play(title.animate.to_edge(UP, buff=0.8), run_time=0.6)
        rows = ["1. Located on the USSR's outer border", "2. Titular nation forms a compact majority", "3. Population of at least one million"]
        items = VGroup(*[Text(t, font_size=38, color=WHITE) for t in rows]).arrange(DOWN, aligned_edge=LEFT, buff=0.55)
        self.play(LaggedStart(*[FadeIn(i, shift=RIGHT * 0.6) for i in items], lag_ratio=0.35), run_time=1.6)
        marks = VGroup(*[Text("✓", font_size=48, color="#2ECC71").next_to(i, RIGHT, buff=0.4) for i in items])
        self.play(LaggedStart(*[GrowFromCenter(m) for m in marks], lag_ratio=0.25), run_time=0.9)
        box = SurroundingRectangle(items[0], color="#F4D03F", buff=0.2, corner_radius=0.1)
        self.play(Create(box), run_time=0.7)
        self.wait(0.6)
