// v2 elements: banners on poles with archival photos, 3D icon sprites, homeland dots, curved arrows,
// big numerals, document card (Ken Burns), cut-out portrait with parallax, smoky title.
import React from 'react';
import {AbsoluteFill, Img, staticFile, spring} from 'remotion';
import {project, px, CamState, KM_PER_PX} from '../lib/proj';
import {clamp, env, ease, easeOut, prog, lerp} from '../lib/anim';
import {FONTS} from '../fonts';
import {iconLayout, bannerSizeK} from '../lib/layout';
import {BANNERS, ICONS, DOTS, DOT_COL, DOT_SHOWS, DOCS, CUTOUTS, NUMERALS, ARROWS, TITLE, TAGS, CHAIN, CREDITS, Banner, STAR, STAR_TARGETS, DEPTH_IDS, LIGHTS, CITY_LIGHTS} from '../v2';
import * as echarts from 'echarts';

const FPS = 30;
const sp = (t: number, from: number, cfg = {damping: 10, mass: 0.6, stiffness: 140}) =>
  t < from ? 0 : spring({frame: (t - from) * FPS, fps: FPS, config: cfg});
export const hash = (i: number, n: number) => { const x = Math.sin(i * 12.9898 + n * 78.233) * 43758.5453; return x - Math.floor(x); };
export const PARCH = 'linear-gradient(180deg,#f4e8c8 0%,#e6d3a6 55%,#d2bb86 100%)';
const WOOD = 'linear-gradient(90deg,#2e1b0f 0%,#6b4428 30%,#a77a4c 50%,#7a5130 68%,#2e1b0f 100%)';
const onScreen = (q: {x: number; y: number}, m = 260) => q.x > -m && q.x < 1920 + m && q.y > -m && q.y < 1080 + m * 1.6;

// ---------------- banner on a pole ----------------
const depthId = (img: string) => { const id = img.replace(/^archive\//, '').replace(/\.(jpg|jpeg|png)$/i, ''); return DEPTH_IDS.includes(id) ? id : null; };
/** v3 2.5D parallax: the photo (background) and its near layer (archive/<id>_fg.png, cut by the depth map) drift apart */
const DepthPhoto: React.FC<{img: string; w: number; h?: number; p: number; filter?: string}> = ({img, w, h, p, filter}) => {
  const id = depthId(img);
  const st = (k: number, dx: number, dy: number): React.CSSProperties => ({position: 'absolute', left: 0, top: 0, width: w, height: h ?? 'auto',
    objectFit: 'cover', filter, transform: `scale(${k}) translate(${dx}px, ${dy}px)`, transformOrigin: '50% 50%'});
  return (
    <>
      <Img src={staticFile(img)} style={{...st(id ? 1.05 + 0.025 * p : 1, id ? -5 * p : 0, id ? -1.5 * p : 0), position: h ? 'absolute' : 'relative', display: 'block'}} />
      {id ? <Img src={staticFile(`archive/${id}_fg.png`)} style={st(1.05 + 0.08 * p, 5 * p, 1.6 * p)} /> : null}
    </>
  );
};

const ClothFace: React.FC<{img: string; W: number; H: number; p?: number}> = ({img, W, H, p = 0}) => (
  <div style={{position: 'absolute', left: 0, top: 0, width: W, height: H + 12}}>
    <div style={{position: 'absolute', left: 0, top: 0, width: W, height: H, background: 'linear-gradient(180deg,#922b2b,#5c1414)',
      boxShadow: 'inset 0 0 0 3px #d8b25a, inset 0 0 0 6px #5c1414, inset 0 0 0 7px #d8b25a'}}>
      <div style={{position: 'absolute', left: 11, top: 11, width: W - 22, height: H - 22, overflow: 'hidden'}}>
        <DepthPhoto img={img} w={W - 22} h={H - 22} p={p} filter="sepia(0.12) contrast(1.06) saturate(0.95)" />
      </div>
      <div style={{position: 'absolute', left: 11, top: 11, width: W - 22, height: H - 22, boxShadow: 'inset 0 0 14px rgba(0,0,0,0.6)'}} />
    </div>
    <div style={{position: 'absolute', left: 4, top: H, width: W - 8, height: 12,
      background: 'repeating-linear-gradient(90deg,#e2bf6a 0 3px,#9c7a2e 3px 5px,transparent 5px 8px)'}} />
  </div>
);

export const BannerOnPole: React.FC<{b: Banner; x: number; y: number; s: number; t: number}> = ({b, x, y, s, t}) => {
  const k = sp(t, b.from);
  const out = clamp((b.to - t) / 0.45);
  const o = clamp((t - b.from) / 0.1) * out;
  if (o <= 0) return null;
  const unfurl = easeOut(prog(t, b.from + 0.2, 0.6));
  const S = s * (b.size ?? 1) * (0.5 + 0.5 * k) * (0.8 + 0.2 * out);
  const poleH = 236, W = 204, H = 142, bar = 228, N = 10, top = -poleH;
  const sway = Math.sin(t * 1.25 + x * 0.013) * 1.2 + (b.lean ?? 0);
  const strips = Array.from({length: N}, (_, i) => {
    const ph = t * 5.0 - i * 0.6 + x * 0.004;
    const sy = 1 + 0.04 * Math.sin(ph) * (0.35 + (0.65 * i) / N);
    const br = 1 + 0.11 * Math.cos(ph);
    return (
      <div key={i} style={{position: 'absolute', left: (i * W) / N, top: 0, width: W / N + 0.9, height: H + 12, overflow: 'hidden',
        transformOrigin: '50% 0', transform: `scaleY(${sy * unfurl})`, filter: `brightness(${br.toFixed(3)})`}}>
        <div style={{position: 'absolute', left: (-i * W) / N, top: 0}}><ClothFace img={b.img} W={W} H={H} p={prog(t, b.from, Math.max(0.5, b.to - b.from))} /></div>
      </div>
    );
  });
  const L = poleH * 0.62 * S * clamp(k);
  return (
    <div style={{position: 'absolute', left: 0, top: 0, opacity: o}}>
      {/* cast shadow on the map (light from upper-left) */}
      <div style={{position: 'absolute', left: x, top: y - 2.5 * S, width: L, height: 5 * S, transformOrigin: '0 50%', transform: 'rotate(24deg)',
        background: 'linear-gradient(90deg, rgba(0,0,0,0.45), rgba(0,0,0,0.12))', filter: `blur(${1.5 * S}px)`, borderRadius: 3}} />
      <div style={{position: 'absolute', left: x + Math.cos(0.42) * L * 0.78 - W * 0.32 * S, top: y + Math.sin(0.42) * L * 0.78 - H * 0.1 * S,
        width: W * 0.64 * S, height: H * 0.2 * S, borderRadius: '50%', background: 'rgba(0,0,0,0.32)', filter: `blur(${6 * S}px)`, opacity: unfurl}} />
      <div style={{position: 'absolute', left: x - 13 * S, top: y - 4 * S, width: 26 * S, height: 8 * S, borderRadius: '50%',
        background: 'radial-gradient(rgba(40,26,14,0.75), rgba(40,26,14,0))'}} />
      <div style={{position: 'absolute', left: x, top: y, width: 0, height: 0, transformOrigin: '0 0', transform: `scale(${S}) rotate(${sway * 0.35}deg)`,
        filter: 'drop-shadow(0 5px 7px rgba(0,0,0,0.45))'}}>
        <div style={{position: 'absolute', left: -3.5, top, width: 7, height: poleH, background: WOOD, borderRadius: 3}} />
        <div style={{position: 'absolute', left: -bar / 2, top: top + 6, width: bar, height: 7, borderRadius: 3,
          background: 'linear-gradient(180deg,#a77a4c,#5a381f)'}} />
        {[-bar / 2 - 7, bar / 2 - 5].map((fx, i) => (
          <div key={i} style={{position: 'absolute', left: fx, top: top + 3, width: 12, height: 12, borderRadius: '50%',
            background: 'radial-gradient(circle at 35% 35%, #fff2b8, #d8b25a 45%, #7d5c18)'}} />
        ))}
        <div style={{position: 'absolute', left: -6, top: top - 14, width: 12, height: 16, borderRadius: '50% 50% 30% 30%',
          background: 'radial-gradient(circle at 35% 35%, #fff2b8, #d8b25a 45%, #7d5c18)'}} />
        <div style={{position: 'absolute', left: -W / 2, top: top + 12, width: W, height: H + 12, transformOrigin: '50% 0',
          transform: `skewX(${(sway * 0.8).toFixed(2)}deg)`}}>{strips}</div>
        <div style={{position: 'absolute', left: -112, top: top + 12 + H + 22, width: 224, height: b.sub ? 54 : 38, background: PARCH, borderRadius: 4,
          boxShadow: '0 3px 6px rgba(0,0,0,0.4), inset 0 0 0 1.5px rgba(90,60,30,0.55)', opacity: unfurl,
          transform: `translateY(${(1 - unfurl) * -10}px)`, textAlign: 'center'}}>
          <div style={{fontFamily: FONTS.head, fontWeight: 700, fontSize: 19, letterSpacing: '0.16em', color: '#3a2614', marginTop: 6}}>{b.title}</div>
          {b.sub ? <div style={{fontFamily: FONTS.serif, fontStyle: 'italic', fontWeight: 600, fontSize: 15, color: '#5a3d22', marginTop: -1}}>{b.sub}</div> : null}
        </div>
      </div>
    </div>
  );
};

// ---------------- 3D icon sprite (pops out of the map) ----------------
const IconSprite: React.FC<{name: string; az: number; x: number; y: number; s: number; t: number; from: number; to: number; dk?: number}> =
  ({name, az, x, y, s, t, from, to, dk = 1}) => {
    const k = sp(t, from, {damping: 8, mass: 0.6, stiffness: 150});
    const o = clamp((t - from) / 0.08) * clamp((to - t) / 0.4) * dk;
    if (o <= 0.004) return null;
    const L = iconLayout(name, az, x, y, s);     // v4: sized by visible content, base on the anchor
    const bob = Math.sin((t - from) * 2.2) * 3 * s;
    const sw = L.cw * 0.86;
    return (
      <div style={{position: 'absolute', left: 0, top: 0, opacity: o}}>
        <div style={{position: 'absolute', left: x - sw / 2, top: L.by - sw * 0.07, width: sw, height: sw * 0.14, borderRadius: '50%',
          background: 'radial-gradient(ellipse at center, rgba(0,0,0,0.5) 0%, rgba(0,0,0,0.25) 45%, rgba(0,0,0,0) 72%)',
          transform: `scale(${Math.max(0, k)})`}} />
        <div style={{position: 'absolute', left: L.left, top: L.top + bob, width: L.size, height: L.size,
          transformOrigin: `${((x - L.left) / L.size) * 100}% ${((L.by - L.top) / L.size) * 100}%`, transform: `scale(${Math.max(0, k)})`}}>
          <Img src={staticFile(`icons/${name}_a${az}.png`)} style={{position: 'absolute', left: 0, top: 0, width: L.size, height: L.size,
            filter: 'drop-shadow(0 5px 7px rgba(0,0,0,0.38))'}} />
        </div>
      </div>
    );
  };

// ---------------- homeland dots ----------------
const HomelandDots: React.FC<{t: number; cam: CamState}> = ({t, cam}) => {
  const out: React.ReactNode[] = [];
  DOT_SHOWS.forEach((sh, si) => {
    if (t < sh.from || t > sh.to + 0.6) return;
    const fade = clamp((sh.to + 0.6 - t) / 0.6);
    let order = 0;
    sh.layers.forEach((layer, li) => {
      DOTS.filter((d) => d.layer === layer).forEach((d, di) => {
        const t0 = sh.from + li * (sh.stagger ?? 0.3) + di * 0.025;
        order++;
        if (t < t0) return;
        const [wx, wy] = px(d.lon, d.lat);
        const q = project(cam, wx, wy);
        if (!onScreen(q, 40)) return;
        const k = sp(t, t0, {damping: 9, mass: 0.4, stiffness: 180});
        const r = (layer === 0 ? 7 : layer === 1 ? 5.4 : 4.6) * clamp(Math.sqrt(cam.zoom / 0.24), 0.9, 1.6);
        const pr = clamp((t - t0) / 0.9);
        const col = DOT_COL[layer];
        out.push(
          <div key={`${si}_${d.n}`} style={{position: 'absolute', left: q.x, top: q.y, opacity: fade}}>
            {pr < 1 ? <div style={{position: 'absolute', left: -r * (1 + 3 * pr), top: -r * (1 + 3 * pr), width: 2 * r * (1 + 3 * pr),
              height: 2 * r * (1 + 3 * pr), borderRadius: '50%', border: `1.5px solid ${col}`, opacity: 1 - pr}} /> : null}
            <div style={{position: 'absolute', left: -r, top: -r, width: 2 * r, height: 2 * r, borderRadius: '50%', background: col,
              transform: `scale(${Math.max(0, k)})`, boxShadow: `0 0 ${r * 1.6}px ${col}, 0 0 0 1.5px rgba(12,18,24,0.85)`}} />
          </div>,
        );
      });
    });
  });
  return <>{out}</>;
};

/** screen-space v2 billboards (banners, icons, dots) for the map stage */

// ---------------- v3: the Soviet star shatters into 15 shards, one lands on each republic ----------------
const STAR_GEO = (() => {
  const C0: [number, number] = [960, 455], R = 150, r = 61;
  const V = Array.from({length: 10}, (_, i) => {
    const a = -Math.PI / 2 + (i * Math.PI) / 5, rr = i % 2 ? r : R;
    return [C0[0] + rr * Math.cos(a), C0[1] + rr * Math.sin(a)] as [number, number];
  });
  const tris: [number, number][][] = [];
  for (let i = 0; i < 10; i++) {
    const A = V[i], B = V[(i + 1) % 10];
    if (i % 2 === 0) {               // tip triangle -> split in two (10 + 5 = 15 shards)
      const M: [number, number] = [(C0[0] + A[0]) / 2, (C0[1] + A[1]) / 2];
      tris.push([M, A, B], [C0, M, B]);
    } else tris.push([C0, A, B]);
  }
  const shards = tris.map((p) => {
    const c: [number, number] = [(p[0][0] + p[1][0] + p[2][0]) / 3, (p[0][1] + p[1][1] + p[2][1]) / 3];
    return {c, rel: p.map(([x, y]) => [x - c[0], y - c[1]] as [number, number]), ang: Math.atan2(c[1] - C0[1], c[0] - C0[0])};
  });
  return {C0, V, shards};
})();

const StarShatter: React.FC<{t: number; cam: CamState}> = ({t, cam}) => {
  const s0 = STAR.from;
  if (t < s0 || t > s0 + 3.3) return null;
  const {C0, V, shards} = STAR_GEO;
  const pop = sp(t, s0, {damping: 11, mass: 0.6, stiffness: 160});
  const crack = clamp((t - s0 - 0.55) / 0.2);
  // targets on screen, matched to shards by angle around the star (paths do not cross much)
  const tg = STAR_TARGETS.map(([iso, lon, lat]) => {
    const [wx, wy] = px(lon, lat); const q = project(cam, wx, wy);
    return {iso, x: q.x, y: q.y, ang: Math.atan2(q.y - C0[1], q.x - C0[0])};
  });
  const sOrd = shards.map((s, i) => ({i, a: s.ang})).sort((p, q) => p.a - q.a).map((p) => p.i);
  const tOrd = tg.map((x, i) => ({i, a: x.ang})).sort((p, q) => p.a - q.a).map((p) => p.i);
  const match: number[] = []; sOrd.forEach((si, k) => (match[si] = tOrd[k]));
  const whole = t < s0 + 0.78;
  return (
    <svg style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}} width={1920} height={1080}>
      <defs>
        <radialGradient id="starG" cx="45%" cy="38%" r="70%"><stop offset="0%" stopColor="#ff5a4a" /><stop offset="55%" stopColor="#c8102e" /><stop offset="100%" stopColor="#6e0a12" /></radialGradient>
        <filter id="starGlow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
      </defs>
      {whole ? (
        <g transform={`translate(${C0[0]},${C0[1]}) scale(${Math.max(0, pop)}) translate(${-C0[0]},${-C0[1]})`} filter="url(#starGlow)">
          <polygon points={V.map((p) => p.join(',')).join(' ')} fill="url(#starG)" stroke="#f4cf73" strokeWidth={3} />
          {crack > 0 ? shards.map((s, i) => (
            <polyline key={i} points={[s.rel[0], s.rel[1], s.rel[2], s.rel[0]].map(([x, y]) => `${x + s.c[0]},${y + s.c[1]}`).join(' ')}
              fill="none" stroke="#ffe7a8" strokeWidth={1.6} opacity={crack} />
          )) : null}
        </g>
      ) : shards.map((s, i) => {
        const T = tg[match[i]];
        const t0 = s0 + 0.78 + (i % 5) * 0.045;
        const e = ease(clamp((t - t0) / 1.25));
        const mx = (s.c[0] + T.x) / 2, my = Math.min(s.c[1], T.y) - 200;
        const x = (1 - e) * (1 - e) * s.c[0] + 2 * (1 - e) * e * mx + e * e * T.x;
        const y = (1 - e) * (1 - e) * s.c[1] + 2 * (1 - e) * e * my + e * e * T.y;
        const rot = e * (i % 2 ? 300 : -300), sc = 1 - 0.72 * e;
        const land = clamp((t - t0 - 1.25) / 0.6);
        return (
          <g key={i}>
            {e < 1 ? <polygon points={s.rel.map(([px_, py_]) => `${px_},${py_}`).join(' ')} fill="url(#starG)" stroke="#f4cf73" strokeWidth={2}
              transform={`translate(${x},${y}) rotate(${rot}) scale(${sc})`} filter="url(#starGlow)" /> : null}
            {land > 0 && land < 1 ? <circle cx={T.x} cy={T.y} r={8 + 46 * land} fill="none" stroke="#ffd98a" strokeWidth={3 * (1 - land)} opacity={1 - land} /> : null}
          </g>
        );
      })}
    </svg>
  );
};


// ---------------- v3: the union at night - city lights go out one by one, then 15 nations light up ----------------
const CityLights: React.FC<{t: number; cam: CamState}> = ({t, cam}) => {
  const L = LIGHTS;
  if (t < L.from || t > L.lift1) return null;
  const dark = clamp((t - L.from) / 0.5) * (1 - clamp((t - L.lift0) / (L.lift1 - L.lift0)));
  const rz = clamp(Math.sqrt(cam.zoom / 0.3), 0.7, 1.5);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, rgba(3,7,16,0.62), rgba(2,4,10,0.82))', opacity: dark}} />
      {CITY_LIGHTS.map(([lon, lat, sz], i) => {
        const off = L.off0 + hash(i, 7) * (L.off1 - L.off0);
        if (t > off + 0.15) return null;
        const [wx, wy] = px(lon, lat); const q = project(cam, wx, wy);
        if (q.x < -40 || q.x > 1960 || q.y < -40 || q.y > 1120) return null;
        const flick = t > off - 0.28 ? 0.45 + 0.55 * Math.abs(Math.sin((t - off) * 47 + i * 1.7)) : 1;
        const on = clamp((off + 0.15 - t) / 0.15) * clamp((t - L.from - 0.1 - hash(i, 3) * 0.45) / 0.3);
        const r = (sz === 3 ? 30 : sz === 2 ? 19 : 11) * rz;
        return <div key={i} style={{position: 'absolute', left: q.x - r, top: q.y - r, width: 2 * r, height: 2 * r, borderRadius: '50%',
          opacity: on * flick * dark, mixBlendMode: 'screen',
          background: 'radial-gradient(circle, rgba(255,248,222,1) 0%, rgba(255,216,130,0.9) 16%, rgba(255,170,60,0.38) 42%, rgba(255,150,40,0) 70%)'}} />;
      })}
    </AbsoluteFill>
  );
};

export const V2Billboards: React.FC<{t: number; cam: CamState; dec?: (id: string) => number}> = ({t, cam, dec = () => 1}) => {
  const sizeK = bannerSizeK(cam.zoom);   // banners ~270-360 px wide
  const items: {y: number; el: React.ReactNode}[] = [];
  BANNERS.forEach((b, i) => {
    if (t < b.from || t > b.to) return;
    const [wx, wy] = px(b.at[0], b.at[1]);
    const q = project(cam, wx, wy);
    if (!onScreen(q)) return;
    const dk = dec('banner:' + i);
    if (dk <= 0.004) return;
    items.push({y: q.y, el: <div key={'b' + i} style={{position: 'absolute', left: 0, top: 0, opacity: dk}}><BannerOnPole b={b} x={q.x} y={q.y} s={sizeK * q.s} t={t} /></div>});
  });
  ICONS.forEach((ic, i) => {
    if (t < ic.from || t > ic.to) return;
    const [wx, wy] = px(ic.at[0], ic.at[1]);
    const q = project(cam, wx, wy);
    if (!onScreen(q)) return;
    items.push({y: q.y, el: <IconSprite key={'i' + i} name={ic.name} az={ic.az} x={q.x} y={q.y} s={(sizeK / 1.55) * q.s * (ic.size ?? 1)} t={t} from={ic.from} to={ic.to} dk={dec('icon:' + i)} />});
  });
  items.sort((a, b) => a.y - b.y);
  return <AbsoluteFill><HomelandDots t={t} cam={cam} /><BalticChain t={t} cam={cam} />{items.map((x) => x.el)}<StarShatter t={t} cam={cam} /><CityLights t={t} cam={cam} /></AbsoluteFill>;
};

// ---------------- curved growing arrows (world space, inside the map SVG) ----------------
export const ArrowsSvg: React.FC<{t: number; z: number}> = ({t, z}) => (
  <>
    {ARROWS.map((a, i) => {
      const o = env(t, a.t, a.to, 0.15, 0.6);
      if (o <= 0) return null;
      const [x0, y0] = px(a.a[0], a.a[1]), [x1, y1] = px(a.b[0], a.b[1]);
      const mx = (x0 + x1) / 2, my = (y0 + y1) / 2, dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy);
      const cx = mx - (dy / L) * L * (a.bend ?? 0.2), cy = my + (dx / L) * L * (a.bend ?? 0.2);
      const d = `M${x0},${y0} Q${cx},${cy} ${x1},${y1}`;
      const p = ease(prog(t, a.t, a.dur));
      const w = 5.5 / z;
      const ang = (Math.atan2(y1 - cy, x1 - cx) * 180) / Math.PI;
      const head = 22 / z;
      return (
        <g key={i} opacity={o}>
          <path d={d} fill="none" stroke="rgba(0,0,0,0.35)" strokeWidth={w * 1.6} transform={`translate(${2.5 / z},${3 / z})`}
            pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} strokeLinecap="round" />
          <path d={d} fill="none" stroke={a.color} strokeWidth={w * 3.2} opacity={0.25} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} strokeLinecap="round" />
          <path d={d} fill="none" stroke={a.color} strokeWidth={w} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} strokeLinecap="round" />
          {p > 0.97 ? <path d={`M0,0 L${-head},${-head * 0.55} L${-head * 0.72},0 L${-head},${head * 0.55} Z`} fill={a.color}
            transform={`translate(${x1},${y1}) rotate(${ang})`} opacity={clamp((p - 0.97) / 0.03)} /> : null}
        </g>
      );
    })}
  </>
);

// ---------------- screen overlays: numerals, document, cut-out, title ----------------
const Numerals: React.FC<{t: number}> = ({t}) => (
  <>
    {NUMERALS.map((n, i) => {
      const o = env(t, n.from, n.to, 0.12, 0.18);
      if (o <= 0) return null;
      const k = easeOut(prog(t, n.from, 0.45));
      return (
        <div key={i} style={{position: 'absolute', left: 0, width: 1920, top: n.y ?? 250, textAlign: 'center', opacity: o,
          transform: `scale(${lerp(1.3, 1, k)})`, filter: `blur(${(1 - k) * 10}px)`}}>
          <span style={{fontFamily: FONTS.head, fontWeight: 800, fontSize: n.size ?? 250, letterSpacing: '0.04em',
            background: 'linear-gradient(180deg,#fff6d6 0%,#f0cf7a 45%,#b8892f 100%)', WebkitBackgroundClip: 'text', color: 'transparent',
            filter: 'drop-shadow(0 6px 18px rgba(0,0,0,0.65))'}}>{n.text}</span>
          {n.sub ? <div style={{fontFamily: FONTS.serif, fontStyle: 'italic', fontWeight: 600, fontSize: 40, color: '#F4EBD6', letterSpacing: '0.06em',
            marginTop: -18, textShadow: '0 2px 12px rgba(0,0,0,0.9)', opacity: clamp((t - n.from - 0.25) / 0.35)}}>{n.sub}</div> : null}
        </div>
      );
    })}
  </>
);

const DocCard: React.FC<{t: number}> = ({t}) => (
  <>
    {DOCS.map((d, i) => {
      if (t < d.from || t > d.to) return null;
      const k = sp(t, d.from, {damping: 14, mass: 0.8, stiffness: 110});
      const out = clamp((d.to - t) / 0.4);
      const w = d.w ?? 420, kb = 1 + 0.07 * prog(t, d.from, d.to - d.from);
      const left = d.side === 'l' ? 130 : 1920 - 130 - w;
      return (
        <div key={i} style={{position: 'absolute', left, top: 120, width: w, opacity: clamp(k * 2) * out,
          transform: `translateX(${(1 - k) * (d.side === 'l' ? -700 : 700)}px) rotate(${d.side === 'l' ? -2.5 : 2.5}deg)`}}>
          <div style={{padding: 14, background: PARCH, borderRadius: 3, boxShadow: '0 18px 40px rgba(0,0,0,0.6), inset 0 0 0 1.5px rgba(90,60,30,0.5)'}}>
            <div style={{overflow: 'hidden', borderRadius: 2, position: 'relative'}}>
              {depthId(d.img) ? <DepthPhoto img={d.img} w={w - 28} p={prog(t, d.from, d.to - d.from)} />
                : <Img src={staticFile(d.img)} style={{width: w - 28, display: 'block', transform: `scale(${kb})`, transformOrigin: '50% 30%'}} />}
            </div>
            {d.sigs ? <div style={{display: 'flex', justifyContent: 'space-between', gap: 6, marginTop: 10}}>
              {d.sigs.map((g, j) => {
                const s0 = d.from + 0.55 + j * 0.85, r = clamp((t - s0) / 0.8), x = r * 112 - 8;
                const m = `linear-gradient(90deg, #000 ${x}%, transparent ${x + 8}%)`;
                return (
                  <div key={j} style={{flex: 1, textAlign: 'center'}}>
                    <div style={{height: 46, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                      <Img src={staticFile(g.img)} style={{maxHeight: 42, maxWidth: '100%', objectFit: 'contain', mixBlendMode: 'multiply',
                        WebkitMaskImage: m, maskImage: m} as React.CSSProperties} />
                    </div>
                    <div style={{borderTop: '1px solid rgba(90,60,30,0.45)', paddingTop: 3, fontFamily: FONTS.body, fontWeight: 700, fontSize: 10.5,
                      letterSpacing: '0.12em', color: '#5a3d22', opacity: clamp((t - s0 - 0.45) / 0.3)}}>{g.name}</div>
                  </div>
                );
              })}
            </div> : null}
          </div>
          {d.cap ? <div style={{marginTop: 14, textAlign: 'center', fontFamily: FONTS.head, fontWeight: 700, fontSize: 22, letterSpacing: '0.18em',
            color: '#F6E7C1', textShadow: '0 2px 8px rgba(0,0,0,0.9)'}}>{d.cap}</div> : null}
        </div>
      );
    })}
  </>
);

const CutoutCard: React.FC<{t: number}> = ({t}) => (
  <>
    {CUTOUTS.map((c, i) => {
      if (t < c.from || t > c.to) return null;
      const k = sp(t, c.from, {damping: 15, mass: 0.9, stiffness: 100});
      const out = clamp((c.to - t) / 0.45);
      const drift = prog(t, c.from, c.to - c.from);
      const H = 900;
      const right = c.side === 'r';
      return (
        <div key={i} style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, opacity: clamp(k * 1.6) * out}}>
          <div style={{position: 'absolute', [right ? 'right' : 'left']: 40 - drift * 18, bottom: -40, height: H,
            transform: `translateY(${(1 - k) * 160}px) scale(${1 + 0.04 * drift})`, transformOrigin: '50% 100%',
            filter: 'drop-shadow(0 0 22px rgba(255,214,140,0.28)) drop-shadow(0 20px 30px rgba(0,0,0,0.7))'} as React.CSSProperties}>
            <Img src={staticFile(c.img)} style={{height: H}} />
          </div>
          <div style={{position: 'absolute', [right ? 'right' : 'left']: 90, bottom: 70, padding: '10px 22px', background: PARCH, borderRadius: 4,
            boxShadow: '0 6px 16px rgba(0,0,0,0.55)', transform: `translateY(${(1 - easeOut(prog(t, c.from + 0.35, 0.5))) * 40}px)`,
            opacity: clamp((t - c.from - 0.35) / 0.3)} as React.CSSProperties}>
            <div style={{fontFamily: FONTS.head, fontWeight: 700, fontSize: 30, letterSpacing: '0.16em', color: '#3a2614'}}>{c.name}</div>
            {c.sub ? <div style={{fontFamily: FONTS.serif, fontStyle: 'italic', fontWeight: 600, fontSize: 20, color: '#5a3d22'}}>{c.sub}</div> : null}
          </div>
        </div>
      );
    })}
  </>
);

const SMOKE = Array.from({length: 9}, (_, i) => ({x: hash(i, 1) * 1920, y: 300 + hash(i, 2) * 520, r: 380 + hash(i, 3) * 420,
  vx: (hash(i, 4) - 0.5) * 50, vy: -12 - hash(i, 5) * 22, o: 0.07 + hash(i, 6) * 0.09}));

const TitleSmoke: React.FC<{t: number}> = ({t}) => {
  const o = env(t, TITLE.from, TITLE.to, 0.6, 0.7);
  if (o <= 0) return null;
  const tt = t - TITLE.from;
  return (
    <AbsoluteFill style={{opacity: o}}>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 50%, rgba(8,12,18,0.55) 0%, rgba(4,6,10,0.88) 75%)'}} />
      {SMOKE.map((s, i) => (
        <div key={i} style={{position: 'absolute', left: s.x + s.vx * tt - s.r, top: s.y + s.vy * tt - s.r, width: 2 * s.r, height: 2 * s.r,
          borderRadius: '50%', background: 'radial-gradient(circle, rgba(220,226,232,1) 0%, rgba(220,226,232,0) 70%)',
          opacity: s.o * clamp(tt / 1.5), filter: 'blur(30px)'}} />
      ))}
      <div style={{position: 'absolute', left: 0, top: 330, width: 1920, textAlign: 'center'}}>
        {TITLE.lines.map((l, i) => {
          const k = easeOut(prog(t, l.from, 0.9));
          if (t < l.from) return <div key={i} style={{height: i === 2 ? 118 : 92}} />;
          const big = i === 2;
          const parts = l.hi ? l.text.split(l.hi) : [l.text];
          const hk = l.hiAt !== undefined ? sp(t, l.hiAt, {damping: 9, mass: 0.5, stiffness: 160}) : 1;
          return (
            <div key={i} style={{height: big ? 118 : 92, opacity: k, filter: `blur(${(1 - k) * 14}px)`,
              letterSpacing: `${lerp(0.42, big ? 0.12 : 0.2, k)}em`, fontFamily: FONTS.head, fontWeight: 700, fontSize: big ? 96 : 66,
              color: '#F3E3B9', textShadow: '0 4px 20px rgba(0,0,0,0.8)'}}>
              {parts[0]}
              {l.hi ? <span style={{display: 'inline-block', color: '#E0484F', transform: `scale(${0.6 + 0.4 * Math.max(0, hk)})`,
                textShadow: '0 0 26px rgba(224,72,79,0.55), 0 4px 18px rgba(0,0,0,0.8)'}}>{l.hi}</span> : null}
              {l.hi ? parts[1] : null}
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', left: 760, width: 400, top: 650, height: 2, opacity: clamp((t - TITLE.lines[2].from) / 0.8),
        background: 'linear-gradient(90deg, rgba(226,191,106,0), rgba(226,191,106,0.9), rgba(226,191,106,0))'}} />
    </AbsoluteFill>
  );
};

const Credits: React.FC<{t: number}> = ({t}) => t < CREDITS.from ? null : (
  <div style={{position: 'absolute', left: 160, right: 160, bottom: 46, opacity: clamp((t - CREDITS.from) / 0.8), textAlign: 'center',
    fontFamily: FONTS.serif, fontSize: 17, lineHeight: 1.45, color: 'rgba(240,232,214,0.78)', letterSpacing: '0.02em'}}>
    {CREDITS.lines.map((l, i) => <div key={i} style={{marginTop: i ? 6 : 0}}>{l}</div>)}
  </div>
);

export const V2Overlays: React.FC<{t: number}> = ({t}) => (
  <AbsoluteFill>
    <Tags t={t} />
    <Credits t={t} />
    <Numerals t={t} />
    <DocCard t={t} />
    <CutoutCard t={t} />
    <TitleSmoke t={t} />
  </AbsoluteFill>
);
// ---------------- the Baltic Way: a human chain drawn with Apache ECharts (SSR) along the real route ----------------
const PERSON = 'path://M5,0 C6.4,0 7.5,1.1 7.5,2.5 C7.5,3.9 6.4,5 5,5 C3.6,5 2.5,3.9 2.5,2.5 C2.5,1.1 3.6,0 5,0 Z M1.5,6 L8.5,6 L10,12 L8.6,12 L7.4,8.5 L7.4,20 L5.6,20 L5,13.5 L4.4,20 L2.6,20 L2.6,8.5 L1.4,12 L0,12 Z';
const BalticChain: React.FC<{t: number; cam: CamState}> = ({t, cam}) => {
  const o = env(t, CHAIN.from, CHAIN.to, 0.3, 0.5);
  if (o <= 0) return null;
  const P = CHAIN.pts.map(([lon, lat]) => { const [wx, wy] = px(lon, lat); const q = project(cam, wx, wy); return [q.x, q.y]; });
  const seg = P.slice(1).map((p, i) => Math.hypot(p[0] - P[i][0], p[1] - P[i][1]));
  const total = seg.reduce((a, b) => a + b, 0);
  let left = total * ease(prog(t, CHAIN.from, CHAIN.dur));
  const vis: number[][] = [P[0]];
  for (let i = 0; i < seg.length && left > 0; i++) {
    const f = Math.min(1, left / seg[i]); vis.push([lerp(P[i][0], P[i + 1][0], f), lerp(P[i][1], P[i + 1][1], f)]); left -= seg[i];
  }
  const people: number[][] = [];
  const step = Math.max(9, total / 420);
  for (let i = 1, acc = 0; i < vis.length; i++) {
    const L = Math.hypot(vis[i][0] - vis[i - 1][0], vis[i][1] - vis[i - 1][1]);
    for (; acc < L; acc += step) people.push([lerp(vis[i - 1][0], vis[i][0], acc / L), lerp(vis[i - 1][1], vis[i][1], acc / L) - 7]);
    acc -= L;
  }
  const chart = echarts.init(null as any, null as any, {renderer: 'svg', ssr: true, width: 1920, height: 1080});
  chart.setOption({
    animation: false, backgroundColor: 'transparent',
    grid: {left: 0, right: 0, top: 0, bottom: 0},
    xAxis: {type: 'value', min: 0, max: 1920, show: false}, yAxis: {type: 'value', min: 0, max: 1080, inverse: true, show: false},
    series: [
      {type: 'line', data: vis, smooth: 0.3, symbol: 'none', lineStyle: {width: 10, color: 'rgba(255,214,120,0.28)'}},
      {type: 'line', data: vis, smooth: 0.3, symbol: 'none', lineStyle: {width: 3, color: '#FFE3A0', shadowBlur: 12, shadowColor: '#FFC24A'}},
      {type: 'scatter', data: people, symbol: PERSON, symbolSize: [8, 15], itemStyle: {color: '#FFF6DD', borderColor: 'rgba(40,20,0,0.6)', borderWidth: 0.6}},
    ],
  } as any);
  const svg = chart.renderToSVGString();
  chart.dispose();
  return <div style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, opacity: o}} dangerouslySetInnerHTML={{__html: svg}} />;
};

// ---------------- parchment plaques (Stalin's rules, the secession law) ----------------
const Tags: React.FC<{t: number}> = ({t}) => (
  <>
    {TAGS.map((g, i) => {
      if (t < g.from || t > g.to + 0.4) return null;
      const k = sp(t, g.from, {damping: 11, mass: 0.7, stiffness: 150});
      const out = clamp((g.to + 0.4 - t) / 0.4);
      const W = g.num ? 700 : 500;
      const cx = g.slot === undefined ? 960 : 960 + (g.slot - 1) * 560;
      const swing = Math.sin((t - g.from) * 3.1) * 2.2 * Math.exp(-(t - g.from) * 1.4);
      return (
        <div key={i} style={{position: 'absolute', left: cx - W / 2, top: 852 + (1 - k) * -60, width: W, opacity: clamp(k * 2) * out,
          transformOrigin: '50% -40px', transform: `rotate(${swing}deg)`}}>
          <div style={{background: PARCH, borderRadius: 6, padding: '14px 26px', display: 'flex', alignItems: 'center', gap: 20,
            boxShadow: '0 10px 26px rgba(0,0,0,0.55), inset 0 0 0 2px rgba(90,60,30,0.55), inset 0 0 26px rgba(120,80,30,0.25)'}}>
            {g.num ? <div style={{width: 66, height: 66, borderRadius: '50%', flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'radial-gradient(circle at 38% 35%, #c2453f, #7d1a17 70%)', boxShadow: '0 3px 8px rgba(0,0,0,0.45), inset 0 0 0 3px rgba(255,210,160,0.25)',
              fontFamily: FONTS.head, fontWeight: 800, fontSize: 30, color: '#F6E3C0'}}>{g.num}</div> : null}
            <div style={{flex: 1, textAlign: g.num ? 'left' : 'center', fontFamily: FONTS.head, fontWeight: 700, fontSize: g.num ? 34 : 30,
              letterSpacing: '0.12em', color: '#3a2614'}}>{g.text}</div>
          </div>
        </div>
      );
    })}
  </>
);
export {KM_PER_PX};
