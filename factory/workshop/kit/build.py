"""Workshop entry (Blender 4.5): builds one described scene and renders it, or writes its preview.
blender -b -P build.py -- --params scene.json --data DIR --out DIR --preview
blender -b -P build.py -- --params scene.json --data DIR --out DIR --start A --end B --ev X --gpu OPTIX --budget-min M
scene.json = one scene of <order>/scenes.json; DIR/meta.json lists the store pictures copied into DIR (file, aspect, credit)."""
import bpy, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import mats as M
import plan as P
import stage as ST

scene, O = C.args()
mp = os.path.join(O.data or "", "meta.json")
meta = json.load(open(mp)) if O.data and os.path.exists(mp) else {"items": {}}
st = ST.Stage(scene, O.data, meta, O)
sc = st.sc
C.setup_cycles(sc, O, samples=int(scene.get("samples", 160)), motion_blur=True)
sc.view_settings.view_transform = "Standard"
try: sc.view_settings.look = "None"
except Exception: pass


def exact(s, *a):
    """pictures keep their file colours at any exposure: camera rays see their emission at 2^-exposure"""
    v = 2.0 ** -s.view_settings.exposure
    for nd in M.EXACT: nd.outputs[0].default_value = v


bpy.app.handlers.frame_change_pre.append(exact)
exact(sc)

if st.errors and any("not built yet" in e or "never placed" in e for e in st.errors):
    for e in st.errors: print("SCENE ERROR:", e, flush=True)
    if O.preview:
        json.dump({"frames": st.n, "key_frames": [], "errors": st.errors, "warnings": st.warnings, "fatal": True},
                  open(os.path.join(O.out, "check.json"), "w"))
    sys.exit(2)

if O.preview:
    st.bvh()
    found = st.checks()
    json.dump(st.label_json, open(os.path.join(O.out, "labels.json"), "w"))
    key = P.key_frames(st.beats, st.cams, st.T)
    rnd = lambda v: [round(float(x), 3) for x in v]
    stats = {"credits": meta.get("credits", []), "layout": {k: {q: (round(v, 3) if isinstance(v, float) else v) for q, v in m.items()}
             for k, m in st.L.items()}, "camera": [{"t": round(s0, 2), "dur": round(d, 2), "target": rnd(b["T"]), "dist": round(b["D"], 3),
             "az": round(b["A"], 1), "el": round(b["E"], 1)} for s0, d, a, b in st.plan["states"]], "found": found,
             "lights": [ob.name for ob in sc.objects if ob.type == "LIGHT"], "L0": round(st.L0, 3), "mood": st.mood, "place": st.place}
    void = st.place == "void"
    EV_RANGE = (-3.0, 3.0)
    C.preview_run(sc, O, st.n, st.classify, subject=("o",) if void else ("r",), target=st.target, tol=round(0.25 * st.target, 3),
                  ev_range=EV_RANGE, stats=stats, errors=st.errors, warnings=st.warnings, dark_max=st.dark_max,
                  fallback_subject=None if void else ("o",), key=key)
    cp = os.path.join(O.out, "check.json"); ck = json.load(open(cp))
    res = st.fidelity(O.out, ck["key_frames"], ck.get("ext", ".jpg"))
    if ck.get("calibration") and min(abs(ck["ev"] - EV_RANGE[0]), abs(ck["ev"] - EV_RANGE[1])) < 0.02:
        st.errors.append(f"the exposure stopped at its limit ({ck['ev']:+.2f} EV): the light levels are off for this scene")
    ck["errors"] = list(dict.fromkeys(st.errors)); ck["warnings"] = list(dict.fromkeys(st.warnings))
    ck.setdefault("stats", {})["picture_fidelity"] = res
    json.dump(ck, open(cp, "w"))
    print(f"picture colours: {res}", flush=True)
    print(f"preview: {len(ck['errors'])} errors, {len(ck['warnings'])} warnings", flush=True)
    sys.exit(0)

C.render_frames(sc, O.out, list(range(O.start, (O.end or st.n) + 1)), O.budget)
