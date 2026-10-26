"""Timeline of the 'shatter' template, shared by the preflight (is the clip long enough?) and the Blender script.
break: crack (shared borders light up) -> split (pieces move apart and lift, one after another) -> flags (each top wipes
       from the union flag to its own flag) -> hold
rise : rise (pieces lift out of the map, tops showing the land) -> flags (tops wipe to their flags) -> hold
drop : drop (pieces fall into place, one after another, and land with a ring in their own outline) -> hold"""

HOLD_MIN = 1.0
KEYS = {"break": ("crack", "split", "flags"), "rise": ("rise", "flags"), "drop": ("drop",)}


def clamp(x, a, b):
    return max(a, min(b, x))


def schedule(action, sec, n, timing=None):
    """phase start times (s), per-piece durations and staggers; ValueError when the order cannot fit in the clip"""
    tm = dict(timing or {})
    bad = set(tm) - set(KEYS.get(action, ()))
    if bad: raise ValueError(f"timing for {action}: unknown key(s) {', '.join(sorted(bad))} (allowed: {', '.join(KEYS[action])})")
    k = max(1, n - 1)
    s = {"action": action, "n": n, "sec": float(sec)}
    if action == "break":
        s["crack"] = float(tm.get("crack", max(1.0, 0.13 * sec)))
        s["split"] = float(tm.get("split", s["crack"] + max(0.6, 0.06 * sec)))
        s["move"] = clamp(0.16 * sec, 1.3, 2.4)
        s["stagger"] = min(0.12, 0.8 / k)
        s["flags"] = float(tm.get("flags", s["split"] + 0.55 * s["move"]))
        s["wipe"], s["wstagger"] = 0.9, min(0.32, 2.2 / k)
        if s["split"] < s["crack"] + 0.4: raise ValueError("timing: split must come at least 0.4 s after crack")
        if s["flags"] < s["split"] + 0.3: raise ValueError("timing: flags must come at least 0.3 s after split")
        s["motion_end"] = s["split"] + s["stagger"] * (n - 1) + s["move"]
        s["flags_end"] = s["flags"] + s["wstagger"] * (n - 1) + s["wipe"]
    elif action == "rise":
        s["rise"] = float(tm.get("rise", max(0.6, 0.1 * sec)))
        s["move"] = clamp(0.15 * sec, 1.2, 2.2)
        s["stagger"] = min(0.25, 1.5 / k)
        s["flags"] = float(tm.get("flags", s["rise"] + 0.7 * s["move"]))
        s["wipe"], s["wstagger"] = 0.9, min(0.3, 2.0 / k)
        if s["flags"] < s["rise"] + 0.3: raise ValueError("timing: flags must come at least 0.3 s after rise")
        s["motion_end"] = s["rise"] + s["stagger"] * (n - 1) + s["move"]
        s["flags_end"] = s["flags"] + s["wstagger"] * (n - 1) + s["wipe"]
    elif action == "drop":
        s["drop"] = float(tm.get("drop", max(0.5, 0.08 * sec)))
        s["move"] = clamp(0.08 * sec, 0.7, 1.1)
        s["stagger"] = min(0.3, 1.8 / k)
        s["bounce"], s["ring"] = 0.35, 1.1
        s["motion_end"] = s["drop"] + s["stagger"] * (n - 1) + s["move"] + s["bounce"]
        s["flags_end"] = s["drop"] + s["stagger"] * (n - 1) + s["move"] + s["ring"]
    else:
        raise ValueError(f"unknown action {action!r}")
    first = min(v for key, v in s.items() if key in KEYS[action])
    if first < 0: raise ValueError("timing values must be >= 0")
    s["end"] = max(s["motion_end"], s["flags_end"])
    if s["end"] + HOLD_MIN > sec:
        raise ValueError(f"{sec:g} s is too short for {n} pieces with this timing: the animation ends at {s['end']:.1f} s "
                         f"and needs {HOLD_MIN:g} s of hold (seconds >= {s['end'] + HOLD_MIN:.1f})")
    return s


def ease_out_back(p, over=1.0):
    p = clamp(p, 0.0, 1.0) - 1.0
    return 1.0 + p * p * ((over + 1.0) * p + over)


def smooth(x):
    x = clamp(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)
