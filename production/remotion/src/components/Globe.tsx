// Three.js (@remotion/three) globe for hooks: textured Earth (public/globe_day_4k.jpg or globe_night_4k.jpg from the base
// terrain release), atmosphere rim, star field, a camera path of keyframes (lon/lat/dist, eased), optional overlay texture.
// Data: GLOBE in src/script.ts (project). The canvas mounts only after the textures have loaded (no blank first frames).
import React, {useEffect, useState} from 'react';
import {ThreeCanvas} from '@remotion/three';
import {AbsoluteFill, continueRender, delayRender, staticFile} from 'remotion';
import * as THREE from 'three';
import {GLOBE} from '../script';
import {ease, prog, lerp, env, clamp} from '../lib/anim';

const D = Math.PI / 180;
const STARS = Array.from({length: 260}, (_, i) => {
  const r = (n: number) => { const x = Math.sin(i * 12.9898 + n * 78.233) * 43758.5453; return x - Math.floor(x); };
  return {x: r(1) * 1920, y: r(2) * 1080, s: 0.4 + r(3) * 1.4, o: 0.25 + r(4) * 0.6};
});

function camAt(t: number) {
  const K = GLOBE.keys;
  if (t <= K[0].t) return {...K[0], lon: K[0].lon + (GLOBE.spin ?? 0) * (t - K[0].t)};
  for (let i = 0; i + 1 < K.length; i++) {
    const a = K[i], b = K[i + 1];
    if (t <= b.t) {
      const e = ease(clamp((t - a.t) / Math.max(0.01, b.t - a.t)));
      return {t, lon: lerp(a.lon, b.lon, e), lat: lerp(a.lat, b.lat, e), dist: lerp(a.dist, b.dist, e)};
    }
  }
  return K[K.length - 1];
}

export const Globe: React.FC<{t: number}> = ({t}) => {
  const [tex, setTex] = useState<THREE.Texture | null>(null);
  const [ov, setOv] = useState<THREE.Texture | null>(null);
  const [n, setN] = useState(0);
  const need = GLOBE.overlay ? 2 : 1;
  const [handle] = useState(() => delayRender('globe textures'));
  useEffect(() => {
    const L = new THREE.TextureLoader();
    L.load(staticFile(GLOBE.tex), (x) => { x.colorSpace = THREE.SRGBColorSpace; x.anisotropy = 8; setTex(x); setN((c) => c + 1); }, undefined, () => setN((c) => c + 1));
    if (GLOBE.overlay) L.load(staticFile(GLOBE.overlay), (x) => { x.colorSpace = THREE.SRGBColorSpace; setOv(x); setN((c) => c + 1); }, undefined, () => setN((c) => c + 1));
  }, []);
  useEffect(() => {
    if (n >= need) requestAnimationFrame(() => requestAnimationFrame(() => continueRender(handle)));
  }, [n, need, handle]);
  const c = camAt(t);
  const ovO = GLOBE.overlayFrom !== undefined ? env(t, GLOBE.overlayFrom, 1e9, 1.4, 0) : 0;
  const o = 1 - prog(t, GLOBE.to - 1.1, 1.0);
  const night = GLOBE.tex.includes('night');
  return (
    <AbsoluteFill style={{opacity: o, background: 'radial-gradient(ellipse at 50% 55%, #10202e 0%, #050a10 70%)'}}>
      <svg width={1920} height={1080} style={{position: 'absolute'}}>
        {STARS.map((s, i) => <circle key={i} cx={s.x} cy={s.y} r={s.s} fill="#fff" opacity={s.o * 0.7} />)}
      </svg>
      {n >= need ? <ThreeCanvas width={1920} height={1080} camera={{fov: 30, position: [0, 0, c.dist], near: 0.1, far: 50}} style={{position: 'absolute'}}>
        <ambientLight intensity={0.55} />
        <directionalLight position={[-3, 2.2, 3.5]} intensity={1.7} color={'#fff4e0'} />
        <group rotation={[c.lat * D, (-90 - c.lon) * D, 0]}>
          <mesh>
            <sphereGeometry args={[1, 160, 160]} />
            {tex ? (night ? <meshBasicMaterial map={tex} /> : <meshStandardMaterial map={tex} roughness={0.92} metalness={0} />)
              : <meshStandardMaterial color={'#24506a'} />}
          </mesh>
          {ov ? (
            <mesh>
              <sphereGeometry args={[1.0025, 160, 160]} />
              <meshBasicMaterial map={ov} transparent opacity={ovO} depthWrite={false} />
            </mesh>
          ) : null}
        </group>
        <mesh>
          <sphereGeometry args={[1.07, 96, 96]} />
          <meshBasicMaterial color={'#5fb2ff'} transparent opacity={0.13} side={THREE.BackSide} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      </ThreeCanvas> : null}
    </AbsoluteFill>
  );
};
