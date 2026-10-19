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
