#!/usr/bin/env python3
"""Starts a factory workflow. With KAGGLE_API_TOKEN + KAGGLE_USERNAME in the environment, the key is lent to the run
as two temporary repository secrets and withdrawn as soon as the run's job has started (always, also on failure);
the script ends only when the secret list no longer holds them.
usage: GH_TOKEN=... [KAGGLE_API_TOKEN=... KAGGLE_USERNAME=...] python3 factory/tools/dispatch.py <workflow.yml> [--job name] key=value ...
(film.yml: --job defaults to "voice", the job with the score step)
needs: pip install pynacl"""
import base64, calendar, json, os, sys, time, urllib.request, urllib.error

REPO = os.environ.get("REPO", "vidlgtm/videomaps")
GH = os.environ["GH_TOKEN"]
a = sys.argv[1:]
WF = a[0]
JOB = a[a.index("--job") + 1] if "--job" in a else ("voice" if WF == "film.yml" else None)
inputs = dict(x.split("=", 1) for x in a[1:] if "=" in x)
NAMES = ("KAGGLE_API_TOKEN", "KAGGLE_USERNAME")


def api(path, method="GET", data=None):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}", method=method,
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Authorization": f"Bearer {GH}", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req) as r:
            b = r.read(); return r.status, (json.loads(b) if b else {})
    except urllib.error.HTTPError as e:
        return e.code, {}


def secret_names():
    s, d = api("actions/secrets?per_page=100")
    return [x["name"] for x in d.get("secrets", [])] if s == 200 else None


def withdraw():
    for n in NAMES: api(f"actions/secrets/{n}", "DELETE")
    for _ in range(10):
        names = secret_names()
        left = [n for n in (NAMES if names is None else names) if n in NAMES]
        if not left: print("key withdrawn: no Kaggle secret left in the repository", flush=True); return True
        for n in left: api(f"actions/secrets/{n}", "DELETE")
        time.sleep(3)
    print("WARNING: could not confirm the Kaggle secrets are gone - delete them by hand", flush=True); return False


lend = all(os.environ.get(n) for n in NAMES)
try:
    if lend:
        from nacl import encoding, public
        s, k = api("actions/secrets/public-key")
        if s != 200: sys.exit("cannot read the repository public key (token needs Secrets read/write)")
        box = public.SealedBox(public.PublicKey(k["key"].encode(), encoding.Base64Encoder()))
        for n in NAMES:
            enc = base64.b64encode(box.encrypt(os.environ[n].encode())).decode()
            s, _ = api(f"actions/secrets/{n}", "PUT", {"encrypted_value": enc, "key_id": k["key_id"]})
            if s not in (201, 204): sys.exit(f"could not lend the key (HTTP {s})")
        print("key lent to the run (2 temporary secrets)", flush=True)
    t0 = time.time()
    s, _ = api(f"actions/workflows/{WF}/dispatches", "POST", {"ref": "main", "inputs": inputs})
    if s != 204: sys.exit(f"dispatch failed (HTTP {s})")
    run = None
    for _ in range(60):
        time.sleep(4)
        s, d = api(f"actions/workflows/{WF}/runs?per_page=5&event=workflow_dispatch")
        for r in d.get("workflow_runs", []):
            if calendar.timegm(time.strptime(r["created_at"], "%Y-%m-%dT%H:%M:%SZ")) >= t0 - 10:
                run = r; break
        if run: break
    if not run: sys.exit("the run did not appear")
    print("run:", run["html_url"], flush=True)
    if lend:
        for _ in range(225):
            s, d = api(f"actions/runs/{run['id']}/jobs")
            js = [j for j in d.get("jobs", []) if JOB is None or JOB in j["name"]]
            started = [j for j in js if j["status"] == "completed" or (j.get("steps") and j["steps"][0]["status"] == "completed")]
            if js and len(started) == len(js): print("job started:", ", ".join(j["name"] for j in js), flush=True); break
            s, rr = api(f"actions/runs/{run['id']}")
            if rr.get("status") == "completed": break
            time.sleep(4)
finally:
    if lend: withdraw()
