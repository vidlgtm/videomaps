// Sound map (constitution "sound"): SFX for every event, accents chosen in the order, one continuous music bed that
// cross-fades between chapter cues under the voice.
import type {Director} from './plan';
import {r3} from './util';

const ACCENT: Record<string, [string, number][]> = {
  war: [['war_rumble', 0.5]], tension: [['drone_hit', 0.35]], crowd: [['crowd_bed', 0.26]], bell: [['bell_toll', 0.45]],
  seal: [['stamp', 0.36]], annex: [['stamp', 0.34]], boom: [['boom', 0.4]], swell: [['swell', 0.45]], forge: [['forge_hiss', 0.45]],
  count: [['tick', 0.45]], finale: [['bell_small', 0.42], ['swell', 0.4]], riser: [['riser', 0.3]], shimmer: [['shimmer', 0.3]],
  wind: [['wind_bed', 0.4]], paper: [['paper', 0.4]], draw: [['line_draw', 0.3]],
};
export function sound(d: Director) {
  // camera moves: a soft whoosh for every real move (not the slow drifts)
  let w = 0;
  d.keys.forEach((k) => { const dur = k.dur ?? 2.2; if (k.t > 1 && dur > 1.5 && dur <= 3.2 && k.kind !== 'drift') d.sfx(`whoosh_${(w++ % 3) + 1}`, k.t - 0.15, 0.24); });
  d.accents.forEach(({t, a}) => (ACCENT[a] ?? (() => { throw new Error(`unknown accent "${a}" (${Object.keys(ACCENT).join(', ')})`); })())
    .forEach(([f, v], i) => d.sfx(f, t - (f === 'riser' || f === 'swell' ? 2.4 : 0) + i * 0.05, v)));
  // the same sound twice within 0.12 s -> keep the louder
  const s = d.F.sfx.sort((a, b) => a.t - b.t), out: any[] = [];
  for (const e of s) { const dup = out.find((o) => o.f === e.f && Math.abs(o.t - e.t) < 0.12); if (dup) dup.v = Math.max(dup.v, e.v); else out.push(e); }
  d.F.sfx = out.filter((e) => e.t < d.END - 0.3);
  // music: consecutive chapters with the same cue share one continuous bed
  const blocks: {music: string; c0: number; c1: number}[] = [];
  d.chapters.forEach((ch) => {
    const last = blocks[blocks.length - 1];
    if (last && last.music === ch.music) last.c1 = ch.cs[ch.cs.length - 1];
    else blocks.push({music: ch.music, c0: ch.cs[0], c1: ch.cs[ch.cs.length - 1]});
  });
  d.F.music = blocks.map((b, i) => {
    const m = d.a.music?.[b.music] ?? {file: `music/music_${b.music}.mp3`, lufs: -11};
    const first = i === 0, lastB = i === blocks.length - 1;
    const to = lastB ? d.END : first ? d.pStart(blocks[1].c0) + 3.0 : d.pEnd(b.c1) + 2.5;
    return {src: m.file, from: first ? 0 : r3(d.pStart(b.c0) - 2.2), to: r3(to),
      lufs: m.lufs, xin: first ? 1.5 : 4.5, xout: lastB ? 3.5 : 5.0};
  });
}
