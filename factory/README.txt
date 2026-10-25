MAP FILM FACTORY (in the repo videomaps, folder factory/)
Order in -> film out. The brain (third model, in a chat) decides everything that needs thinking and writes an order
(order/ORDER_SPEC.txt). The factory does every mechanical step with the fixed rules (rules/constitution.json).

  rules/constitution.json   the fixed identity of every film (look, camera, timing, rhythm, layout, sound, quality gate)
  order/ORDER_SPEC.txt      the order format (storyboard beats the director understands)
  director/                 THE AUTOMATIC DIRECTOR (TypeScript): order + voice timeline -> engine/src/data/film.json
                            cues (word times) · geo (places) · cam (framing, moves, drifts) · plan (every element) ·
                            fit (in-frame re-framing, spots/sides/corners) · sound (SFX map, music bed) · feedback (audit)
  engine/                   our Remotion engine; script.ts / v2.ts / names.ts only LOAD film.json (no hand-written scene code)
                            tools/audit.ts = overlap + OFF-SCREEN + title-safe audit (machine-readable)
  orders/ussr15/            acceptance test of phase 1: our film v5 written as an order
  .github/workflows/factory.yml   direct -> tiles -> stills (+ side-by-side with the reference release)

Kaggle key: never stored in GitHub - injected as temporary secrets by the brain and withdrawn as soon as the Kaggle job
has started. Status: phase 0 done; phase 1 (automatic director) built, under test with orders/ussr15.
