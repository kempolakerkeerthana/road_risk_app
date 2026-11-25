// Small helpers shared by all route files: errors and input checks.
class HttpError extends Error {
  constructor(status, detail) { super(detail); this.status = status; this.detail = detail; }
}
const wrap = fn => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);

// query-string values (always text) -> numbers, 422 if they are not valid
function intQ(v, name) {
  if (v === undefined || !/^-?\d+$/.test(String(v))) throw new HttpError(422, `${name} must be a whole number`);
  return Number(v);
}
function numQ(v, name) {
  const n = Number(v);
  if (v === undefined || v === '' || !Number.isFinite(n)) throw new HttpError(422, `${name} must be a number`);
  return n;
}
// JSON body values
function num(b, name, { min, max, int = false, def } = {}) {
  let v = b[name];
  if (v === undefined || v === null || v === '') {
    if (def !== undefined) return def;
    throw new HttpError(422, `${name} is required`);
  }
  v = Number(v);
  if (!Number.isFinite(v) || (int && !Number.isInteger(v))) throw new HttpError(422, `${name} must be ${int ? 'a whole number' : 'a number'}`);
  if (min !== undefined && v < min) throw new HttpError(422, `${name} must be at least ${min}`);
  if (max !== undefined && v > max) throw new HttpError(422, `${name} must be at most ${max}`);
  return v;
}
function str(b, name, { min = 0, max = 500, def } = {}) {
  let v = b[name];
  if (v === undefined || v === null) {
    if (def !== undefined) return def;
    throw new HttpError(422, `${name} is required`);
  }
  v = String(v).trim();
  if (v.length < min) throw new HttpError(422, `${name} must have at least ${min} characters`);
  if (v.length > max) throw new HttpError(422, `${name} is too long`);
  return v;
}
const round = (x, d = 1) => Math.round(x * 10 ** d) / 10 ** d;

module.exports = { HttpError, wrap, intQ, numQ, num, str, round };
