# Kaggle GPU kernel (T4): the order's 3D objects from their cut-outs (release files of this repository) -
# TripoSR for small map icons, Hunyuan3D-2 (shape + texture, low-VRAM offload) for models - then Blender Cycles GPU
# renders from 4 azimuths with the factory's object look (factory/objects/render_obj.py at the same commit).
# Writes /kaggle/working: <rkey>_a<az>.png, <rkey>_render.json, <rkey>.glb (models), batch.json (one result per object).
# Placeholders filled by factory/objects/objects.py: __REPO_URL__ __SHA__ __BATCH__ __DATA_URL__
import base64, glob, json, os, shutil, subprocess, sys, time, traceback, urllib.request

REPO, SHA, DATA = "__REPO_URL__", "__SHA__", "__DATA_URL__"
JOBS = json.loads(base64.b64decode("__BATCH__"))
W = "/kaggle/working"
T0 = time.time()
TRIPOSR_SHA = "107cefdc244c39106fa830359024f6a2f1c78871"
TORCHMCUBES_SHA = "a9ac95aa329957ba646e7bb057f825f5dfa77f38"
HY3D_SHA = "f8db63096c8282cb27354314d896feba5ba6ff8a"
VIEWS = "0,90,180,270"
res = {}


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')} UTC +{time.time() - T0:6.0f}s]", *a, flush=True)


def sh(c, check=True, timeout=3600):
    try:
        r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"timed out after {timeout}s: {c[:160]}")
    if check and r.returncode:
        raise RuntimeError(f"failed ({r.returncode}): {c[:200]}\n{r.stdout[-1500:]}\n{r.stderr[-2500:]}")
    return r


def fail(j, msg):
    res[j["name"]] = {"name": j["name"], "rkey": j["rkey"], "kind": j["kind"], "error": msg[-3000:]}
    log("OBJECT FAILED", j["name"], msg[-600:])


log("objects: start", SHA[:7], ", ".join(f"{j['name']} ({j['engine']})" for j in JOBS))
sh(f"git clone -q {REPO} /tmp/vm && cd /tmp/vm && git checkout -q {SHA}")
os.makedirs("/tmp/cuts", exist_ok=True)
for j in JOBS:
    j["cut_path"] = f"/tmp/cuts/{j['ikey']}.png"
    try:
        urllib.request.urlretrieve(DATA + j["cut"], j["cut_path"])
    except Exception as e:
        fail(j, f"cut-out {j['cut']} could not be downloaded: {e}")
r = sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", check=False)
log("GPU:", r.stdout.strip().replace("\n", " | "))
icons = [j for j in JOBS if j["engine"] == "triposr" and j["name"] not in res]
models = [j for j in JOBS if j["engine"] == "hunyuan" and j["name"] not in res]

# ---------------------------------------------------------------- TripoSR (icons)
if icons:
    try:
        t = time.time()
        sh(f"git clone -q https://github.com/VAST-AI-Research/TripoSR /tmp/TripoSR && cd /tmp/TripoSR && git checkout -q {TRIPOSR_SHA}")
        sh("pip install -q onnxruntime rembg omegaconf==2.3.0 einops transformers==4.57.6 trimesh huggingface-hub "
           "imageio[ffmpeg] xatlas moderngl")
        r = sh(f"pip install -q git+https://github.com/tatsy/torchmcubes.git@{TORCHMCUBES_SHA}", check=False, timeout=2400)
        if r.returncode:
            log("torchmcubes build failed; installing its scikit-build backend and retrying without isolation")
            sh("pip install -q scikit-build-core scikit-build cmake ninja pybind11")
            sh(f"pip install -q --no-build-isolation git+https://github.com/tatsy/torchmcubes.git@{TORCHMCUBES_SHA}", timeout=2400)
        log("TripoSR ready in", round(time.time() - t), "s; Transformers",
            sh("python -c 'import transformers; print(transformers.__version__)'").stdout.strip())
        sys.path.insert(0, "/tmp/vm/factory/objects")
        import cut
        ins = []
        for i, j in enumerate(icons):
            os.makedirs(f"/tmp/tsr_out/{i}", exist_ok=True)
            cut.grey_input(j["cut_path"], f"/tmp/tsr_in_{i}.png"); ins.append(f"/tmp/tsr_in_{i}.png")
        t = time.time()
        sh(f"cd /tmp/TripoSR && python run.py {' '.join(ins)} --device cuda:0 --mc-resolution 320 --no-remove-bg "
           f"--output-dir /tmp/tsr_out --model-save-format obj", timeout=3600)
        log("TripoSR meshes in", round(time.time() - t), "s")
        for i, j in enumerate(icons):
            p = f"/tmp/tsr_out/{i}/mesh.obj"
            if os.path.exists(p): j["mesh"] = p
            else: fail(j, "TripoSR made no mesh")
    except Exception:
        for j in icons:
            if j["name"] not in res: fail(j, "TripoSR stage: " + traceback.format_exc())

# ---------------------------------------------------------------- Hunyuan3D-2 (models)
HY = r'''
import json, sys, time, traceback, torch
from PIL import Image
sys.path.insert(0, "/tmp/hy3d")
job = json.load(open("/tmp/hy3d_job.json"))
out, meshes = {m["name"]: {} for m in job}, {}
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline, FloaterRemover, DegenerateFaceRemover, FaceReducer
shape = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained("tencent/Hunyuan3D-2", subfolder="hunyuan3d-dit-v2-0",
                                                         use_safetensors=True, device="cuda")
for m in job:
    t = time.time()
    try:
        img = Image.open(m["cut_path"]).convert("RGBA")
        mesh = shape(image=img, num_inference_steps=50, octree_resolution=380, num_chunks=20000,
                     generator=torch.manual_seed(int(m["seed"])), output_type="trimesh")[0]
        mesh = FloaterRemover()(mesh); mesh = DegenerateFaceRemover()(mesh); mesh = FaceReducer()(mesh, max_facenum=int(m["faces"]))
        meshes[m["name"]] = mesh
        mesh.export(f"/tmp/hy3d_out/{m['rkey']}_shape.glb")
        out[m["name"]]["shape_s"] = round(time.time() - t); out[m["name"]]["faces"] = int(len(mesh.faces))
        print("shape", m["name"], out[m["name"]], flush=True)
    except Exception:
        out[m["name"]]["error"] = "shape: " + traceback.format_exc()[-2500:]
del shape
torch.cuda.empty_cache()
tex = [m for m in job if m["name"] in meshes and m.get("texture", True)]
for m in job:
    if m["name"] in meshes and not m.get("texture", True):
        meshes[m["name"]].export(f"/tmp/hy3d_out/{m['rkey']}.glb")
if tex:
    try:
        from hy3dgen.texgen import Hunyuan3DPaintPipeline
        paint = Hunyuan3DPaintPipeline.from_pretrained("tencent/Hunyuan3D-2")
        paint.enable_model_cpu_offload()
    except Exception:
        for m in tex: out[m["name"]]["error"] = "texture model: " + traceback.format_exc()[-2500:]
        tex = []
    for m in tex:
        t = time.time()
        try:
            img = Image.open(m["cut_path"]).convert("RGBA")
            tm = paint(meshes[m["name"]], image=img)
            tm.export(f"/tmp/hy3d_out/{m['rkey']}.glb")
            out[m["name"]]["texture_s"] = round(time.time() - t)
            print("texture", m["name"], out[m["name"]], flush=True)
        except Exception:
            out[m["name"]]["error"] = "texture: " + traceback.format_exc()[-2500:]
        torch.cuda.empty_cache()
json.dump(out, open("/tmp/hy3d_out/result.json", "w"))
'''
if models:
    try:
        t = time.time()
        sh(f"git clone -q https://github.com/Tencent-Hunyuan/Hunyuan3D-2 /tmp/hy3d && cd /tmp/hy3d && git checkout -q {HY3D_SHA}")
        sh("pip install -q diffusers accelerate pymeshlab pygltflib xatlas opencv-python omegaconf einops trimesh ninja "
           "pybind11 rembg onnxruntime transformers==4.57.6")
        sh("cd /tmp/hy3d && pip install -q --no-deps -e .")
        if any(m.get("texture", True) for m in models):
            sh("cd /tmp/hy3d/hy3dgen/texgen/custom_rasterizer && TORCH_CUDA_ARCH_LIST=7.5 pip install -q --no-build-isolation .", timeout=3000)
            # the mesh painter: compiled in place (the package imports it relatively; its pure-Python twin is the fallback)
            r = sh("cd /tmp/hy3d/hy3dgen/texgen/differentiable_renderer && c++ -O3 -Wall -shared -std=c++11 -fPIC "
                   "$(python -m pybind11 --includes) mesh_processor.cpp -o mesh_processor$(python -c \"import sysconfig; "
                   "print(sysconfig.get_config_var('EXT_SUFFIX'))\")", check=False, timeout=1200)
            log("mesh painter:", "compiled" if r.returncode == 0 else "pure-Python fallback (" + (r.stderr or "")[-300:] + ")")
        log("Hunyuan3D-2 ready in", round(time.time() - t), "s")
        os.makedirs("/tmp/hy3d_out", exist_ok=True)
        json.dump(models, open("/tmp/hy3d_job.json", "w"))
        open("/tmp/hy3d_run.py", "w").write(HY)
        t = time.time()
        r = sh("cd /tmp/hy3d && python /tmp/hy3d_run.py", check=False, timeout=4 * 3600)
        for l in (r.stdout or "").splitlines():
            if l.startswith(("shape", "texture")): log(l[:300])
        log("Hunyuan3D-2 done in", round(time.time() - t), "s, exit", r.returncode)
        out = json.load(open("/tmp/hy3d_out/result.json")) if os.path.exists("/tmp/hy3d_out/result.json") else {}
        for j in models:
            o = out.get(j["name"])
            if o is None: fail(j, "Hunyuan3D-2 ended without a result:\n" + (r.stderr or "")[-2500:]); continue
            if "error" in o: fail(j, o["error"]); continue
            p = f"/tmp/hy3d_out/{j['rkey']}.glb"
            if not os.path.exists(p): fail(j, "Hunyuan3D-2 wrote no GLB"); continue
            j["mesh"] = p; j["stats"] = o
    except Exception:
        for j in models:
            if j["name"] not in res: fail(j, "Hunyuan3D-2 stage: " + traceback.format_exc())

# ---------------------------------------------------------------- Blender GPU renders
todo = [j for j in JOBS if j.get("mesh") and j["name"] not in res]
if todo:
    try:
        sh("apt-get -qq install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libxkbcommon0 libsm6 libice6 "
           "> /dev/null 2>&1 || true", check=False)
        sh("F=$(curl -s https://download.blender.org/release/Blender4.5/ | grep -oE 'blender-4\\.5\\.[0-9]+-linux-x64\\.tar\\.xz' "
           "| sort -V | uniq | tail -1); curl -sfL --retry 3 -o /tmp/b.tar.xz https://download.blender.org/release/Blender4.5/$F "
           "&& mkdir -p /tmp/blender && tar -xf /tmp/b.tar.xz -C /tmp/blender --strip-components=1 && rm /tmp/b.tar.xz")
        log(sh("/tmp/blender/blender -b --version").stdout.splitlines()[0])
    except Exception:
        for j in todo: fail(j, "Blender setup: " + traceback.format_exc())
        todo = []
for j in todo:
    t = time.time()
    samples = 256 if j["kind"] == "icon" else 160
    r = sh(f"/tmp/blender/blender -b --python-exit-code 1 -P /tmp/vm/factory/objects/render_obj.py -- --mesh {j['mesh']} "
           f"--out {W} --name {j['rkey']} --res 768 --samples {samples} --views {VIEWS} --gpu OPTIX --ref {j['cut_path']}",
           check=False, timeout=3600)
    for l in r.stdout.splitlines():
        if l.startswith(("GPU devices", "rendered", "OBJECT ERROR")): log(j["name"], l[:200])
    pngs = [f"{j['rkey']}_a{az}.png" for az in VIEWS.split(",")]
    if r.returncode or not all(os.path.exists(f"{W}/{p}") for p in pngs):
        fail(j, f"Blender render failed (exit {r.returncode}):\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"); continue
    files = pngs + [f"{j['rkey']}_render.json"]
    if j["kind"] == "model":
        shutil.copy(j["mesh"], f"{W}/{j['rkey']}.glb"); files.append(f"{j['rkey']}.glb")
    res[j["name"]] = {"name": j["name"], "rkey": j["rkey"], "kind": j["kind"], "files": files, "stats": j.get("stats", {}),
                      "render_s": round(time.time() - t), "minutes": round((time.time() - T0) / 60, 1)}
    log("made", j["name"], "in", round(time.time() - t), "s (render)")
json.dump([res.get(j["name"]) or {"name": j["name"], "rkey": j["rkey"], "kind": j["kind"], "error": "not reached"} for j in JOBS],
          open(f"{W}/batch.json", "w"), indent=1)
for p in glob.glob(f"{W}/*.blend1"): os.remove(p)
log("done:", sum(1 for x in res.values() if "error" not in x), "made,", sum(1 for x in res.values() if "error" in x), "failed")
