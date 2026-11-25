// Member 1: road incidents (construction, accident, road damage) and the driver inbox.
// When an incident is reported, every registered driver whose home area is within RADIUS_KM gets a message.
// Messages are stored in the app (in-app inbox); real SMS would need an SMS provider such as Twilio.
// Tables read: incidents, junctions, locations, drivers, driver_messages.
const { Router } = require('express');
const { q } = require('../db');
const { haversineKm } = require('../geo');
const { HttpError, wrap, intQ, num, str } = require('../util');
const router = Router();
const KINDS = ['Construction', 'Accident', 'Road damage'];
const RADIUS_KM = 8;
const TIPS = { Construction: 'Expect delays and take another route if you can.', Accident: 'Drive carefully and expect long delays.',
  'Road damage': 'Slow down and watch for damage on the road.' };

async function notify(incidentId, junctionId, kind, description, cleared = false) {
  const [j] = await q('SELECT j.name, l.area, j.lat, j.lon FROM junctions j JOIN locations l ON l.id=j.location_id WHERE j.id=?', [junctionId]);
  const drivers = await q('SELECT d.id, l.lat, l.lon FROM drivers d JOIN locations l ON l.id = d.location_id');
  let n = 0;
  for (const d of drivers) {
    const km = haversineKm(j.lat, j.lon, d.lat, d.lon);
    if (km > RADIUS_KM) continue;
    const head = cleared ? `CLEARED: ${kind} at ${j.name} (${j.area}).` : `${kind.toUpperCase()} at ${j.name} (${j.area}): ${description}.`;
    const tail = cleared ? 'The road is open again.' : `${km.toFixed(1)} km from your area. ${TIPS[kind]}`;
    await q('INSERT INTO driver_messages(driver_id,incident_id,`text`) VALUES (?,?,?)', [d.id, incidentId, `${head} ${tail}`]);
    n++;
  }
  return n;
}

router.post('/incidents', wrap(async (req, res) => {
  const b = req.body || {};
  const i = { junction_id: num(b, 'junction_id', { int: true }), kind: str(b, 'kind'), description: str(b, 'description', { min: 3 }),
    reporter: str(b, 'reporter', { def: 'Road Safety Officer', max: 80 }) };
  if (!KINDS.includes(i.kind)) throw new HttpError(400, 'kind must be Construction, Accident or Road damage');
  if (!(await q('SELECT 1 FROM junctions WHERE id=?', [i.junction_id])).length) throw new HttpError(404, 'Unknown junction');
  const iid = (await q('INSERT INTO incidents(junction_id,kind,description,reporter) VALUES (?,?,?,?)', [i.junction_id, i.kind, i.description, i.reporter])).insertId;
  res.json({ incident_id: iid, drivers_notified: await notify(iid, i.junction_id, i.kind, i.description) });
}));

router.get('/incidents', wrap(async (req, res) => {
  res.json(await q(`SELECT i.id, i.kind, i.description, i.reporter, i.status, i.created, j.name AS junction, l.area, j.lat, j.lon
                    FROM incidents i JOIN junctions j ON j.id = i.junction_id JOIN locations l ON l.id = j.location_id
                    WHERE i.status=? ORDER BY i.id DESC`, [String(req.query.status || 'Active')]));
}));

router.put('/incidents/:iid/clear', wrap(async (req, res) => {
  const iid = intQ(req.params.iid, 'iid');
  const [r] = await q('SELECT junction_id, kind, description, status FROM incidents WHERE id=?', [iid]);
  if (!r) throw new HttpError(404, 'Unknown incident');
  let n = 0;
  if (r.status === 'Active') {
    await q("UPDATE incidents SET status='Cleared' WHERE id=?", [iid]);
    n = await notify(iid, r.junction_id, r.kind, r.description, true);
  }
  res.json({ message: 'Cleared', drivers_notified: n });
}));

router.get('/drivers', wrap(async (req, res) => {
  res.json(await q(`SELECT d.id, d.name, d.phone, d.vehicle, l.area FROM drivers d JOIN locations l ON l.id = d.location_id ORDER BY d.id`));
}));

router.post('/drivers', wrap(async (req, res) => {
  const b = req.body || {};
  const d = { name: str(b, 'name', { min: 2, max: 80 }), phone: str(b, 'phone', { min: 10, max: 15 }), vehicle: str(b, 'vehicle', { def: '', max: 30 }),
    location_id: num(b, 'location_id', { int: true }) };
  if (!/^\d+$/.test(d.phone)) throw new HttpError(400, 'Phone must contain digits only');
  if (!(await q('SELECT 1 FROM locations WHERE id=?', [d.location_id])).length) throw new HttpError(404, 'Unknown area');
  const r = await q('INSERT INTO drivers(name,phone,vehicle,location_id) VALUES (?,?,?,?)', [d.name, d.phone, d.vehicle, d.location_id]);
  res.json({ id: r.insertId });
}));

router.get('/messages', wrap(async (req, res) => {
  const msgs = await q(`SELECT m.id, m.\`text\` AS text, m.status, m.created, i.kind, j.name AS junction, l.area
                        FROM driver_messages m
                        JOIN incidents i ON i.id = m.incident_id
                        JOIN junctions j ON j.id = i.junction_id
                        JOIN locations l ON l.id = j.location_id
                        WHERE m.driver_id=? ORDER BY m.id DESC`, [intQ(req.query.driver_id, 'driver_id')]);
  res.json({ unread: msgs.filter(m => m.status === 'Unread').length, messages: msgs });
}));

router.put('/messages/:mid/read', wrap(async (req, res) => {
  await q("UPDATE driver_messages SET status='Read' WHERE id=?", [intQ(req.params.mid, 'mid')]);
  res.json({ message: 'Updated' });
}));

router.delete('/messages/:mid', wrap(async (req, res) => {
  await q('DELETE FROM driver_messages WHERE id=?', [intQ(req.params.mid, 'mid')]);
  res.json({ message: 'Deleted' });
}));
module.exports = router;
