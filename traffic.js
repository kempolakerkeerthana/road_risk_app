// Member 2: traffic patterns (weekday / Saturday / Sunday) and the driver claim check.
// Tables read: traffic_records + junctions + locations (joined), and claims.
const { Router } = require('express');
const { q } = require('./db');
const { HttpError, wrap, intQ, num, str, round } = require('./util');
const router = Router();
const DAYS = ['Weekday', 'Saturday', 'Sunday'];

router.get('/junctions', wrap(async (req, res) => {
  const rows = await q('SELECT id, name FROM junctions WHERE location_id=? ORDER BY id', [intQ(req.query.location_id, 'location_id')]);
  res.json(rows.map(r => ({ id: r.id, name: r.name })));
}));

router.get('/traffic', wrap(async (req, res) => {
  const rows = await q(`SELECT j.name AS junction, l.area, l.district, t.day_type, t.\`hour\` AS hr, t.avg_delay_min AS delay
                        FROM traffic_records t
                        JOIN junctions j ON j.id = t.junction_id
                        JOIN locations l ON l.id = j.location_id
                        WHERE t.junction_id=? ORDER BY t.day_type, t.\`hour\``, [intQ(req.query.junction_id, 'junction_id')]);
  if (!rows.length) throw new HttpError(404, 'Junction not found');
  const series = Object.fromEntries(DAYS.map(d => [d, Array(24).fill(0)]));
  rows.forEach(r => { series[r.day_type][r.hr] = r.delay; });
  const summary = {};
  for (const d of DAYS) {
    let peak = 0;
    series[d].forEach((v, h) => { if (v > series[d][peak]) peak = h; });
    summary[d] = { peak_hour: peak, peak_delay: series[d][peak], average: round(series[d].reduce((a, b) => a + b, 0) / 24) };
  }
  res.json({ junction: rows[0].junction, area: rows[0].area, district: rows[0].district, series, summary });
}));

router.post('/claims', wrap(async (req, res) => {
  const b = req.body || {};
  const c = { junction_id: num(b, 'junction_id', { int: true }), driver: str(b, 'driver', { min: 2, max: 80 }), day_type: str(b, 'day_type'),
    start_hour: num(b, 'start_hour', { int: true, min: 0, max: 23 }), end_hour: num(b, 'end_hour', { int: true, min: 0, max: 23 }),
    claimed_delay_min: num(b, 'claimed_delay_min', { min: 0 }) };
  if (!DAYS.includes(c.day_type) || c.end_hour < c.start_hour) throw new HttpError(400, 'Check the day type and the hours');
  const [row] = await q(`SELECT AVG(avg_delay_min) AS t FROM traffic_records
                         WHERE junction_id=? AND day_type=? AND \`hour\` BETWEEN ? AND ?`, [c.junction_id, c.day_type, c.start_hour, c.end_hour]);
  if (row.t === null) throw new HttpError(404, 'Junction not found');
  const typical = round(Number(row.t));
  // a claimed delay up to 1.5 x the typical delay (+3 min) is accepted as consistent
  const ok = c.claimed_delay_min <= typical * 1.5 + 3;
  const verdict = ok ? 'Consistent with typical traffic' : 'Higher than typical traffic - verify the claim';
  await q(`INSERT INTO claims(junction_id,driver,day_type,start_hour,end_hour,claimed_delay_min,typical_delay_min,verdict) VALUES (?,?,?,?,?,?,?,?)`,
    [c.junction_id, c.driver, c.day_type, c.start_hour, c.end_hour, c.claimed_delay_min, typical, verdict]);
  res.json({ typical_delay_min: typical, claimed_delay_min: c.claimed_delay_min, verdict, consistent: ok });
}));

router.get('/claims', wrap(async (req, res) => {
  res.json(await q(`SELECT c.id, c.driver, j.name AS junction, l.area, c.day_type, c.start_hour, c.end_hour,
                           c.claimed_delay_min AS claimed, c.typical_delay_min AS typical, c.verdict, c.created
                    FROM claims c JOIN junctions j ON j.id = c.junction_id
                    JOIN locations l ON l.id = j.location_id ORDER BY c.id DESC`));
}));

router.delete('/claims/:cid', wrap(async (req, res) => {
  await q('DELETE FROM claims WHERE id=?', [intQ(req.params.cid, 'cid')]);
  res.json({ message: 'Deleted' });
}));
module.exports = router;
