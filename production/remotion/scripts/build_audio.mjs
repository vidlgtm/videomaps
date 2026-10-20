// Bundle scripts/audio_events.tsx for Node with 'remotion' replaced by the shim
import {build} from 'esbuild';
import path from 'path';
await build({entryPoints: ['scripts/audio_events.tsx'], bundle: true, platform: 'node', format: 'cjs', outfile: 'out/audio_events.cjs',
  jsx: 'automatic', alias: {remotion: path.resolve('scripts/remotion_shim.js')}, logLevel: 'error'});
