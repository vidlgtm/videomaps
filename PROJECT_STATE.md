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
