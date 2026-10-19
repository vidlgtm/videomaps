"""Probe GPU-only models through their public Hugging Face Spaces (gradio_client):
Tencent Hunyuan3D-2 (image->3D), TripoSR (image->3D), ACE-Step (music generation)."""
import json, os, shutil, traceback
from gradio_client import Client, handle_file

OUT = "out/spaces"
os.makedirs(OUT, exist_ok=True)
TOKEN = os.environ.get("HF_TOKEN") or None
IMG = "https://raw.githubusercontent.com/VAST-AI-Research/TripoSR/main/examples/chair.png"
report = {}


def save(res, tag):
    paths = []
    def walk(x):
        if isinstance(x, str) and os.path.exists(x):
            paths.append(x)
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x: walk(v)
    walk(res)
    kept = []
    for p in paths:
        dst = f"{OUT}/{tag}_{os.path.basename(p)}"
        shutil.copy(p, dst); kept.append(dst)
    return kept


def endpoints(client, space):
    api = client.view_api(print_info=False, return_format="dict")
    json.dump(api, open(f"{OUT}/{space.replace('/', '__')}_api.json", "w"), indent=1, default=str)
    eps = api.get("named_endpoints", {})
    for name, ep in eps.items():
        params = [f"{p.get('parameter_name')}:{p.get('component')}" for p in ep.get("parameters", [])]
        print(f"  {space} {name} -> {params}")
    return eps


def call(client, eps, name, overrides):
    kwargs = {}
    for p in eps[name].get("parameters", []):
        pn = p.get("parameter_name")
        if pn in overrides:
            kwargs[pn] = overrides[pn]
        elif p.get("component") == "Image" and "image" in pn.lower() and not kwargs.get(pn):
            kwargs[pn] = handle_file(IMG) if pn == "image" else None
    return client.predict(api_name=name, **kwargs)


for space in ["ACE-Step/ACE-Step", "tencent/Hunyuan3D-2"]:
    tag = space.split("/")[1]
    try:
        try:
            c = Client(space, token=TOKEN, verbose=False) if TOKEN else Client(space, verbose=False)
        except TypeError:
            c = Client(space)
        eps = endpoints(c, space)
        report[space] = {"reachable": True, "endpoints": list(eps.keys())}
        if space == "tencent/Hunyuan3D-2":
            name = "/generation_all" if "/generation_all" in eps else next((n for n in eps if "shape" in n), None)
            res = call(c, eps, name, {"image": handle_file(IMG)})
            report[space]["result"] = save(res, tag)
        elif space == "ACE-Step/ACE-Step":
            name = "/__call__" if "/__call__" in eps else None
            if name:
                res = call(c, eps, name, {"prompt": "cinematic orchestral documentary underscore, soft strings, warm piano, low drones, 80 bpm, instrumental",
                                          "lyrics": "[instrumental]", "audio_duration": 30})
                report[space]["result"] = save(res, tag)
    except Exception as e:
        report.setdefault(space, {})["error"] = repr(e)[:600]
        traceback.print_exc(limit=1)
    print("RESULT", space, json.dumps(report.get(space, {}))[:700])

json.dump(report, open(f"{OUT}/report.json", "w"), indent=1)
