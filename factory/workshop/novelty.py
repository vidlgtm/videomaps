#!/usr/bin/env python3
"""NO REPEATED SCENES - every 3D scene of an order is compared with every scene ever made (factory/rules/ideas_used.json)
and with the other scenes of the same order. Refused (exit 2) when:
  - the same hero (what it is + what it does + where) with a similar make-up (>= 0.4) or idea (>= 0.3),
  - the same make-up: similarity >= 0.6 over place, light, cast, verbs (verb > noun) and camera moves (Jaccard),
  - the same idea in other words: >= 0.5 of the meaningful words of the idea sentence in common.
usage: python novelty.py <orderDir>            check
       python novelty.py <orderDir> --record   add the order's scenes to the log (when its film is published)"""
import json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(os.path.dirname(HERE), "rules", "ideas_used.json")
STOP = set("the a an of and or to in on at by for with from into over under its it is are was were be this that these "
           "those as than then while when where which who whom whose what how why their there here they them his her "
           "one two three each every all both shot scene camera viewer sees see slowly".split())
J_MAX, IDEA_MAX, HERO_J, HERO_IDEA = 0.6, 0.5, 0.4, 0.3


def hero(sc):
    cast, beats = sc.get("cast") or {}, sc.get("beats") or []
    count = {}
    for b in beats: count[b.get("who")] = count.get(b.get("who"), 0) + 1
    name = max(cast, key=lambda n: (count.get(n, 0), -list(cast).index(n))) if cast else None
    verbs = [b.get("do") for b in beats if b.get("who") == name]
    main = max(set(verbs), key=verbs.count) if verbs else "hold"
    return [cast.get(name, {}).get("is"), main, (sc.get("place") or {}).get("kind")]


def features(sc):
    f = set()
    pl, lt = sc.get("place") or {}, sc.get("light") or {}
    f |= {f"place:{pl.get('kind')}", f"surface:{pl.get('surface')}", f"mood:{lt.get('mood')}", f"weather:{lt.get('weather', 'clear')}",
          f"output:{sc.get('output', 'film')}"}
    cast = sc.get("cast") or {}
    f |= {f"noun:{c.get('is')}" for c in cast.values()} | {f"material:{c.get('material')}" for c in cast.values() if c.get("material")}
    for b in sc.get("beats") or []:
        f |= {f"verb:{b.get('do')}", f"vn:{b.get('do')}>{cast.get(b.get('who'), {}).get('is')}"}
    moves = [c.get("move") for c in sc.get("camera") or []]
    f |= {f"move:{m}" for m in moves} | {f"moves:{a}>{b}" for a, b in zip(moves, moves[1:])}
    return f


def words(s):
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) >= 4 and w not in STOP}


def jac(a, b): return len(a & b) / max(1, len(a | b))


def entry(film, sid, sc):
    return {"film": film, "scene": sid, "idea": sc.get("idea", ""), "hero": hero(sc), "features": sorted(features(sc))}


def compare(a, b):
    """reasons why scene a repeats b (empty = new)"""
    why = []
    j = jac(set(a["features"]), set(b["features"]))
    k = jac(words(a["idea"]), words(b["idea"]))
    if j >= J_MAX: why.append(f"same make-up ({j:.2f})")
    if k >= IDEA_MAX: why.append(f"same idea in other words ({k:.2f})")
    if a["hero"] == b["hero"] and not why and (j >= HERO_J or k >= HERO_IDEA):
        why.append(f"same hero ({' / '.join(map(str, a['hero']))}) with a similar make-up ({j:.2f}) or idea ({k:.2f})")
    return why


def main(order, record=False):
    S = json.load(open(os.path.join(order, "scenes.json"), encoding="utf-8")).get("scenes", {})
    film = os.path.basename(os.path.normpath(order))
    L = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else {"scenes": []}
    mine = [entry(film, sid, sc) for sid, sc in S.items()]
    bad = 0
    for i, a in enumerate(mine):
        for b in [x for x in L["scenes"] if x["film"] != film] + mine[:i]:
            why = compare(a, b)
            if why:
                bad += 1
                print(f'REPEATED: scene {a["scene"]} repeats {b["film"]}/{b["scene"]} ("{b["idea"][:70]}"): {"; ".join(why)}')
    print(f"{len(mine)} scenes checked against {len(L['scenes'])} past scenes: {bad} repeats")
    if record and not bad:
        L["scenes"] = [x for x in L["scenes"] if x["film"] != film] + [{**m, "recorded": time.strftime("%Y-%m-%d")} for m in mine]
        json.dump(L, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1); open(LOG, "a").write("\n")
        print("recorded in", os.path.relpath(LOG))
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], "--record" in sys.argv))
