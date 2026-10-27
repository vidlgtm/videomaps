// FACTORY - automatic director. usage (from the repo root, after npm ci in factory/engine):
//   npx tsx factory/director/main.ts <orderDir> [--feedback audit.json] [--out factory/engine/src/data/film.json]
// Reads: <order>/order.json, narration.json, storyboard.json, assets.json (+ the line's 3D pieces), out/pack.json (processing station),
//        data/timeline.json (voice job) + the rules. Also writes <order>/out/CREDITS.txt (YouTube description).
// Writes: film.json (every element of the film) + <order>/out/director_report.txt. Fails with a clear message on any
// mistake in the order (cue not in the narration, unknown place, missing asset).
import * as fs from 'fs';
import * as path from 'path';
import {readJSON, exists, r3, DirectorError} from './lib/util';
import {Cues} from './lib/cues';
import {Director} from './lib/plan';
import {visibility, placement, rhythm, flagCuts} from './lib/fit';
import {sound} from './lib/sound';
import {feedbackToPatches} from './lib/feedback';

const args = process.argv.slice(2);
const orderDir = args[0];
const opt = (k: string, d?: string) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const ROOT = path.resolve(path.dirname(path.resolve(process.argv[1])), '..');   // factory/
const out = opt('--out', path.join(ROOT, 'engine/src/data/film.json'))!;
try {
  if (!orderDir || !exists(path.join(orderDir, 'order.json'))) throw new DirectorError('usage: main.ts <orderDir> (with order.json)');
  const o = readJSON(path.join(orderDir, 'order.json'));
  const nar = readJSON(path.join(orderDir, 'narration.json'));
  const sb = readJSON(path.join(orderDir, 'storyboard.json'));
  const assets = exists(path.join(orderDir, 'assets.json')) ? readJSON(path.join(orderDir, 'assets.json')) : {};
  // phase 2: the processing station's pack (photos, cut-outs, documents, signatures, extra flags, credits) wins over assets.json
  const packFile = opt('--pack', path.join(orderDir, 'out/pack.json'))!;
  const pack = exists(packFile) ? readJSON(packFile) : null;
  if (pack) {
    for (const k of ['archive', 'cutouts', 'docs', 'sig']) assets[k] = {...(assets[k] ?? {}), ...(pack[k] ?? {})};
    assets.credits = [...(pack.credits ?? []), ...(assets.credits ?? [])]; if (pack.credits_fixed) assets.credits_fixed = pack.credits_fixed;
    o.flag_aspect = {...(o.flag_aspect ?? {}), ...Object.fromEntries(Object.entries(pack.flags ?? {}).map(([c, f]: any) => [c, f.aspect]))};
    console.log(`station pack: ${Object.keys(pack.archive ?? {}).length} banner photos, ${Object.keys(pack.cutouts ?? {}).length} portraits, ${Object.keys(pack.docs ?? {}).length} documents, ${Object.keys(pack.sig ?? {}).length} signatures`);
  }
  const K = readJSON(path.join(ROOT, 'rules/constitution.json'));
  const tlPath = exists(path.join(orderDir, 'data/timeline.json')) ? path.join(orderDir, 'data/timeline.json') : path.join(ROOT, 'engine/src/data/timeline.json');
  const tl = readJSON(tlPath);
  const cues = new Cues(tl, nar.paragraphs.map((p: any) => p.id));
  const patchFile = path.join(orderDir, 'out/patches.json');
  let patches = exists(patchFile) ? readJSON(patchFile) : {};
  const fb = opt('--feedback');
  const D0 = () => { const d = new Director(o, sb, assets, K, cues, patches); d.structure(); d.parse(); d.planCamera(); d.elements(); visibility(d); placement(d); return d; };
  let d = D0();
  if (fb && exists(fb)) {
    const prev = exists(out) ? readJSON(out) : null;
    patches = feedbackToPatches(readJSON(fb), d, prev, patches);
    fs.mkdirSync(path.dirname(patchFile), {recursive: true});
    fs.writeFileSync(patchFile, JSON.stringify(patches, null, 1));
    d = D0();
  }
  // opening (order.json): text lines on the hook, the map comes in on the first shot
  const op = o.opening;
  if (op) {
    const t = (c: string) => cues.resolve(0, c).t;
    const lines = op.lines.map((l: any, i: number) => ({text: l.text, kind: l.kind,
      from: r3(l.cue ? t(l.cue) : (i > 0 ? (t(op.lines[i - 1].cue) + 0.55) : 0.3))}));
    const yr = lines.find((l: any) => l.kind === 'year');
    const mapIn = op.map_in ? t(op.map_in) - 0.25 : 3;
    const clip = op.clip ? (assets.clips?.[op.clip]?.src ?? op.clip) : null;
    d.opening = {clip, mapIn: r3(mapIn), end: r3(mapIn + 1.55), textOut: r3(op.text_out ? t(op.text_out) - 0.05 : mapIn - 0.5),
      rule: yr ? r3(yr.from + 0.25) : undefined, bloom: op.bloom ?? 0.45, lines};
    (assets.clips?.[op.clip]?.opening_sfx ?? []).forEach((s: any) => d.sfx(s.f, s.at, s.v ?? 0.3));
  } else d.opening = {clip: null, mapIn: 0, end: -1000, textOut: 0, lines: []};
  const drifts = rhythm(d);
  flagCuts(d);
  sound(d);
  // credits under the end card: only the files the film really shows (station pack: licence + author from Commons)
  const used = new Set<string>();
  d.F.banners.forEach((b: any) => used.add(b.img)); d.F.cutouts.forEach((c: any) => used.add(c.img));
  d.F.docs.forEach((x: any) => { used.add(x.img); (x.sigs ?? []).forEach((g: any) => used.add(g.img)); });
  d.F.clips.forEach((c: any) => used.add(c.src));
  Object.values(d.FLAG ?? {}).forEach((c: any) => used.add(`flags/4x3/${c}.svg`));
  const seen = new Set<string>();
  const cr = (assets.credits ?? []).filter((c: any) => !c.files || c.files.some((f: string) => used.has(f))).filter((c: any) => {
    const k = `${c.what}|${c.license}|${c.license === 'Public domain' ? '' : c.author ?? ''}`; if (seen.has(k)) return false; seen.add(k); return true; });
  const lic: Record<string, string[]> = {};
  cr.forEach((c: any) => (lic[c.license] ??= []).push(c.author && c.license !== 'Public domain' && c.author !== 'unknown author' ? `${c.what} — ${c.author}` : c.what));
  const parts = Object.entries(lic).sort((a, b) => (a[0] === 'Public domain' ? -1 : b[0] === 'Public domain' ? 1 : 0)).map(([l, xs]) => `${l}: ${xs.join(' · ')}`);
  const lines: string[] = [];
  let cur = parts.length ? 'Archival images via Wikimedia Commons — ' : '';
  parts.forEach((p) => { if ((cur + p).length > 250 && cur.length > 60) { lines.push(cur.trim()); cur = ''; } cur += (cur && !cur.endsWith('— ') ? '   |   ' : '') + p; });
  if (cur.trim()) lines.push(cur.trim());
  lines.push(...(assets.credits_fixed ?? ['Relief: AWS Terrain Tiles (SRTM, ETOPO) · Imagery: NASA Blue Marble & Black Marble · Boundaries: Natural Earth · Narration: synthetic voice · Music: original score']));
  const last = cues.ids.length - 1;
  const yt = ['CREDITS', '', 'Archival images (Wikimedia Commons):',
    ...cr.map((c: any) => `• ${c.what} — ${c.author && c.author !== 'unknown author' ? c.author + ' — ' : ''}${c.license}${c.page ? ' — ' + c.page : ''}`),
    '', ...(assets.credits_fixed ?? [])];
  fs.mkdirSync(path.join(orderDir, 'out'), {recursive: true});
  fs.writeFileSync(path.join(orderDir, 'out/CREDITS.txt'), yt.join('\n') + '\n');
  d.credits = {from: r3(cues.end(last) + 0.1), lines};
  // era names
  const N = o.names ?? {sets: {}, eras: [], neighbours: {}};
  const names = {sets: N.sets, ctx: Object.fromEntries(Object.entries(N.neighbours ?? {}).map(([k, v]) => [k.replace(/^ctx:/, ''), v])),
    eras: N.eras.map((e: any) => ({from: r3(e.from === 'start' ? 0 : cues.resolve(0, e.from).t), set: e.set, extra: e.extra, neighbours: !!e.neighbours}))};
  // assemble film.json (element keys kept apart for the audit feedback)
  const keys: Record<string, string[]> = {};
  const clean = (name: string) => d.F[name].map((e: any) => { (keys[name] ??= []).push(e._k ?? ''); const {_k, _g, _fixedSide, _ov, _adapted, _keep, _posFixed, ...r} = e; return r; });
  const film = {
    meta: {title: o.title, slug: o.slug, total: cues.total, generated: new Date().toISOString(), director: 'factory/director v1',
      beats: d.beats.length, camera_keys: d.keys.length, drifts},
    col: d.COL, iso: d.ISO, flag_code: d.FLAG, flag_aspect: o.flag_aspect ?? {}, name: {},
    camera: [...d.keys].sort((a, b) => a.t - b.t).map(({src, kind, ...k}) => k), fills: clean('fills'), strokes: clean('strokes'), lines: clean('lines'), rings: clean('rings'),
    labels: clean('labels'), markers: clean('markers'), flags: clean('flags'), flag_hide: d.F.flag_hide, cards: clean('cards'),
    clips: clean('clips'), doll_labels: d.F.doll_labels, music: d.F.music, sfx: d.F.sfx, globe: null, opening: d.opening,
    banners: clean('banners'), icons: clean('icons'), dots: d.F.dots, dot_shows: clean('dot_shows'), docs: clean('docs'), cutouts: clean('cutouts'),
    numerals: clean('numerals'), arrows: clean('arrows'), tags: clean('tags'), chain: d.chain, title: d.title, credits: d.credits,
    star: d.star, star_targets: d.star_targets, depth_ids: Object.entries(assets.archive ?? {}).filter(([, v]: any) => v.depth).map(([k]) => k),
    focus: Object.fromEntries(Object.values(assets.archive ?? {}).filter((v: any) => v.focus).map((v: any) => [v.file, [...v.focus, v.aspect ?? 1.5]])),
    lights: d.lights, city_lights: d.city_lights, names, extra_cities: d.gaz.extraCities, keys,
    camera_src: [...d.keys].sort((a, b) => a.t - b.t).map((k) => `${k.src ?? ''}|${k.kind ?? ''}`),
  };
  fs.mkdirSync(path.dirname(out), {recursive: true});
  fs.writeFileSync(out, JSON.stringify(film));
  const rep = [`DIRECTOR REPORT - ${o.title}`, `beats ${d.beats.length} · camera keys ${d.keys.length} (drifts ${drifts}) · fills ${film.fills.length} · labels ${film.labels.length} · flags ${film.flags.length}`,
    `banners ${film.banners.length} · icons ${film.icons.length} · cards ${film.cards.length} · docs ${film.docs.length} · portraits ${film.cutouts.length} · numerals ${film.numerals.length} · sfx ${film.sfx.length}`,
    `patches applied: ${Object.keys(patches).length}`, '', 'WARNINGS:', ...(d.warn.length ? d.warn : ['none']), '',
    'CAMERA:', ...d.keys.map((k) => `${k.t.toFixed(2).padStart(7)}  ${(k.kind ?? '').padEnd(5)} ${k.lon !== undefined ? `lon ${k.lon} lat ${k.lat}` : `x ${k.x} y ${k.y}`} w ${k.w} tilt ${k.tilt} dur ${k.dur}  ${k.src ?? ''}`)];
  fs.mkdirSync(path.join(orderDir, 'out'), {recursive: true});
  fs.writeFileSync(path.join(orderDir, 'out/director_report.txt'), rep.join('\n') + '\n');
  console.log(rep.slice(0, 8).join('\n'));
  console.log('film.json ->', out);
} catch (e: any) {
  if (e instanceof DirectorError) { console.error('ORDER ERROR: ' + e.message); process.exit(2); }
  throw e;
}
