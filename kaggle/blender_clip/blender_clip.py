# Kaggle GPU kernel (2x T4, Cycles OptiX): render one Blender clip of the project -> /kaggle/working/<NAME>.mp4 + a
# contact sheet. Contract of the Blender script (see production/blender/caucasus3.py, the reference):
#   blender -b -P production/blender/<SCRIPT> -- <ARGS> --out <dir> --start 1 --end <FRAMES> --gpu OPTIX
#   writes <dir>/f_0001.jpg ... (or .png); optional PREP = a python command run first (data preparation).
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
p = subprocess.Popen(cmd + " > /tmp/render.log 2>&1", shell=True)
count = lambda: len(glob.glob("/tmp/frames/f_*.jpg")) + len(glob.glob("/tmp/frames/f_*.png"))
while p.poll() is None:
    time.sleep(90); log(f"rendered {count()}/{FRAMES}")
for l in open("/tmp/render.log"):
    if "GPU devices" in l or "Error" in l or "Traceback" in l: log(l.strip()[:300])
n = count(); log("render rc", p.returncode, "frames", n)
if n != FRAMES:
    log(open("/tmp/render.log").read()[-3000:]); raise SystemExit(1)
ext = "jpg" if glob.glob("/tmp/frames/f_*.jpg") else "png"
sh(f"ffmpeg -v error -y -framerate 30 -start_number 1 -i /tmp/frames/f_%04d.{ext} -c:v libx264 -crf 12 -preset slow -pix_fmt yuv420p {W}/{NAME}.mp4")
sh(f"ffmpeg -v error -y -i {W}/{NAME}.mp4 -vf \"select='not(mod(n\\,60))',scale=640:-1,tile=3x2\" -frames:v 1 {W}/{NAME}_sheet.jpg", check=False)
log("done", os.path.getsize(f"{W}/{NAME}.mp4"))
