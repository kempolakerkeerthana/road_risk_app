// Distance between two GPS points (haversine formula), in km. No library needed.
function haversineKm(lat1, lon1, lat2, lon2) {
  const rad = d => (d * Math.PI) / 180;
  const p1 = rad(lat1), p2 = rad(lat2);
  const a = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(rad(lon2 - lon1) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(a));
}
module.exports = { haversineKm };
