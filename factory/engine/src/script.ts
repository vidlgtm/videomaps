// FACTORY ENGINE - generic score loader. Nothing here is written by hand for a film: every array comes from
// data/film.json, which the automatic director (factory/director) builds from the order + the voice timeline.
import film from './data/film.json';
import {TOTAL} from './lib/cues';
import {CITIES} from './lib/paths';
import {px} from './lib/proj';
import {OFF} from './types';
import type {CamKey, Fill, Stroke, Label, Marker, Flag, Line, Ring, Card, Portrait, Clip, Sfx, Music, GlobeSpec} from './types';
export type {CamKey, Fill, Stroke, Label, Marker, Flag, Line, Ring, Card, Portrait, Step, Clip, Sfx, Music} from './types';

const F: any = film;
// places named in the order that are not in geo.json cities (lon/lat from the order's gazetteer) -> usable by markers
Object.entries((F.extra_cities ?? {}) as Record<string, [number, number]>).forEach(([n, ll]) => {
  if (!CITIES[n]) (CITIES as any)[n] = {lonlat: ll, px: px(ll[0], ll[1])};
});

export const END = TOTAL;
export const COL: Record<string, string> = F.col;
export const ISO15: string[] = F.iso;
export const FLAG_CODE: Record<string, string> = F.flag_code;
export const FLAG_ASPECT: Record<string, number> = F.flag_aspect ?? {};
export const NAME: Record<string, string> = F.name ?? {};
export const T = {};
export const GLOBE: GlobeSpec = F.globe ?? {from: OFF, to: OFF + 1, tex: 'globe_night_4k.jpg', overlay: null, keys: [{t: OFF, lon: 0, lat: 0, dist: 3}]};
export const CAMERA: CamKey[] = F.camera;
export const FILLS: Fill[] = F.fills;
export const STROKES: Stroke[] = F.strokes;
export const LINES: Line[] = F.lines;
export const RINGS: Ring[] = F.rings;
export const LABELS: Label[] = F.labels;
export const MARKERS: Marker[] = F.markers;
export const FLAGS: Flag[] = F.flags;
export const FLAG_HIDE: [number, number][] = F.flag_hide;
export const CARDS: Card[] = F.cards;
export const PORTRAITS: Portrait[] = [];
export const CLIPS: Clip[] = F.clips;
export const DOLL_LABELS: {text: string; k: number; from: number; to: number}[] = F.doll_labels;
export const CHART = {from: OFF, to: OFF + 1};
export const FLAGPOLE = {from: OFF, lower: OFF + 0.2, lowered: OFF + 0.4, raise: OFF + 0.6, to: OFF + 0.8,
  from2: OFF, lower2: OFF + 0.2, raise2: OFF + 0.4, to2: OFF + 0.6};
export const MUSIC: Music[] = F.music;
export const SFX: Sfx[] = F.sfx;
