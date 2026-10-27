#!/usr/bin/env python3
"""Kaggle GPU job runner shared by the factory's GPU steps (music, 3D models): push one private script kernel
(2x T4, internet on), wait for it within a time limit, download its outputs. The account comes from the environment
(KAGGLE_API_TOKEN + KAGGLE_USERNAME); the account name never appears in a log.
usage as a module:
    import kaggle_job
    od, status = kaggle_job.run(code, slug, limit_min, out_dir)     # od = folder with the kernel's /kaggle/working files
"""
import json, os, re, subprocess, sys, time
from pathlib import Path


class KaggleError(Exception):
    pass


def creds():
    tok, user = os.environ.get("KAGGLE_API_TOKEN", ""), os.environ.get("KAGGLE_USERNAME", "")
    if not tok or not user:
        raise KaggleError("this step needs the Kaggle account for this run (KAGGLE_API_TOKEN + KAGGLE_USERNAME secrets)")
    return tok, user


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def mask(s, user):
    return s.replace(user, "***") if user else s


def slug_ok(slug):
    s = re.sub(r"[^a-z0-9-]", "-", slug.lower()).strip("-")[:48]
    if len(s) < 5: raise KaggleError(f"kernel slug too short: {slug}")
    return s


def push(code, slug, gpu=True):
    _, user = creds()
    slug = slug_ok(slug)
    kd = Path("/tmp/kaggle_push") / slug
    kd.mkdir(parents=True, exist_ok=True)
    (kd / "kernel.py").write_text(code)
    meta = {"id": f"{user}/{slug}", "title": slug, "code_file": "kernel.py", "language": "python", "kernel_type": "script",
            "is_private": "true", "enable_gpu": "true" if gpu else "false", "enable_internet": "true",
            "dataset_sources": [], "competition_sources": [], "kernel_sources": [], "model_sources": []}
    if gpu: meta["machine_shape"] = "NvidiaTeslaT4"
    json.dump(meta, open(kd / "kernel-metadata.json", "w"))
    rc, out = _run(["kaggle", "kernels", "push", "-p", str(kd)])
    if rc or "error" in out.lower():
        raise KaggleError("Kaggle push failed: " + mask(out, user)[-800:])
    print(f"KAGGLE_PUSHED {slug}", flush=True)
    return slug


def wait(slug, limit_min, every_s=60):
    _, user = creds()
    t0, st = time.time(), "?"
    while time.time() - t0 < limit_min * 60:
        time.sleep(every_s)
        _, out = _run(["kaggle", "kernels", "status", f"{user}/{slug}"])
        m = re.search(r"(QUEUED|RUNNING|COMPLETE|ERROR|CANCEL\w*)", out.upper())
        st = m.group(1) if m else "?"
        print(f"  {int((time.time() - t0) / 60):3d} min  {st}", flush=True)
        if st in ("COMPLETE", "ERROR") or st.startswith("CANCEL"): break
    return st


def output(slug, out_dir):
    _, user = creds()
    od = Path(out_dir)
    od.mkdir(parents=True, exist_ok=True)
    rc, out = _run(["kaggle", "kernels", "output", f"{user}/{slug}", "-p", str(od), "-o"])
    if rc: print(mask(out, user)[-600:], flush=True)
    return od


def log_tail(od, n=3000):
    _, user = creds()
    logs = sorted(Path(od).glob("*.log"))
    return mask(logs[0].read_text(errors="replace")[-n:], user) if logs else "no log"


def run(code, slug, limit_min, out_dir, gpu=True):
    slug = push(code, slug, gpu)
    st = wait(slug, limit_min)
    return output(slug, out_dir), st


if __name__ == "__main__":
    print(__doc__); sys.exit(1)
