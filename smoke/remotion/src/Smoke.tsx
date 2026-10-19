import React, {useMemo} from 'react';
import {AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {evolvePath} from '@remotion/paths';
import {geoCentroid, geoMercator, geoPath} from 'd3-geo';
import {feature} from 'topojson-client';
import * as echarts from 'echarts';
import world from 'world-atlas/countries-50m.json';

const countries: any = (feature as any)(world as any, (world as any).objects.countries);
const RUS = countries.features.find((f: any) => String(f.id) === '643');
const CLAMP = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const MapLayer: React.FC = () => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const t = interpolate(frame, [0, 140], [0, 1], {...CLAMP, easing: Easing.bezier(0.65, 0, 0.35, 1)});
  const lon0 = interpolate(t, [0, 1], [60, 92]);
  const lat0 = interpolate(t, [0, 1], [48, 58]);
  const proj = geoMercator().rotate([-lon0, 0]).center([0, lat0]).scale(interpolate(t, [0, 1], [330, 560])).translate([width / 2, height / 2]);
  const path = geoPath(proj);
  const [cx, cy] = proj(geoCentroid(RUS)) as [number, number];
  const draw = interpolate(frame, [15, 75], [0, 1], {...CLAMP, easing: Easing.inOut(Easing.cubic)});
  const fill = interpolate(frame, [60, 90], [0, 0.55], CLAMP);
  const drop = spring({frame: frame - 70, fps, config: {damping: 11, stiffness: 140, mass: 0.9}});
  const y = interpolate(drop, [0, 1], [-650, 0]);
  const arrow = 'M 420 930 C 700 760, 980 1000, 1300 800';
  const ev = evolvePath(interpolate(frame, [40, 120], [0, 1], CLAMP), arrow);
  return (
    <AbsoluteFill>
      <svg width={width} height={height} style={{position: 'absolute'}}>
        <defs>
          <radialGradient id="sea" cx="50%" cy="45%" r="75%">
            <stop offset="0%" stopColor="#24435f" />
            <stop offset="100%" stopColor="#0d1b2a" />
          </radialGradient>
        </defs>
        <rect width={width} height={height} fill="url(#sea)" />
        {countries.features.map((f: any, i: number) => (
          <path key={i} d={path(f) || ''} fill={f === RUS ? '#d9cfb4' : '#cbbf9f'} stroke="#8a7d62" strokeWidth={0.8} />
        ))}
        <path d={path(RUS) || ''} fill="#b22222" fillOpacity={fill} stroke="none" />
        <path d={path(RUS) || ''} fill="none" stroke="#ffdf6b" strokeWidth={3} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw}
          style={{filter: 'drop-shadow(0 0 6px rgba(255,210,90,.9))'}} />
        <path d={arrow} fill="none" stroke="#f4d03f" strokeWidth={7} strokeLinecap="round" strokeDasharray={ev.strokeDasharray} strokeDashoffset={ev.strokeDashoffset} />
        <ellipse cx={cx} cy={cy + 8} rx={70 * interpolate(drop, [0, 1], [0.3, 1])} ry={14 * interpolate(drop, [0, 1], [0.3, 1])} fill="rgba(0,0,0,.35)" opacity={drop} />
      </svg>
      <Img src={staticFile('flags/ru.svg')} style={{position: 'absolute', left: cx - 80, top: cy - 125 + y, width: 160, height: 120, border: '4px solid #fff', borderRadius: 6, boxShadow: '0 14px 30px rgba(0,0,0,.5)'}} />
    </AbsoluteFill>
  );
};

const Chart: React.FC = () => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [20, 110], [0, 1], {...CLAMP, easing: Easing.out(Easing.cubic)});
  const svg = useMemo(() => {
    const chart = echarts.init(null as any, undefined, {renderer: 'svg', ssr: true, width: 640, height: 340});
    chart.setOption({
      animation: false,
      backgroundColor: 'rgba(10,20,35,0.78)',
      title: {text: 'Population, 1989 census (millions)', left: 16, top: 10, textStyle: {color: '#f1e9d2', fontSize: 18}},
      grid: {left: 110, right: 50, top: 50, bottom: 24},
      xAxis: {type: 'value', max: 160, axisLabel: {color: '#aab'}, splitLine: {lineStyle: {color: '#334'}}},
      yAxis: {type: 'category', data: ['Estonia', 'Latvia', 'Georgia', 'Kazakhstan', 'Ukraine', 'Russia'], axisLabel: {color: '#f1e9d2', fontSize: 15}},
      series: [{type: 'bar', data: [1.6, 2.7, 5.4, 16.5, 51.7, 147.4].map((v) => +(v * p).toFixed(1)), itemStyle: {color: '#c0392b', borderRadius: [0, 4, 4, 0]}, label: {show: true, position: 'right', color: '#fff'}}],
    });
    const s = chart.renderToSVGString();
    chart.dispose();
    return s;
  }, [p]);
  return <div style={{position: 'absolute', left: 60, bottom: 60, width: 640, height: 340}} dangerouslySetInnerHTML={{__html: svg}} />;
};

const Globe: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <ThreeCanvas width={440} height={440} style={{position: 'absolute', right: 50, top: 40}} camera={{fov: 35, position: [0, 0, 6]}}>
      <ambientLight intensity={0.5} />
      <directionalLight position={[4, 2, 5]} intensity={1.4} />
      <mesh rotation={[0.35, frame * 0.025, 0]}>
        <sphereGeometry args={[1.6, 64, 64]} />
        <meshStandardMaterial color="#1f5f8b" roughness={0.6} metalness={0.1} />
      </mesh>
      <mesh rotation={[0.35, frame * 0.025, 0]}>
        <sphereGeometry args={[1.62, 32, 16]} />
        <meshBasicMaterial color="#bfe3ff" wireframe transparent opacity={0.3} />
      </mesh>
    </ThreeCanvas>
  );
};

export const Smoke: React.FC = () => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [0, 20], [0, 1], CLAMP);
  return (
    <AbsoluteFill style={{backgroundColor: '#0d1b2a', fontFamily: 'DejaVu Sans, Arial, sans-serif'}}>
      <MapLayer />
      <Chart />
      <Globe />
      <div style={{position: 'absolute', left: 60, top: 50, color: '#f1e9d2', fontSize: 54, fontWeight: 800, letterSpacing: 2, opacity: o, textShadow: '0 4px 14px rgba(0,0,0,.6)'}}>
        VIDEOMAPS · SMOKE TEST
      </div>
    </AbsoluteFill>
  );
};
