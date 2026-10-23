// PROJECT USSR60 — five paragraphs, five scenes. Every event is synchronized through P and the forced word timeline.
import {TOTAL} from './lib/cues';
import {OFF} from './types';
import type {CamKey, Fill, Stroke, Label, Marker, Flag, Line, Ring, Card, Portrait, Clip, Sfx, Music, GlobeSpec} from './types';
import {P, CHAIN, ICONS, BANNERS, CREDITS} from './v2';
export type {CamKey, Fill, Stroke, Label, Marker, Flag, Line, Ring, Card, Portrait, Step, Clip, Sfx, Music} from './types';

export const END = TOTAL;
const {p0, p1, p2, p3, p4} = P;
export const T = P;

// ---------- house palette and republic identifiers ----------
export const COL: Record<string, string> = {
  RUS: '#A23E44', UKR: '#D2A93F', BLR: '#7A9B4E', KAZ: '#3F8F7F', UZB: '#5577B0', TKM: '#9BB25A', KGZ: '#C0663D',
  TJK: '#8D6CB0', GEO: '#86B39A', ARM: '#D9893A', AZE: '#9F78C9', MDA: '#B79257', EST: '#5C86C2', LVA: '#9B4F6E',
  LTU: '#C98B4E', UNION: '#8E3741', GOLD: '#E2BF6A', INK: '#0E1A24', TXT: '#F4EFE6', RED: '#D2434E', TEAL: '#4FA39E',
};
export const ISO15 = ['RUS', 'UKR', 'BLR', 'KAZ', 'UZB', 'TKM', 'KGZ', 'TJK', 'GEO', 'ARM', 'AZE', 'MDA', 'EST', 'LVA', 'LTU'];
export const FLAG_CODE: Record<string, string> = {
  RUS: 'ru', UKR: 'ua', BLR: 'by', KAZ: 'kz', UZB: 'uz', TKM: 'tm', KGZ: 'kg', TJK: 'tj', GEO: 'ge', ARM: 'am', AZE: 'az',
  MDA: 'md', EST: 'ee', LVA: 'lv', LTU: 'lt', SU: 'su',
};
export const FLAG_ASPECT: Record<string, number> = {su: 2};
export const NAME: Record<string, string> = {
  RUS: 'Russia', UKR: 'Ukraine', BLR: 'Belarus', KAZ: 'Kazakhstan', UZB: 'Uzbekistan', TKM: 'Turkmenistan', KGZ: 'Kyrgyzstan',
  TJK: 'Tajikistan', GEO: 'Georgia', ARM: 'Armenia', AZE: 'Azerbaijan', MDA: 'Moldova', EST: 'Estonia', LVA: 'Latvia', LTU: 'Lithuania',
};

// ---------- night globe -> Kremlin -> Soviet map ----------
export const GLOBE: GlobeSpec = {
  from: 0, to: p0.nextDay + 1.0, tex: 'globe_night_4k.jpg', overlay: null, spin: 1.6,
  keys: [
    {t: 0, lon: 10, lat: 28, dist: 4.9},
    {t: p0.date, lon: 35, lat: 48, dist: 3.4},
    {t: p0.fell, lon: 37.62, lat: 55.75, dist: 2.0},
  ],
};

// ---------- camera path (w = visible width in km; all moves eased) ----------
const V = {
  WIDE: {lon: 52, lat: 55, w: 9300, tilt: 12},
  MOSCOW: {lon: 37.6, lat: 55.75, w: 5000, tilt: 18},
  FOUNDERS: {lon: 39, lat: 50, w: 6200, tilt: 16},
  TATAR: {lon: 49.12, lat: 55.79, w: 1500, tilt: 30},
  ESTONIA: {lon: 25.0, lat: 58.8, w: 1250, tilt: 30},
  BALTIC: {lon: 26, lat: 57, w: 2450, tilt: 26},
  KARELIA: {lon: 31.5, lat: 61.5, w: 1900, tilt: 28},
  OUTER: {lon: 53, lat: 53, w: 9300, tilt: 12},
};
const cam = (t: number, v: any, dur = 2.2): CamKey => ({t, dur, ...v});
export const CAMERA: CamKey[] = [
  cam(0, V.WIDE, 0.01),
  cam(p0.fell - 0.3, V.MOSCOW, 3.2),
  cam(p0.fifteen - 0.3, V.WIDE, 2.8),
  cam(p1.s - 0.2, V.FOUNDERS, 2.6),
  cam(p2.s - 0.2, V.TATAR, 2.5),
  cam(p2.estonia - 0.25, V.ESTONIA, 2.0),
  cam(p3.s - 0.2, V.BALTIC, 2.4),
  cam(p3.karelo - 0.2, V.KARELIA, 2.3),
  cam(p4.s - 0.2, V.OUTER, 3.0),
  cam(p4.founders - 0.25, {...V.OUTER, w: 8800}, 3.2),
];

// ---------- national fills and historical silhouettes ----------
const repFill = (iso: string, from: number, to: number, op = 0.58, fi = 0.5): Fill =>
  ({id: `rep:${iso}`, color: COL[iso], op, from, to, fi, fo: 0.7});
const repStroke = (iso: string, from: number, to: number, width = 2.2): Stroke =>
  ({id: `rep:${iso}`, color: '#F2D58B', width, from, to, draw: 0.9, glow: true});
export const FILLS: Fill[] = [
  // Opening: union red, then the patchwork of fifteen modern states (same staging as accepted v5).
  {id: 'shape:ussr_1991', color: COL.UNION, op: 0.64, from: p0.nextDay - 0.15, to: p0.gone + 0.65, fi: 0.8, fo: 0.7},
  ...ISO15.map((iso, k) => repFill(iso, p0.fifteen + 0.05 + k * 0.10, p0.e + 1.0, 0.62, 0.45)),
  // 1922: four founding republics and the Transcaucasian federation.
  {id: 'shape:rsfsr_1922', color: COL.RUS, op: 0.58, from: p1.four, to: p1.e + 0.5, fi: 0.7},
  {id: 'shape:ukr_1936', color: COL.UKR, op: 0.58, from: p1.ukraine, to: p1.e + 0.5, fi: 0.7},
  {id: 'shape:blr_1936', color: COL.BLR, op: 0.58, from: p1.belarus, to: p1.e + 0.5, fi: 0.7},
  {id: 'shape:tsfsr', color: COL.GEO, op: 0.6, from: p1.transcaucasia, to: p1.e + 0.5, fi: 0.7},
  // 1936: the internal Russian boundary versus an outer union republic.
  {id: 'shape:ussr_1938', color: COL.UNION, op: 0.34, from: p2.s, to: p2.e + 0.6, fi: 0.8},
  {id: 'shape:rsfsr_1936', color: COL.RUS, op: 0.45, from: p2.s, to: p3.s + 0.2, fi: 0.7},
  {id: 'rr:Tatarstan', color: COL.GOLD, op: 0.88, from: p2.tatar, to: p2.noFrontier + 0.5, fi: 0.35, pulse: true},
  {id: 'rep:EST', color: COL.EST, op: 0.82, from: p2.estonia, to: p2.e + 0.5, fi: 0.5},
  // 1940–1956: the Baltic additions and the short-lived Karelo-Finnish republic.
  ...(['EST', 'LVA', 'LTU'] as const).map((iso, k) => ({...repFill(iso, p3.annexed + 0.1 + k * 0.22, p3.e + 0.5, 0.58, 0.5), color: COL.UNION})),
  {id: 'shape:kfssr', color: '#6C8EBF', op: 0.76, from: p3.karelo, to: p3.demotion + 0.35, fi: 0.7, fo: 1.2},
  {id: 'shape:rsfsr_1940', color: COL.RUS, op: 0.48, from: p3.demotion, to: p3.e + 0.5, fi: 0.7},
  // 1991: all fifteen national tints return and remain on screen.
  ...ISO15.map((iso) => repFill(iso, p4.fifteen - 0.2, END + 1, 0.62, 0.7)),
];
export const STROKES: Stroke[] = [
  {id: 'shape:ussr_1991', color: '#E6D3A6', width: 2.2, from: p0.nextDay - 0.1, to: p0.gone + 0.6, draw: 1.2, glow: true},
  ...ISO15.map((iso, k) => repStroke(iso, p0.fifteen + 0.02 + k * 0.08, END + 1, 2.0)),
  {id: 'shape:rsfsr_1922', color: '#FFE3A0', width: 2.1, from: p1.four, to: p1.e + 0.5, draw: 1.1, glow: true},
  {id: 'shape:tsfsr', color: '#FFE3A0', width: 2.1, from: p1.transcaucasia, to: p1.e + 0.5, draw: 1.0, glow: true},
  {id: 'rr:Tatarstan', color: '#FFE3A0', width: 2.8, from: p2.tatar, to: p2.noFrontier + 0.55, draw: 1.0, glow: true},
  {id: 'rep:EST', color: '#FFE3A0', width: 2.6, from: p2.estonia, to: p2.e + 0.5, draw: 1.0, glow: true},
  {id: 'shape:kfssr', color: '#F4EFE6', width: 2.4, from: p3.karelo, to: p3.demotion + 0.4, draw: 1.2, glow: true},
];

// ---------- original light traces: the flag's thread and the founding-republic seams ----------
export const LINES: Line[] = [
  {pts: [[37.62, 55.75], [24.75, 59.44], [27.56, 53.9], [30.52, 50.45], [44.79, 41.72], [49.87, 40.41], [58.33, 37.96], [69.28, 41.31], [76.89, 43.24]],
    from: p0.fifteen - 0.1, dur: 2.8, to: p0.why + 0.5, color: '#FFE3A0', width: 3.2},
  {pts: CHAIN.pts, from: p1.union - 0.1, dur: CHAIN.dur, to: p1.e + 0.5, color: '#E2BF6A', width: 2.8},
];
export const RINGS: Ring[] = [];

// ---------- names and event markers ----------
export const LABELS: Label[] = [
  {text: 'U.S.S.R.', at: 'shape:ussr_1991', size: 76, from: p0.nextDay, to: p0.fifteen + 0.3, spacing: 0.28},
  {text: 'RUSSIAN SFSR', at: 'shape:rsfsr_1922', size: 28, from: p1.four, to: p1.e + 0.45},
  {text: 'UKRAINIAN SSR', at: 'rep:UKR', size: 25, from: p1.ukraine, to: p1.e + 0.45},
  {text: 'BYELORUSSIAN SSR', at: 'rep:BLR', size: 22, from: p1.belarus, to: p1.e + 0.45},
  {text: 'TRANSCAUCASIAN SFSR', at: 'shape:tsfsr', size: 24, from: p1.transcaucasia, to: p1.e + 0.45},
  {text: 'TATARSTAN', at: 'rr:Tatarstan', size: 30, from: p2.tatar + 0.15, to: p2.noFrontier + 0.5},
  {text: 'ESTONIAN SSR', at: 'rep:EST', size: 23, from: p2.estonia + 0.2, to: p2.e + 0.5},
  {text: 'KARELO-FINNISH SSR', at: 'shape:kfssr', size: 25, from: p3.karelo + 0.2, to: p3.demotion + 0.35},
];
export const MARKERS: Marker[] = [
  {city: 'Moscow', label: 'Kremlin', sub: '25 DECEMBER 1991', from: p0.fell - 0.2, to: p0.nextDay + 0.3, side: 'r'},
  {city: 'Moscow', label: 'Treaty', sub: '30 DECEMBER 1922', from: p1.treaty, to: p1.noExit + 0.25, side: 'r'},
  {city: 'Kazan', label: 'Tatarstan', sub: 'inside Russia', from: p2.tatar, to: p2.noFrontier + 0.5, side: 'r'},
  {city: 'Tallinn', label: 'Estonia', sub: 'outer border', from: p2.estonia, to: p2.e + 0.45, side: 'r'},
  {city: 'Petrozavodsk', label: 'Karelia', sub: '1956', from: p3.karelo, to: p3.demotion + 0.5, side: 'r'},
];

// ---------- flags: all fifteen drop onto their countries in the hook and return in the finale ----------
const openingFlags: Flag[] = ISO15.map((iso, k) => ({iso, t: p0.fifteen + k * 0.12, to: p0.e + 0.45}));
const finaleFlags: Flag[] = ISO15.map((iso, k) => ({iso, t: p4.fifteen + k * 0.08, to: CREDITS.from - 0.2}));
export const FLAGS: Flag[] = [...openingFlags, ...finaleFlags];
export const FLAG_HIDE: [number, number][] = [[p1.s - 0.15, p4.s - 0.2]];

// ---------- date cards and overlays ----------
export const CARDS: Card[] = [
  {kind: 'date', text: '25 DECEMBER 1991', sub: 'THE LAST SOVIET FLAG', from: p0.date, to: p0.fifteen + 0.35, pos: 'tr'},
  {kind: 'date', text: '30 DECEMBER 1922', sub: 'FOUR REPUBLICS FORM THE UNION', from: p1.treaty, to: p1.noExit + 0.25, pos: 'tr'},
  {kind: 'date', text: '1936', sub: 'THREE TESTS FOR UNION STATUS', from: p2.tests, to: p2.e + 0.4, pos: 'tr'},
  {kind: 'date', text: '1940', sub: 'THE MAP EXPANDS', from: p3.y1940, to: p3.demotion - 0.1, pos: 'tr'},
  {kind: 'date', text: '1956', sub: 'SIXTEEN RETURNS TO FIFTEEN', from: p3.demotion, to: p3.e + 0.25, pos: 'tr'},
];
export const PORTRAITS: Portrait[] = [];
export const CLIPS: Clip[] = [];
export const DOLL_LABELS: {text: string; k: number; from: number; to: number}[] = [];
export const CHART = {from: OFF, to: OFF + 1};
export const FLAGPOLE = {
  from: p0.redFlag - 0.35, lower: p0.fell - 0.15, lowered: p0.fell + 0.45, raise: p0.nextDay, to: p0.fifteen + 0.4,
  from2: OFF, lower2: OFF + 0.2, raise2: OFF + 0.4, to2: OFF + 0.6,
};

// ---------- original music and sparse, cue-pinned sound design ----------
export const MUSIC: Music[] = [
  {src: 'music/music_c1_hook.mp3', from: 0, to: p1.s + 2.5, lufs: -9.5, xin: 1.2, xout: 4.5},
  {src: 'music/music_c2_origins.mp3', from: p1.s - 1.3, to: p3.s + 1.5, lufs: -11.3, xin: 4.5, xout: 4.5},
  {src: 'music/music_c4_collapse.mp3', from: p3.s - 1.3, to: p4.founders + 1.0, lufs: -11.8, xin: 4.5, xout: 4.5},
  {src: 'music/music_c5_resolution.mp3', from: p4.founders - 1.3, to: END, lufs: -9.5, xin: 4.5, xout: 3.0},
];
const whooshes: Sfx[] = CAMERA.filter((k) => (k.dur ?? 2) > 1.5 && k.t > 1).map((k, i) => ({f: `whoosh_${(i % 3) + 1}`, t: k.t - 0.15, v: 0.22}));
export const SFX: Sfx[] = [
  {f: 'wind_bed', t: 0, v: 0.28},
  {f: 'riser', t: Math.max(0, p0.fell - 1.2), v: 0.28},
  {f: 'flag_drop', t: p0.fell + 0.42, v: 0.35},
  {f: 'swell', t: p0.fifteen - 0.15, v: 0.38},
  {f: 'line_draw', t: p0.fifteen - 0.1, v: 0.3},
  {f: 'paper', t: p1.treaty, v: 0.34},
  {f: 'line_draw', t: p1.union, v: 0.32},
  {f: 'stamp', t: p3.annexed + 0.12, v: 0.32},
  {f: 'pop', t: p3.demotion + 0.15, v: 0.28},
  {f: 'bell_small', t: p4.fifteen - 0.1, v: 0.38},
  ...whooshes,
  ...FLAGS.map((f) => ({f: 'flag_drop', t: f.t + 0.42, v: 0.34})),
  ...CARDS.map((c) => ({f: 'paper', t: c.from, v: 0.28})),
  ...ICONS.map((ic) => ({f: 'wood_thunk', t: ic.from + 0.35, v: 0.35})),
  ...BANNERS.map((b) => ({f: 'cloth_flap', t: b.from + 0.2, v: 0.3})),
];
