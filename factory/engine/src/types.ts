// Engine data types (shared by every project). A project's src/script.ts and src/v2.ts re-export these and fill the
// arrays; every time value is in seconds of the film and is normally pinned to a narration word with cue().
// Map coordinates are [lon, lat] (degrees); screen coordinates are 1920x1080 px.

// ---------- script.ts (map stage, cards, clips, audio) ----------
/** camera key: target (lon/lat or canvas x/y), w = visible screen width in KILOMETRES (smaller = closer; zoom = 1920 / (w / 1.16622 km per canvas px)), tilt deg, rotK = local-north rotation share */
export type CamKey = {t: number; lon?: number; lat?: number; x?: number; y?: number; w: number; tilt?: number; rotK?: number; dur?: number};
/** region fill: id = 'rep:EST' | 'ctx:FIN' | 'shape:<id>' | 'rr:<id>' | 'brk:<id>' */
export type Fill = {id: string; color: string; op?: number; from: number; to?: number; fi?: number; fo?: number; pulse?: boolean; hatch?: boolean};
/** border stroke: id as Fill, or 'borders' (all ISO15 republics), 'frontier'; draw = seconds of the light-trace draw-on */
export type Stroke = {id: string; color: string; width: number; from: number; to?: number; draw?: number; dash?: boolean; glow?: boolean; op?: number};
/** map label (Cinzel, or Cormorant italic with italic:true) at a path label anchor ('rep:EST', 'river:Volga') or [lon, lat] */
export type Label = {text: string; at: string | [number, number]; size: number; from: number; to?: number; color?: string; italic?: boolean; spacing?: number; sub?: string};
/** city marker (city name must exist in data/geo.json cities) */
export type Marker = {city: string; label?: string; sub?: string; from: number; to?: number; color?: string; pulse?: boolean; side?: 'r' | 'l' | 't' | 'b'; dot?: boolean};
/** flag drop: iso key -> FLAG_CODE[iso] (flag-icons 4x3 code); anchor = 'rep:'+iso label or at [lon, lat] */
export type Flag = {iso: string; t: number; to?: number; date?: string; at?: [number, number]; atUntil?: number; hide?: [number, number][]};
export type Line = {pts: [number, number][]; from: number; dur: number; to?: number; color: string; width: number; dash?: boolean};
export type Ring = {at: string; km: number[]; from: number; to?: number};
export type Card = {kind: 'date' | 'chapter' | 'quote' | 'big' | 'title' | 'strike' | 'end' | 'callout'; text: string; sub?: string; from: number; to: number;
  num?: string; at?: [number, number]; pos?: 'tl' | 'tr'};
export type Portrait = {img: string; name: string; sub?: string; caption?: string; captionFrom?: number; side: 'left' | 'right'; from: number; to: number};
/** stepped clip playback: from film time `at`, play source seconds s0..s1 (then hold the last frame) */
export type Step = {at: number; s0: number; s1: number; rate?: number};
/** 'manim' / 'doll' = transparent overlay video (webm alpha); 'cauc' = full-frame 3D clip (labels from data/caucasus_labels.json) */
export type Clip = {src: string; from: number; to: number; steps: Step[]; kind: 'manim' | 'doll' | 'cauc'; dx?: number};
export type Sfx = {f: string; t: number; v?: number};
export type Music = {src: string; from: number; to: number; lufs: number; xin?: number; xout?: number};
export type GlobeKey = {t: number; lon: number; lat: number; dist: number};
export type GlobeSpec = {from: number; to: number; tex: string; overlay?: string | null; overlayFrom?: number; keys: GlobeKey[]; spin?: number};

// ---------- v2.ts (billboards, documents, cut-outs, titles, opening, creative layers) ----------
export type Banner = {at: [number, number]; img: string; title: string; sub?: string; from: number; to: number; size?: number; lean?: number};
export type Icon = {name: string; az: number; at: [number, number]; from: number; to: number; size?: number};
export type Dot = {n: string; lon: number; lat: number; layer: 0 | 1 | 2 | 3};
export type DotShow = {from: number; to: number; layers: number[]; stagger?: number};
export type Doc = {img: string; from: number; to: number; side: 'l' | 'r'; cap?: string; w?: number; sigs?: {img: string; name: string}[]};
export type Cutout = {img: string; name: string; sub?: string; from: number; to: number; side: 'l' | 'r'};
export type Numeral = {text: string; from: number; to: number; y?: number; size?: number; sub?: string};
export type Arrow = {a: [number, number]; b: [number, number]; t: number; dur: number; to: number; color: string; bend?: number};
export type TitleLine = {text: string; from: number; hi?: string; hiAt?: number};
export type Tag = {num?: string; text: string; from: number; to: number; slot?: number};
export type Chain = {pts: [number, number][]; from: number; dur: number; to: number};
export type OpeningLine = {text: string; from: number; step?: number; kind: 'kicker' | 'year' | 'place'};
export type OpeningSpec = {clip: string | null; mapIn: number; end: number; textOut: number; rule?: number; bloom?: number; lines: OpeningLine[]};

/** a time far outside the film: use it to switch a feature off (e.g. STAR = {from: OFF}) */
export const OFF = -1000;
