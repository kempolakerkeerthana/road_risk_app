// Member 3: weather based route advice.
// Tables read: route_options + locations + weather_rules (joined in one query). Does not use the ML model.
const { Router } = require('express');
const { q } = require('./db');
const { HttpError, wrap, intQ } = require('./util');
const router = Router();

router.get('/weather-types', wrap(async (req, res) => {
  res.json((await q('SELECT weather FROM weather_rules ORDER BY id')).map(r => r.weather));
}));

router.get('/route-advice', wrap(async (req, res) => {
  const locationId = intQ(req.query.location_id, 'location_id'), weather = String(req.query.weather || '');
  const rows = await q(`SELECT l.area, l.district, r.route_name, r.via, r.is_main, r.waterlogging_prone,
                               r.extra_minutes, w.avoid_prone, w.advice
                        FROM route_options r
                        JOIN locations l ON l.id = r.location_id
                        JOIN weather_rules w ON w.weather = ?
                        WHERE r.location_id = ? ORDER BY r.is_main DESC, r.extra_minutes`, [weather, locationId]);
  if (!rows.length) throw new HttpError(404, 'Unknown location or weather');
  // Avoid = the weather rule says avoid prone roads AND this road is water-logging prone
  const routes = rows.map(r => ({ route: r.route_name, via: r.via, is_main: !!r.is_main, extra_minutes: r.extra_minutes,
    waterlogging_prone: !!r.waterlogging_prone, status: r.avoid_prone && r.waterlogging_prone ? 'Avoid' : 'OK' }));
  const best = routes.filter(r => r.status === 'OK').sort((a, b) => a.extra_minutes - b.extra_minutes)[0];
  res.json({ area: rows[0].area, district: rows[0].district, weather, advice: rows[0].advice, recommended: best.route, routes });
}));
module.exports = router;
