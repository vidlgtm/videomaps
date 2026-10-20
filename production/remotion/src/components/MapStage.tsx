import React from 'react';
import {AbsoluteFill, Img, staticFile, spring} from 'remotion';
import geo from '../data/geo.json';
import {px, project, cssTransform, meridian, KM_PER_PX, WORLD_W, WORLD_H, PERSP, CamState} from '../lib/proj';
import {env, clamp, ease, lerp, prog, easeOut} from '../lib/anim';
import {CAMERA, CamKey, FILLS, STROKES, LABELS, MARKERS, FLAGS, FLAG_HIDE, LINES, RINGS, ISO15, FLAG_CODE, COL} from '../script';
import {FONTS} from '../fonts';
import hd from '../data/hd_index.json';
import {V2Billboards, ArrowsSvg} from './V2';

const G: any = geo;
type P = {d: string; label: [number, number]; bbox?: number[]};
export const PATHS: Record<string, P> = {};
G.republics.forEach((r: any) => (PATHS['rep:' + r.id] = r));
Object.entries(G.shapes).forEach(([k, v]: any) => (PATHS['shape:' + k] = v));
G.rus_republics.forEach((r: any) => (PATHS['rr:' + r.id] = r));
G.breakaway.forEach((r: any) => (PATHS['brk:' + r.id] = r));
G.rivers.forEach((r: any) => (PATHS['river:' + r.id] = r));
PATHS['frontier'] = G.shapes.ussr_frontier;
export const anchor = (id: string | [number, number]): [number, number] =>
  Array.isArray(id) ? px(id[0], id[1]) : (PATHS[id]?.label as [number, number]) ?? [0, 0];

// ---------------- camera ----------------
function keyState(k: CamKey): CamState {
  const [x, y] = k.x !== undefined ? [k.x, k.y as number] : px(k.lon as number, k.lat as number);
  const zoom = 1920 / (k.w / KM_PER_PX);
  const rot = k.lon !== undefined ? (k.rotK ?? 0.72) * meridian(k.lon) : 0;
  return {x, y, zoom, tilt: k.tilt ?? 0, rot};
}
const STATES = CAMERA.map(keyState);
function stateAt(t: number, upto = CAMERA.length - 1): CamState {
  let i = upto;
  while (i > 0 && CAMERA[i].t > t) i--;
  const k = CAMERA[i], to = STATES[i], dur = k.dur ?? 2.2;
  const drift = (s: CamState, since: number) => ({...s, zoom: s.zoom * (1 + Math.min(0.07, 0.0045 * Math.max(0, since)))});
  if (i === 0) return drift(to, t - k.t);
  const from = stateAt(k.t, i - 1);
  const p = clamp((t - k.t) / dur);
  if (p >= 1) return drift(to, t - k.t - dur);
  const e = ease(p);
  let zoom = Math.exp(lerp(Math.log(from.zoom), Math.log(to.zoom), e));
  const dist = Math.hypot(to.x - from.x, to.y - from.y) * Math.min(from.zoom, to.zoom);
  if (dist > 1500) zoom *= 1 - 0.32 * Math.sin(Math.PI * e) * clamp((dist - 1500) / 3000);
  return {x: lerp(from.x, to.x, e), y: lerp(from.y, to.y, e), zoom, tilt: lerp(from.tilt, to.tilt, e), rot: lerp(from.rot, to.rot, e)};
}
/** inverse of project(): screen px -> world px on the map plane */
function unproject(c: CamState, sx: number, sy: number): [number, number] {
  const D = Math.PI / 180, r = c.rot * D, tl = c.tilt * D, a = sy - 540;
  const Y1 = (a * PERSP) / (PERSP * Math.cos(tl) + a * Math.sin(tl));
  const k = PERSP / (PERSP - Y1 * Math.sin(tl));
  const X1 = (sx - 960) / k;
  const X0 = X1 * Math.cos(r) + Y1 * Math.sin(r), Y0 = -X1 * Math.sin(r) + Y1 * Math.cos(r);
  return [X0 / c.zoom + c.x, Y0 / c.zoom + c.y];
}
/** keep the camera inside the basemap canvas: shift, and zoom in if the view is larger than the canvas */
function clampCam(c: CamState): CamState {
  let s = {...c};
  const M = 6;
  for (let it = 0; it < 6; it++) {
    const pts = [[-M, -M], [1920 + M, -M], [-M, 1080 + M], [1920 + M, 1080 + M], [960, -M], [960, 1080 + M], [-M, 540], [1920 + M, 540]]
      .map(([x, y]) => unproject(s, x, y));
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const spanX = maxX - minX, spanY = maxY - minY;
    if (spanX > WORLD_W || spanY > WORLD_H) { s = {...s, zoom: s.zoom * Math.max(spanX / WORLD_W, spanY / WORLD_H) * 1.01}; continue; }
    let dx = 0, dy = 0;
    if (minX < 0) dx = -minX; else if (maxX > WORLD_W) dx = WORLD_W - maxX;
    if (minY < 0) dy = -minY; else if (maxY > WORLD_H) dy = WORLD_H - maxY;
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) break;
    s = {...s, x: s.x + dx, y: s.y + dy};
  }
  return s;
}
export const cameraAt = (t: number) => clampCam(stateAt(t));

// ---------------- world layers ----------------
const pulseK = (t: number) => 0.72 + 0.28 * Math.sin((2 * Math.PI * t) / 1.7);
const HATCH_COLORS = Array.from(new Set(FILLS.filter((f) => f.hatch).map((f) => f.color)));

const WorldSvg: React.FC<{t: number; cam: CamState}> = ({t, cam}) => {
  const z = cam.zoom;
  const fills = FILLS.map((f, i) => {
    const p = PATHS[f.id];
    const o = env(t, f.from, f.to, f.fi ?? 0.8, f.fo ?? 0.8) * (f.op ?? 0.6) * (f.pulse ? pulseK(t) : 1);
    if (!p || o <= 0.002) return null;
    const glow = !f.hatch && f.id !== 'shape:ussr_1991_soft';
    return (
      <g key={'f' + i} opacity={o}>
        <path d={p.d} fill={f.hatch ? `url(#hatch${HATCH_COLORS.indexOf(f.color)})` : f.color} fillRule="evenodd" />
        {glow ? <>
          <clipPath id={'fc' + i}><path d={p.d} fillRule="evenodd" /></clipPath>
          <path d={p.d} fill="none" stroke={f.color} strokeWidth={16 / z} opacity={0.6} clipPath={`url(#fc${i})`} />
          <path d={p.d} fill="none" stroke="#ffffff" strokeWidth={3.2 / z} opacity={0.32} clipPath={`url(#fc${i})`} />
        </> : null}
      </g>
    );
  });
  const strokes = STROKES.flatMap((s, i) => {
    const o = env(t, s.from, s.to, 0.6, 0.8) * (s.op ?? 1);
    if (o <= 0.002) return [];
    const ids = s.id === 'borders' ? ISO15.map((x) => 'rep:' + x) : [s.id];
    const drawP = s.draw ? ease(prog(t, s.from, s.draw)) : 1;
    return ids.map((id, j) => {
      const p = PATHS[id];
      if (!p) return null;
      const common: any = {d: p.d, fill: 'none', strokeLinejoin: 'round', strokeLinecap: 'round'};
      const dash = s.draw && drawP < 1 ? {pathLength: 1, strokeDasharray: 1, strokeDashoffset: 1 - drawP} :
        s.dash ? {strokeDasharray: `${6 / z} ${5 / z}`} : {};
      return (
        <g key={`s${i}_${j}`} opacity={o}>
          {s.glow ? <path {...common} {...dash} stroke={s.color} strokeWidth={(s.width * 5) / z} opacity={0.22} /> : null}
          {!s.dash ? <path {...common} {...dash} stroke="rgba(0,0,0,0.38)" strokeWidth={(s.width * 1.5) / z} transform={`translate(${1.6 / z},${2.2 / z})`} /> : null}
          <path {...common} {...dash} stroke={s.color} strokeWidth={s.width / z} />
        </g>
      );
    });
  });
  const lines = LINES.map((l, i) => {
    const o = env(t, l.from, l.to ?? 1e9, 0.3, 0.8);
    if (o <= 0) return null;
    const pts = l.pts.map(([lo, la]) => px(lo, la));
    const d = 'M' + pts.map((q) => q.join(',')).join('L');
    const dp = ease(prog(t, l.from, l.dur));
    const flow = l.dash ? {strokeDasharray: `${10 / z} ${8 / z}`, strokeDashoffset: (-t * 40) / z} : {};
    return (
      <g key={'l' + i} opacity={o}>
        <path d={d} fill="none" stroke={l.color} strokeWidth={(l.width * 4.5) / z} opacity={0.25} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - dp} strokeLinecap="round" />
        <path d={d} fill="none" stroke={l.color} strokeWidth={l.width / z} strokeLinecap="round"
          {...(dp < 1 ? {pathLength: 1, strokeDasharray: 1, strokeDashoffset: 1 - dp} : flow)} />
      </g>
    );
  });
  const rings = RINGS.map((r, i) => {
    const o = env(t, r.from, r.to ?? 1e9, 0.4, 0.8);
    if (o <= 0) return null;
    const [cx, cy] = anchor(r.at);
    return (
      <g key={'r' + i} opacity={o}>
        {r.km.map((km, j) => {
          const g = easeOut(prog(t, r.from + j * 0.45, 1.4));
          return <circle key={j} cx={cx} cy={cy} r={(km / KM_PER_PX) * g} fill="none" stroke="#FFE9A8"
            strokeWidth={1.6 / z} strokeDasharray={`${7 / z} ${6 / z}`} opacity={1 - j * 0.22} />;
        })}
      </g>
    );
  });
  const labels = LABELS.map((l, i) => {
    const o = env(t, l.from, l.to, 0.6, 0.6);
    if (o <= 0) return null;
    const [x, y] = anchor(l.at);
    const fs = l.size / z;
    return (
      <g key={'t' + i} opacity={o} transform={`translate(${x},${y}) rotate(${-cam.rot})`}>
        <text textAnchor="middle" fontFamily={l.italic ? FONTS.serif : FONTS.head} fontSize={fs} fontWeight={l.italic ? 600 : 700}
          fontStyle={l.italic ? 'italic' : 'normal'} letterSpacing={`${(l.spacing ?? (l.italic ? 0.22 : 0.2)) * fs}`}
          fill={l.color ?? (l.italic ? '#E6F3FA' : '#FFFFFF')} stroke={l.italic ? 'rgba(20,60,80,0.45)' : 'rgba(10,16,22,0.55)'}
          strokeWidth={fs * (l.italic ? 0.06 : 0.09)} paintOrder="stroke" y={fs * 0.35} style={{filter: 'drop-shadow(0 2px 3px rgba(0,0,0,0.45))'}}>
          {l.text}
        </text>
        {l.sub ? (
          <text textAnchor="middle" fontFamily={FONTS.body} fontSize={fs * 0.5} fontWeight={600} letterSpacing={`${0.06 * fs}`}
            fill="#F4E3B0" stroke="rgba(10,16,22,0.8)" strokeWidth={fs * 0.08} paintOrder="stroke" y={fs * 1.1}>
            {l.sub}
          </text>
        ) : null}
      </g>
    );
  });
  const hs = 9 / z;
  return (
    <svg width={WORLD_W} height={WORLD_H} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
      <defs>
        {HATCH_COLORS.map((c, k) => (
          <pattern key={k} id={`hatch${k}`} patternUnits="userSpaceOnUse" width={hs} height={hs} patternTransform={`rotate(${45 - cam.rot})`}>
            <rect width={hs} height={hs} fill={c} opacity={0.22} />
            <line x1={0} y1={0} x2={0} y2={hs} stroke={c} strokeWidth={hs * 0.55} />
          </pattern>
        ))}
      </defs>
      {fills}
      {strokes}
      {rings}
      {lines}
      <ArrowsSvg t={t} z={z} />
      {labels}
    </svg>
  );
};

// ---------------- billboards (screen space) ----------------
const OFF: Record<string, [number, number]> = {EST: [-26, -40], LVA: [-52, -6], LTU: [-40, 30], BLR: [-6, 14], MDA: [-30, 26],
  UKR: [0, 0], GEO: [-34, -10], ARM: [-26, 34], AZE: [30, 26], KGZ: [16, -8], TJK: [-6, 22], TKM: [0, 6], UZB: [6, -6], KAZ: [0, 0], RUS: [0, 0]};

const Flag: React.FC<{iso: string; x: number; y: number; ax: number; ay: number; size: number; drop: number; o: number; date?: string; dateO: number; t: number}> =
  ({iso, x, y, ax, ay, size, drop, o, date, dateO, t}) => {
    const w = 60 * size, h = 45 * size, pole = 72 * size;
    const fall = (1 - drop) * -320;
    const wave = Math.sin(t * 3.1 + x * 0.05) * 2.2;
    const leader = Math.hypot(x - ax, y - ay) > 4;
    return (
      <>
        {leader ? <svg style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', opacity: o * drop}} width={1} height={1}>
          <line x1={ax} y1={ay} x2={x} y2={y} stroke="rgba(255,246,224,0.8)" strokeWidth={1.2} />
          <circle cx={ax} cy={ay} r={2.6} fill="#FFF6E0" />
        </svg> : null}
        <div style={{position: 'absolute', left: x - 9 * size, top: y - 3 * size, width: 18 * size, height: 6 * size, borderRadius: '50%',
          background: 'rgba(0,0,0,0.45)', filter: 'blur(2px)', opacity: o * drop}} />
        <div style={{position: 'absolute', left: x, top: y - pole + fall, opacity: o, width: w + 4, height: pole}}>
          <div style={{position: 'absolute', left: 0, top: 0, width: 2.4 * size, height: pole, background: 'linear-gradient(#f5f1e6,#9c968a)', borderRadius: 2}} />
          <div style={{position: 'absolute', left: 2.4 * size, top: 1, width: w, height: h, transform: `skewY(${wave}deg)`, transformOrigin: 'left center',
            boxShadow: '0 3px 8px rgba(0,0,0,0.45)', overflow: 'hidden', borderRadius: 1.5}}>
            <Img src={staticFile(`flags/4x3/${FLAG_CODE[iso]}.svg`)} style={{width: w, height: h, display: 'block'}} />
            <div style={{position: 'absolute', inset: 0, background: `linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,${0.16 + 0.1 * Math.sin(t * 3.1)}) 45%, rgba(0,0,0,0.18) 100%)`}} />
          </div>
        </div>
        {date ? <div style={{position: 'absolute', left: x - 60, top: y + 6, width: 120, textAlign: 'center', opacity: dateO * o,
          fontFamily: FONTS.body, fontSize: 13 * Math.min(size, 1.3), fontWeight: 700, color: '#FFF3D0', letterSpacing: '0.06em',
          textShadow: '0 1px 3px rgba(0,0,0,0.9)'}}>{date}</div> : null}
      </>
    );
  };

const Billboards: React.FC<{t: number; cam: CamState; fps: number}> = ({t, cam, fps}) => {
  const sizeK = clamp(Math.sqrt(cam.zoom / 0.24), 0.85, 1.6);
  const hidden = FLAG_HIDE.some(([a, b]) => t > a && t < b);
  const hideO = FLAG_HIDE.reduce((m, [a, b]) => Math.min(m, 1 - env(t, a, b, 0.6, 0.8)), 1);
  // latest active entry per iso wins
  const active: Record<string, any> = {};
  FLAGS.forEach((f) => { if (t >= f.t - 0.05 && t <= (f.to ?? 1e9)) active[f.iso] = f; });
  const flags = Object.values(active).map((f: any) => {
    const [wx, wy] = anchor('rep:' + f.iso);
    const q = project(cam, wx, wy);
    if (q.x < -200 || q.x > 2120 || q.y < -100 || q.y > 1300) return null;
    const ov = cam.zoom < 0.42 ? OFF[f.iso] ?? [0, 0] : [0, 0];
    const k = clamp((0.42 - cam.zoom) / 0.1);
    const x = q.x + ov[0] * k * sizeK, y = q.y + ov[1] * k * sizeK;
    const drop = spring({frame: Math.max(0, (t - f.t) * fps), fps, config: {damping: 11, mass: 0.55, stiffness: 120}});
    const o = env(t, f.t - 0.05, f.to ?? 1e9, 0.15, 0.6) * (hidden ? hideO : 1);
    const dateO = env(t, f.t + 0.3, f.t + 3.2, 0.3, 0.6);
    return <Flag key={f.iso} iso={f.iso} x={x} y={y} ax={q.x} ay={q.y} size={sizeK * q.s} drop={drop} o={o} date={f.date} dateO={dateO} t={t} />;
  });
  const markers = MARKERS.map((m, i) => {
    const o = env(t, m.from, m.to, 0.4, 0.5);
    if (o <= 0) return null;
    const c = G.cities[m.city];
    if (!c) return null;
    const q = project(cam, c.px[0], c.px[1]);
    const side = m.side ?? 'r';
    const col = m.color ?? COL.GOLD;
    const pr = m.pulse ? (t * 0.8) % 1 : 0;
    return (
      <div key={'m' + i} style={{position: 'absolute', left: q.x, top: q.y, opacity: o}}>
        {m.pulse ? <div style={{position: 'absolute', left: -6 - 22 * pr, top: -6 - 22 * pr, width: 12 + 44 * pr, height: 12 + 44 * pr,
          borderRadius: '50%', border: `2px solid ${col}`, opacity: 1 - pr}} /> : null}
        <div style={{position: 'absolute', left: -6, top: -6, width: 12, height: 12, borderRadius: '50%', background: col,
          border: '2px solid #10161c', boxShadow: `0 0 10px ${col}`}} />
        {m.label || m.sub ? (
          <div style={{position: 'absolute', whiteSpace: 'nowrap', top: side === 'b' ? 12 : side === 't' ? -54 : -14,
            left: side === 'r' ? 14 : undefined, right: side === 'l' ? 14 : undefined,
            transform: side === 't' || side === 'b' ? 'translateX(-50%)' : undefined, textAlign: side === 'l' ? 'right' : 'left'}}>
            {m.label ? <div style={{fontFamily: FONTS.serif, fontWeight: 700, fontSize: 25, color: '#FFFFFF', letterSpacing: '0.08em',
              fontVariant: 'small-caps', textShadow: '0 2px 6px rgba(0,0,0,0.9)'}}>{m.label}</div> : null}
            {m.sub ? <div style={{fontFamily: FONTS.body, fontWeight: 600, fontSize: 15, color: '#F4E3B0', letterSpacing: '0.05em',
              textShadow: '0 1px 4px rgba(0,0,0,0.95)'}}>{m.sub}</div> : null}
          </div>
        ) : (
          <div style={{position: 'absolute', left: 12, top: -11, whiteSpace: 'nowrap', fontFamily: FONTS.body, fontWeight: 600, fontSize: 16,
            color: '#FFFFFF', textShadow: '0 1px 4px rgba(0,0,0,0.95)'}}>{m.city}</div>
        )}
      </div>
    );
  });
  return <AbsoluteFill>{markers}{flags}</AbsoluteFill>;
};

const HD: any = hd;
/** 4 px per canvas px terrain tiles, faded in above zoom 1 (only tiles in view are mounted) */
const HdTiles: React.FC<{cam: CamState}> = ({cam}) => {
  const o = clamp((cam.zoom - 1.0) / 0.18);
  if (o <= 0) return null;
  const pts = [[0, 0], [1920, 0], [0, 1080], [1920, 1080], [960, 0]].map(([x, y]) => unproject(cam, x, y));
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs) - 64, Math.max(...xs) + 64, Math.min(...ys) - 64, Math.max(...ys) + 64];
  return (
    <>
      {HD.tiles.map(([i, j]: [number, number]) => {
        const x = HD.x0 + i * HD.tile, y = HD.y0 + j * HD.tile;
        if (x > x1 || x + HD.tile < x0 || y > y1 || y + HD.tile < y0) return null;
        return <Img key={`hd${i}_${j}`} src={staticFile(`hd/t_${i}_${j}.jpg`)}
          style={{position: 'absolute', left: x - 0.3, top: y - 0.3, width: HD.tile + 0.6, height: HD.tile + 0.6, opacity: o}} />;
      })}
    </>
  );
};

export const MapStage: React.FC<{t: number; lite: boolean; fps: number}> = ({t, lite, fps}) => {
  const cam = cameraAt(t);
  return (
    <AbsoluteFill style={{background: '#0c1822', overflow: 'hidden'}}>
      <AbsoluteFill style={{perspective: PERSP, perspectiveOrigin: '960px 540px'}}>
        <div style={{position: 'absolute', left: 0, top: 0, width: WORLD_W, height: WORLD_H, transformOrigin: '0 0', transform: cssTransform(cam)}}>
          <Img src={staticFile(lite ? 'basemap_v2_half.jpg' : 'basemap_v2.jpg')} style={{position: 'absolute', left: 0, top: 0, width: WORLD_W, height: WORLD_H}} />
          {!lite ? <HdTiles cam={cam} /> : null}
          <WorldSvg t={t} cam={cam} />
        </div>
      </AbsoluteFill>
      {/* atmosphere: soft haze toward the receding top edge when tilted */}
      <AbsoluteFill style={{background: `linear-gradient(180deg, rgba(150,180,200,${0.32 * clamp(cam.tilt / 36)}) 0%, rgba(150,180,200,0) 38%)`}} />
      <Billboards t={t} cam={cam} fps={fps} />
      <V2Billboards t={t} cam={cam} />
    </AbsoluteFill>
  );
};
