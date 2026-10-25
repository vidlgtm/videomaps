// FACTORY ENGINE - generic loader for billboards, documents, cut-outs, titles, opening and creative layers (data/film.json).
import film from './data/film.json';
import {OFF} from './types';
import type {Banner, Icon, Dot, DotShow, Doc, Cutout, Numeral, Arrow, TitleLine, Tag, Chain, OpeningSpec} from './types';
export type {Banner, Icon, Dot, DotShow, Doc, Cutout, Numeral, Arrow, TitleLine, Tag, Chain} from './types';

const F: any = film;
export const P = {};
export const OPENING: OpeningSpec = F.opening;
export const BANNERS: Banner[] = F.banners;
export const ICONS: Icon[] = F.icons;
export const DOTS: Dot[] = F.dots;
export const DOT_COL: string[] = F.dot_col ?? ['#FFD36B', '#FFFFFF', '#8FD3FF', '#B9F28C'];
export const DOT_SHOWS: DotShow[] = F.dot_shows;
export const DOCS: Doc[] = F.docs;
export const CUTOUTS: Cutout[] = F.cutouts;
export const NUMERALS: Numeral[] = F.numerals;
export const ARROWS: Arrow[] = F.arrows;
export const TAGS: Tag[] = F.tags;
export const CHAIN: Chain = F.chain ?? {pts: [[0, 0], [0.1, 0.1]], from: OFF, dur: 1, to: OFF + 1};
export const TITLE: {from: number; to: number; lines: TitleLine[]} = F.title ?? {from: OFF, to: OFF + 1, lines: []};
export const CREDITS: {from: number; lines: string[]} = F.credits;
export const STAR: {from: number} = F.star ?? {from: OFF};
export const STAR_TARGETS: [string, number, number][] = F.star_targets ?? [];
export const DEPTH_IDS: string[] = F.depth_ids ?? [];
export const LIGHTS = F.lights ?? {from: OFF, off0: OFF, off1: OFF, lift0: OFF, lift1: OFF};
export const CITY_LIGHTS: [number, number, number][] = F.city_lights ?? [];
