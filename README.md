# videomaps

Programmatic production pipeline for a professional animated history/geography explainer
(“Why the Soviet Union Broke Into Exactly 15 Countries”).

**Director:** AI agent (writes code, launches jobs, QA). **Factory:** GitHub Actions. **Archive:** Google Drive.

## Mandatory core tools
Remotion · Three.js (@remotion/three) · Apache ECharts · Manim · Blender · Tencent Hunyuan3D-2 / TripoSR

## Additional open-source tools
d3-geo · topojson/world-atlas · Natural Earth (nvkelso/natural-earth-vector) · historical-basemaps · flag-icons ·
mapshaper · turf · polylabel · flubber · three-globe · react-three-fiber/drei/postprocessing · BlenderGIS ·
rembg · Depth-Anything-V2 · Real-ESRGAN · faster-whisper / stable-ts · Kokoro / Chatterbox · ACE-Step ·
VSCO-2 CE + sfizz/FluidSynth · pedalboard · pyloudnorm · FFmpeg · gradio_client

Music policy: original music only — **no YouTube Audio Library**.

## Layout
- `smoke/` – smoke tests proving every tool runs on GitHub-hosted runners
- `.github/workflows/` – CI factory jobs
- `PROJECT_STATE.md` – live project memory (what is done / next)
