# PROJECT STATE (memory file — updated after every work session)

## Brief (hard requirements — never forget)
1. Pro **American English** voice-over + calm, non-annoying **music** + **sound effects**. Music must be original (NO YouTube Audio Library).
2. **New topic**, **≥ 7 minutes** (target ~8:00). **Flags drop onto each relevant country**, borders drawn/changed.
3. Graphics, colours, **smooth animation** matching the 3 reference videos (see Drive analysis).
4. More professional and smarter than the references.
5. **Zero mistakes**: every fact sourced, borders/flags verified, preview before final render.
- Mandatory tools: Remotion, Three.js, Apache ECharts, Manim, Blender, Hunyuan3D-2 or TripoSR (+ extra GitHub tools).
- Everything stored in Google Drive. Keep chat short. Stop at limits and ask user to continue.

## Topic
**Why the Soviet Union Broke Into Exactly 15 Countries** (Stalin's 1936 criteria; Tatarstan vs Estonia; Chechnya; matryoshka federalism).

## Known traps
- Natural Earth default view may assign Crimea to Russia → for 1991 maps Crimea MUST be in Ukraine (Ukrainian SSR since 1954).
- Abkhazia / South Ossetia / Transnistria: show as parts of Georgia / Moldova in 1991.
- Russia crosses the antimeridian → always rotate projections (e.g. rotate([-95,0])).

## Status
- [x] Repo created (public) — token lacks *Secrets* permission (needed for HF token / encryption).
- [ ] Smoke test of all tools on GitHub Actions (workflow `smoke-test.yml`).
- [ ] Analysis of 3 reference videos → Drive.
- [ ] Research + script + sources → user approval.
- [ ] Voice → word timings.  - [ ] Storyboard + style frames → approval.
- [ ] Assets / scenes / preview / final render → Drive.

## 2026-10-19 — Production stage 1 launched
- Voice: 7 clips production/voice/vo_00..06.mp3 (voice-00), total 538 s narration (~9:10 with pauses).
- Drive 01 Analysis: 4 Google Docs + 1 Sheet uploaded (00 DNA, 01-03, shot log).
- stage1.yml run 39314086382 -> publishes GitHub release "stage1": voice.wav, timeline.json (word timings), subtitles.srt,
  music.zip (5 cues c1..c5), sfx.zip, geo.json (LCC lon0=90, 8192x5996 px canvas), basemap.jpg, globe.jpg,
  caucasus.mp4 + caucasus_labels.json, matryoshka.mov/.webm (alpha) + timing, matryoshka.glb, 6 Manim .mov overlays.
- Next: Remotion production composition (stage2) synced to timeline.json -> preview -> final render -> Drive.

## 2026-10-20 — Stage 2 (final film) wired
- fix1.yml (run 39396432904): matryoshka missing frames, Caucasus relief x2.6 re-render, 4 Manim layout fixes -> release stage1 (clobber).
- Corrected geo.json (breakaways + rsfsr_1924/1929/1940) committed in production/remotion/src/data; music c4/c5 (ACE-Step) uploaded as music_c*.mp3.
- production/remotion: Remotion 4.0.537 film. script.ts = every event pinned to narration words (timeline.json).
  MapStage = CSS-3D tilted LCC basemap + SVG layers + billboard flags; camera clamp keeps view inside canvas.
  Globe = Three.js (@remotion/three); Chart = ECharts SSR; Clips = stepped Manim/Blender videos; AudioMix = voice + 5 cues ducked + SFX.
- stage2.yml auto-runs after fix1 succeeds: 20 parallel chunks -> concat -> loudnorm -14 LUFS -> release "final" (USSR15_final_1080p.mp4 + 720p preview).
- Next: download final from release, upload to Drive (resumable upload), report.

## Stage 2 – rerun (2026-10-20)
- Run 39403022652: video chunks OK but at high map zoom the 4-tab render dropped overlay layers (date cards, LTU flag, clip start);
  Remotion audio job hit the 60-min limit.
- Fixes: render = 3 independent browsers x concurrency 1 per chunk + self-check vs fresh-page stills (auto per-frame fallback);
  audio = exact AudioMix event export (scripts/audio_events.tsx) -> pipeline/mix.py -> pipeline/master.py (-14 LUFS, -1.5 dBTP,
  VO ~12 dB over music, SFX -5 dB); all job limits 360 min; QA sheets + qa_report.txt published with release "final".
- Design fixes: chapter III title on one line; chapter IV card ends before Gorbachev portrait; chapter V card before the dolls;
  map flags hidden under the closing title; Stalin captions note "photo 1943".

## FINAL (2026-10-20)
- stage2 run 39419766208 (render + audio) -> assemble run 39443672706 (frame-exact) -> release `final`.
- Final: 1920x1080p30 H.264, 16,807 frames = 9:20.23, AAC 320k, -14.0 LUFS integrated, true peak -1.3 dBFS.
- QA sheets checked: all earlier defects fixed (chapter III title, Gorbachev card, chapter V/dolls, 1989/1990 date cards + LTU flag,
  closing title clean, Stalin photo-year captions).
- Drive "04 Final Film" 11AtYTpfPWmbDN8tzPdp5R9nMVhUcedbg: final 1X6PghuDCzXJx5W_mLrNPIoPcemBs064k,
  preview 1ybJeH0iVjrz3qNGyJdrKU4OhPJCal9Im, subtitles 1sIRc4WG1kIXeYqObyIzneZfObWQrUeUP (production/subtitles/).
