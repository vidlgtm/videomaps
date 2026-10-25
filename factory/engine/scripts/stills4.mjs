// v4 verification stills, rendered exactly like the film (swangle GL): node scripts/stills4.mjs <outDir> t1 t2 ...
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import path from 'path';
const [outDir, ...ts] = process.argv.slice(2);
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), publicDir: path.resolve('public')});
const chromiumOptions = {gl: 'swangle'};
const comp = await selectComposition({serveUrl, id: 'Main', inputProps: {}, chromiumOptions});
for (const t of ts) {
  const frame = Math.min(comp.durationInFrames - 1, Math.round(parseFloat(t) * comp.fps));
  const output = path.join(outDir, `t${String(t).replace('.', '_')}.jpg`);
  const t0 = Date.now();
  await renderStill({composition: comp, serveUrl, output, frame, inputProps: {}, imageFormat: 'jpeg', jpegQuality: 95, chromiumOptions,
    timeoutInMilliseconds: 900000});
  console.log('still', t, 'frame', frame, output, ((Date.now() - t0) / 1000).toFixed(1) + 's');
}
