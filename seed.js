// Sample data for the demo. All places, hospitals, doctors, phone numbers and traffic numbers
// are SAMPLE data made up for the project - replace with real data before any real use.
const PLACES = [
  ['Telangana', 'Hyderabad', ['Madhapur', 'Gachibowli', 'Kukatpally', 'Secunderabad', 'Ameerpet', 'LB Nagar']],
  ['Telangana', 'Rangareddy', ['Shamshabad', 'Ibrahimpatnam']],
  ['Karnataka', 'Bengaluru Urban', ['Whitefield', 'Koramangala', 'Electronic City']],
];
// approximate centre of each area [latitude, longitude]
const COORDS = {
  Madhapur: [17.4486, 78.3908], Gachibowli: [17.4401, 78.3489], Kukatpally: [17.4948, 78.3996],
  Secunderabad: [17.4399, 78.4983], Ameerpet: [17.4375, 78.4483], 'LB Nagar': [17.3457, 78.5522],
  Shamshabad: [17.2403, 78.4294], Ibrahimpatnam: [17.2230, 78.6700],
  Whitefield: [12.9698, 77.7500], Koramangala: [12.9352, 77.6245], 'Electronic City': [12.8452, 77.6602],
};
const WEATHER = [
  ['Clear', 0, 'Normal conditions. Use the fastest route.'],
  ['Light Rain', 0, 'Roads are slippery. Drive slowly, keep extra distance.'],
  ['Heavy Rain', 1, 'Water logging is likely. Avoid low-lying and water-logging-prone roads.'],
  ['Storm', 1, 'Fallen trees and water logging are likely. Avoid prone roads and flyover edges.'],
  ['Fog', 0, 'Low visibility. Use fog lights and prefer well-lit main roads.'],
];
const DRIVERS = [['Ravi Kumar', '9876500001', 'TS09 AB 1234', 'Madhapur'], ['Anita Reddy', '9876500002', 'TS08 CD 5678', 'Gachibowli'],
  ['Imran Khan', '9876500003', 'TS10 EF 9012', 'Kukatpally'], ['Suresh Gowda', '9876500004', 'KA01 GH 3456', 'Whitefield']];

// small seeded random generator, so the sample data is the same on every laptop
function rng(seed) {
  let a = seed;
  const next = () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  return { uniform: (lo, hi) => lo + (hi - lo) * next(), randint: (lo, hi) => lo + Math.floor(next() * (hi - lo + 1)), random: next };
}
const r1 = x => Math.round(x * 10) / 10;
const r5 = x => Math.round(x * 1e5) / 1e5;
const pad = (n, w) => String(n).padStart(w, '0');
const peak = (h, c, w) => Math.exp(-(((h - c) / w) ** 2));
function delay(day, hour, factor, rnd) {
  let base;
  if (day === 'Weekday') base = 14 * peak(hour, 9, 1.6) + 16 * peak(hour, 18, 1.8) + 3 * peak(hour, 13, 2) + 1;
  else if (day === 'Saturday') base = 6 * peak(hour, 12, 2.5) + 10 * peak(hour, 19, 2.2) + 1;
  else base = 4 * peak(hour, 11, 3) + 6 * peak(hour, 18, 2.5) + 0.8;
  return r1(Math.max(0.5, base * factor + rnd.uniform(-0.8, 0.8)));
}

module.exports = async function seed(q) {
  const [{ c }] = await q('SELECT COUNT(*) AS c FROM locations');
  if (c) return;                                   // already filled
  const rnd = rng(7);
  for (const w of WEATHER) await q('INSERT INTO weather_rules(weather, avoid_prone, advice) VALUES (?,?,?)', w);
    const ids = {};
  for (const [state, district, areas] of PLACES) {
    for (const area of areas) {
      const [alat, alon] = COORDS[area];
      const lid = (await q('INSERT INTO locations(state,district,area,lat,lon) VALUES (?,?,?,?,?)', [state, district, area, alat, alon])).insertId;
      ids[area] = lid;
      // 2 junctions per area + typical delay for every day type and hour
      for (const jname of [`${area} Main Junction`, `${area} Market Junction`]) {
        const jid = (await q('INSERT INTO junctions(location_id,name,lat,lon) VALUES (?,?,?,?)',
          [lid, jname, r5(alat + rnd.uniform(-0.01, 0.01)), r5(alon + rnd.uniform(-0.01, 0.01))])).insertId;
        const factor = rnd.uniform(0.7, 1.4), rows = [];
        for (const day of ['Weekday', 'Saturday', 'Sunday'])
          for (let hour = 0; hour < 24; hour++) rows.push([jid, day, hour, delay(day, hour, factor, rnd)]);
        await q('INSERT INTO traffic_records(junction_id,day_type,`hour`,avg_delay_min) VALUES ?', [rows]);
      }
      // routes: the main road is water-logging prone in some areas, the others never are
      const prone = rnd.random() < 0.6 ? 1 : 0;
      await q('INSERT INTO route_options(location_id,route_name,via,is_main,waterlogging_prone,extra_minutes) VALUES ?', [[
        [lid, `${area} Main Road`, 'Main road through the area', 1, prone, 0],
        [lid, `${area} Flyover Route`, 'Flyover and service road', 0, 0, rnd.randint(4, 9)],
        [lid, `${area} Ring Road Route`, 'Outer ring road', 0, 0, rnd.randint(10, 18)]]]);
      await q('INSERT INTO police_stations(location_id,name,phone) VALUES (?,?,?)', [lid, `${area} Traffic Police Station`, `90000 ${pad(10000 + lid, 5)}`]);
    }
  }
  // a few sample drivers (home area) so the driver inbox can be shown
  for (const [name, phone, vehicle, area] of DRIVERS)
    await q('INSERT INTO drivers(name,phone,vehicle,location_id) VALUES (?,?,?,?)', [name, phone, vehicle, ids[area]]);
  console.log('Sample data created in MySQL.');
};
