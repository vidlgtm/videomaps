// EXAMPLE PROJECT "The Baltic Way" (5 scenes = 5 narration paragraphs, ~60 s). The film's visual score: every event is
// pinned to a word of the narration (cue(paragraphIndex, 'exact words') -> seconds, from data/timeline.json).
// Copy this structure for a new project (scripts/new_project.sh); keep every export, switch unused features OFF.
import {TOTAL} from './lib/cues';
import {OFF} from './types';
import type {CamKey, Fill, Stroke, Label, Marker, Flag, Line, Ring, Card, Portrait, Clip, Sfx, Music, GlobeSpec} from './types';
import {P, CHAIN, ICONS, BANNERS} from './v2';
export type {CamKey, Fill, Stroke, Label, Marker, Flag, Line, Ring, Card, Portrait, Step, Clip, Sfx, Music} from './types';

export const END = TOTAL;

// ---------- palette (our house colours; national tints are muted, never neon) ----------
export const COL: Record<string, string> = {
  EST: '#5C86C2', LVA: '#9B4F6E', LTU: '#C98B4E', UNION: '#8E3741', GOLD: '#E2BF6A', INK: '#0E1A24', TXT: '#F4EFE6', RED: '#D2434E',
  TEAL: '#4FA39E', CHAIN: '#FFE3A0',
};
/** the countries this film is about: 'borders' strokes and the title-card flag row use this list */
export const ISO15 = ['EST', 'LVA', 'LTU'];
/** flag key -> flag-icons 4x3 file code (public/flags/4x3/<code>.svg). SU1..3 = three Soviet flags (su.svg added at prep) */
export const FLAG_CODE: Record<string, string> = {EST: 'ee', LVA: 'lv', LTU: 'lt', SU1: 'su', SU2: 'su', SU3: 'su'};
/** flag width/height ratio per file code (default 4/3) */
export const FLAG_ASPECT: Record<string, number> = {su: 2};
export const NAME: Record<string, string> = {EST: 'Estonia', LVA: 'Latvia', LTU: 'Lithuania'};

// ---------- cue times: defined once in v2.ts (P), shared by both files ----------
const {p0, p1, p2, p3, p4} = P;
export const T = P;


// ---------- Three.js globe hook (night Earth -> dive onto the Baltic) ----------
export const GLOBE: GlobeSpec = {from: 0, to: p0.hands + 0.9, tex: 'globe_night_4k.jpg', overlay: null, spin: 2.0,
  keys: [{t: 0, lon: -18, lat: 22, dist: 4.9}, {t: p0.y89, lon: 12, lat: 46, dist: 3.4}, {t: p0.hands + 0.2, lon: 24.6, lat: 57.2, dist: 1.9}]};

// ---------- camera (w = visible width in km; tilt in degrees; local north is rotated ~72 % towards screen-up) ----------
const V = {
  IN: {lon: 24.9, lat: 57.1, w: 1250, tilt: 30},
  PACT: {lon: 25.6, lat: 56.7, w: 1900, tilt: 24},
  BALTIC: {lon: 24.8, lat: 57.0, w: 1050, tilt: 32},
  TAL: {lon: 24.9, lat: 58.75, w: 860, tilt: 34},
  RIGA: {lon: 24.3, lat: 57.05, w: 860, tilt: 34},
  VIL: {lon: 25.1, lat: 55.45, w: 900, tilt: 34},
  BACK: {lon: 24.9, lat: 57.0, w: 1250, tilt: 30},
  INDEP: {lon: 25.1, lat: 57.0, w: 1450, tilt: 28},
  OUT: {lon: 25.6, lat: 57.0, w: 2200, tilt: 22},
};
const cam = (t: number, v: any, dur = 2.2): CamKey => ({t, dur, ...v});
export const CAMERA: CamKey[] = [
  cam(0, V.IN, 0.01),
  cam(p0.hands + 0.3, {...V.IN, w: 1150}, 4.0),          // slow push-in under the globe dissolve
  cam(p1.fifty - 0.2, V.PACT, 2.6),
  cam(p2.s - 0.2, V.BALTIC, 2.4),
  cam(p2.tallinn - 0.3, V.TAL, 1.9),
  cam(p2.riga - 0.2, V.RIGA, 1.8),
  cam(p2.vilnius - 0.2, V.VIL, 1.8),
  cam(p2.fifteen - 0.1, V.BACK, 2.4),
  cam(p3.s - 0.2, V.INDEP, 2.2),
  cam(p4.s - 0.2, V.OUT, 3.0),
];

// ---------- fills, borders, lines ----------
const B3 = ['rep:EST', 'rep:LVA', 'rep:LTU'];
export const FILLS: Fill[] = [
  // 1940: the three republics turn Soviet red, one by one, as they are named
  ...([['rep:EST', p1.est], ['rep:LVA', p1.lva], ['rep:LTU', p1.ltu]] as [string, number][]).map(([id, t]) =>
    ({id, color: COL.UNION, op: 0.58, from: t - 0.1, to: p2.s + 0.4, fi: 0.7, fo: 0.8} as Fill)),
  // 1989: a quieter red under the chain
  ...B3.map((id) => ({id, color: COL.UNION, op: 0.26, from: p2.s, to: p3.ltu + 0.3, fi: 0.6, fo: 0.6} as Fill)),
  ...B3.slice(0, 2).map((id) => ({id, color: COL.UNION, op: 0.26, from: p3.ltu, to: p3.estlva + 0.3, fi: 0.3, fo: 0.6} as Fill)),
  // independence: national tints
  {id: 'rep:LTU', color: COL.LTU, op: 0.5, from: p3.ltu, to: END + 1, fi: 0.8},
  {id: 'rep:EST', color: COL.EST, op: 0.5, from: p3.estlva, to: END + 1, fi: 0.8},
  {id: 'rep:LVA', color: COL.LVA, op: 0.5, from: p3.lva, to: END + 1, fi: 0.8},
];
export const STROKES: Stroke[] = [
  // borders traced in light the moment each country (re)appears
  ...([['rep:EST', p1.est], ['rep:LVA', p1.lva], ['rep:LTU', p1.ltu]] as [string, number][]).map(([id, t]) =>
    ({id, color: '#F4D58A', width: 2.6, from: t - 0.15, to: p2.s + 0.3, draw: 1.2, glow: true} as Stroke)),
  {id: 'rep:LTU', color: '#FFE7A8', width: 2.8, from: p3.ltu - 0.1, to: END + 1, draw: 1.3, glow: true},
  {id: 'rep:EST', color: '#FFE7A8', width: 2.8, from: p3.estlva - 0.1, to: END + 1, draw: 1.3, glow: true},
  {id: 'rep:LVA', color: '#FFE7A8', width: 2.8, from: p3.lva - 0.1, to: END + 1, draw: 1.3, glow: true},
];
export const LINES: Line[] = [
  // hook: the "living line" flashes across the three nations as the globe hands over to the map
  {pts: CHAIN.pts, from: p0.drew - 0.1, dur: 2.6, to: p0.e + 0.6, color: '#FFF3C4', width: 3},
];
export const RINGS: Ring[] = [];

// ---------- labels and markers ----------
export const LABELS: Label[] = [
  {text: 'Baltic Sea', at: [20.6, 57.9], size: 30, from: p0.hands + 0.6, to: END + 1, italic: true},
  {text: 'Gulf of Finland', at: [26.6, 59.85], size: 22, from: p2.s + 0.5, to: p3.s, italic: true},
];
export const MARKERS: Marker[] = [
  {city: 'Tallinn', label: 'Tallinn', from: p2.tallinn - 0.1, to: p2.fifteen + 0.6, side: 'r'},
  {city: 'Riga', label: 'Riga', from: p2.riga - 0.1, to: p2.fifteen + 0.6, side: 'r'},
  {city: 'Vilnius', label: 'Vilnius', from: p2.vilnius - 0.1, to: p2.fifteen + 0.6, side: 'r'},
];

// ---------- flags (spring drop, leader line when pushed aside, date under the flag) ----------
export const FLAGS: Flag[] = [
  {iso: 'SU1', t: p1.est + 0.1, to: p2.s + 0.3, at: [25.9, 58.75]},
  {iso: 'SU2', t: p1.lva + 0.1, to: p2.s + 0.3, at: [25.6, 56.85]},
  {iso: 'SU3', t: p1.ltu + 0.1, to: p2.s + 0.3, at: [24.1, 55.35]},
  {iso: 'LTU', t: p3.first - 0.1, to: END + 1, date: '11 MAR 1990'},
  {iso: 'EST', t: p3.estlva + 0.05, to: END + 1, date: '20 AUG 1991'},
  {iso: 'LVA', t: p3.lva + 0.2, to: END + 1, date: '21 AUG 1991'},
];
export const FLAG_HIDE: [number, number][] = [[p4.flags - 0.3, END + 1]];   // flags step back under the closing title

// ---------- screen cards ----------
export const CARDS: Card[] = [
  {kind: 'date', text: '23 AUGUST 1939', sub: 'MOLOTOV–RIBBENTROP PACT', from: p1.fifty, to: p1.pact - 0.45, pos: 'tr'},
  {kind: 'date', text: 'AUGUST 1940', sub: 'ANNEXED BY THE USSR', from: p1.aug40 - 0.05, to: p1.e + 0.5, pos: 'tr'},
  {kind: 'date', text: '23 AUGUST 1989', sub: 'THE BALTIC WAY · 19:00', from: p2.anniv - 0.1, to: p2.tallinn - 0.2, pos: 'tl'},
  {kind: 'date', text: '11 MARCH 1990', sub: 'LITHUANIA DECLARES INDEPENDENCE', from: p3.ltu - 0.05, to: p3.estlva - 0.25, pos: 'tr'},
  {kind: 'date', text: '20–21 AUGUST 1991', sub: 'ESTONIA · LATVIA', from: p3.estlva, to: p3.e + 0.4, pos: 'tr'},
  {kind: 'date', text: '6 SEPTEMBER 1991', sub: 'MOSCOW RECOGNISES ALL THREE', from: p4.sept - 0.05, to: p4.flags - 0.3, pos: 'tl'},
];
export const PORTRAITS: Portrait[] = [];

// ---------- clips (Manim parchment: the 1939 pact) ----------
export const CLIPS: Clip[] = [
  // full-frame parchment (Manim doc_scene.py from projects/<p>/manim/pact1939.json); kind 'cauc' = opaque full-frame clip
  {kind: 'cauc', src: 'clips/pact1939.mp4', from: p1.pact - 0.3, to: p1.aug40 - 0.2, steps: [{at: p1.pact - 0.3, s0: 0, s1: 6.0, rate: 1.2}]},
];
export const DOLL_LABELS: {text: string; k: number; from: number; to: number}[] = [];
export const CHART = {from: OFF, to: OFF + 1};
export const FLAGPOLE = {from: OFF, lower: OFF + 0.2, lowered: OFF + 0.4, raise: OFF + 0.6, to: OFF + 0.8,
  from2: OFF, lower2: OFF + 0.2, raise2: OFF + 0.4, to2: OFF + 0.6};

// ======================= MUSIC & SFX =======================
// house score (assets/music, original): one continuous bed; cues cross-fade ~5 s under the voice (equal power)
export const MUSIC: Music[] = [
  {src: 'music/music_c1_hook.mp3', from: 0, to: p2.s + 3.0, lufs: -9.5, xin: 1.2, xout: 4.5},
  {src: 'music/music_c5_resolution.mp3', from: p2.s - 1.5, to: END, lufs: -9.5, xin: 4.5, xout: 3.0},
];
const whooshes: Sfx[] = CAMERA.filter((k) => (k.dur ?? 2) > 1.5 && k.t > 1).map((k, i) => ({f: `whoosh_${(i % 3) + 1}`, t: k.t - 0.15, v: 0.22}));
export const SFX: Sfx[] = [
  {f: 'wind_bed', t: 0, v: 0.35}, {f: 'riser', t: Math.max(0, p0.hands - 2.2), v: 0.3}, {f: 'swell', t: p0.hands - 0.2, v: 0.4},
  {f: 'line_draw', t: p0.drew - 0.1, v: 0.3},
  {f: 'stamp', t: p1.annexed + 0.1, v: 0.32},
  {f: 'crowd_bed', t: p2.chain - 0.3, v: 0.26}, {f: 'line_draw', t: CHAIN.from, v: 0.3},
  {f: 'drone_hit', t: p3.coup, v: 0.3},
  {f: 'bell_small', t: p4.flags - 0.1, v: 0.42},
  ...whooshes,
  ...FLAGS.map((f) => ({f: 'flag_drop', t: f.t + 0.42, v: 0.38})),
  ...CARDS.filter((c) => c.kind === 'date').map((c) => ({f: 'paper', t: c.from, v: 0.32})),
  ...ICONS.map((ic) => ({f: 'wood_thunk', t: ic.from + 0.35, v: 0.36})),
  ...BANNERS.map((b) => ({f: 'cloth_flap', t: b.from + 0.2, v: 0.3})),
];
