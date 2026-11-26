// Member 4: places list (state -> district -> area) and "which area is closest to my GPS position".
// Tables read: locations. Distances come from geo.js.
const { Router } = require('express');
const { q } = require('./db');
const { haversineKm } = require('./geo');
const { wrap, numQ, round } = require('./util');
const router = Router();

router.get('/locations', wrap(async (req, res) => {
  res.json(await q('SELECT id, state, district, area, lat, lon FROM locations ORDER BY state, district, area'));
}));

router.get('/nearest-area', wrap(async (req, res) => {
  const lat = numQ(req.query.lat, 'lat'), lon = numQ(req.query.lon, 'lon');
  const rows = await q('SELECT id, state, district, area, lat, lon FROM locations');
  const best = rows.map(r => ({ r, d: haversineKm(lat, lon, r.lat, r.lon) })).sort((a, b) => a.d - b.d)[0];
  const d = round(best.d);
  res.json({ ...best.r, distance_km: d, outside_coverage: d > 40 });
}));
module.exports = router;
