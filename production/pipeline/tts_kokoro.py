"""Fallback narration (only when the project has no platform-TTS takes in projects/<P>/vo/): Kokoro-82M (Apache-2.0),
American English, one take per paragraph -> out/tts/vo_<id>.wav. Voice: narration.json "kokoro_voice" or env KOKORO_VOICE;
"auto" = match the gender of our narrator (assets/voice_reference/narrator_reference.mp3: median F0 < 165 Hz -> am_michael,
else af_heart). install: apt espeak-ng; pip kokoro>=0.9.4 soundfile"""
import json, os, subprocess
import numpy as np, soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = os.environ.get("PROJECT", "example_baltic")
N = json.load(open(f"{ROOT}/projects/{P}/narration.json"))
voice = os.environ.get("KOKORO_VOICE") or N.get("kokoro_voice", "auto")
if voice == "auto":
    ref = f"{ROOT}/assets/voice_reference/narrator_reference.mp3"
    voice = "am_michael"
    if os.path.exists(ref):
        import pyworld as pw
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", ref, "-f", "f64le", "-ac", "1", "-ar", "16000", "-"], check=True, capture_output=True).stdout
        x = np.frombuffer(raw, dtype=np.float64).copy()
        f0, t = pw.dio(x, 16000, f0_floor=60, f0_ceil=320); f0 = pw.stonemask(x, f0, t, 16000); v = f0[f0 > 0]
        med = float(np.median(v)) if len(v) else 120.0
        voice = "am_michael" if med < 165 else "af_heart"
        print(f"reference narrator median F0 {med:.1f} Hz -> {voice}")
from kokoro import KPipeline
pipe = KPipeline(lang_code="a")          # 'a' = American English
os.makedirs("out/tts", exist_ok=True)
for p in N["paragraphs"]:
    parts = [np.asarray(a, dtype=np.float32) for _, _, a in pipe(p["text"], voice=voice, speed=float(N.get("kokoro_speed", 1.0)))]
    audio = np.concatenate(parts)
    sf.write(f"out/tts/vo_{p['id']}.wav", audio, 24000)
    print(f"vo_{p['id']}.wav {len(audio) / 24000:.2f}s ({voice})", flush=True)
