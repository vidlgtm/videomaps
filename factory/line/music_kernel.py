# Kaggle GPU kernel (T4): the film's original score with ACE-Step 1.5 (MIT licence; turbo DiT + 5 Hz LM planner).
# One job per music cue: instrumental, the cue's caption / tempo / key / length, two takes (two seeds) ->
# /kaggle/working/<key_hash>_0.flac, <key_hash>_1.flac, <key_hash>.json; result.json lists every job (ok or error).
# The kernel stops starting new cues once its time budget is used (a stuck model never burns GPU hours).
# Placeholders filled by factory/line/music.py: __JOBS__ __ACE_COMMIT__ __BUDGET_MIN__
import base64, glob, json, os, shutil, subprocess, sys, time, traceback

JOBS = json.loads(base64.b64decode("__JOBS__").decode())
COMMIT, BUDGET_MIN = "__ACE_COMMIT__", float("__BUDGET_MIN__")
W = "/kaggle/working"; ACE = "/tmp/ace"; T0 = time.time()
DIT, LM = "acestep-v15-turbo", "acestep-5Hz-lm-1.7B"


def log(*a): print(f"[{time.strftime('%H:%M:%S')} UTC +{time.time() - T0:6.0f}s]", *a, flush=True)


def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(f"FAILED: {c[:160]}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r.stdout


res = []
try:
    log("music jobs:", [(j["key_hash"], j["cue"], j["duration"]) for j in JOBS])
    sh(f"git clone -q https://github.com/ace-step/ACE-Step-1.5 {ACE} && cd {ACE} && git checkout -q {COMMIT}")
    sh(f"cd {ACE} && pip install -q -e . --extra-index-url https://download.pytorch.org/whl/cu128")
    log("ACE-Step installed", sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader").strip())
    sys.path.insert(0, ACE); os.chdir(ACE)
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music
    dit = AceStepHandler()
    msg, ok = dit.initialize_service(project_root=ACE, config_path=DIT, device="cuda", offload_to_cpu=True,
                                     prefer_source="huggingface")
    if not ok: raise RuntimeError(f"DiT init failed: {msg}")
    log("DiT ready:", str(msg)[:200])
    llm = None
    try:
        from acestep.model_downloader import ensure_lm_model
        ok_dl, m_dl = ensure_lm_model(LM, os.path.join(ACE, "checkpoints"), prefer_source="huggingface")
        log("LM download:", ok_dl, str(m_dl)[:160])
        llm = LLMHandler()
        m2, ok2 = llm.initialize(checkpoint_dir=os.path.join(ACE, "checkpoints"), lm_model_path=LM, backend="pt",
                                 device="cuda", offload_to_cpu=True)
        log("LM:", ok2, str(m2)[:200])
        if not ok2: llm = None
    except Exception:
        log("LM unavailable, DiT only:\n" + traceback.format_exc()[-1200:]); llm = None
    for j in JOBS:
        if (time.time() - T0) / 60 > BUDGET_MIN:
            res.append({"key": j["key_hash"], "error": f"time budget {BUDGET_MIN:.0f} min used before this cue"}); continue
        t1 = time.time(); out = f"/tmp/out_{j['key_hash']}"
        shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
        try:
            p = GenerationParams(task_type="text2music", caption=j["caption"], lyrics="[Instrumental]", instrumental=True,
                                 vocal_language="unknown", bpm=j.get("bpm"), keyscale=j.get("key", ""),
                                 timesignature=str(j.get("timesig", "")), duration=float(j["duration"]),
                                 inference_steps=8, seed=int(j["seed"]), thinking=llm is not None,
                                 use_cot_metas=False, use_cot_caption=False, use_cot_language=False, use_cot_lyrics=False)
            files, costs, s0 = [], [], int(j["seed"])
            for attempt in range(2):                   # two takes; the VRAM guard may make one per call
                need = 2 - len(files)
                c = GenerationConfig(batch_size=need, use_random_seed=False, seeds=[s0 + len(files) + q for q in range(need)],
                                     audio_format="flac")
                r = generate_music(dit, llm, p, c, save_dir=out)
                if not r.success: raise RuntimeError(f"generation failed: {r.error} {r.status_message}")
                costs.append(r.extra_outputs.get("time_costs", {}))
                for a in r.audios[:need]:
                    dst = f"{W}/{j['key_hash']}_{len(files)}.flac"; shutil.copy(a["path"], dst); files.append(os.path.basename(dst))
                if len(files) >= 2: break
            meta = {**j, "files": files, "minutes": round((time.time() - t1) / 60, 2), "lm": LM if llm else None,
                    "dit": DIT, "ace_commit": COMMIT, "time_costs": costs}
            json.dump(meta, open(f"{W}/{j['key_hash']}.json", "w"), indent=1, default=str)
            res.append({"key": j["key_hash"], "files": files, "minutes": meta["minutes"]})
            log(f"cue {j['cue']} ({j['duration']} s): {len(files)} takes in {meta['minutes']} min")
        except Exception:
            res.append({"key": j["key_hash"], "error": traceback.format_exc()[-2500:]}); log(f"cue {j['cue']} FAILED")
except Exception:
    err = traceback.format_exc()[-3000:]; log("SETUP FAILED\n" + err)
    done = {x["key"] for x in res}
    res += [{"key": j["key_hash"], "error": "setup failed:\n" + err} for j in JOBS if j["key_hash"] not in done]
json.dump(res, open(f"{W}/result.json", "w"), indent=1)
for f in glob.glob(f"{W}/*"):
    if not f.endswith((".flac", ".json", ".log")): shutil.rmtree(f, ignore_errors=True) if os.path.isdir(f) else os.remove(f)
log("done:", sum(1 for x in res if "files" in x), "of", len(JOBS), "cues")
