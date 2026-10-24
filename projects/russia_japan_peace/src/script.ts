import {TOTAL} from './lib/cues';
import {OFF} from './types';
import type {CamKey, Fill, Stroke, Label, Marker, Flag, Line, Ring, Card, Portrait, Clip, Sfx, Music, GlobeSpec} from './types';
import {P, ICONS, BANNERS} from './v2';
export type {CamKey, Fill, Stroke, Label, Marker, Flag, Line, Ring, Card, Portrait, Step, Clip, Sfx, Music} from './types';

export const END = TOTAL;
export const COL: Record<string, string> = {RUS: '#A23E44', JPN: '#C98B4E', UNION: '#8E3741', GOLD: '#E2BF6A', INK: '#0E1A24', TXT: '#F4EFE6', RED: '#D2434E', TEAL: '#4FA39E'};
export const ISO15 = ['RUS'];
export const FLAG_CODE: Record<string, string> = {RUS: 'ru', JPN: 'jp', SU: 'su'};
export const FLAG_ASPECT: Record<string, number> = {su: 2};
export const NAME: Record<string, string> = {RUS: 'Russia', JPN: 'Japan'};
export const T = P;

export const GLOBE: GlobeSpec = {from: OFF, to: OFF + 1, tex: 'globe_night_4k.jpg', overlay: null, keys: [{t: OFF, lon: 0, lat: 0, dist: 5}]};
const V = {
  PACIFIC: {lon: 145.6, lat: 44.6, w: 1450, tilt: 24}, HOKKAIDO: {lon: 143.2, lat: 43.4, w: 900, tilt: 28},
  SOUTHERN: {lon: 145.8, lat: 44.3, w: 680, tilt: 30}, CHAIN: {lon: 147.2, lat: 45.5, w: 1200, tilt: 24},
  URUP: {lon: 150.3, lat: 46.2, w: 780, tilt: 29}, SAKHALIN: {lon: 142.8, lat: 48.0, w: 1350, tilt: 24},
  YALTA: {lon: 34.3, lat: 44.5, w: 1100, tilt: 25}, MOSCOW: {lon: 37.6, lat: 55.7, w: 1200, tilt: 24},
  SANFRAN: {lon: 146.0, lat: 44.6, w: 760, tilt: 30}, OKHOTSK: {lon: 148.0, lat: 46.0, w: 1650, tilt: 22},
  TOKYO: {lon: 140.5, lat: 39.5, w: 2000, tilt: 22}, OUT: {lon: 146.0, lat: 45.3, w: 2100, tilt: 20},
};
const cam = (t: number, v: any, dur = 2.3): CamKey => ({t, dur, ...v});
export const CAMERA: CamKey[] = [
  cam(0, V.PACIFIC, 0.01), cam(P.p0.islands + 0.35, {...V.PACIFIC, w: 1320}, 4.0),
  cam(P.p1.chain - 0.25, V.CHAIN, 2.3), cam(P.p1.hokkaido - 0.2, V.HOKKAIDO, 2.0), cam(P.p1.habomai - 0.15, V.SOUTHERN, 2.1), cam(P.p1.administers - 0.15, V.CHAIN, 2.5),
  cam(P.p2.s - 0.2, V.SOUTHERN, 2.2), cam(P.p2.boundary - 0.2, V.URUP, 2.1), cam(P.p2.documents - 0.2, V.CHAIN, 2.2),
  cam(P.p3.y1875 - 0.2, V.SAKHALIN, 2.3), cam(P.p3.kuril - 0.2, V.CHAIN, 2.3), cam(P.p3.southern - 0.25, V.SAKHALIN, 2.5),
  cam(P.p4.yalta - 0.25, V.YALTA, 2.5), cam(P.p4.august - 0.25, V.PACIFIC, 2.7), cam(P.p4.order - 0.2, V.SOUTHERN, 2.0), cam(P.p4.contested - 0.25, V.CHAIN, 2.4),
  cam(P.p5.s + 0.2, V.SOUTHERN, 2.2), cam(P.p5.iturup - 0.2, V.CHAIN, 2.1), cam(P.p5.difficult - 0.2, V.PACIFIC, 2.3),
  cam(P.p6.y1951 - 0.2, V.SANFRAN, 2.1), cam(P.p6.renounced - 0.2, V.SOUTHERN, 2.0), cam(P.p6.unresolved - 0.2, V.CHAIN, 2.4),
  cam(P.p7.okhotsk - 0.2, V.OKHOTSK, 2.4), cam(P.p7.fishing - 0.2, {...V.OKHOTSK, w: 1350}, 2.2), cam(P.p7.geography - 0.2, V.SOUTHERN, 2.6),
  cam(P.p8.y1956 - 0.2, V.MOSCOW, 2.4), cam(P.p8.declaration - 0.2, V.SOUTHERN, 2.4), cam(P.p8.habomai - 0.2, V.HOKKAIDO, 2.0), cam(P.p8.bridge - 0.15, V.CHAIN, 2.3),
  cam(P.p9.conditional - 0.2, V.SOUTHERN, 2.2), cam(P.p9.four - 0.2, V.CHAIN, 2.1), cam(P.p9.whichTreaty - 0.2, V.PACIFIC, 2.4),
  cam(P.p10.y1991 - 0.2, V.MOSCOW, 2.3), cam(P.p10.tokyo - 0.2, V.SOUTHERN, 2.4), cam(P.p10.dilemma - 0.2, V.PACIFIC, 2.5),
  cam(P.p11.declaration - 0.2, V.CHAIN, 2.2), cam(P.p11.august - 0.2, V.SOUTHERN, 2.0), cam(P.p11.crisis - 0.2, V.OUT, 2.7),
  cam(P.p12.noTreaty - 0.2, V.PACIFIC, 2.3), cam(P.p12.foundation - 0.2, V.SOUTHERN, 2.4),
  cam(P.p13.border - 0.2, V.SAKHALIN, 2.2), cam(P.p13.generations - 0.2, V.CHAIN, 2.6),
  cam(P.p14.question - 0.2, V.OUT, 2.5), cam(P.p14.hokkaido - 0.2, V.PACIFIC, 2.6),
];

export const FILLS: Fill[] = [
  {id: 'rep:RUS', color: COL.RUS, op: 0.46, from: P.p0.islands, to: END + 1, fi: 0.8},
  {id: 'ctx:JPN', color: COL.JPN, op: 0.46, from: P.p0.islands, to: END + 1, fi: 0.8},
  {id: 'rep:RUS', color: COL.UNION, op: 0.28, from: P.p4.august, to: P.p10.dissolved + 0.2, fi: 0.7, fo: 0.8},
];
export const STROKES: Stroke[] = [
  {id: 'borders', color: '#F4D58A', width: 2.4, from: P.p0.islands, to: END + 1, draw: 2.0, glow: true},
  {id: 'frontier', color: '#FFF0B5', width: 2.0, from: P.p1.chain, to: END + 1, draw: 1.5, glow: false},
];
export const LINES: Line[] = []; export const RINGS: Ring[] = [];
export const LABELS: Label[] = [
  {text: 'SEA OF OKHOTSK', at: [147.7, 47.4], size: 24, from: P.p1.chain + 0.4, to: END + 1, italic: true},
];
export const MARKERS: Marker[] = [];
export const FLAGS: Flag[] = [
  {iso: 'JPN', t: P.p0.surrender + 0.15, to: P.p4.august - 0.15, at: [143.1, 43.4]},
  // Exact mainland anchors: Soviet/Russian flag is on southern Sakhalin; Japanese flag is on eastern Hokkaido.
  // Neither national flag is placed over the Sea of Okhotsk or a disputed island.
  {iso: 'SU', t: P.p0.occupied + 0.2, to: P.p10.dissolved + 0.1, at: [142.55, 47.85]},
  {iso: 'JPN', t: P.p1.hokkaido + 0.1, to: P.p14.controls - 0.4, at: [143.1, 43.4]},
  {iso: 'RUS', t: P.p10.dissolved + 0.12, to: P.p14.controls - 0.4, at: [142.55, 47.85]},
];
export const FLAG_HIDE: [number, number][] = [[P.p14.controls - 0.25, END + 1]];
export const CARDS: Card[] = [
  {kind: 'date', text: '1855', sub: 'TREATY OF SHIMODA', from: P.p2.y1855 - 0.1, to: P.p2.boundary - 0.25, pos: 'tr'},
  {kind: 'date', text: '1875', sub: 'SAKHALIN FOR THE KURILS', from: P.p3.y1875 - 0.1, to: P.p3.y1904 - 0.25, pos: 'tr'},
  {kind: 'date', text: 'AUGUST–SEPTEMBER 1945', sub: 'THE MAP CHANGES AGAIN', from: P.p4.august - 0.1, to: P.p4.order - 0.25, pos: 'tl'},
  {kind: 'date', text: '1951', sub: 'SAN FRANCISCO PEACE TREATY', from: P.p6.y1951 - 0.1, to: P.p6.soviet - 0.25, pos: 'tr'},
  {kind: 'date', text: '19 OCTOBER 1956', sub: 'STATE OF WAR ENDS · TREATY TALKS CONTINUE', from: P.p8.y1956 - 0.1, to: P.p8.article - 0.25, pos: 'tl'},
  {kind: 'date', text: '1993', sub: 'TOKYO DECLARATION', from: P.p10.y1993 - 0.1, to: P.p10.names - 0.2, pos: 'tr'},
  {kind: 'chapter', text: 'THE UNFINISHED PRESENT', sub: 'THE DISPUTE MEETS A NEW CRISIS', from: P.p11.february - 0.1, to: P.p11.putin - 0.25, pos: 'tl'},
];
export const PORTRAITS: Portrait[] = [];
export const CLIPS: Clip[] = [
  {kind: 'cauc', src: 'clips/shimoda_treaty.mp4', from: P.p2.shimoda - 0.25, to: P.p2.japanese - 0.15, steps: [{at: P.p2.shimoda - 0.25, s0: 0, s1: 5.5, rate: 1.0}]},
  {kind: 'cauc', src: 'clips/san_francisco.mp4', from: P.p6.sanfran - 0.2, to: P.p6.soviet - 0.12, steps: [{at: P.p6.sanfran - 0.2, s0: 0, s1: 5.5, rate: 1.0}]},
  {kind: 'cauc', src: 'clips/joint_declaration_1956.mp4', from: P.p8.article - 0.2, to: P.p8.bridge - 0.12, steps: [{at: P.p8.article - 0.2, s0: 0, s1: 5.5, rate: 1.0}]},
  {kind: 'cauc', src: 'clips/treaty_scale.mp4', from: P.p9.conditional - 0.2, to: P.p9.concession + 1.2, steps: [{at: P.p9.conditional - 0.2, s0: 0, s1: 9.0, rate: 1.0}]},
];
export const DOLL_LABELS: {text: string; k: number; from: number; to: number}[] = [];
export const CHART = {from: OFF, to: OFF + 1};
export const FLAGPOLE = {from: OFF, lower: OFF + 0.2, lowered: OFF + 0.4, raise: OFF + 0.6, to: OFF + 0.8, from2: OFF, lower2: OFF + 0.2, raise2: OFF + 0.4, to2: OFF + 0.6};

export const MUSIC: Music[] = [
  {src: 'music/music_c1_hook.mp3', from: 0, to: P.p2.s + 2.0, lufs: -9.5, xin: 1.2, xout: 5.0},
  {src: 'music/music_c2_origins.mp3', from: P.p2.s - 2.0, to: P.p4.s + 2.0, lufs: -11.3, xin: 5.0, xout: 5.0},
  {src: 'music/music_c3_annex.mp3', from: P.p4.s - 2.0, to: P.p8.s + 2.0, lufs: -15.3, xin: 5.0, xout: 5.0},
  {src: 'music/music_c4_collapse.mp3', from: P.p8.s - 2.0, to: P.p11.s + 2.0, lufs: -11.8, xin: 5.0, xout: 5.0},
  {src: 'music/music_c5_resolution.mp3', from: P.p11.s - 2.0, to: END, lufs: -9.5, xin: 5.0, xout: 3.0},
];
const whooshes: Sfx[] = CAMERA.filter((k) => (k.dur ?? 2) > 1.5 && k.t > 1).map((k, i) => ({f: `whoosh_${(i % 3) + 1}`, t: k.t - 0.15, v: 0.22}));
export const SFX: Sfx[] = [
  {f: 'wind_bed', t: 0, v: 0.3}, {f: 'riser', t: Math.max(0, P.p0.treaty - 1.8), v: 0.32}, {f: 'swell', t: P.p0.islands - 0.2, v: 0.4},
  {f: 'paper', t: P.p2.shimoda, v: 0.32}, {f: 'stamp', t: P.p6.sanfran + 0.25, v: 0.38}, {f: 'paper', t: P.p8.article, v: 0.32},
  {f: 'wood_thunk', t: P.p9.four + 0.3, v: 0.34}, {f: 'drone_hit', t: P.p11.putin, v: 0.34}, {f: 'bell_small', t: P.p14.controls - 0.1, v: 0.4},
  ...whooshes, ...FLAGS.map((f) => ({f: 'flag_drop', t: f.t + 0.42, v: 0.36})),
  ...ICONS.map((ic) => ({f: 'wood_thunk', t: ic.from + 0.32, v: 0.34})), ...BANNERS.map((b) => ({f: 'cloth_flap', t: b.from + 0.22, v: 0.28})),
];
