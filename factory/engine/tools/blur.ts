// Sharpness audit (pure math, no rendering): for every 1/6 s, sample a 16x9 grid of screen points on the map plane and
// estimate how many screen px each *source texel* covers (local magnification / texel density of the layer that is
// actually visible there: UHD 8 px/canvas px, HD 4 px nominal (~3 effective, Blue Marble colour), basemap 1).
// > 1.5 screen px per texel reads as blurry, 1.15-1.5 as soft. Also flags raster up-scaling (perspective > SS) and haze.
// usage: npx -y tsx tools/blur.ts [step_s] [threshold]
import {cameraAt, unproject} from '../src/lib/camera';
import {px} from '../src/lib/proj';
import {CLIPS, END} from '../src/script';
import {OPENING} from '../src/v2';
import hd from '../src/data/hd_index.json';
import uhd from '../src/data/uhd_index.json';

const HD: any = hd, UHD: any = uhd;
const SS = Number(process.env.SS ?? 1.4);
const HD_EFF = Number(process.env.HD_EFF ?? 3.5);
const hdSet = new Set(HD.tiles.map(([i, j]: number[]) => `${i},${j}`));
const uhdSet = new Set(UHD.tiles.map(([x, y]: number[]) => `${x},${y}`));
const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const step = Number(process.argv[2] ?? 1 / 6), thr = Number(process.argv[3] ?? 1.5);

function inv2(J: number[][]) { const d = J[0][0] * J[1][1] - J[0][1] * J[1][0]; return [[J[1][1] / d, -J[0][1] / d], [-J[1][0] / d, J[0][0] / d]]; }
function maxSing(M: number[][]) {   // largest singular value of a 2x2
  const a = M[0][0], b = M[0][1], c = M[1][0], d = M[1][1];
  const s1 = a * a + b * b + c * c + d * d, s2 = Math.sqrt((a * a + b * b - c * c - d * d) ** 2 + 4 * (a * c + b * d) ** 2);
  return Math.sqrt((s1 + s2) / 2);
}
type Row = {t: number; zoom: number; tilt: number; blur: number; frac: number; soft: number; where: string; layer: string; persp: number; lonlat: string};
const rows: Row[] = [];
const opaque = (t: number) => CLIPS.some((c) => c.kind === 'cauc' && t >= c.from + 0.7 && t <= c.to - 0.6);
const lonlatOf = (wx: number, wy: number) => {   // brute inverse via px() (coarse search), only for reporting
  let best = [0, 0], bd = 1e18;
  for (let lo = 15; lo <= 180; lo += 0.5) for (let la = 30; la <= 80; la += 0.5) {
    const [x, y] = px(lo, la); const d = (x - wx) ** 2 + (y - wy) ** 2; if (d < bd) { bd = d; best = [lo, la]; }
  }
  return `${best[0].toFixed(1)}E ${best[1].toFixed(1)}N`;
};
for (let t = OPENING.mapIn; t < END; t += step) {
  if (opaque(t)) continue;
  const cam = cameraAt(t);
  const oh = clamp((cam.zoom - Number(process.env.HD_Z0 ?? 0.70)) / Number(process.env.HD_FADE ?? 0.12)), ou = clamp((cam.zoom - Number(process.env.UHD_Z0 ?? 1.85)) / 0.3);
  let worst = 0, n = 0, nb = 0, ns = 0, wp = '', wl = '', pmax = 0;
  for (let gy = 0; gy < 9; gy++) for (let gx = 0; gx < 16; gx++) {
    const sx = 60 + gx * 120, sy = 40 + gy * 125;
    const [wx, wy] = unproject(cam, sx, sy);
    const [ax, ay] = unproject(cam, sx + 1, sy), [bx, by] = unproject(cam, sx, sy + 1);
    const J = [[ax - wx, bx - wx], [ay - wy, by - wy]];          // world px per screen px
    const mag = maxSing(inv2(J));                                 // max screen px per world px
    const uh = uhdSet.has(`${Math.floor(wx / UHD.tile) * UHD.tile},${Math.floor(wy / UHD.tile) * UHD.tile}`) && ou >= 0.5;
    const hh = hdSet.has(`${Math.floor((wx - HD.x0) / HD.tile)},${Math.floor((wy - HD.y0) / HD.tile)}`) && oh >= 0.5;
    const k = uh ? 8 : hh ? HD_EFF : 1;
    const b = mag / k, pr = mag / cam.zoom / SS;
    pmax = Math.max(pmax, pr);
    n++; if (b > thr) nb++; if (b > 1.15) ns++;
    if (b > worst) { worst = b; wp = `${sx},${sy}`; wl = uh ? 'UHD' : hh ? 'HD' : 'base'; }
  }
  rows.push({t, zoom: cam.zoom, tilt: cam.tilt, blur: worst, frac: nb / n, soft: ns / n, where: wp, layer: wl, persp: pmax, lonlat: ''});
}
// merge into intervals where >= 8% of the screen is blurry
const out: string[] = [];
let cur: Row[] = [];
const flush = () => {
  if (!cur.length) return;
  const w = cur.reduce((m, r) => (r.frac > m.frac ? r : m), cur[0]);
  const cam = cameraAt(w.t), [cx, cy] = [cam.x, cam.y];
  out.push(`${cur[0].t.toFixed(1)}-${cur[cur.length - 1].t.toFixed(1)}s  maxFrac ${(w.frac * 100).toFixed(0)}%  worst ${w.blur.toFixed(2)} (${w.layer} @${w.where})  zoom ${w.zoom.toFixed(2)} tilt ${w.tilt.toFixed(0)}  centre ${lonlatOf(cx, cy)}`);
  cur = [];
};
for (const r of rows) { if (r.frac >= Number(process.env.FRAC ?? 0.08)) cur.push(r); else flush(); }
flush();
console.log(`BLURRY (>${thr} screen px per texel on >=8% of the frame):`);
console.log(out.join('\n') || 'none');
const pr = rows.filter((r) => r.persp > 1.0);
console.log(`\nraster up-scale (perspective > SS=${SS}) in ${pr.length} samples, max ${Math.max(0, ...rows.map((r) => r.persp)).toFixed(2)}`);
console.log("haze overlay: removed in v5");
