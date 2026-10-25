MAP FILM FACTORY (in the repo videomaps, folder factory/)
Order in -> film out. The brain (third model, in a chat) decides everything that needs thinking and writes an order
(order/ORDER_SPEC.txt). The factory does every mechanical step with the fixed rules (rules/constitution.json).

  rules/constitution.json   the fixed identity of every film (look, camera, timing, rhythm, layout, sound, quality gate)
  order/ORDER_SPEC.txt      the order format (storyboard beats the director understands)
  director/                 THE AUTOMATIC DIRECTOR (TypeScript): order + voice timeline -> engine/src/data/film.json
                            cues (word times) · geo (places) · cam (framing, moves, drifts) · plan (every element) ·
                            fit (in-frame re-framing, spots/sides/corners) · sound (SFX map, music bed) · feedback (audit)
  station/                  THE PROCESSING STATION (Python + Manim): the brain's picks (orders/<o>/sources.json) ->
                            licence gate, super-resolution, levels, depth + near layer, focus point, cut-outs, signatures,
                            extra flags, Manim documents, credits, review sheets  (station.py, doc_scene.py)
  engine/                   our Remotion engine; script.ts / v2.ts / names.ts only LOAD film.json (no hand-written scene code)
                            tools/audit.ts = overlap + OFF-SCREEN + title-safe audit (machine-readable)
  orders/ussr15/            acceptance test: our film v5 written as an order (storyboard + sources.json)
  .github/workflows/factory.yml   station -> direct -> tiles -> stills (+ side-by-side with the reference release);
                            started by workflow_dispatch (inputs: order, tag factory_*, stills, compare)

Kaggle key: never stored in GitHub (phase 3 decides the safest hand-over). Status: phases 0-1 done and approved;
phase 2 (processing station) built, under test with orders/ussr15.
