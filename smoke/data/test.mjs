// Smoke test of geo tools: Natural Earth + mapshaper output + turf + polylabel + flubber + d3-geo.
// Also checks known border traps (Crimea, Abkhazia, Transnistria) so the final maps are historically correct for 1991.
import fs from 'fs';
import * as turf from '@turf/turf';
import polylabel from 'polylabel';
import flubber from 'flubber';
import {geoMercator, geoPath} from 'd3-geo';

const fc = JSON.parse(fs.readFileSync('ussr15.json', 'utf8'));
const report = {features: fc.features.length, flags: {}, traps: {}};
console.log('USSR-15 features:', fc.features.length);
for (const f of fc.features) {
  const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
  const biggest = polys.map((p) => ({p, a: turf.area(turf.polygon(p))})).sort((a, b) => b.a - a.a)[0].p;
  const pl = polylabel(biggest, 0.05);
  report.flags[f.properties.ADM0_A3] = [+pl[0].toFixed(2), +pl[1].toFixed(2)];
}
console.log('Flag landing points (polylabel):', JSON.stringify(report.flags));

const world = JSON.parse(fs.readFileSync('ne50.geojson', 'utf8'));
const owner = (lon, lat) => {
  const pt = turf.point([lon, lat]);
  const f = world.features.find((g) => turf.booleanPointInPolygon(pt, g));
  return f ? f.properties.ADM0_A3 : 'none';
};
report.traps = {
  'Crimea (34.1,45.0)': owner(34.1, 45.0),
  'Sevastopol (33.52,44.6)': owner(33.52, 44.6),
  'Abkhazia (41.0,43.0)': owner(41.0, 43.0),
  'South Ossetia (44.0,42.3)': owner(44.0, 42.3),
  'Transnistria (29.6,47.0)': owner(29.6, 47.0),
  'Kaliningrad (20.5,54.7)': owner(20.5, 54.7),
};
console.log('Border traps in Natural Earth default view:', JSON.stringify(report.traps));

const adm1 = JSON.parse(fs.readFileSync('rus_adm1.json', 'utf8'));
const reps = adm1.features.filter((f) => /republic/i.test(f.properties.type_en || '')).map((f) => f.properties.name);
report.russia_admin1 = adm1.features.length;
report.russia_republics = reps;
console.log('Russia admin-1 units:', adm1.features.length, '| republics:', reps.length, reps.join('; '));

const proj = geoMercator().rotate([-70, 0]).center([0, 55]).scale(600).translate([960, 540]);
const path = geoPath(proj);
const first = (d) => d.split('Z')[0] + 'Z';
const a = first(path(fc.features[0])), b = first(path(fc.features[1]));
const interp = flubber.interpolate(a, b, {maxSegmentLength: 8});
report.flubber_mid_len = interp(0.5).length;
console.log('flubber morph OK, mid-path chars:', report.flubber_mid_len);
fs.writeFileSync('report.json', JSON.stringify(report, null, 1));
