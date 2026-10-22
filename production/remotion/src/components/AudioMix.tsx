import React from 'react';
import {Audio, Sequence, staticFile} from 'remotion';
import {MUSIC, SFX, END} from '../script';
import {speechAt} from '../lib/cues';
import {clamp} from '../lib/anim';

const FPS = 30;
// v4: speech presence over +-1 s, so the bed stays put through normal sentence pauses (no pumping) and only
// breathes up (+5 dB max) in real beats such as the title
const duck = (t: number) => {
  let s = 0;
  for (let k = -8; k <= 8; k++) s += speechAt(t + k * 0.125);
  return s / 17;
};
const eqp = (x: number) => Math.sin((Math.PI / 2) * clamp(x));   // equal-power fade shape
export const AudioMix: React.FC = () => (
  <>
    <Audio src={staticFile('voice.wav')} volume={1} />
    {MUSIC.map((m, i) => {
      const from = Math.round(m.from * FPS), dur = Math.round((Math.min(m.to, END) - m.from) * FPS);
      const g = Math.pow(10, (-27.5 - m.lufs) / 20);
      return (
        <Sequence key={'m' + i} from={from} durationInFrames={dur} layout="none">
          <Audio src={staticFile(m.src)} volume={(f) => {
            const t = m.from + f / FPS;
            const fade = Math.min(eqp(f / ((m.xin ?? 1.5) * FPS)), eqp((dur - f) / ((m.xout ?? 1.8) * FPS)));
            return g * (1 + 0.8 * Math.pow(1 - duck(t), 1.5)) * fade;
          }} />
        </Sequence>
      );
    })}
    {SFX.filter((s) => s.t >= 0 && s.t < END - 0.5).map((s, i) => (
      <Sequence key={'s' + i} from={Math.round(s.t * FPS)} durationInFrames={Math.round(6.5 * FPS)} layout="none">
        <Audio src={staticFile(`sfx/${s.f}.wav`)} volume={s.v ?? 0.35} />
      </Sequence>
    ))}
  </>
);
