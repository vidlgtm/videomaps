// Render preview stills at given seconds: node scripts/stills.mjs <publicDir> <outDir> <lite 0|1> t1 t2 ...
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import path from 'path';
const [publicDir, outDir, lite, ...ts] = process.argv.slice(2);
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), publicDir: path.resolve(publicDir)});
const inputProps = {lite: lite === '1'};
const comp = await selectComposition({serveUrl, id: 'Main', inputProps});
for (const t of ts) {
  const frame = Math.min(comp.durationInFrames - 1, Math.round(parseFloat(t) * comp.fps));
  const out = path.join(outDir, `still_${String(t).replace('.', '_')}.jpg`);
  const t0 = Date.now();
  await renderStill({composition: comp, serveUrl, output: out, frame, inputProps, imageFormat: 'jpeg', jpegQuality: 80,
    chromiumOptions: {gl: 'swangle'}, timeoutInMilliseconds: 120000, scale: 0.5});
  console.log('still', t, frame, ((Date.now() - t0) / 1000).toFixed(1) + 's');
}
