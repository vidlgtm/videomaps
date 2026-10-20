// Opening: night globe (Three.js, NASA Black Marble) -> the Kremlin Senate dome at night, snow, the red flag lowered.
import React, {useEffect, useState} from 'react';
import {ThreeCanvas} from '@remotion/three';
import {AbsoluteFill, continueRender, delayRender, Img, staticFile} from 'remotion';
import * as THREE from 'three';
import {OPENING, h} from '../v2';
import {clamp, ease, easeOut, env, lerp, prog} from '../lib/anim';
import {FONTS} from '../fonts';
import {hash} from './V2';

const D = Math.PI / 180;
const STARS = Array.from({length: 240}, (_, i) => ({x: hash(i, 1) * 1920, y: hash(i, 2) * 1080, s: 0.4 + hash(i, 3) * 1.3, o: 0.25 + hash(i, 4) * 0.6}));
const FLAKES = Array.from({length: 170}, (_, i) => ({x: hash(i, 11) * 1920, y: hash(i, 12) * 1180, z: hash(i, 13),
  ph: hash(i, 14) * 6.28, w: 0.6 + hash(i, 15) * 1.2}));

export const Snow: React.FC<{t: number; o: number}> = ({t, o}) => (
  <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, opacity: o}}>
    {FLAKES.map((f, i) => {
      const v = 40 + f.z * 110, r = 1.1 + f.z * 3.2;
      const y = ((f.y + v * t) % 1180) - 50;
      const x = (((f.x + Math.sin(t * f.w + f.ph) * (12 + f.z * 30) - t * 18 * f.z) % 1920) + 1920) % 1920;
      return <circle key={i} cx={x} cy={y} r={r} fill="#ffffff" opacity={0.35 + f.z * 0.5} />;
    })}
  </svg>
);

const NightGlobe: React.FC<{t: number}> = ({t}) => {
  const [tex, setTex] = useState<THREE.Texture | null>(null);
  const [handle] = useState(() => delayRender('night globe texture'));
  useEffect(() => {
    new THREE.TextureLoader().load(staticFile('globe_night_4k.jpg'), (x) => {
      x.colorSpace = THREE.SRGBColorSpace; x.anisotropy = 8; setTex(x);
      requestAnimationFrame(() => requestAnimationFrame(() => continueRender(handle)));
    }, undefined, () => continueRender(handle));
  }, [handle]);
  const e = ease(prog(t, 0, OPENING.kremlinIn + 0.3));
  const lon = lerp(-8, 37.6, e), lat = lerp(22, 55.75, e);
  const dist = lerp(4.9, 1.75, ease(prog(t, 0.6, OPENING.kremlinIn - 0.2)));
  return tex ? (
    <ThreeCanvas width={1920} height={1080} camera={{fov: 30, position: [0, 0, dist], near: 0.05, far: 50}} style={{position: 'absolute'}}>
      <ambientLight intensity={1.0} />
      <group rotation={[lat * D, (-90 - lon) * D, 0]}>
        <mesh>
          <sphereGeometry args={[1, 192, 192]} />
          <meshBasicMaterial map={tex} />
        </mesh>
      </group>
      <mesh>
        <sphereGeometry args={[1.06, 96, 96]} />
        <meshBasicMaterial color={'#3d7dd8'} transparent opacity={0.16} side={THREE.BackSide} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
    </ThreeCanvas>
  ) : null;
};

// Kremlin Senate (dome + flagpole), Senate tower, battlemented wall: an original night illustration
const MERLONS = (() => {
  let d = 'M0,1080 L0,872';
  for (let x = 0; x < 1920; x += 64) d += ` L${x + 8},872 L${x + 8},836 L${x + 20},848 L${x + 32},836 L${x + 32},872 L${x + 64},872`;
  return d + ' L1920,1080 Z';
})();
const WINDOWS = Array.from({length: 2 * 26}, (_, i) => ({x: 548 + (i % 26) * 33, y: i < 26 ? 702 : 772, on: hash(i, 21) > 0.35, o: 0.45 + hash(i, 22) * 0.45}));

const SovietFlag: React.FC<{t: number; W: number; H: number}> = ({t, W, H}) => {
  const N = 12;
  return (
    <div style={{position: 'relative', width: W, height: H}}>
      {Array.from({length: N}, (_, i) => {
        const ph = t * 6.2 - i * 0.55;
        const dy = Math.sin(ph) * (1.5 + 7 * (i / N));
        const br = 1 + 0.16 * Math.cos(ph);
        return (
          <div key={i} style={{position: 'absolute', left: (i * W) / N, top: dy, width: W / N + 0.8, height: H, overflow: 'hidden',
            filter: `brightness(${br.toFixed(3)})`}}>
            <Img src={staticFile('archive/sovflag.jpg')} style={{position: 'absolute', left: (-i * W) / N, top: 0, width: W, height: H}} />
          </div>
        );
      })}
    </div>
  );
};

const Kremlin: React.FC<{t: number}> = ({t}) => {
  const low = ease(prog(t, OPENING.lower, OPENING.lowered - OPENING.lower));
  const flagY = 168 + low * 236;
  const flagO = 1 - clamp((low - 0.93) / 0.07);
  const push = prog(t, OPENING.kremlinIn, OPENING.end - OPENING.kremlinIn);
  return (
    <AbsoluteFill style={{transform: `scale(${1 + 0.06 * push})`, transformOrigin: '50% 40%'}}>
      <svg width={1920} height={1080} style={{position: 'absolute'}}>
        <defs>
          <linearGradient id="ksky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#070d18" /><stop offset="0.7" stopColor="#16243a" /><stop offset="1" stopColor="#2a2a35" /></linearGradient>
          <radialGradient id="kglow" cx="0.5" cy="1" r="0.7"><stop offset="0" stopColor="#ffb766" stopOpacity="0.35" /><stop offset="1" stopColor="#ffb766" stopOpacity="0" /></radialGradient>
          <linearGradient id="kdome" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#0f2622" /><stop offset="0.45" stopColor="#3f7a6b" /><stop offset="1" stopColor="#0c1d1a" /></linearGradient>
          <linearGradient id="kbeam" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stopColor="#fff3d6" stopOpacity="0.0" /><stop offset="0.5" stopColor="#fff3d6" stopOpacity="0.10" /><stop offset="1" stopColor="#fff3d6" stopOpacity="0.0" /></linearGradient>
        </defs>
        <rect width={1920} height={1080} fill="url(#ksky)" />
        {STARS.slice(0, 120).map((s, i) => <circle key={i} cx={s.x} cy={s.y * 0.6} r={s.s * 0.8} fill="#fff" opacity={s.o * 0.5} />)}
        <rect width={1920} height={1080} fill="url(#kglow)" />
        <path d="M960,980 L1180,170 L1250,170 Z" fill="url(#kbeam)" />
        <path d="M960,980 L700,170 L770,170 Z" fill="url(#kbeam)" />
        {/* Senate building */}
        <rect x={520} y={660} width={880} height={240} fill="#121a25" />
        <rect x={520} y={652} width={880} height={10} fill="#1b2533" />
        {WINDOWS.map((w, i) => w.on ? <rect key={i} x={w.x} y={w.y} width={14} height={30} fill="#f3c47e" opacity={w.o} /> : null)}
        <rect x={860} y={560} width={200} height={100} fill="#16202c" />
        {Array.from({length: 7}, (_, i) => <rect key={i} x={872 + i * 27} y={576} width={8} height={70} fill="#2b3a4b" />)}
        <path d="M850,562 C850,470 905,432 960,428 C1015,432 1070,470 1070,562 Z" fill="url(#kdome)" />
        <rect x={949} y={404} width={22} height={26} fill="#2f5d52" />
        <rect x={958} y={150} width={4} height={256} fill="#c9ccd2" />
        <circle cx={960} cy={148} r={4} fill="#e8d18a" />
        {/* Senate tower (left) with glowing star */}
        <rect x={250} y={590} width={110} height={300} fill="#3b1714" />
        <path d="M244,592 L305,372 L366,592 Z" fill="#2c1714" />
        <path d="M244,592 L305,372 L305,592 Z" fill="#1d0f0d" opacity={0.6} />
        <circle cx={305} cy={360} r={26} fill="#ff4a3a" opacity={0.22} />
        <path d="M305,342 L310,355 L324,355 L313,363 L317,377 L305,368 L293,377 L297,363 L286,355 L300,355 Z" fill="#ff5a48" />
        {/* battlemented wall */}
        <path d={MERLONS} fill="#3a1916" />
        <path d={MERLONS} fill="none" stroke="#e9eef5" strokeOpacity={0.55} strokeWidth={2.2} transform="translate(0,-1)" />
        <rect x={0} y={872} width={1920} height={208} fill="url(#ksky)" opacity={0.25} />
      </svg>
      <div style={{position: 'absolute', left: 962, top: flagY, opacity: flagO, filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.5))'}}>
        <SovietFlag t={t} W={250} H={125} />
      </div>
    </AbsoluteFill>
  );
};

export const Opening: React.FC<{t: number}> = ({t}) => {
  if (t > OPENING.end) return null;
  const kIn = clamp((t - OPENING.kremlinIn) / 0.6);
  const outO = 1 - clamp((t - OPENING.mapIn) / (OPENING.end - OPENING.mapIn));
  const dateO = env(t, h.dec - 0.05, OPENING.kremlinIn + 0.5, 0.3, 0.5);
  const d1 = easeOut(prog(t, h.dec - 0.05, 0.6)), d2 = easeOut(prog(t, h.y91 - 0.05, 0.6));
  return (
    <AbsoluteFill style={{opacity: outO}}>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 55%, #0c1624 0%, #03060a 72%)'}}>
        <svg width={1920} height={1080} style={{position: 'absolute'}}>
          {STARS.map((s, i) => <circle key={i} cx={s.x} cy={s.y} r={s.s} fill="#fff" opacity={s.o * 0.7} />)}
        </svg>
        {kIn < 1 ? <NightGlobe t={t} /> : null}
      </AbsoluteFill>
      <AbsoluteFill style={{opacity: kIn}}><Kremlin t={t} /></AbsoluteFill>
      <AbsoluteFill style={{background: '#ffffff', opacity: 0.35 * (1 - Math.abs(kIn - 0.5) * 2) * (kIn > 0 && kIn < 1 ? 1 : 0)}} />
      <Snow t={t} o={clamp((t - 1.2) / 2.5)} />
      <div style={{position: 'absolute', left: 0, width: 1920, top: 120, textAlign: 'center', opacity: dateO}}>
        <div style={{fontFamily: FONTS.head, fontWeight: 700, fontSize: 54, letterSpacing: `${lerp(0.5, 0.26, d1)}em`, color: '#F1DFAE',
          opacity: d1, filter: `blur(${(1 - d1) * 8}px)`, textShadow: '0 3px 16px rgba(0,0,0,0.9)'}}>25 DECEMBER</div>
        <div style={{fontFamily: FONTS.head, fontWeight: 800, fontSize: 92, letterSpacing: `${lerp(0.5, 0.2, d2)}em`, color: '#E9C46A',
          opacity: d2, filter: `blur(${(1 - d2) * 8}px)`, marginTop: -4, textShadow: '0 4px 22px rgba(0,0,0,0.9)'}}>1991</div>
        <div style={{fontFamily: FONTS.serif, fontStyle: 'italic', fontWeight: 600, fontSize: 30, color: '#d9e3ee', letterSpacing: '0.12em',
          opacity: clamp((t - h.y91 - 0.6) / 0.5)}}>Moscow, the Kremlin</div>
      </div>
      <AbsoluteFill style={{boxShadow: 'inset 0 0 260px rgba(0,0,0,0.75)'}} />
    </AbsoluteFill>
  );
};
