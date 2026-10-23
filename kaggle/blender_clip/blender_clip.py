# Kaggle GPU kernel (2x T4, Cycles OptiX): render one Blender clip of the project -> /kaggle/working/<NAME>.mp4 + a
# contact sheet. Contract of the Blender script (see production/blender/caucasus3.py, the reference):
#   blender -b -P production/blender/<SCRIPT> -- <ARGS> --out <dir> --start 1 --end <FRAMES> --gpu OPTIX
#   writes <dir>/f_0001.jpg ... (or .png; numbering may start later, e.g. flag_open.py at 61); optional PREP = a python
#   command run first (data preparation). NAME=<name>.webm keeps the alpha (RGBA PNG frames -> VP9 yuva420p), otherwise
#   <NAME>.mp4. A script that supports --labels-only (caucasus3.py) also gets a labels pass; *.json in <dir> are kept.
# Placeholders filled by scripts/kaggle_push.sh: __REPO_URL__ __SHA__ __SCRIPT__ __ARGS__ __FRAMES__ __NAME__ __PREP__
import subprocess, os, time, glob
REPO, SHA = "__REPO_URL__", "__SHA__"
SCRIPT, ARGS, FRAMES, NAME, PREP = "__SCRIPT__", "__ARGS__", int("__FRAMES__"), "__NAME__", "__PREP__"
W = "/kaggle/working"; T0 = time.time()
def log(*a): print(f"[{time.strftime('%H:%M:%S')} UTC +{time.time() - T0:6.0f}s]", *a, flush=True)
def sh(c, check=True):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    if check and r.returncode:
        log("FAILED:", c[:200]); log(r.stdout[-2500:]); log(r.stderr[-2500:]); raise SystemExit(1)
    return r
log("blender_clip:", NAME, SCRIPT, FRAMES, "frames")
sh(f"git clone -q {REPO} /tmp/vm && cd /tmp/vm && git checkout -q {SHA}")
os.chdir("/tmp/vm")
if PREP.strip(): log("prep:", sh(PREP).stdout[-600:])
sh("apt-get -qq install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libxkbcommon0 libsm6 libice6 > /dev/null 2>&1 || true", check=False)
sh("F=$(curl -s https://download.blender.org/release/Blender4.5/ | grep -oE 'blender-4\\.5\\.[0-9]+-linux-x64\\.tar\\.xz' | sort -V | uniq | tail -1); "
   "curl -sfL --retry 3 -o /tmp/b.tar.xz https://download.blender.org/release/Blender4.5/$F && mkdir -p /tmp/blender && "
   "tar -xf /tmp/b.tar.xz -C /tmp/blender --strip-components=1 && rm /tmp/b.tar.xz")
cmd = f"/tmp/blender/blender -b --python-exit-code 1 -P production/blender/{SCRIPT} -- {ARGS} --out /tmp/frames --start 1 --end {FRAMES} --gpu OPTIX"
if "--labels-only" in open(f"production/blender/{SCRIPT}").read():   # e.g. caucasus3.py: per-frame label tracks (json)
    sh(cmd + " --labels-only > /tmp/labels.log 2>&1"); log("labels pass done")
p = subprocess.Popen(cmd + " > /tmp/render.log 2>&1", shell=True)
count = lambda: len(glob.glob("/tmp/frames/f_*.jpg")) + len(glob.glob("/tmp/frames/f_*.png"))
while p.poll() is None:
    time.sleep(90); log(f"rendered {count()}/{FRAMES}")
for l in open("/tmp/render.log"):
    if "GPU devices" in l or "Error" in l or "Traceback" in l: log(l.strip()[:300])
n = count(); log("render rc", p.returncode, "frames", n)
if n != FRAMES:
    log(open("/tmp/render.log").read()[-3000:]); raise SystemExit(1)
for j in glob.glob("/tmp/frames/*.json"): sh(f"cp {j} {W}/")      # label tracks / timing files travel with the clip
frames = sorted(glob.glob("/tmp/frames/f_*.jpg") + glob.glob("/tmp/frames/f_*.png"))
ext = frames[0].rsplit(".", 1)[1]; first = int(os.path.basename(frames[0])[2:6])   # e.g. flag_open.py starts at 61
if NAME.endswith(".webm"):        # keep the alpha channel: transparent clip in Remotion (e.g. the matryoshka)
    if ext != "png": log("a .webm clip needs RGBA PNG frames"); raise SystemExit(1)
    OUTF = f"{W}/{NAME}"
    enc = f"-framerate 30 -start_number {first} -i /tmp/frames/f_%04d.png -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 18 -row-mt 1 {OUTF}"
    if sh(f"ffmpeg -v error -y {enc}", check=False).returncode:          # system ffmpeg without libvpx -> static build
        sh("pip install -q imageio-ffmpeg")
        ff = sh("python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'").stdout.strip()
        sh(f"{ff} -v error -y {enc}")
else:
    OUTF = f"{W}/{NAME}.mp4"
    sh(f"ffmpeg -v error -y -framerate 30 -start_number {first} -i /tmp/frames/f_%04d.{ext} -c:v libx264 -crf 12 -preset slow -pix_fmt yuv420p {OUTF}")
SHEET = OUTF.rsplit(".", 1)[0] + "_sheet.jpg"
sh(f"ffmpeg -v error -y -i {OUTF} -vf \"select='not(mod(n\\,60))',scale=640:-1,tile=3x2\" -frames:v 1 {SHEET}", check=False)
log("done", OUTF, os.path.getsize(OUTF))
