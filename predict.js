// Member 1: prediction, history, dashboard and analysis.
// The trained model (model.json) is run in JavaScript by model.js, so no Python is needed.
// This file checks the input, predicts, and saves the result in MySQL.
// Tables read: predictions + locations.
const fs = require('fs');
const path = require('path');
const { Router } = require('express');
const { q } = require('./db');
const { predict } = require('./model');
const { HttpError, wrap, intQ, num, str } = require('./util');
const router = Router();
router.get('/health', wrap(async (req, res) => {
  await q('SELECT 1');
  res.json({ status: 'ok', database: 'mysql', model: 'loaded' });
}));

router.post('/predict', wrap(async (req, res) => {
  const b = req.body || {};
  const a = {
    hour: num(b, 'hour', { int: true, min: 0, max: 23 }), day_of_week: num(b, 'day_of_week', { int: true, min: 0, max: 6 }),
    temperature: num(b, 'temperature'), humidity: num(b, 'humidity'), visibility: num(b, 'visibility'),
    state: str(b, 'state', { def: 'CA', max: 40 }), weather: str(b, 'weather', { def: 'Fair', max: 40 }),
    wind_speed: num(b, 'wind_speed', { def: 0 }), precipitation: num(b, 'precipitation', { def: 0 }),
    junction: num(b, 'junction', { def: 0, int: true }), traffic_signal: num(b, 'traffic_signal', { def: 0, int: true }),
    crossing: num(b, 'crossing', { def: 0, int: true }), stop: num(b, 'stop', { def: 0, int: true }),
    railway: num(b, 'railway', { def: 0, int: true }), is_night: num(b, 'is_night', { def: 0, int: true }),
    location_id: b.location_id ? num(b, 'location_id', { int: true }) : null, save: num(b, 'save', { def: 1, int: true }),
  };
  if (a.save && a.location_id && !(await q('SELECT 1 FROM locations WHERE id=?', [a.location_id])).length) throw new HttpError(400, 'Unknown area');
  const out = predict(a);
  if (a.save)
    await q('INSERT INTO predictions(location_id,inputs,severity,confidence) VALUES (?,?,?,?)', [a.location_id, JSON.stringify(a), out.severity, out.confidence]);
  res.json(out);
}));

router.get('/history', wrap(async (req, res) => {
  const rows = await q(`SELECT p.id, p.inputs, p.severity, p.confidence, p.note, p.created, l.area, l.district
                        FROM predictions p LEFT JOIN locations l ON l.id = p.location_id ORDER BY p.id DESC`);
  res.json(rows.map(r => ({ id: r.id, inputs: JSON.parse(r.inputs), severity: r.severity, confidence: r.confidence,
    note: r.note, created: r.created, area: r.area, district: r.district })));
}));

router.put('/history/:hid', wrap(async (req, res) => {
  await q('UPDATE predictions SET note=? WHERE id=?', [str(req.body || {}, 'note', { max: 255 }), intQ(req.params.hid, 'hid')]);
  res.json({ message: 'Updated' });
}));

router.delete('/history/:hid', wrap(async (req, res) => {
  await q('DELETE FROM predictions WHERE id=?', [intQ(req.params.hid, 'hid')]);
  res.json({ message: 'Deleted' });
}));

router.get('/stats', wrap(async (req, res) => {
  const rows = await q('SELECT severity, COUNT(*) AS n FROM predictions GROUP BY severity');
  res.json({ by_severity: Object.fromEntries(rows.map(r => [r.severity, Number(r.n)])) });
}));

// analysis numbers were made by train_model.py (from the notebook's analysis)
router.get('/analysis', wrap(async (req, res) => {
  const f = path.join(__dirname, 'analysis.json');
  if (!fs.existsSync(f)) throw new HttpError(404, 'Run train_model.py first');
  res.json(JSON.parse(fs.readFileSync(f, 'utf8')));
}));
module.exports = router;
