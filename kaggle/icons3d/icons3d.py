# Kaggle GPU kernel (2x T4): TripoSR image-to-3D for the project's icon references + Blender Cycles OptiX renders
# at 4 azimuths -> /kaggle/working/icons.zip (<name>_a0/_a90/_a180/_a270.png). Same output as the "icons" job of
# film.yml, ~10x faster. Placeholders are filled by scripts/kaggle_push.sh: __REPO_URL__ __SHA__ __PROJECT__
import subprocess, os, time, glob, json
REPO, SHA, PROJECT = "__REPO_URL__", "__SHA__", "__PROJECT__"
W = "/kaggle/working"; T0 = time.time()
def log(*a): print(f"[{time.strftime('%H:%M:%S')} UTC +{time.time() - T0:6.0f}s]", *a, flush=True)
def sh(c, check=True):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    if check and r.returncode:
        log("FAILED:", c[:200]); log(r.stdout[-2500:]); log(r.stderr[-2500:]); raise SystemExit(1)
    return r
log("icons3d: start", PROJECT, SHA[:7])
sh(f"git clone -q {REPO} /tmp/vm && cd /tmp/vm && git checkout -q {SHA}")
os.chdir("/tmp/vm")
pj = json.load(open(f"projects/{PROJECT}/project.json"))
icons = pj.get("icons", [])
if not icons: log("project has no icons"); raise SystemExit(0)
names = ",".join(i["name"] for i in icons)
refs = " ".join(f"/tmp/vm/projects/{PROJECT}/{i['ref']}" for i in icons)
sh("git clone -q --depth 1 https://github.com/VAST-AI-Research/TripoSR /tmp/TripoSR")
sh("pip install -q onnxruntime rembg omegaconf einops transformers trimesh huggingface-hub imageio[ffmpeg] xatlas moderngl")
r = sh("pip install -q git+https://github.com/tatsy/torchmcubes.git", check=False)
if r.returncode: log("torchmcubes build failed, retry without isolation"); sh("pip install -q --no-build-isolation git+https://github.com/tatsy/torchmcubes.git")
sh(f"cd /tmp/TripoSR && python run.py {refs} --device cuda:0 --mc-resolution 320 --output-dir /tmp/icons3d --model-save-format obj")
log("meshes:", sorted(glob.glob("/tmp/icons3d/*/mesh.obj")))
sh("apt-get -qq install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libxkbcommon0 libsm6 libice6 zip > /dev/null 2>&1 || true", check=False)
sh("F=$(curl -s https://download.blender.org/release/Blender4.5/ | grep -oE 'blender-4\\.5\\.[0-9]+-linux-x64\\.tar\\.xz' | sort -V | uniq | tail -1); "
   "curl -sfL --retry 3 -o /tmp/b.tar.xz https://download.blender.org/release/Blender4.5/$F && mkdir -p /tmp/blender && "
   "tar -xf /tmp/b.tar.xz -C /tmp/blender --strip-components=1 && rm /tmp/b.tar.xz")
r = sh(f"CYCLES_GPU=OPTIX /tmp/blender/blender -b --python-exit-code 1 -P production/blender/icons.py -- /tmp/icons3d {names} /tmp/icons")
for l in r.stdout.splitlines():
    if "GPU devices" in l or "rendered" in l: log(l[:200])
pngs = sorted(glob.glob("/tmp/icons/*.png")); log("renders:", len(pngs))
if len(pngs) != 4 * len(icons): raise SystemExit(f"expected {4 * len(icons)} renders")
import zipfile
with zipfile.ZipFile(f"{W}/icons.zip", "w") as z:
    for p in pngs: z.write(p, os.path.basename(p))
log("done", os.path.getsize(f"{W}/icons.zip"))
