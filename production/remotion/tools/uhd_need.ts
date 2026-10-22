// Which 256-px UHD tiles does the camera path need so that no visible map point is up-scaled?
// A point needs UHD when HD (4 px/canvas px nominal, ~3.5 effective) would still be soft there
// (local magnification / 3.5 > 0.92) or when no HD tile exists and the basemap would be magnified > 1.12x.
// usage: npx -y tsx tools/uhd_need.ts [out.json]   (prints counts; writes the *missing* tile list)
import fs from 'fs';
import {cameraAt, unproject} from '../src/lib/camera';
import {CLIPS} from '../src/script';
import {OPENING} from '../src/v2';
import hd from '../src/data/hd_index.json';
import uhd from '../src/data/uhd_index.json';

const HD: any = hd, UHD: any = uhd, TL = 256;
const hdSet = new Set(HD.tiles.map(([i, j]: number[]) => `${i},${j}`));
const have = new Set(UHD.tiles.map(([x, y]: number[]) => `${x},${y}`));
const END = 580.2;
const HD_Z0 = Number(process.env.HD_Z0 ?? 0.70), UHD_Z0 = Number(process.env.UHD_Z0 ?? 1.7);
const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const opaque = (t: number) => CLIPS.some((c) => c.kind === 'cauc' && t >= c.from + 0.7 && t <= c.to - 0.6);
function mag(cam: any, sx: number, sy: number) {
  const [wx, wy] = unproject(cam, sx, sy), [ax, ay] = unproject(cam, sx + 1, sy), [bx, by] = unproject(cam, sx, sy + 1);
  const a = ax - wx, b = bx - wx, c = ay - wy, d = by - wy, det = a * d - b * c;
  const M = [[d / det, -b / det], [-c / det, a / det]];
  const p = M[0][0], q = M[0][1], r = M[1][0], s = M[1][1];
  const s1 = p * p + q * q + r * r + s * s, s2 = Math.sqrt((p * p + q * q - r * r - s * s) ** 2 + 4 * (p * r + q * s) ** 2);
  return {wx, wy, m: Math.sqrt((s1 + s2) / 2)};
}
const need = new Map<string, number>();     // tile -> first time needed
const hdNeed = new Map<string, number>();   // missing HD cells (512 px) needed below the UHD zoom
let lowZoomNoHd = 0;
for (let t = OPENING.mapIn; t < END; t += 1 / 15) {
  if (opaque(t)) continue;
  const cam = cameraAt(t);
  const ou = clamp((cam.zoom - UHD_Z0) / 0.3);
  for (let sy = 0; sy <= 1080; sy += 45) for (let sx = 0; sx <= 1920; sx += 48) {
    const {wx, wy, m} = mag(cam, sx, sy);
    const hasHd = hdSet.has(`${Math.floor((wx - HD.x0) / HD.tile)},${Math.floor((wy - HD.y0) / HD.tile)}`) && cam.zoom >= HD_Z0 + 0.07;
    const bad = hasHd ? m / 3.5 > 0.92 : m > 1.12;
    if (!bad) continue;
    if (ou < 0.5) {                                 // UHD not shown at this zoom: needs an HD cell
      lowZoomNoHd++;
      const k = `${Math.floor((wx - HD.x0) / HD.tile)},${Math.floor((wy - HD.y0) / HD.tile)}`;
      if (!hdNeed.has(k)) hdNeed.set(k, t);
      continue;
    }
    // the tile under the point plus a 1-tile safety ring on the side of the screen edge
    for (const [dx, dy] of [[0, 0], [-1, 0], [1, 0], [0, -1], [0, 1]]) {
      const k = `${(Math.floor(wx / TL) + dx) * TL},${(Math.floor(wy / TL) + dy) * TL}`;
      if (dx || dy) { if (sx > 0 && sx < 1920 && sy > 0 && sy < 1080) continue; }
      if (!need.has(k)) need.set(k, t);
    }
  }
}
const missing = [...need.keys()].filter((k) => !have.has(k)).map((k) => k.split(',').map(Number)).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
console.log(`needed ${need.size} tiles, have ${have.size}, missing ${missing.length}; low-zoom points without HD/UHD: ${lowZoomNoHd}`);
const byT = new Map<number, number>();
for (const [k, t] of need) if (!have.has(k)) byT.set(Math.floor(t / 10) * 10, (byT.get(Math.floor(t / 10) * 10) ?? 0) + 1);
console.log('missing by first-need time (10 s bins):', [...byT.entries()].sort((a, b) => a[0] - b[0]).map(([t, n]) => `${t}s:${n}`).join(' '));
console.log('missing HD cells:', JSON.stringify([...hdNeed.entries()].map(([k, t]) => k + '@' + t.toFixed(1))));
if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify({uhd: missing, hd: [...hdNeed.keys()].map((k) => k.split(',').map(Number))}));
