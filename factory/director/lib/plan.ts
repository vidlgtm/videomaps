// THE AUTOMATIC DIRECTOR: the brain's beats (WHAT, pinned to words) -> every element of the film (HOW: exact times,
// camera, positions, sizes, colours, sides, sound). Rules come from factory/rules/constitution.json and our film v5.
import {Cues} from './cues';
import {Gazetteer, Place, PATHS, unionBox, Box, lonlat, px, hasLabel} from './geo';
import {CamKey, CamPath, frameBox, framePoint, overviewKey, keyDistance, keyState, inSafe, unproject, scr} from './cam';
import * as BX from './boxes';
import {arr, clamp, r2, r3, fail, hash} from './util';
import type {Order, Storyboard, Assets, Constitution, Beat} from './types';

type RB = {key: string; pid: string; c: number; i: number; t: number; t1: number; b: Beat};
type Shot = {t: number; place: Place | null; kind: string; key: string; explicit: boolean; box: Box | null; pt: [number, number] | null;
  variant?: number; tiltAdd?: number; wMul?: number; hold?: boolean; shiftW?: [number, number]; box0?: Box | null; pts?: [number, number][]};
const OPTS = new Set(['cue', 'until', 'look', 'like', 'except', 'style', 'at', 'glide', 'sub', 'side', 'pulse', 'alert', 'dot', 'num', 'group',
  'title', 'near', 'name', 'caption', 'signatures', 'size', 'kind', 'layers', 'tempo', 'steps', 'labels', 'shot', 'params', 'hi', 'hi_cue', 'op', 'color',
  'width', 'note', 'dates', 'km', 'text', 'italic', 'order', 'stagger']);
const ACTIONS = ['go', 'fill', 'unfill', 'border', 'flag', 'flags', 'label', 'marker', 'date', 'numeral', 'tag', 'quote', 'strike', 'callout', 'big',
  'banner', 'portrait', 'document', 'icon', 'arrow', 'route', 'rings', 'dots', 'clip', 'titles', 'closing', 'creative', 'accent', 'camera'];
/** keys that are an action on their own but an option when they sit next to another action (flag date plate, marker label) */
const OPT_OF: Record<string, string[]> = {flag: ['date'], marker: ['label']};
export function actionsOf(b: Beat): string[] {
  const acts = Object.keys(b).filter((k) => ACTIONS.includes(k));
  const claimed = new Set(acts.flatMap((a) => OPT_OF[a] ?? []));
  return acts.filter((a) => !claimed.has(a));
}
const ISO2: Record<string, string> = {RUS: 'ru', UKR: 'ua', BLR: 'by', KAZ: 'kz', UZB: 'uz', TKM: 'tm', KGZ: 'kg', TJK: 'tj', GEO: 'ge', ARM: 'am',
  AZE: 'az', MDA: 'md', EST: 'ee', LVA: 'lv', LTU: 'lt', FIN: 'fi', POL: 'pl', ROU: 'ro', TUR: 'tr', IRN: 'ir', CHN: 'cn', MNG: 'mn', JPN: 'jp',
  DEU: 'de', FRA: 'fr', GBR: 'gb', ITA: 'it', ESP: 'es', PRT: 'pt', USA: 'us', SWE: 'se', NOR: 'no', AFG: 'af', PAK: 'pk', IND: 'in', GRC: 'gr',
  BGR: 'bg', HUN: 'hu', CZE: 'cz', SVK: 'sk', AUT: 'at', CHE: 'ch', NLD: 'nl', BEL: 'be', DNK: 'dk', IRQ: 'iq', SYR: 'sy', EGY: 'eg', SAU: 'sa',
  ISR: 'il', KOR: 'kr', PRK: 'kp', SRB: 'rs', HRV: 'hr', ALB: 'al', MKD: 'mk', BIH: 'ba', MNE: 'me', SVN: 'si', CYP: 'cy', LBN: 'lb', JOR: 'jo'};
const OVERLAY = new Set(['focus', 'gain', 'highlight', 'war', 'boycott', 'disputed', 'new']);
const QUILT = ['#B9785A', '#7F9C6B', '#C9A45C', '#6E8FB0', '#A0687E', '#8FB0A0', '#B58C55', '#7C7AA8'];

export class Director {
  o: Order; sb: Storyboard; a: Assets; K: Constitution; cues: Cues; gaz: Gazetteer; patches: Record<string, any>;
  END: number; warn: string[] = []; beats: RB[] = [];
  chOf: number[] = []; chFirst: boolean[] = []; chapters: {title: string; n?: string | null; card: boolean; music: string; cs: number[]}[] = [];
  COL: Record<string, string>; ISO: string[]; FLAG: Record<string, string>;
  shots: Shot[] = []; keys: CamKey[] = []; path!: CamPath; moves: number[] = [];
  area!: Box;
  F: Record<string, any[]> = {fills: [], strokes: [], lines: [], rings: [], labels: [], markers: [], flags: [], flag_hide: [], cards: [], clips: [],
    doll_labels: [], banners: [], icons: [], dots: [], dot_shows: [], docs: [], cutouts: [], numerals: [], arrows: [], tags: [], sfx: [], music: []};
  title: any = null; opening: any = null; chain: any = null; star: any = null; star_targets: any[] = []; lights: any = null; city_lights: any[] = [];
  credits: any = null; accents: {t: number; a: string}[] = [];

  constructor(o: Order, sb: Storyboard, a: Assets, K: Constitution, cues: Cues, patches: Record<string, any> = {}) {
    this.o = o; this.sb = sb; this.a = a; this.K = K; this.cues = cues; this.patches = patches;
    this.END = cues.total; this.gaz = new Gazetteer(o.places ?? {});
    this.ISO = o.countries;
    const tints = {...(K.look?.national_tints ?? {}), ...(o.tints ?? {})};
    this.COL = {...(K.look?.palette ?? {}), ...tints, TATAR: '#E2BF6A', KFSSR: '#6C8EBF', HIST: '#9E7A55'};
    this.ISO.forEach((i, k) => { if (!this.COL[i]) this.COL[i] = QUILT[(hash(i) + k) % QUILT.length]; });
    this.FLAG = {};
    this.ISO.forEach((i) => { this.FLAG[i] = o.flags?.[i] ?? ISO2[i] ?? fail(`no flag code for ${i}: add "flags": {"${i}": "<flag-icons code>"} to order.json`); });
    Object.entries(o.flags ?? {}).forEach(([k, v]) => (this.FLAG[k] = v));
  }

  // ------------------------------------------------------------------ structure
  P(c: number) { return this.cues.ids[c]; }
  pStart(c: number) { return this.cues.start(c); }
  pEnd(c: number) { return this.cues.end(c); }
  chapterEnd(c: number) { const ch = this.chOf[c]; const cs = this.chapters[ch].cs; return this.pEnd(cs[cs.length - 1]); }
  isLastChapter(c: number) { return this.chOf[c] === this.chapters.length - 1; }
  structure() {
    const all = [{title: 'HOOK', n: null, card: false, music: this.o.hook.music, paragraphs: this.o.hook.paragraphs}, ...this.o.chapters];
    all.forEach((ch, k) => {
      const cs = ch.paragraphs.map((p) => this.cues.idx(p));
      cs.forEach((c, j) => { this.chOf[c] = k; this.chFirst[c] = j === 0; });
      this.chapters.push({title: ch.title, n: ch.n ?? null, card: k > 0 && ch.card !== false, music: ch.music, cs});
    });
    this.cues.ids.forEach((id, c) => { if (this.chOf[c] === undefined) fail(`paragraph ${id} is in no chapter of order.json`); });
    const areaIds = this.o.area ? this.gaz.ids(this.o.area, this.ISO) : this.ISO.map((i) => 'rep:' + i);
    this.area = unionBox(areaIds.map((id) => { const p = PATHS[id]; return p?.bbox ? [p.bbox[0], p.bbox[1], p.bbox[2], p.bbox[3]] as Box : null; }))!;
  }
  parse() {
    const ids = new Set(this.cues.ids);
    this.sb.paragraphs.forEach((p) => {
      if (!ids.has(p.id)) fail(`storyboard paragraph "${p.id}" is not in narration.json`);
      const c = this.cues.idx(p.id);
      p.beats.forEach((b, i) => {
        const key = `${p.id}.${String(i + 1).padStart(2, '0')}`;
        if (!b.cue) fail(`beat ${key} has no "cue"`);
        const bad = Object.keys(b).filter((k) => !OPTS.has(k) && !ACTIONS.includes(k));
        if (bad.length) fail(`beat ${key} ("${b.cue}"): unknown key(s) ${bad.join(', ')} - actions: ${ACTIONS.join(', ')}`);
        if (!actionsOf(b).length) fail(`beat ${key} ("${b.cue}") has no action`);
        const r = this.cues.resolve(c, b.cue);
        this.beats.push({key, pid: p.id, c, i, t: r.t, t1: r.t1, b});
      });
    });
    this.beats.sort((x, y) => x.t - y.t || x.c - y.c || x.i - y.i);
  }
  /** time of an "until" spec relative to beat rb; undefined -> default */
  until(rb: RB, spec: string | undefined, dflt: () => number): number {
    if (spec === undefined || spec === null || spec === '') return dflt();
    const s = String(spec).trim();
    if (s === 'end') return this.END + 1;
    if (s === 'paragraph') return this.pEnd(rb.c) + 0.4;
    if (s === 'chapter') return this.isLastChapter(rb.c) ? this.END + 1 : this.chapterEnd(rb.c) + 1.0;
    if (s === 'shot') return this.nextMove(rb.t + 0.8) + 0.1;
    if (/^\+\d+(\.\d+)?$/.test(s)) return rb.t + parseFloat(s.slice(1));
    const r = this.cues.resolve(rb.c, s);
    if (r.t < rb.t) fail(`beat ${rb.key}: "until": "${s}" is before its cue "${rb.b.cue}"`);
    return r.t;
  }
  nextBeat(t: number) { const n = this.beats.find((b) => b.t > t + 0.05); return n ? n.t : this.END; }
  nextMove(t: number) { const m = this.moves.find((x) => x > t); return m ?? this.END + 1; }
  nextOfKind(rb: RB, kind: string) { const n = this.beats.find((b) => b.t > rb.t + 0.05 && b.b[kind] !== undefined); return n ? n.t : null; }
  place(q: any) { return this.gaz.resolve(q); }
  /** width/height of an image used by a document or portrait (assets.json), for the layout of screen boxes */
  aspect(img: string): number {
    const all = [...Object.values(this.a.archive ?? {}), ...Object.values(this.a.cutouts ?? {}), ...Object.values(this.a.docs ?? {})] as any[];
    return all.find((x) => x.file === img)?.aspect ?? (img.includes('_cut') ? 0.8 : 0.75);
  }
  ll(q: any): [number, number] { return this.place(q).lonlat; }

  // ------------------------------------------------------------------ full-frame clips (Blender / Manim) hide the map
  windows: {from: number; to: number}[] = [];
  fullWindows() {
    for (const rb of this.beats) {
      let len = 0;
      if (rb.b.clip !== undefined) {
        const C = this.a.clips?.[rb.b.clip];
        if (!C || C.kind === 'doll') continue;
        const st = arr(rb.b.steps), seg = C.segments[(st[st.length - 1] as any)?.seg ?? Object.keys(C.segments)[0]];
        len = seg ? (seg[1] - seg[0]) / (C.rate ?? 1) : 6;
      } else if (rb.b.document !== undefined && this.a.docs?.[rb.b.document]?.clip) len = this.a.docs[rb.b.document].length ?? 7;
      else continue;
      const from = rb.t - 0.3, to = this.until(rb, rb.b.until, () => from + len + 0.2) - 0.2;
      this.windows.push({from, to});
    }
  }
  inWindow(t: number) { return this.windows.find((w) => t > w.from + 0.2 && t < w.to - 0.3) ?? null; }
  /** map elements that would start under a full-frame clip wait for its end (screen cards stay: they draw above clips) */
  afterWindows() {
    const shift = (e: any, a: string, k: number) => {
      const w = this.inWindow(e[a]); if (!w) return true;
      const nf = w.to - 0.2 + k * 0.15;
      const end = e.to ?? this.END;
      if (end < nf + 1.2) { this.warn.push(`dropped ${e.text ?? e.title ?? e.city ?? e.iso ?? e.name ?? 'element'} (it would only show under a full-frame clip)`); return false; }
      e[a] = r3(nf); return true;
    };
    for (const n of ['labels', 'markers', 'banners', 'icons', 'rings', 'lines', 'dot_shows']) { let k = 0; this.F[n] = this.F[n].filter((e) => shift(e, 'from', this.inWindow(e.from) ? k++ : 0)); }
    let k = 0;
    this.F.flags = this.F.flags.filter((e) => shift(e, 't', this.inWindow(e.t) ? k++ : 0));
    this.F.arrows = this.F.arrows.filter((e) => shift(e, 't', 0));
  }

  // ------------------------------------------------------------------ camera
  planCamera() {
    this.fullWindows();
    const sh: Shot[] = [];
    const goBeats = this.beats.filter((b) => b.b.go !== undefined);
    goBeats.forEach((rb) => {
      const g = rb.b.go;
      const pl = g === 'overview' || g === 'wide' ? null : this.place(g);
      sh.push({t: rb.t, place: pl, kind: rb.b.shot ?? (pl ? 'auto' : 'wide'), key: 'cam:' + rb.key, explicit: true, box: pl?.box ?? null, pt: pl?.pt ?? null,
        pts: pl && pl.shape.length > 1 ? pl.shape : undefined,
        hold: rb.b.camera === 'hold'});
    });
    // wide chapter openings (constitution camera.chapter_opens_wide)
    this.chapters.forEach((ch, k) => {
      if (k === 0) return;
      const cs = this.pStart(ch.cs[0]);
      if (!sh.some((s) => s.t > cs - 0.6 && s.t < cs + 2.6)) sh.push({t: cs + 0.5, place: null, kind: 'wide', key: `cam:open${k}`, explicit: false, box: null, pt: null});
    });
    // opening: the map comes in on the first shot; key 0 sits on that framing (hidden under the opening clip)
    sh.sort((a, b) => a.t - b.t);
    const op = this.o.opening;
    const mapIn = op?.map_in ? this.cues.resolve(0, op.map_in).t : 0;
    if (!sh.length || sh[0].t > mapIn + 0.5) sh.unshift({t: mapIn, place: null, kind: 'wide', key: 'cam:mapin', explicit: false, box: null, pt: null});
    this.shots = sh;
    this.buildKeys();
  }
  shotKey(s: Shot, ovCount: number): CamKey {
    const p = this.patches[s.key] ?? {};
    let k: CamKey;
    const wm = clamp((s.wMul ?? 1) * (p.wmul ?? 1), 0.8, 1.25);
    if (!s.place) {
      k = overviewKey(this.area, s.variant ?? ovCount);
      if (wm !== 1) k = {...k, w: Math.round(Math.min(9800, k.w * wm))};
      if (s.shiftW) k = {...k, x: Math.round(k.x! + s.shiftW[0]), y: Math.round(k.y! + s.shiftW[1])};
    } else if (s.pts) k = frameBox(s.pts, s.kind, {tiltAdd: s.tiltAdd, wMul: wm});
    else if (s.box) k = frameBox(s.box, s.kind, {tiltAdd: s.tiltAdd, wMul: wm});
    else { k = framePoint(s.pt!, s.kind); if (wm !== 1) k = {...k, w: Math.round(Math.min(9800, k.w * wm))}; }
    if (p.shift) {                                                             // audit feedback: move the view by screen px (bounded)
      const sh = [clamp(p.shift[0], -220, 220), clamp(p.shift[1], -220, 220)];
      const c = keyState(k), [wx, wy] = unproject(c, 960 + sh[0], 540 + sh[1]);
      if (k.lon !== undefined) { const l = lonlat(wx, wy); k = {...k, lon: r3(l[0]), lat: r3(l[1])}; }
      else k = {...k, x: Math.round(wx), y: Math.round(wy)};
    }
    return k;
  }
  buildKeys() {
    const keys: CamKey[] = [];
    let ov = 0;
    this.shots.forEach((s, i) => {
      let k = this.shotKey(s, ov);
      if (!s.place) ov++;
      // never repeat a framing within 60 s (except straight after itself)
      for (let v = 0; v < 4; v++) {
        const similar = keys.filter((q, j) => j < keys.length - 1 && q.t > s.t - 60 && keyDistance(q, k) < 0.14);
        if (!similar.length) break;
        if (!s.place) { s.variant = (s.variant ?? ov) + 1; k = this.shotKey(s, ov); continue; }
        s.tiltAdd = [5, -4, 8, -7][v]; s.wMul = [0.9, 1.12, 0.84, 1.2][v]; k = this.shotKey(s, ov);
      }
      const prev = keys[keys.length - 1];
      let dur = 2.2, lead = 0.3;
      if (prev) {
        const a = keyState(prev), b = keyState(k);
        const m = Math.abs(Math.log(b.zoom / a.zoom)) + Math.hypot(b.x - a.x, b.y - a.y) * Math.min(a.zoom, b.zoom) / 1920;
        const hook = this.chOf[this.cues.tl.chunks.findIndex((ch) => ch.end >= s.t)] === 0;
        dur = clamp(1.25 + 0.32 * m, hook ? 1.3 : 1.6, hook ? 2.4 : 2.8);
        if (!s.explicit && !s.place) dur = Math.max(dur, 2.0);
        lead = clamp(0.15 + 0.12 * dur, 0.2, 0.5);
      }
      let t = i === 0 ? 0 : s.t - lead;
      const win = this.inWindow(s.t);
      if (win && i > 0) {
        const firstIn = !(prev && prev.t >= win.from);
        if (firstIn) { t = win.from + 1.0; dur = 0.01; } else { dur = 2.2; t = Math.max(prev!.t + 0.5, win.to - dur - 0.1); }
      }
      if (prev && t < prev.t + 0.5) t = prev.t + 0.5;
      if (prev && prev.t + (prev.dur ?? 2.2) > t) prev.dur = Math.max(1.0, r2(t - prev.t));
      keys.push({...k, t: r3(t), dur: i === 0 ? 0.01 : r2(dur), src: s.key, kind: s.explicit ? 'go' : 'auto'});
    });
    this.keys = keys;
    this.path = new CamPath(keys);
    this.moves = keys.filter((k, i) => i > 0 && keyDistance(keys[i - 1], k) > 0.3).map((k) => k.t);
  }
  /** make every world point in pts visible (title-safe) while the shot covering t is held: re-frame that shot */
  /** 'ok' = already visible, 'fixed' = the shot was re-framed a little, 'no' = would need too much (the element adapts instead) */
  ensureVisible(t: number, pts: [number, number][], why: string): 'ok' | 'fixed' | 'no' {
    const c = this.path.at(t);
    if (pts.every((p) => inSafe(c, p, 24))) return 'ok';
    const i = this.path.keyAt(t), k = this.keys[i];
    const s = this.shots.find((x) => x.key === k.src);
    if (!s) return 'no';
    if (!s.place) {                                                          // overview: slide (never wider than the canvas)
      const q = pts.map((p) => scr(c, p));
      const lo = Math.min(...q.map((p) => p.y)), hi = Math.max(...q.map((p) => p.y)), le = Math.min(...q.map((p) => p.x)), ri = Math.max(...q.map((p) => p.x));
      const dy = hi > 960 ? hi - 960 : lo < 120 ? lo - 120 : 0, dx = ri > 1800 ? ri - 1800 : le < 120 ? le - 120 : 0;
      if (Math.abs(dx) < 4 && Math.abs(dy) < 4) return 'no';
      const cur = s.shiftW ?? [0, 0], nx = clamp(cur[0] + dx / c.zoom, -320, 320), ny = clamp(cur[1] + dy / c.zoom, -320, 320);
      if (Math.abs(nx - cur[0]) < 2 && Math.abs(ny - cur[1]) < 2) return 'no';
      s.shiftW = [nx, ny]; this.warn.push(`camera: overview slid for ${why}`); return 'fixed';
    }
    // the original target of the shot bounds every re-framing: at most 1.35x its size, never compounding
    if (s.box0 === undefined) s.box0 = s.box ?? (s.pt ? [s.pt[0] - 80, s.pt[1] - 80, s.pt[0] + 80, s.pt[1] + 80] : null);
    const b0 = s.box0 ?? this.area, base: Box = s.box ?? b0;
    const nb = unionBox([base], pts)!;
    const grow = Math.max((nb[2] - nb[0]) / Math.max(1, b0[2] - b0[0]), (nb[3] - nb[1]) / Math.max(1, b0[3] - b0[1]));
    if (grow > 1.35) return 'no';
    if (nb[0] === base[0] && nb[1] === base[1] && nb[2] === base[2] && nb[3] === base[3]) return 'no';
    s.box = nb; if (s.pts) s.pts = [...s.pts, ...pts]; if (s.kind === 'close') s.kind = 'region';
    this.warn.push(`camera: ${s.key} re-framed x${grow.toFixed(2)} for ${why}`);
    return 'fixed';
  }

  // ------------------------------------------------------------------ helpers for elements
  tint(id: string, like?: string): string {
    if (like && this.COL[like]) return this.COL[like];
    if (id.startsWith('rep:') && this.COL[id.slice(4)]) return this.COL[id.slice(4)];
    return QUILT[hash(id) % QUILT.length];
  }
  look(id: string, look: string | undefined, like?: string, k = 0): any {
    const L = look ?? 'tint';
    if (L.startsWith('#')) return {color: L, op: 0.62};
    switch (L) {
      case 'tint': case 'born': return {color: this.tint(id, like), op: 0.62};
      case 'state': case 'union': return {color: this.COL.UNION ?? '#8E3741', op: 0.6};
      case 'faint': return {color: like ? this.tint(id, like) : this.COL.UNION ?? '#8E3741', op: 0.4};
      case 'focus': return {color: this.COL.GOLD ?? '#E2BF6A', op: 0.88, pulse: true};
      case 'highlight': return {color: '#D9A35A', op: 0.75};
      case 'muted': return {color: '#8E8A84', op: 0.76};
      case 'war': return {color: this.COL.RED ?? '#D2434E', op: 0.9, pulse: true};
      case 'disputed': return {color: '#F3F0E8', op: 0.6, hatch: true};
      case 'boycott': return {color: '#E8E8E8', op: 0.55, hatch: true};
      case 'new': return {color: '#FFE08A', op: 0.9, hatch: true};
      case 'quilt': return {color: QUILT[k % QUILT.length], op: 0.62};
      case 'gain': return {color: '#5FC1BA', op: 0.55, pulse: true};
      default: return fail(`unknown look "${L}" (tint, born, state, faint, focus, highlight, muted, war, disputed, boycott, new, quilt, gain, #hex)`);
    }
  }
  stagger(rb: RB, n: number, lo: number, hi: number) { const avail = Math.min(4, this.nextBeat(rb.t) - rb.t); return n <= 1 ? 0 : clamp((avail - 0.6) / n, lo, hi); }
  endDefault(rb: RB, minDur: number, maxDur: number, alsoNext?: string) {
    let e = Math.min(this.nextMove(rb.t + minDur) + 0.1, this.pEnd(rb.c) + 0.6, rb.t + maxDur);
    if (alsoNext) { const n = this.nextOfKind(rb, alsoNext); if (n !== null && n > rb.t + minDur * 0.5) e = Math.min(e, n - 0.25); }
    return Math.max(e, rb.t + minDur);
  }
  push(arrName: string, el: any, key: string) { el._k = key; const p = this.patches[`${arrName}:${key}`]; this.F[arrName].push(p ? {...el, ...p.set} : el); return el; }

  // ------------------------------------------------------------------ elements
  elements() {
    for (const rb of this.beats) {
      const b = rb.b;
      for (const act of actionsOf(b)) {
        const fn = (this as any)['a_' + act];
        if (fn) fn.call(this, rb, b[act]);
      }
    }
    this.chapterCards();
    this.fixFillOverlaps();
    this.afterWindows();
  }
  a_go() {}
  a_camera() {}
  a_fill(rb: RB, v: any) {
    const ids = this.gaz.ids(v, this.ISO).filter((id) => !arr(rb.b.except).map((x: string) => (x.includes(':') ? x : 'rep:' + x)).includes(id));
    const st = rb.b.look === 'quilt' ? 0.07 : this.stagger(rb, ids.length, 0.03, 0.12);
    ids.forEach((id, k) => {
      const from = rb.t + (rb.b.look === 'quilt' ? (k % 9) * 0.07 : k * st);
      const to = this.until(rb, rb.b.until, () => (this.isLastChapter(rb.c) ? this.END + 1 : this.chapterEnd(rb.c) + 1.0));
      const L = this.look(id, rb.b.look, rb.b.like, k);
      const n = ids.length;
      const el = {id, ...L, ...(rb.b.op ? {op: rb.b.op} : {}), ...(rb.b.color ? {color: rb.b.color} : {}), from: r3(from), to: r3(to),
        fi: n > 5 ? 0.45 : 0.8, fo: 0.8, _ov: OVERLAY.has(rb.b.look ?? 'tint')};
      this.push('fills', el, `${rb.key}/f${k}`);
      if (rb.b.look === 'born') {
        this.push('strokes', {id, color: '#FFE9B0', width: 2.6, from: r3(from), to: r3(from + 2.4), draw: 1.5, glow: true}, `${rb.key}/s${k}`);
        this.sfx('pop', from, 0.3);
      }
      if (rb.b.look === 'focus' || rb.b.look === 'war') {
        this.push('strokes', {id, color: rb.b.look === 'war' ? '#FFD0C8' : '#FFE9A8', width: 2.2, from: r3(from), to: r3(to), glow: true}, `${rb.key}/o${k}`);
        if (k === 0) this.sfx('shimmer', from + 0.2, 0.3);
      }
      if (rb.b.look === 'muted') this.push('strokes', {id, color: '#D8D2C4', width: 1.8, from: r3(from), to: r3(to), dash: true}, `${rb.key}/d${k}`);
      if (rb.b.look === 'quilt') this.push('strokes', {id, color: '#FFF6E0', width: 1.1, from: r3(from), to: r3(to), dash: true, op: 0.85}, `${rb.key}/q${k}`);
    });
  }
  a_unfill(rb: RB, v: any) {
    const ids = this.gaz.ids(v, this.ISO);
    for (const f of this.F.fills) if (ids.includes(f.id) && f.from < rb.t && f.to > rb.t) f.to = r3(rb.t + 0.15);
    for (const s of this.F.strokes) if (ids.includes(s.id) && s.from < rb.t && s.to > rb.t) s.to = r3(rb.t + 0.15);
  }
  /** a newer STATE fill of a region replaces the older ones (crossfade 0.3 s); highlight looks only lie on top for a while */
  fixFillOverlaps() {
    const by: Record<string, any[]> = {};
    this.F.fills.forEach((f) => (by[f.id] ??= []).push(f));
    Object.values(by).forEach((l) => {
      l.sort((a, b) => a.from - b.from);
      l.forEach((f, i) => { if (f._ov) return; for (let j = 0; j < i; j++) if (l[j].to > f.from + 0.3 && l[j].from < f.from) l[j].to = r3(f.from + 0.3); });
    });
  }
  a_border(rb: RB, v: any) {
    const style = rb.b.style ?? 'trace';
    const ids = v === 'film' || v === 'all' ? ['borders'] : this.gaz.ids(v, this.ISO);
    const st = this.stagger(rb, ids.length, 0.15, 0.5);
    ids.forEach((id, k) => {
      const from = rb.t + k * st;
      const S: Record<string, any> = {
        trace: {color: '#FFE9B0', width: 2.6, draw: 1.5, glow: true, dto: 2.4},
        plain: {color: '#FFF6E0', width: 1.2, op: 0.85},
        gold: {color: this.COL.GOLD ?? '#E2BF6A', width: id === 'frontier' ? 3.2 : 2.0, draw: 3.0, glow: true},
        fire: {color: '#FF8A3D', width: 2.6, draw: 1.4, glow: true, dto: 3.4},
        dashed: {color: '#FFE7A0', width: 1.6, dash: true},
        light: {color: '#FFF6E0', width: 1.4, draw: 1.6},
        river: {color: '#9FE3FF', width: 3.0, draw: 2.0, glow: true},
      };
      const s = S[style] ?? fail(`beat ${rb.key}: unknown border style "${style}" (trace, plain, gold, fire, dashed, light, river)`);
      const to = s.dto ? from + s.dto : this.until(rb, rb.b.until, () => (this.isLastChapter(rb.c) ? this.END + 1 : this.chapterEnd(rb.c) + 1.0));
      const {dto, ...rest} = s;
      this.push('strokes', {id, ...rest, from: r3(from - 0.1), to: r3(to)}, `${rb.key}/b${k}`);
      if ((s.draw ?? 0) >= 2.0 || id === 'borders') this.sfx('line_draw', from, 0.3);
    });
  }
  a_flag(rb: RB, v: any) {
    const isos: string[] = v === 'film' ? [...this.ISO] : arr(v);
    const st = this.stagger(rb, isos.length, 0.1, 0.35);
    isos.forEach((iso, k) => {
      if (!this.FLAG[iso]) fail(`beat ${rb.key}: no flag code for "${iso}" (order.json "flags")`);
      const t = rb.t + 0.15 + k * st;
      const date = typeof rb.b.date === 'string' && isos.length === 1 ? rb.b.date : rb.b.dates?.[iso] ?? (typeof rb.b.date === 'object' ? rb.b.date?.[iso] : undefined);
      const el: any = {iso, t: r3(t), to: r3(this.until(rb, rb.b.until, () => (this.isLastChapter(rb.c) ? this.END + 1 : this.chapterEnd(rb.c) + 0.6)))};
      if (date) el.date = date;
      if (rb.b.at) { el.at = this.ll(rb.b.at); if (rb.b.glide) el.atUntil = r3(this.until(rb, rb.b.glide, () => rb.t + 3)); }
      if (!PATHS['rep:' + iso] && !el.at) fail(`beat ${rb.key}: flag ${iso} has no region in geo.json - give "at": place`);
      this.push('flags', el, `${rb.key}/g${k}`);
      this.sfx('flag_drop', t + 0.42, 0.38);
    });
  }
  a_flags(rb: RB, v: any) {
    if (v !== 'hide') fail(`beat ${rb.key}: "flags" only takes "hide"`);
    this.F.flag_hide.push([r3(rb.t - 0.5), r3(this.until(rb, rb.b.until, () => this.pEnd(rb.c)))]);
  }
  labelSize(at: string | [number, number], t: number, style: string, text: string, sub?: string): number {
    const c = this.path.at(t + 0.6);
    if (style === 'water') {
      const k = /ocean/i.test(text) ? 1 : /sea/i.test(text) ? 0.76 : /gulf|bay|lake|strait/i.test(text) ? 0.68 : 0.6;
      return clamp(Math.round((22 + 18 * Math.sqrt(1920 / c.zoom / 8000)) * k), 18, 42);
    }
    if (style === 'italic') return 20;
    if (typeof at === 'string' && PATHS[at]?.area_px) {
      const q = scr(c, PATHS[at].label);
      const L = Math.sqrt(PATHS[at].area_px!) * c.zoom * q.s;
      if (style === 'title') return Math.round(clamp(L * 0.12, 40, 120) * (sub ? 0.6 : 1));
      return Math.round(clamp(L * 0.085, 20, text.length > 14 ? 34 : 52));
    }
    return style === 'small' ? 20 : style === 'title' ? 64 : 24;
  }
  a_label(rb: RB, v: any) {
    const style = rb.b.style ?? (rb.b.italic ? 'water' : 'region');
    const pl = this.place(rb.b.at ?? v);
    const at: string | [number, number] = pl.ids.length === 1 && !pl.city && hasLabel(pl.ids[0]) ? pl.ids[0] : pl.lonlat;
    const from = rb.t + 0.3;
    const to = this.until(rb, rb.b.until, () => this.endDefault(rb, 2.5, 12));
    const el: any = {text: v, at, size: rb.b.size ?? this.labelSize(at, from, style, v, rb.b.sub), from: r3(from), to: r3(to)};
    if (style === 'water' || style === 'italic') el.italic = true;
    if (rb.b.sub) el.sub = rb.b.sub;
    if (rb.b.color) el.color = rb.b.color;
    if (style === 'title') el.spacing = el.size > 90 ? 0.32 : 0.4;
    this.push('labels', el, `${rb.key}/l`);
  }
  a_marker(rb: RB, v: any) {
    const pl = this.place(v);
    if (!pl.city) fail(`beat ${rb.key}: marker "${v}" must be a city of geo.json or a [lon, lat] place in order.json "places"`);
    const from = rb.t - 0.1, to = this.until(rb, rb.b.until, () => this.endDefault(rb, 2.5, 12));
    const el: any = {city: pl.city, from: r3(from), to: r3(to)};
    if (rb.b.label !== undefined) el.label = rb.b.label;
    if (typeof rb.b.text === 'string') el.label = rb.b.text;
    if (rb.b.sub) el.sub = rb.b.sub;
    if (rb.b.dot) el.dot = true;
    if (rb.b.pulse || rb.b.alert) el.pulse = true;
    if (rb.b.alert) el.color = this.COL.RED;
    el.side = rb.b.side ?? 'r';
    this.push('markers', el, `${rb.key}/m`);
    if (el.label && !el.dot) this.sfx('pop', from + 0.1, 0.3);
  }
  card(rb: RB, kind: string, text: string, from: number, to: number, extra: any = {}) {
    this.push('cards', {kind, text, ...extra, from: r3(from), to: r3(to)}, `${rb.key}/c`);
  }
  a_date(rb: RB, v: any) {
    const to = this.until(rb, rb.b.until, () => {
      const n = this.beats.find((b) => b.t > rb.t + 1.2 && (b.b.date !== undefined || b.b.quote !== undefined || b.b.closing !== undefined));
      return clamp(Math.min(n ? n.t - 0.05 : 1e9, this.nextMove(rb.t + 2.5) + 0.3, this.pEnd(rb.c) + 0.5), rb.t + 2.5, rb.t + 7.5);
    });
    this.card(rb, 'date', v, rb.t, to, rb.b.sub ? {sub: rb.b.sub} : {});
    this.sfx('paper', rb.t, 0.35);
  }
  a_quote(rb: RB, v: any) {
    const to = this.until(rb, rb.b.until, () => Math.min(rb.t + 7, this.nextBeat(rb.t + 3) - 0.2));
    this.card(rb, 'quote', v, rb.t + 0.2, to, rb.b.sub ? {sub: rb.b.sub} : {});
  }
  a_strike(rb: RB, v: any) {
    const to = this.until(rb, rb.b.until, () => rb.t + 4);
    this.card(rb, 'strike', arr(v).join('|'), rb.t - 0.2, to);
    this.sfx('stamp', rb.t + 0.6, 0.3);
  }
  a_callout(rb: RB, v: any) {
    const to = this.until(rb, rb.b.until, () => this.endDefault(rb, 2.5, 8));
    this.card(rb, 'callout', v, rb.t + 0.2, to, {at: [960, 930]});
    this.sfx('stamp', rb.t + 0.3, 0.32);
  }
  a_big(rb: RB, v: any) {
    const to = this.until(rb, rb.b.until, () => Math.min(rb.t + 3.5, this.nextBeat(rb.t + 1) - 0.1));
    this.card(rb, 'big', v, rb.t, to, rb.b.sub ? {sub: rb.b.sub} : {});
    this.sfx('tick', rb.t + 0.05, 0.5);
  }
  a_numeral(rb: RB, v: any) {
    const nx = this.nextOfKind(rb, 'numeral');
    const to = this.until(rb, rb.b.until, () => {
      if (nx !== null && nx - rb.t < 4.5) return nx - 0.07;
      return Math.max(rb.t + 1.5, Math.min(rb.t + 4.2, this.nextBeat(rb.t + 1.2) - 0.1));
    });
    const size = v.length >= 4 ? 200 : 220;
    this.push('numerals', {text: v, ...(rb.b.sub ? {sub: rb.b.sub} : {}), from: r3(rb.t - 0.05), to: r3(to), y: 700, size}, `${rb.key}/n`);
    this.sfx('tick', rb.t, 0.45);
  }
  a_tag(rb: RB, v: any) {
    const numbered = rb.b.num !== undefined;
    const group = rb.b.group ?? (numbered ? 'num' : 'slots');
    const prev = this.F.tags.filter((g) => g._g === group && g.to > rb.t - 0.01);
    const end = this.until(rb, rb.b.until, () => this.nextMove(rb.t + 1.5) - 0.3);
    if (numbered) prev.forEach((g) => (g.to = r3(Math.min(g.to, rb.t - 0.2))));
    const el: any = {text: v, from: r3(rb.t), to: r3(end), _g: group};
    if (numbered) el.num = rb.b.num;
    else { el.slot = prev.length % 3; prev.forEach((g) => (g.to = r3(Math.max(g.to, end)))); }
    this.push('tags', el, `${rb.key}/t`);
    this.sfx('stamp', rb.t + 0.15, 0.35);
  }
  a_banner(rb: RB, v: any) {
    const A = this.a.archive?.[v] ?? fail(`beat ${rb.key}: banner image "${v}" is not in assets.json archive`);
    const pl = this.place(rb.b.near ?? rb.b.at ?? fail(`beat ${rb.key}: banner needs "near": place`));
    const from = rb.t + 0.15, to = this.until(rb, rb.b.until, () => this.endDefault(rb, 3, 14, 'banner') - 0.2);
    const el: any = {at: pl.lonlat, img: A.file, title: rb.b.title ?? fail(`beat ${rb.key}: banner needs "title"`), from: r3(from), to: r3(to)};
    if (rb.b.sub) el.sub = rb.b.sub;
    if (rb.b.size) el.size = rb.b.size;
    this.push('banners', el, `${rb.key}/ban`);
    this.sfx('wood_thunk', from + 0.2, 0.45); this.sfx('cloth_flap', from + 0.3, 0.3);
  }
  a_portrait(rb: RB, v: any) {
    const A = this.a.cutouts?.[v] ?? fail(`beat ${rb.key}: portrait "${v}" is not in assets.json cutouts`);
    const from = rb.t - 0.1;
    const to = this.until(rb, rb.b.until, () => this.endDefault(rb, 3, 9, 'portrait') - 0.05);
    const el: any = {img: A.file, name: rb.b.name ?? fail(`beat ${rb.key}: portrait needs "name"`), from: r3(from), to: r3(to), side: rb.b.side ?? ''};
    if (rb.b.sub) el.sub = rb.b.sub;
    this.push('cutouts', el, `${rb.key}/cut`);
    this.sfx('whoosh_3', from - 0.15, 0.28);
  }
  a_document(rb: RB, v: any) {
    const D = this.a.docs?.[v] ?? fail(`beat ${rb.key}: document "${v}" is not in assets.json docs`);
    if (D.clip) {
      const len = D.length ?? 7;
      const to = this.until(rb, rb.b.until, () => rb.t + len + 0.3) - 0.2;
      const win = to - (rb.t - 0.3);
      const rate = clamp(len / Math.max(1, win), 0.8, 1.3);
      this.push('clips', {kind: 'cauc', src: D.clip, from: r3(rb.t - 0.3), to: r3(to), steps: [{at: r3(rb.t - 0.3), s0: 0, s1: len, ...(Math.abs(rate - 1) > 0.04 ? {rate: r2(rate)} : {})}]}, `${rb.key}/dclip`);
      this.sfx('paper', rb.t - 0.2, 0.4);
      return;
    }
    const from = rb.t - 0.2, to = this.until(rb, rb.b.until, () => Math.min(rb.t + 6.5, this.nextMove(rb.t + 3) + 0.2));
    const el: any = {img: D.file, from: r3(from), to: r3(to), side: rb.b.side ?? ''};
    if (rb.b.caption) el.cap = rb.b.caption;
    if (rb.b.signatures) el.sigs = arr(rb.b.signatures).map((s: any) => ({img: this.a.sig?.[s.img] ?? s.img, name: s.name}));
    this.push('docs', el, `${rb.key}/doc`);
    this.sfx('paper', from, 0.4);
  }
  a_icon(rb: RB, v: any) {
    const I = this.a.icons?.[v] ?? fail(`beat ${rb.key}: icon "${v}" is not in assets.json icons`);
    const pl = this.place(rb.b.near ?? rb.b.at ?? fail(`beat ${rb.key}: icon needs "near": place`));
    const from = rb.t + 0.1, to = this.until(rb, rb.b.until, () => this.endDefault(rb, 2.5, 12) - 0.2);
    const size = typeof rb.b.size === 'number' ? rb.b.size : I.size ?? 0.8;
    this.push('icons', {name: v, az: I.az ?? 270, at: pl.lonlat, from: r3(from), to: r3(to), size}, `${rb.key}/ic`);
    this.sfx('pop', from, 0.35);
  }
  a_arrow(rb: RB, v: any) {
    const pairs: any[] = Array.isArray(v[0]) && !(typeof v[0][0] === 'number') ? v : [v];
    pairs.forEach((pr, k) => {
      const a = this.ll(pr[0]), b = this.ll(pr[1]);
      const t = rb.t + k * 0.35, to = this.until(rb, rb.b.until, () => this.endDefault(rb, 2.5, 10) - 0.2);
      const color = rb.b.kind === 'link' ? '#E8C36A' : '#C8504F';
      const sign = (b[1] < a[1] ? -1 : 1) * (k % 2 ? -1 : 1);
      this.push('arrows', {a, b, t: r3(t), dur: 0.9 + Math.min(0.3, Math.hypot(b[0] - a[0], b[1] - a[1]) / 40), to: r3(to), color, bend: r2(0.18 * sign)}, `${rb.key}/ar${k}`);
    });
  }
  a_route(rb: RB, v: any) {
    const style = rb.b.style ?? 'path';
    const pts = arr(v).map((p: any) => this.ll(p));
    const to = this.until(rb, rb.b.until, () => this.endDefault(rb, 3, 12));
    if (style === 'converge') {
      const tgt = pts[pts.length - 1];
      pts.slice(0, -1).forEach((p, k) => this.push('lines', {pts: [p, tgt], from: r3(rb.t + 0.6 + k * 0.2), dur: 1.6, to: r3(to), color: this.COL.GOLD, width: 2.5, dash: true}, `${rb.key}/r${k}`));
    } else {
      const chain = style === 'chain';
      this.push('lines', {pts, from: r3(rb.t - 0.3), dur: chain ? 3.2 : 2.2, to: r3(to), color: chain ? '#FFF3C4' : this.COL.GOLD, width: chain ? 4 : 3}, `${rb.key}/r`);
    }
    this.sfx('line_draw', rb.t - 0.3, 0.3);
  }
  a_rings(rb: RB, v: any) {
    const pl = this.place(v);
    const at = pl.ids.length === 1 && hasLabel(pl.ids[0]) ? pl.ids[0] : (pl.lonlat as any);
    const to = this.until(rb, rb.b.until, () => this.endDefault(rb, 2.5, 10));
    this.push('rings', {at, km: rb.b.km ?? [130, 260, 390], from: r3(rb.t), to: r3(to)}, `${rb.key}/ring`);
  }
  a_dots(rb: RB, v: any) {
    const ds = this.o.datasets?.[v] ?? fail(`beat ${rb.key}: dataset "${v}" is not in order.json datasets`);
    if (!this.F.dots.length) ds.forEach((d: any) => this.F.dots.push({n: d.n ?? d[0], lon: d.lon ?? d[1], lat: d.lat ?? d[2], layer: d.layer ?? d[3] ?? 0}));
    const tempo = rb.b.tempo ?? 'slow';
    const to = this.until(rb, rb.b.until, () => this.endDefault(rb, 2.5, 10) - 0.2);
    this.push('dot_shows', {from: r3(rb.t + 0.1), to: r3(to), layers: rb.b.layers ?? [0, 1, 2, 3], stagger: tempo === 'slow' ? 0.32 : tempo === 'fast' ? 0.06 : 0}, `${rb.key}/dots`);
    this.sfx('shimmer', rb.t + 0.1, 0.25);
  }
  a_clip(rb: RB, v: any) {
    const C = this.a.clips?.[v] ?? fail(`beat ${rb.key}: clip "${v}" is not in assets.json clips`);
    const steps = arr(rb.b.steps).length ? arr(rb.b.steps) : [{cue: rb.b.cue, seg: Object.keys(C.segments)[0]}];
    const st = steps.map((s: any, i: number) => {
      const seg = C.segments[s.seg] ?? fail(`beat ${rb.key}: clip ${v} has no segment "${s.seg}" (${Object.keys(C.segments).join(', ')})`);
      const at = i === 0 ? rb.t - (C.kind === 'cauc' ? 0.3 : 0.2) : this.cues.resolve(rb.c, s.cue).t;
      return {at: r3(at), s0: seg[0], s1: seg[1], ...(C.rate ? {rate: C.rate} : {})};
    });
    const from = st[0].at;
    const segLen = (st[st.length - 1].s1 - st[st.length - 1].s0) / (st[st.length - 1].rate ?? 1);
    const to = this.until(rb, rb.b.until, () => st[st.length - 1].at + segLen + (C.kind === 'doll' ? 0.6 : 0.2)) + (C.kind === 'doll' ? 0.4 : -0.2);
    const el: any = {kind: C.kind === 'manim' ? 'cauc' : C.kind, src: C.src, from: r3(from), to: r3(to), steps: st};
    if (rb.b.labels && C.dx_with_labels) el.dx = C.dx_with_labels;
    this.push('clips', el, `${rb.key}/clip`);
    arr(rb.b.labels).forEach((l: any) => {
      const t0 = this.cues.resolve(rb.c, l.cue).t;
      const seg = steps.find((s: any) => s.cue === l.cue);
      const delay = seg ? (C.segments[seg.seg][2] ?? 0) : 0;
      this.F.doll_labels.push({text: l.text, k: l.k, from: r3(t0 + delay), to: r3(l.until ? this.until(rb, l.until, () => to) : to)});
    });
    (C.sfx ?? []).forEach((s) => this.sfx(s.f, from + s.at, s.v ?? 0.3));
    st.forEach((s: any, i: number) => { if (i > 0 && C.kind === 'doll') this.sfx('shimmer', s.at + 1.2, 0.25); });
  }
  a_titles(rb: RB, v: any) {
    const lines = arr(v).map((l: any, i: number) => {
      const from = this.cues.resolve(rb.c, l.cue ?? rb.b.cue).t - (i === 0 ? 0.1 : 0);
      const o: any = {text: l.text, from: r3(from)};
      if (l.hi) { o.hi = l.hi; o.hiAt = r3(this.cues.resolve(rb.c, l.hi_cue ?? l.cue).t); }
      return o;
    });
    const from = rb.t - 0.15, to = this.until(rb, rb.b.until, () => (rb.c + 1 < this.cues.ids.length ? this.pStart(rb.c + 1) - 0.25 : this.END));
    this.title = {from: r3(from), to: r3(to), lines};
    this.sfx('swell', from - 2.85, 0.5); this.sfx('boom', from + 0.15, 0.6);
    const hi = lines.find((l: any) => l.hiAt); if (hi) this.sfx('drone_hit', hi.hiAt, 0.35);
  }
  a_closing(rb: RB, v: any) {
    const last = this.cues.ids.length - 1, endT = this.pEnd(last) + 2.5;
    this.card(rb, 'title', v, rb.t, endT);
    if (this.o.end) this.push('cards', {kind: 'end', text: this.o.end.text, ...(this.o.end.sub ? {sub: this.o.end.sub} : {}), from: r3(endT), to: r3(this.END)}, 'end');
    this.sfx('riser', rb.t - 2.4, 0.3); this.sfx('boom', rb.t + 0.1, 0.45);
  }
  a_creative(rb: RB, v: any) {
    const p = rb.b.params ?? {};
    if (v === 'star_shatter') {
      this.star = {from: r3(rb.t - 0.15)};
      this.star_targets = this.ISO.map((iso) => {
        const cap = this.o.capitals?.[iso] ?? fail(`star_shatter needs order.json "capitals" for ${iso}`);
        const ll = this.ll(cap); return [iso, ll[0], ll[1]];
      });
      this.sfx('whoosh_2', rb.t + 0.55, 0.32); this.sfx('shimmer', rb.t + 0.75, 0.34);
    } else if (v === 'lights_out') {
      const off = this.cues.resolve(rb.c, p.off).t, offEnd = this.cues.resolve(rb.c, p.off_end).t, re = this.cues.resolve(rb.c, p.relight).t;
      this.lights = {from: r3(rb.t - 0.3), off0: r3(off - 0.15), off1: r3(offEnd + 0.5), lift0: r3(re - 0.5), lift1: r3(re + 0.7)};
      this.city_lights = this.o.datasets?.[p.cities ?? 'city_lights'] ?? fail('lights_out needs a city_lights dataset');
    } else if (v === 'chain') {
      const pts = arr(p.route).map((x: any) => this.ll(x));
      const to = this.until(rb, rb.b.until, () => rb.t + 8);
      this.chain = {pts, from: r3(rb.t + 1.0), dur: r2(clamp(to - rb.t - 1.6, 3, 8)), to: r3(to - 0.2)};
      this.sfx('line_draw', rb.t + 1.0, 0.3); this.sfx('crowd_bed', rb.t + 0.6, 0.3);
    } else fail(`beat ${rb.key}: unknown creative "${v}" (star_shatter, lights_out, chain; new tools are added in phase 3)`);
  }
  a_accent(rb: RB, v: any) { arr(v).forEach((a: string) => this.accents.push({t: rb.t, a})); }
  sfx(f: string, t: number, v: number) { if (t > -0.5) this.F.sfx.push({f, t: r3(Math.max(0, t)), v}); }

  chapterCards() {
    this.chapters.forEach((ch, k) => {
      if (!ch.card) return;
      const cs = this.pStart(ch.cs[0]);
      let from = cs + 0.1, to = cs + 3.6;
      const scr = [...this.F.cutouts, ...this.F.docs, ...this.F.numerals, ...this.F.cards.filter((c) => c.kind !== 'chapter')]
        .filter((e) => e.from > from + 0.5 && e.from < to);
      if (scr.length) to = Math.max(from + 2.2, Math.min(...scr.map((e) => e.from)) - 0.05);
      // the previous paragraph may still be speaking: never cover its last words
      if (ch.cs[0] > 0 && this.pEnd(ch.cs[0] - 1) > from - 0.3) from = this.pEnd(ch.cs[0] - 1) + 0.3;
      this.F.cards.push({kind: 'chapter', num: ch.n ?? undefined, text: ch.title.toUpperCase(), from: r3(from), to: r3(to), _k: `chapter${k}`});
      this.sfx('boom', from, 0.45);
    });
  }
}
