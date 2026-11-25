// The ML model in JavaScript. model.json holds the trained gradient-boosting trees (made by export_model.py).
// Prediction = baseline + sum of the tree values for each class, then softmax -> probabilities.
const fs = require('fs');
const path = require('path');
const M = JSON.parse(fs.readFileSync(path.join(__dirname, 'model.json'), 'utf8'));

const BAD_WEATHER = /Rain|Snow|Fog|Storm|Haze|Thunder|Drizzle|Sleet/i;
const RUSH_HOURS = [7, 8, 9, 16, 17, 18, 19];

// same steps as features.py: engineered features -> rare weather/state = "Other" -> one-hot -> model column order
function buildRow(a, state) {
  const f = {
    Hour: a.hour, DayOfWeek: a.day_of_week, 'Temperature(F)': a.temperature, 'Humidity(%)': a.humidity,
    'Visibility(mi)': a.visibility, 'Wind_Speed(mph)': a.wind_speed, 'Precipitation(in)': a.precipitation,
    Junction: a.junction, Traffic_Signal: a.traffic_signal, Crossing: a.crossing, Stop: a.stop, Railway: a.railway,
    Is_Night: a.is_night,
  };
  f.Is_Weekend = a.day_of_week >= 5 ? 1 : 0;
  f.Is_Rush_Hour = RUSH_HOURS.includes(a.hour) ? 1 : 0;
  f.Low_Visibility = a.visibility < 2 ? 1 : 0;
  f.Bad_Weather = BAD_WEATHER.test(a.weather) ? 1 : 0;
  f.Night_Bad_Weather = a.is_night * f.Bad_Weather;
  f.Road_Complexity = a.junction + a.traffic_signal + a.crossing + a.stop + a.railway;
  const w = M.weathers.includes(a.weather) ? a.weather : 'Other';
  const s = M.states.includes(state) ? state : 'Other';
  f['Weather_Condition_' + w] = 1;
  f['State_' + s] = 1;
  return M.columns.map(c => f[c] || 0);
}

function treeValue(t, x) {
  let i = 0;
  while (!t.leaf[i]) {
    const v = x[t.feat[i]];
    i = (Number.isNaN(v) ? t.miss[i] : v <= t.thr[i]) ? t.left[i] : t.right[i];
  }
  return t.val[i];
}

function proba(x) {
  const raw = M.baseline.slice();
  for (const round of M.trees) round.forEach((t, k) => { raw[k] += treeValue(t, x); });
  const mx = Math.max(...raw), e = raw.map(v => Math.exp(v - mx)), sum = e.reduce((p, c) => p + c, 0);
  return e.map(v => v / sum);
}

function predictRaw(a) {
  // a state that is not a 2-letter US code (for example an Indian state): ignore location and
  // average the score over all the locations the model knows
  const states = a.state.length === 2 ? [a.state] : M.states;
  const avg = M.classes.map(() => 0);
  for (const s of states) proba(buildRow(a, s)).forEach((p, k) => { avg[k] += p / states.length; });
  return avg;
}

const r2 = x => Math.round(x * 100) / 100;
function predict(a) {
  const p = predictRaw(a), best = p.indexOf(Math.max(...p));
  const probabilities = {};
  M.classes.forEach((c, k) => { probabilities[c] = r2(p[k]); });
  return { severity: M.classes[best], confidence: r2(p[best]), probabilities,
    high_severity_risk: r2((probabilities[3] || 0) + (probabilities[4] || 0)), low_confidence: p[best] < 0.5 };
}
module.exports = { predict, predictRaw };
