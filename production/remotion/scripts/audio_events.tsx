// Dumps every <Audio> of AudioMix (src, start frame, duration, per-frame volume) to JSON for the offline mixer.
import {AudioMix} from '../src/components/AudioMix';
import {END} from '../src/script';
import * as fs from 'fs';
const FPS = 30;
const TOTALF = Math.ceil(END * FPS);
const out: any[] = [];
function walk(node: any, from: number, dur: number) {
  if (node == null || typeof node === 'boolean') return;
  if (Array.isArray(node)) { node.forEach((n) => walk(n, from, dur)); return; }
  const kind = node.type && node.type.__kind;
  if (typeof node.type === 'symbol') { walk(node.props.children, from, dur); return; }
  if (kind === 'Sequence') { walk(node.props.children, from + node.props.from, node.props.durationInFrames); return; }
  if (kind === 'Audio') {
    const v = node.props.volume;
    const d = Math.min(dur, TOTALF - from);
    out.push({src: node.props.src, from, dur: d, vol: typeof v === 'number' ? v : v === undefined ? 1 : null,
      vols: typeof v === 'function' ? Array.from({length: d}, (_, f) => v(f)) : null,
      startFrom: node.props.startFrom ?? 0, rate: node.props.playbackRate ?? 1});
    return;
  }
  throw new Error('unknown node ' + String(node.type));
}
walk(AudioMix({} as any), 0, TOTALF);
if (out.some((e) => e.startFrom !== 0 || e.rate !== 1)) throw new Error('startFrom/playbackRate not supported by mixer');
fs.writeFileSync(process.env.EVENTS_OUT || 'out/audio_events.json', JSON.stringify({fps: FPS, totalFrames: TOTALF, events: out}));
console.log('audio events', out.length, 'music', out.filter((e) => e.vols).length, 'frames', TOTALF);
