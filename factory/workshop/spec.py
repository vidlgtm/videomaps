#!/usr/bin/env python3
"""3D SCENE DESCRIPTIONS - <order>/scenes.json. There are no ready-made scenes in the factory: every 3D shot of a film
is described in the order (what is there, where, what happens, how the camera moves), and the workshop builds it from
general tools (kit/). This file holds the vocabulary of those tools and checks a description before anything runs.

scenes.json
{"scenes": {"<id>": {
   "idea":   one sentence - what the viewer sees and why it matters to the story,
   "seconds": length of the rendered shot (2-40), taken from the word times of the read (film.yml stage voice ->
              words.txt); "t" below is shot time; the film holds the last frame if the words last longer,
   "output": "film" (full frame) | "over_map" (transparent, laid over the 2D map),
   "place":  {"kind": PLACE, "surface": MATERIAL, "region": [lon0, lat0, lon1, lat1] (terrain / sea only)},
   "light":  {"mood": MOOD, "weather": WEATHER},
   "cast":   {"<name>": {"is": NOUN, "from": "store:<key>" | "obj:<object name>" | "map:<ref>[+<ref>...]" | "terrain" |
                                    "text:<words>" | "none",
                         "material": MATERIAL, "size": metres or "S"|"M"|"L", "where": [RELATION, "<name>" | "place"],
                         "region": [lon0, lat0, lon1, lat1] (a terrain block), "at": [lon, lat] (on a terrain or sea
                         place; on a globe: the place it faces when its turns end - the shot lands on it)}},
             map refs: ISO3 | shape:<id> | rr:<region> | brk:<disputed area> (order.json); obj: = a model of objects.json;
             a country is its home land (its dependencies and lands with their own ISO 3166-1 entry, e.g. Svalbard or
             French Guiana, are left out); a cloth on a pole is a flag and shows its picture from the order store
   "beats":  [{"t": seconds, "do": VERB, "who": "<name>" ("place" for a route on a terrain or sea place), ...parameters}],
   "camera": [{"t": seconds, "move": MOVE, "to": "<name>", ...parameters}]   (the first one sets the opening framing)
}}}
usage: python spec.py <orderDir>     exit 2 = the description has errors (all listed at once)"""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "kit"))
from plan import BUILT          # the part of the vocabulary the kit has built so far

NOUNS = {   # what a cast member is -> the sources it can be made from
    "sheet": {"store", "none"}, "print": {"store"}, "canvas": {"store"}, "cutout": {"store"}, "cloth": {"store", "none"},
    "tile": {"map"}, "block": {"store", "text", "none"}, "book": {"store", "none"}, "box": {"store", "none"},
    "disc": {"store", "none"}, "globe": {"none"}, "model": {"store", "obj"}, "terrain": {"terrain"}, "text": {"text"},
    "pole": {"none"}, "table": {"none"}, "plinth": {"none"}, "frame": {"none"}, "wall": {"none"}, "candle": {"none"},
}
VERBS = {   # verb -> parameters it accepts (all optional unless listed in REQUIRED)
    "appear": {"how", "dur"}, "vanish": {"how", "dur"}, "drop": {"from_h", "dur"}, "rise": {"h", "dur"},
    "slide": {"to", "dur"}, "turn": {"deg", "axis", "dur"}, "flip": {"axis", "dur"}, "open": {"deg", "dur"},
    "close": {"dur"}, "unfold": {"dur"}, "fold": {"dur"}, "wave": {"wind", "dur"}, "split": {"into", "gap", "dur"},
    "assemble": {"into", "gap", "dur"}, "burn": {"from", "dur"}, "dissolve": {"dur"}, "stamp": {"with", "dur"}, "glow": {"color", "dur"},
    "light": {"how", "dur"}, "write": {"text", "dur"}, "route": {"path", "color", "dur"}, "label": {"text", "dur"},
    "scatter": {"dur"}, "stack": {"on", "dur"},
}
REQUIRED = {"split": {"into"}, "write": {"text"}, "route": {"path"}, "label": {"text"}, "stamp": {"with"}, "stack": {"on"}}
ONLY = {"open": {"book", "box"}, "close": {"book", "box"}, "unfold": {"cloth", "sheet", "print"}, "fold": {"cloth", "sheet", "print"},
        "wave": {"cloth"}, "split": {"tile", "sheet", "print"}, "assemble": {"tile", "sheet", "print"},
        "write": {"sheet", "print", "block", "book", "box"}, "route": {"tile", "terrain", "globe"}}
OUTDOOR_MOODS = {"dawn", "noon", "dusk", "overcast", "night"}
COLORS = {"warm", "gold", "red", "blue", "white"}
MOVES = {"wide": set(), "close": set(), "top": set(), "low": set(), "push": {"dur"}, "pull": {"dur"},
         "orbit": {"deg", "dur"}, "crane": {"h", "dur"}, "dolly": {"side", "dur"}, "track": {"dur"}, "tilt": {"deg", "dur"},
         "fly": {"path", "dur"}, "rack": {"from", "dur"}, "hold": {"dur"}}
PLACES = {"desk", "museum", "floor", "wall", "terrain", "sea", "sky", "void"}
MOODS = {"studio", "museum", "lamp", "dawn", "noon", "dusk", "night", "candle", "overcast"}
WEATHER = {"clear", "haze", "rain", "snow"}
MATERIALS = {"paper", "parchment", "cloth", "silk", "wood", "walnut", "oak", "stone", "marble", "slate", "sand", "bronze",
             "brass", "gold", "silver", "iron", "glass", "velvet", "leather", "wax", "plaster", "painted", "felt"}
RELATIONS = {"on", "in", "under", "left_of", "right_of", "behind", "in_front_of", "beside", "around", "above", "against"}
SCENE_KEYS = {"idea", "seconds", "output", "place", "light", "cast", "beats", "camera", "note"}
CAST_KEYS = {"is", "from", "material", "size", "where", "what", "note", "region", "at"}


def lonlat(v): return isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v) and -540 <= v[0] <= 540 and -90 <= v[1] <= 90


def path_ok(p): return isinstance(p, list) and len(p) >= 2 and all(lonlat(x) for x in p)


def region_ok(r, max_deg=60.0):
    return (isinstance(r, list) and len(r) == 4 and all(isinstance(x, (int, float)) for x in r) and r[0] < r[2] and r[1] < r[3]
            and -90 <= r[1] and r[3] <= 90 and 0.05 <= r[2] - r[0] <= max_deg and 0.05 <= r[3] - r[1] <= max_deg)


def check(order):
    errs = []
    E = errs.append
    p = os.path.join(order, "scenes.json")
    if not os.path.exists(p): return [f"{p} is missing"], {}
    try: D = json.load(open(p, encoding="utf-8"))
    except Exception as e: return [f"scenes.json is not valid JSON: {e}"], {}
    store = {}
    sp = os.path.join(order, "store.json")
    if os.path.exists(sp): store = json.load(open(sp, encoding="utf-8")).get("items", {})
    S = D.get("scenes") or {}
    if not S: E("scenes.json: no scenes")
    for sid, sc in S.items():
        w = f"scene {sid}"
        if not re.fullmatch(r"[a-z0-9_]+", sid): E(f"{w}: id uses lower-case letters, digits and _ only")
        for k in sc:
            if k not in SCENE_KEYS: E(f'{w}: unknown key "{k}" (allowed: {", ".join(sorted(SCENE_KEYS))})')
        idea = sc.get("idea", "")
        if len(idea.split()) < 6: E(f'{w}: "idea" must say in one sentence what the viewer sees and why (6+ words)')
        T = sc.get("seconds")
        if not isinstance(T, (int, float)) or not 2 <= T <= 40: E(f'{w}: "seconds" must be 2 to 40')
        T = T if isinstance(T, (int, float)) else 0
        if sc.get("output", "film") not in ("film", "over_map"): E(f'{w}: "output" is "film" or "over_map"')
        pl = sc.get("place") or {}
        if pl.get("kind") not in PLACES: E(f'{w}: place.kind must be one of {", ".join(sorted(PLACES))}')
        if pl.get("surface") and pl["surface"] not in MATERIALS: E(f'{w}: place.surface "{pl["surface"]}" is not a known material')
        if pl.get("kind") in ("terrain", "sea"):
            if not region_ok(pl.get("region")):
                E(f"{w}: place.region must be [lon0, lat0, lon1, lat1] for {pl.get('kind')} (0.05 to 60 degrees each way)")
        lt = sc.get("light") or {}
        if lt.get("mood") not in MOODS: E(f'{w}: light.mood must be one of {", ".join(sorted(MOODS))}')
        wx = lt.get("weather", "clear")
        if wx not in WEATHER: E(f'{w}: light.weather must be one of {", ".join(sorted(WEATHER))}')
        if wx in ("rain", "snow") and lt.get("mood") in ("noon", "dawn", "dusk", "studio"):
            E(f"{w}: {wx} needs an overcast or night sky, not {lt.get('mood')} sun")
        if wx in ("rain", "snow") and pl.get("kind") not in ("terrain", "sea", "sky", "floor"):
            E(f"{w}: {wx} falls outdoors (place terrain, sea, sky or floor), not on a {pl.get('kind')}")
        if pl.get("kind") in ("terrain", "sea", "sky") and lt.get("mood") not in OUTDOOR_MOODS:
            E(f"{w}: an outdoor place has an outdoor light ({', '.join(sorted(OUTDOOR_MOODS))}), not {lt.get('mood')}")
        if sc.get("output") == "over_map" and pl.get("kind") not in ("void",):
            E(f'{w}: a shot laid over the map has place.kind "void" (nothing behind the cast)')
        cast = sc.get("cast") or {}
        if not cast and pl.get("kind") not in ("terrain", "sea"): E(f"{w}: no cast")
        for n, c in cast.items():
            cw = f"{w} cast {n}"
            for k in c:
                if k not in CAST_KEYS: E(f'{cw}: unknown key "{k}"')
            nn = c.get("is")
            if nn not in NOUNS: E(f'{cw}: "is" must be one of {", ".join(sorted(NOUNS))} (a missing tool is added on request)'); continue
            src = str(c.get("from", "none")); kind = src.split(":", 1)[0]
            if kind not in NOUNS[nn]: E(f'{cw}: a {nn} is made from {" | ".join(sorted(NOUNS[nn]))}, not "{src}"')
            if kind == "store" and src.split(":", 1)[1] not in store: E(f'{cw}: "{src}" is not in the order store (store.json)')
            if kind == "map" and not re.fullmatch(r"map:[A-Za-z0-9_:-]+(\+[A-Za-z0-9_:-]+)*", src):
                E(f'{cw}: "{src}" - map:<ISO3 | shape:<id> | rr:<name> | brk:<name>>, several joined with +')
            if kind == "obj" and not re.fullmatch(r"obj:[a-z][a-z0-9_]{1,30}", src): E(f'{cw}: "{src}" - obj:<name of a model in objects.json>')
            if kind == "store" and nn == "model" and src.split(":", 1)[1] in store and \
                    not str(store[src.split(":", 1)[1]].get("file", "")).lower().endswith(".glb"):
                E(f'{cw}: a model from the store is a GLB file')
            if nn == "terrain" and not region_ok(c.get("region"), 20.0): E(f'{cw}: a terrain needs "region": [lon0, lat0, lon1, lat1] (0.05 to 20 degrees)')
            if c.get("region") is not None and nn != "terrain": E(f'{cw}: "region" belongs to a terrain')
            if c.get("at") is not None:
                if not lonlat(c["at"]): E(f'{cw}: "at" is [lon, lat]')
                elif nn != "globe" and pl.get("kind") not in ("terrain", "sea"): E(f'{cw}: "at" places a member on a terrain or sea place (or turns a globe)')
                elif nn != "globe" and c.get("where") and c["where"][1] != "place": E(f'{cw}: a member placed "at" a lon/lat stands on the place')
            if pl.get("kind") in ("terrain", "sea") and nn in ("tile", "terrain", "table", "candle"):
                E(f"{cw}: a {nn} does not belong on an outdoor region")
            if c.get("material") and c["material"] not in MATERIALS: E(f'{cw}: material "{c["material"]}" is not known')
            sz = c.get("size")
            if sz is not None and not (sz in ("S", "M", "L") or (isinstance(sz, (int, float)) and 0.01 <= sz <= 50)): E(f'{cw}: size is metres (0.01-50) or S/M/L')
            wh = c.get("where")
            if nn == "cloth" and kind != "store" and isinstance(wh, list) and len(wh) == 2 and wh[0] == "on" and \
                    isinstance(cast.get(wh[1]), dict) and cast[wh[1]].get("is") == "pole":
                E(f'{cw}: a cloth on a pole is a flag - "from": "store:<key>", the picture of that flag in the order store')
            if wh is not None:
                if not (isinstance(wh, list) and len(wh) == 2 and wh[0] in RELATIONS and (wh[1] in cast or wh[1] == "place") and wh[1] != n):
                    E(f'{cw}: "where" is [relation, other cast name or "place"], relations: {", ".join(sorted(RELATIONS))}')
        last = -1
        for i, b in enumerate(sc.get("beats") or []):
            bw = f"{w} beat {i + 1}"
            v = b.get("do")
            if v not in VERBS: E(f'{bw}: "do" must be one of {", ".join(sorted(VERBS))} (a missing tool is added on request)'); continue
            if b.get("who") not in cast and not (v == "route" and b.get("who") == "place" and pl.get("kind") in ("terrain", "sea")):
                E(f'{bw}: "who" must be a cast name ("place" only for a route on a terrain or sea place)')
            elif v in ONLY and b.get("who") in cast and cast[b["who"]].get("is") not in ONLY[v]:
                E(f'{bw}: "{v}" works on {", ".join(sorted(ONLY[v]))}, not on a {cast[b["who"]].get("is")}')
            if v == "route":
                if not path_ok(b.get("path")): E(f'{bw}: route "path" is a list of 2+ [lon, lat] points')
                if b.get("color", "red") not in COLORS: E(f'{bw}: route "color" is one of {", ".join(sorted(COLORS))}')
            if v == "stack" and (b.get("on") not in cast or b.get("on") == b.get("who")): E(f'{bw}: stack "on" names another cast member')
            if v == "wave" and not (isinstance(b.get("wind", 0.7), (int, float)) and 0.1 <= b.get("wind", 0.7) <= 1): E(f'{bw}: wave "wind" is 0.1 to 1')
            if v in ("split", "assemble") and b.get("who") in cast and cast[b["who"]].get("is") in ("sheet", "print") and \
                    b.get("into") is not None and not (isinstance(b["into"], int) or (isinstance(b["into"], list) and len(b["into"]) == 1 and str(b["into"][0]).isdigit())):
                E(f'{bw}: a sheet or print splits "into" a number of pieces (2 to 8)')
            t = b.get("t")
            if not isinstance(t, (int, float)) or not 0 <= t < T: E(f"{bw}: t must be inside the shot (0-{T})")
            elif t < last: E(f"{bw}: beats in time order")
            else: last = t
            for k in b:
                if k not in VERBS[v] | {"t", "do", "who", "note"}: E(f'{bw}: "{v}" has no parameter "{k}" (it has: {", ".join(sorted(VERBS[v])) or "none"})')
            for k in REQUIRED.get(v, ()):
                if k not in b: E(f'{bw}: "{v}" needs "{k}"')
            if v == "split" and isinstance(b.get("into"), list):
                for x in b["into"]:
                    if not re.fullmatch(r"map:[A-Za-z0-9_:-]+|\d+", str(x)): E(f'{bw}: split "into" lists map:<ISO3> pieces or a number of pieces')
        cams = sc.get("camera") or []
        if not cams: E(f"{w}: no camera (the first entry sets the opening framing)")
        lastc = -1
        for i, c in enumerate(cams):
            cw = f"{w} camera {i + 1}"
            mv = c.get("move")
            if mv not in MOVES: E(f'{cw}: "move" must be one of {", ".join(sorted(MOVES))}'); continue
            t = c.get("t")
            if not isinstance(t, (int, float)) or not 0 <= t < T: E(f"{cw}: t must be inside the shot")
            elif t < lastc: E(f"{cw}: camera entries in time order")
            else: lastc = t
            if c.get("to") is not None and c["to"] not in cast: E(f'{cw}: "to" must be a cast name')
            for k in c:
                if k not in MOVES[mv] | {"t", "move", "to", "note"}: E(f'{cw}: "{mv}" has no parameter "{k}"')
            if mv == "fly" and pl.get("kind") not in ("terrain", "sea"): E(f"{cw}: fly is over a terrain or sea place")
            if mv == "fly" and not path_ok(c.get("path")): E(f'{cw}: fly needs "path": 2+ [lon, lat] points')
        # tools of the vocabulary that the kit has not built yet: refused now, before anything runs
        nb = lambda what, x: E(f'{w}: {what} "{x}" - this tool is not built yet in the workshop (added on request)')
        if pl.get("kind") in PLACES and pl["kind"] not in BUILT["places"]: nb("place", pl["kind"])
        if wx in WEATHER and wx not in BUILT["weather"]: nb("weather", wx)
        if sc.get("output", "film") not in BUILT["output"]: nb("output", sc.get("output"))
        for n, c in cast.items():
            if c.get("is") in NOUNS and c["is"] not in BUILT["nouns"]: nb(f"cast {n}: noun", c["is"])
        for b in sc.get("beats") or []:
            if b.get("do") in VERBS and b["do"] not in BUILT["verbs"]: nb("verb", b["do"])
            if b.get("do") == "stamp" and not str(b.get("with", "")).startswith("text:"): nb("stamp with", b.get("with"))
        for c in cams:
            if c.get("move") in MOVES and c["move"] not in BUILT["moves"]: nb("camera move", c["move"])
    return errs, S


if __name__ == "__main__":
    errs, S = check(sys.argv[1])
    for e in errs: print("SCENE ERROR:", e)
    print(f"{len(S)} scenes, {len(errs)} errors")
    sys.exit(2 if errs else 0)
