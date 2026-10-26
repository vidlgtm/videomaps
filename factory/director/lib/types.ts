// Order formats and the asset manifest (written by the processing station / the order).
export type Beat = {cue: string; until?: string; [k: string]: any};
export type Storyboard = {paragraphs: {id: string; beats: Beat[]}[]};
export type Chapter = {n?: string | null; title: string; paragraphs: string[]; music: string; card?: boolean};
export type Order = {
  title: string; slug: string; countries: string[]; flags?: Record<string, string>; flag_aspect?: Record<string, number>;
  tints?: Record<string, string>; places?: Record<string, any>; area?: any;
  hook: {paragraphs: string[]; music: string}; chapters: Chapter[];
  opening?: {clip?: string | null; lines: {text: string; cue?: string; kind: 'kicker' | 'year' | 'place'}[]; text_out?: string; map_in?: string; bloom?: number};
  names?: {sets: Record<string, Record<string, string>>; eras: {from: string; set: string | null; extra?: Record<string, string>; neighbours?: boolean}[];
    neighbours?: Record<string, string>};
  capitals?: Record<string, any>; datasets?: Record<string, any>;
  end?: {text: string; sub?: string};
};
export type ClipAsset = {src: string; kind: 'doll' | 'cauc' | 'manim'; segments: Record<string, [number, number, number?]>; rate?: number;
  /** this clip has a 3D label track (file name in the order's data/), drawn over it by the engine */ labels?: string;
  dx_with_labels?: number; sfx?: {f: string; at: number; v?: number}[]; opening_sfx?: {f: string; at: number; v?: number}[]};
export type Assets = {
  archive?: Record<string, {file: string; aspect?: number; depth?: boolean; focus?: [number, number]}>;
  cutouts?: Record<string, {file: string; aspect?: number}>;
  docs?: Record<string, {file?: string; aspect?: number; clip?: string; length?: number | null}>;
  icons?: Record<string, {az?: number; size?: number; bb?: number[]}>;
  clips?: Record<string, ClipAsset>;
  sig?: Record<string, string>;
  music?: Record<string, {file: string; lufs: number}>;
  credits?: {id?: string; files?: string[]; what: string; author?: string; license: string; page?: string}[];
  credits_fixed?: string[];
};
export type Constitution = any;
