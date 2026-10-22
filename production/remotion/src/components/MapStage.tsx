import React from 'react';
import {AbsoluteFill, Img, staticFile, spring} from 'remotion';
import geo from '../data/geo.json';
import {px, project, KM_PER_PX, WORLD_W, WORLD_H, PERSP, CamState} from '../lib/proj';
import {cameraAt as camAt, unproject} from '../lib/camera';
import {PATHS, anchor} from '../lib/paths';
import {flagLayout, frameLayout, declutter, Layout} from '../lib/layout';
import {env, clamp, ease, lerp, prog, easeOut} from '../lib/anim';
import {CAMERA, CamKey, FILLS, STROKES, LABELS, MARKERS, FLAGS, FLAG_HIDE, LINES, RINGS, ISO15, FLAG_CODE, COL} from '../script';
import {FONTS} from '../fonts';
import hd from '../data/hd_index.json';
import uhd from '../data/uhd_index.json';
import {V2Billboards, ArrowsSvg} from './V2';

const G: any = geo;
export {PATHS, anchor};
export const cameraAt = camAt;
type Dec = (id: string) => number;


// ---------------- world layers ----------------
const pulseK = (t: number) => 0.72 + 0.28 * Math.sin((2 * Math.PI * t) / 1.7);
const HATCH_COLORS = Array.from(new Set(FILLS.filter((f) => f.hatch).map((f) => f.color)));

const WorldSvg: React.FC<{t: number; cam: CamState; L: Layout; dec: Dec}> = ({t, cam, L, dec}) => {
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
    const o = env(t, l.from, l.to, 0.6, 0.6) * dec('label:' + i);
    if (o <= 0.004) return null;
    const [ax, ay] = anchor(l.at);
    let [x, y] = [ax, ay];
    if (L.labelDy[i]) { const q = project(cam, ax, ay); [x, y] = unproject(cam, q.x, q.y + L.labelDy[i]); }
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
  // v4: country names (era-correct), engraved serif caps; neighbours in muted italics
  const names = L.names.map((n) => {
    const o = n.o * dec(n.id);
    if (o <= 0.004) return null;
    const fw = n.fs / (z * n.q.s);
    return (
      <g key={n.id} opacity={o} transform={`translate(${n.wx},${n.wy}) rotate(${-cam.rot})`}>
        <text textAnchor="middle" fontFamily={n.ctx ? FONTS.serif : FONTS.head} fontSize={fw} fontWeight={n.ctx ? 600 : 600}
          fontStyle={n.ctx ? 'italic' : 'normal'} letterSpacing={`${(n.ctx ? 0.18 : 0.28) * fw}`} y={fw * 0.36}
          fill={n.ctx ? '#EFE7D3' : '#FBF3DF'} stroke={n.ctx ? 'rgba(18,24,30,0.45)' : 'rgba(24,16,8,0.62)'} strokeWidth={fw * (n.ctx ? 0.07 : 0.1)}
          paintOrder="stroke" style={{filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.5))'}}>{n.text}</text>
        {n.sub ? <text textAnchor="middle" fontFamily={FONTS.head} fontSize={fw * 0.55} fontWeight={700} letterSpacing={`${0.4 * fw * 0.55}`}
          y={fw * 1.0} fill="#F2E3B8" stroke="rgba(24,16,8,0.6)" strokeWidth={fw * 0.06} paintOrder="stroke">{n.sub}</text> : null}
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
      {names}
      {labels}
    </svg>
  );
};

// ---------------- billboards (screen space) ----------------
const Flag: React.FC<{iso: string; x: number; y: number; ax: number; ay: number; size: number; drop: number; o: number; date?: string; dateO: number; t: number}> =
  ({iso, x, y, ax, ay, size, drop, o, date, dateO, t}) => {
    const w = 60 * size, h = 45 * size, pole = 72 * size;
    const fall = (1 - drop) * -320;
    const wave = Math.sin(t * 3.1 + x * 0.05) * 2.2;
    const dl = Math.hypot(x - ax, y - ay), leader = dl > 3, lo = clamp((dl - 3) / 12);   // leader fades in with the displacement
    return (
      <>
        {leader ? <svg style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', opacity: o * drop * lo}} width={1} height={1}>
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

const Billboards: React.FC<{t: number; cam: CamState; fps: number; dec: Dec}> = ({t, cam, fps, dec}) => {
  const flags = flagLayout(t, cam).map((g) => {
    const drop = spring({frame: Math.max(0, (t - g.f.t) * fps), fps, config: {damping: 11, mass: 0.55, stiffness: 120}});
    const o = g.o * dec('flag:' + g.iso);
    if (o <= 0.004) return null;
    return <Flag key={g.iso} iso={g.iso} x={g.x} y={g.y} ax={g.ax} ay={g.ay} size={g.size} drop={drop} o={o} date={g.f.date}
      dateO={g.dateO * dec('fdate:' + g.iso)} t={t} />;
  });
  const markers = MARKERS.map((m, i) => {
    const o = env(t, m.from, m.to, 0.4, 0.5) * dec('mlab:' + i);
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
        {m.dot ? null : m.label || m.sub ? (
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

const UHD: any = uhd;
/** v3: 8 px per canvas px deep-zoom tiles (Sentinel-2 detail), faded in for close-ups only */
const UhdTiles: React.FC<{cam: CamState}> = ({cam}) => {
  const o = clamp((cam.zoom - 1.85) / 0.3);
  if (o <= 0 || !UHD.tiles.length) return null;
  const pts = [[0, 0], [1920, 0], [0, 1080], [1920, 1080], [960, 0]].map(([x, y]) => unproject(cam, x, y));
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs) - 32, Math.max(...xs) + 32, Math.min(...ys) - 32, Math.max(...ys) + 32];
  return (
    <>
      {UHD.tiles.map(([x, y]: [number, number]) => {
        if (x > x1 || x + UHD.tile < x0 || y > y1 || y + UHD.tile < y0) return null;
        return <Img key={`u${x}_${y}`} src={staticFile(`uhd/u_${x}_${y}.jpg`)}
          style={{position: 'absolute', left: x - 0.2, top: y - 0.2, width: UHD.tile + 0.4, height: UHD.tile + 0.4, opacity: o}} />;
      })}
    </>
  );
};

/** v4 sharpness fix: Chrome rasterizes a layer under a CSS perspective at its *layout* size and then stretches it,
 *  so the old `scale(zoom)` transform turned every close-up into an up-scaled blur (HD/UHD tiles and SVG included).
 *  Now the world is laid out at zoom*SS with CSS `zoom` and the 3D transform only rotates/tilts (scale 1/SS). */
const SS = 1.3;
const worldTransform = (c: CamState, S: number) =>
  `translate(960px,540px) rotateX(${c.tilt}deg) rotateZ(${c.rot}deg) scale(${c.zoom / S}) translate(${-c.x * S}px,${-c.y * S}px)`;

export const MapStage: React.FC<{t: number; lite: boolean; fps: number}> = ({t, lite, fps}) => {
  const L = frameLayout(Math.round(t * fps)).L;
  const dec = declutter(t);
  const cam = L.cam;
  const S = cam.zoom * SS;
  return (
    <AbsoluteFill style={{background: '#0c1822', overflow: 'hidden'}}>
      <AbsoluteFill style={{perspective: PERSP, perspectiveOrigin: '960px 540px'}}>
        <div style={{position: 'absolute', left: 0, top: 0, width: WORLD_W, height: WORLD_H, transformOrigin: '0 0', transform: worldTransform(cam, S)}}>
          <div style={{position: 'absolute', left: 0, top: 0, width: WORLD_W, height: WORLD_H, zoom: S}}>
            <Img src={staticFile(lite ? 'basemap_v2_half.jpg' : 'basemap_v2.jpg')} style={{position: 'absolute', left: 0, top: 0, width: WORLD_W, height: WORLD_H}} />
            {!lite ? <HdTiles cam={cam} /> : null}
            {!lite ? <UhdTiles cam={cam} /> : null}
            <WorldSvg t={t} cam={cam} L={L} dec={dec} />
          </div>
        </div>
      </AbsoluteFill>
      {/* atmosphere: soft haze toward the receding top edge when tilted */}
      <AbsoluteFill style={{background: `linear-gradient(180deg, rgba(150,180,200,${0.32 * clamp(cam.tilt / 36)}) 0%, rgba(150,180,200,0) 38%)`}} />
      <Billboards t={t} cam={cam} fps={fps} dec={dec} />
      <V2Billboards t={t} cam={cam} dec={dec} />
    </AbsoluteFill>
  );
};
