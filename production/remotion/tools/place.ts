// helper: inspect the layout at a time and convert screen positions to lon/lat (for placing elements by hand)
import {layoutAt, inter} from '../src/lib/layout';
import {unproject} from '../src/lib/camera';
import {px, project} from '../src/lib/proj';
export function lonlat(wx: number, wy: number): [number, number] {
  let lon = 60, lat = 50;
  for (let i = 0; i < 40; i++) {
    const [x, y] = px(lon, lat), e = 1e-4;
    const [x1, y1] = px(lon + e, lat), [x2, y2] = px(lon, lat + e);
    const a = (x1 - x) / e, b = (x2 - x) / e, c = (y1 - y) / e, d = (y2 - y) / e, det = a * d - b * c;
    const dx = wx - x, dy = wy - y;
    lon += (d * dx - b * dy) / det; lat += (-c * dx + a * dy) / det;
  }
  return [Math.round(lon * 100) / 100, Math.round(lat * 100) / 100];
}
const args = process.argv.slice(2);
const t = parseFloat(args[0]);
const L = layoutAt(t);
if (args[1] === 'items') {
  const re = new RegExp(args[2] ?? '.');
  L.items.filter((i) => re.test(i.id)).forEach((i) => console.log(i.id, i.prio, i.o.toFixed(2), [i.x0, i.y0, i.x1, i.y1].map(Math.round).join(',')));
  if (args[3]) { const me = L.items.find((i) => i.id === args[3]); if (me) L.items.filter((i) => i !== me && inter(i, me) > 0).forEach((i) => console.log('  covers?', i.id, i.prio, Math.round(inter(i, me)))); }
} else if (args[1] === 'at') {
  const [sx, sy] = [parseFloat(args[2]), parseFloat(args[3])];
  console.log('screen', sx, sy, '-> lonlat', lonlat(...unproject(L.cam, sx, sy)));
} else if (args[1] === 'proj') {
  const q = project(L.cam, ...px(parseFloat(args[2]), parseFloat(args[3])));
  console.log('lonlat', args[2], args[3], '-> screen', Math.round(q.x), Math.round(q.y), 'zoom', L.cam.zoom.toFixed(2));
}
