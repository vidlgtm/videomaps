// which country names are actually visible (after declutter) through the film, sampled every 4 s
import {frameLayout, declutter} from '../src/lib/layout';
import {TOTAL} from '../src/lib/cues';
const mm = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
let last = '';
for (let t = 0; t < TOTAL; t += 4) {
  const {L} = frameLayout(Math.round(t * 30));
  const dec = declutter(t);
  const vis = L.names.filter((n) => n.o * dec(n.id) > 0.5).map((n) => `${n.text}${n.sub ? ' ' + n.sub : ''}(${Math.round(n.fs)})`);
  const line = vis.join(', ');
  if (line !== last) console.log(mm(t), '|', line || '-');
  last = line;
}
