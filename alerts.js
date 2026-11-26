// Member 1: alerts from the Road Safety Officer to a traffic police station.
// Tables read: alerts + junctions + locations + police_stations (4 tables joined).
const { Router } = require('express');
const { q } = require('./db');
const { HttpError, wrap, intQ, num, str } = require('./util');
const router = Router();
const STATUSES = ['Sent', 'Acknowledged', 'Cleared'];

router.get('/stations', wrap(async (req, res) => {
  res.json(await q(`SELECT s.id, s.name, l.area, l.district FROM police_stations s
                    JOIN locations l ON l.id = s.location_id ORDER BY s.id`));
}));

router.post('/alerts', wrap(async (req, res) => {
  const b = req.body || {};
  const junctionId = num(b, 'junction_id', { int: true }), priority = str(b, 'priority', { def: 'High' }), message = str(b, 'message', { min: 3 });
  if (!['High', 'Medium', 'Low'].includes(priority)) throw new HttpError(400, 'Priority must be High, Medium or Low');
  const [st] = await q(`SELECT s.id, s.name FROM junctions j JOIN police_stations s ON s.location_id = j.location_id WHERE j.id=?`, [junctionId]);
  if (!st) throw new HttpError(404, 'No police station found for this junction');
  await q('INSERT INTO alerts(junction_id,station_id,priority,message) VALUES (?,?,?,?)', [junctionId, st.id, priority, message]);
  res.json({ message: 'Alert sent', station: st.name });
}));

router.get('/alerts', wrap(async (req, res) => {
  res.json(await q(`SELECT a.id, j.name AS junction, l.area, s.name AS station, a.priority, a.message, a.status, a.created
                    FROM alerts a
                    JOIN junctions j ON j.id = a.junction_id
                    JOIN locations l ON l.id = j.location_id
                    JOIN police_stations s ON s.id = a.station_id
                    WHERE a.station_id=? ORDER BY a.id DESC`, [intQ(req.query.station_id, 'station_id')]));
}));

router.put('/alerts/:aid', wrap(async (req, res) => {
  const status = str(req.body || {}, 'status');
  if (!STATUSES.includes(status)) throw new HttpError(400, 'Status must be Sent, Acknowledged or Cleared');
  await q('UPDATE alerts SET status=? WHERE id=?', [status, intQ(req.params.aid, 'aid')]);
  res.json({ message: 'Updated' });
}));

router.delete('/alerts/:aid', wrap(async (req, res) => {
  await q('DELETE FROM alerts WHERE id=?', [intQ(req.params.aid, 'aid')]);
  res.json({ message: 'Deleted' });
}));
module.exports = router;
