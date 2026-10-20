import React, {useEffect, useState} from 'react';
import {ThreeCanvas} from '@remotion/three';
import {AbsoluteFill, continueRender, delayRender, staticFile} from 'remotion';
import * as THREE from 'three';
import {GLOBE} from '../script';
import {ease, prog, lerp, env} from '../lib/anim';

const D = Math.PI / 180;
const STARS = Array.from({length: 260}, (_, i) => {
  const r = (n: number) => { const x = Math.sin(i * 12.9898 + n * 78.233) * 43758.5453; return x - Math.floor(x); };
  return {x: r(1) * 1920, y: r(2) * 1080, s: 0.4 + r(3) * 1.4, o: 0.25 + r(4) * 0.6};
});

export const Globe: React.FC<{t: number}> = ({t}) => {
  const [tex, setTex] = useState<THREE.Texture | null>(null);
  const [ov, setOv] = useState<THREE.Texture | null>(null);
  const [n, setN] = useState(0);
  const [handle] = useState(() => delayRender('globe textures'));
  useEffect(() => {
    const L = new THREE.TextureLoader();
    L.load(staticFile('globe_4k.jpg'), (x) => { x.colorSpace = THREE.SRGBColorSpace; x.anisotropy = 8; setTex(x); setN((c) => c + 1); }, undefined, () => setN((c) => c + 1));
    L.load(staticFile('ussr_overlay.png'), (x) => { x.colorSpace = THREE.SRGBColorSpace; setOv(x); setN((c) => c + 1); }, undefined, () => setN((c) => c + 1));
  }, []);
  useEffect(() => {
    if (n >= 2) requestAnimationFrame(() => requestAnimationFrame(() => continueRender(handle)));
  }, [n, handle]);
  const e1 = ease(prog(t, 0, GLOBE.moscowAt));
  const e2 = ease(prog(t, GLOBE.pullBack, 3.4));
  const spin = t * 0.6;
  const lon = lerp(lerp(-20, 37.6, e1), 74, e2) + spin * (1 - e1);
  const lat = lerp(lerp(16, 55.75, e1), 57, e2);
  const dist = lerp(lerp(4.8, 2.45, e1), 3.25, e2);
  const ovO = env(t, GLOBE.pullBack + 0.4, 1e9, 1.4, 0);
  const o = 1 - prog(t, GLOBE.to - 1.1, 1.0);
  return (
    <AbsoluteFill style={{opacity: o, background: 'radial-gradient(ellipse at 50% 55%, #10202e 0%, #050a10 70%)'}}>
      <svg width={1920} height={1080} style={{position: 'absolute'}}>
        {STARS.map((s, i) => <circle key={i} cx={s.x} cy={s.y} r={s.s} fill="#fff" opacity={s.o * 0.7} />)}
      </svg>
      {n >= 2 ? <ThreeCanvas width={1920} height={1080} camera={{fov: 30, position: [0, 0, dist], near: 0.1, far: 50}} style={{position: 'absolute'}}>
        <ambientLight intensity={0.55} />
        <directionalLight position={[-3, 2.2, 3.5]} intensity={1.7} color={'#fff4e0'} />
        <group rotation={[lat * D, (-90 - lon) * D, 0]}>
          <mesh>
            <sphereGeometry args={[1, 160, 160]} />
            {tex ? <meshStandardMaterial map={tex} roughness={0.92} metalness={0} /> : <meshStandardMaterial color={'#24506a'} />}
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
