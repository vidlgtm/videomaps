# Kaggle GPU kernel (2x T4, Cycles OptiX): renders a batch of workshop scenes whose CPU preview passed and was approved.
# Per scene: its data (prepared once, from the release) -> frames within the scene's time budget (a scene over budget
# stops after a few frames instead of using the GPU for hours) -> <hash>.mp4 (or .webm with alpha) + <hash>_sheet.jpg
# + <hash>.json in /kaggle/working.
# Placeholders filled by factory/workshop/run.py: __REPO_URL__ __SHA__ __BATCH__ __DATA_URL__
import subprocess, os, time, glob, json, base64, shutil
REPO, SHA, BATCH, DATA_URL = "__REPO_URL__", "__SHA__", "__BATCH__", "__DATA_URL__"
JOBS = json.loads(base64.b64decode(BATCH).decode())
W = "/kaggle/working"; T0 = time.time()
KIT = "factory/workshop/kit"


def log(*a): print(f"[{time.strftime('%H:%M:%S')} UTC +{time.time() - T0:6.0f}s]", *a, flush=True)


class Fail(Exception): pass


def sh(c, check=True):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    if check and r.returncode:
        raise Fail(f"FAILED: {c[:160]}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r


def tail(p, n=2500):
    try: return open(p, errors="replace").read()[-n:]
    except Exception: return ""


log("workshop batch:", [(j["id"], j["budget_min"]) for j in JOBS])
sh(f"git clone -q {REPO} /tmp/vm && cd /tmp/vm && git checkout -q {SHA}")
os.chdir("/tmp/vm")
sh("apt-get -qq install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libxkbcommon0 libsm6 libice6 > /dev/null 2>&1 || true", check=False)
sh("F=$(curl -s https://download.blender.org/release/Blender4.5/ | grep -oE 'blender-4\\.5\\.[0-9]+-linux-x64\\.tar\\.xz' | sort -V | uniq | tail -1); "
   "curl -sfL --retry 3 -o /tmp/b.tar.xz https://download.blender.org/release/Blender4.5/$F && mkdir -p /tmp/blender && "
   "tar -xf /tmp/b.tar.xz -C /tmp/blender --strip-components=1 && rm /tmp/b.tar.xz")
log("blender ready")
FF = "ffmpeg"
if sh("ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libvpx-vp9", check=False).returncode:
    sh("pip install -q imageio-ffmpeg")
    FF = sh("python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'").stdout.strip()

results = []
for j in JOBS:
    h, d = j["hash"], f"/tmp/ws/{j['hash']}"
    os.makedirs(d, exist_ok=True)
    frames = int(round(float(j["seconds"]) * 30))
    json.dump({**j["params"], "seconds": j["seconds"]}, open(f"{d}/params.json", "w"))
    t1 = time.time()
    try:
        sh(f"curl -sfL --retry 5 -o {d}/data.tar {DATA_URL}{j['dkey']}_data.tar && tar -xf {d}/data.tar -C {d} && rm {d}/data.tar")
        log(j["id"], "data ready")
        cmd = (f"/tmp/blender/blender -b --python-exit-code 1 -P {KIT}/{j['script']} -- --params {d}/params.json --data {d}/data "
               f"--out {d}/frames --start 1 --end {frames} --gpu OPTIX --ev {j['ev']} --budget-min {j['budget_min']}")
        p = subprocess.Popen(cmd + f" > {d}/render.log 2>&1", shell=True)
        count = lambda: len(glob.glob(f"{d}/frames/f_*.jpg")) + len(glob.glob(f"{d}/frames/f_*.png"))
        while p.poll() is None:
            time.sleep(60); log(j["id"], f"rendered {count()}/{frames}")
        for l in open(f"{d}/render.log", errors="replace"):
            if l.startswith(("GPU devices", "budget:", "BUDGET", "SCENE ERROR")): log(l.strip()[:300])
        if "BUDGET EXCEEDED" in tail(f"{d}/render.log", 4000):
            raise Fail(f"over budget, stopped after {count()} frames ({(time.time() - t1) / 60:.1f} min): "
                       + [l for l in tail(f"{d}/render.log", 4000).splitlines() if "BUDGET EXCEEDED" in l][-1])
        if p.returncode or count() != frames: raise Fail(f"render rc {p.returncode}, frames {count()}/{frames}\n" + tail(f"{d}/render.log"))
        pngs = sorted(glob.glob(f"{d}/frames/f_*.png"))
        if j.get("alpha"):
            if not pngs: raise Fail("a transparent piece needs RGBA PNG frames")
            out = f"{W}/{h}.webm"
            sh(f"{FF} -v error -y -framerate 30 -start_number 1 -i {d}/frames/f_%04d.png -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 18 -row-mt 1 {out}")
        else:
            ext = "png" if pngs else "jpg"
            out = f"{W}/{h}.mp4"
            sh(f"ffmpeg -v error -y -framerate 30 -start_number 1 -i {d}/frames/f_%04d.{ext} -c:v libx264 -crf 12 -preset slow -pix_fmt yuv420p {out}")
        k = max(1, frames // 6)
        sh(f"ffmpeg -v error -y -i {out} -vf \"select='not(mod(n\\,{k}))',scale=640:-1,tile=3x2\" -frames:v 1 {W}/{h}_sheet.jpg", check=False)
        dm = json.load(open(f"{d}/data/meta.json")) if os.path.exists(f"{d}/data/meta.json") else {}
        meta = {"hash": h, "id": j["id"], "seconds": j["seconds"], "frames": frames, "fps": 30,
                "file": os.path.basename(out), "lkey": j["lkey"], "ev": j["ev"], "budget_min": j["budget_min"],
                "minutes": round((time.time() - t1) / 60, 1), "credits": dm.get("credits", [])}
        json.dump(meta, open(f"{W}/{h}.json", "w")); results.append(meta)
        log(j["id"], "done", meta["file"], os.path.getsize(out), "bytes", meta["minutes"], "min")
    except Exception as e:
        results.append({"hash": h, "id": j["id"], "error": str(e)[-4000:]}); log(j["id"], "FAILED", str(e)[-1500:])
    shutil.rmtree(d, ignore_errors=True)
json.dump(results, open(f"{W}/batch.json", "w"), indent=1)
log("batch finished:", sum(1 for r in results if "error" not in r), "ok,", sum(1 for r in results if "error" in r), "failed")
