// MySQL connection for the whole app. Creates the database + tables, and fills sample data the first time.
const fs = require('fs');
const path = require('path');
const mysql = require('mysql2/promise');

// read settings from the .env file (tiny parser, no extra package)
try {
  for (const line of fs.readFileSync(path.join(__dirname, '.env'), 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z_]+)\s*=\s*(.*?)\s*$/);
    if (m && !line.trim().startsWith('#') && process.env[m[1]] === undefined) process.env[m[1]] = m[2];
  }
} catch (e) { /* no .env file: defaults below are used */ }

const cfg = {
  host: process.env.DB_HOST || '127.0.0.1',
  port: Number(process.env.DB_PORT || 3306),
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
};
const DB_NAME = process.env.DB_NAME || 'roadsafety';
let pool;

// q(sql, [values]) -> rows (SELECT) or {insertId, affectedRows} (INSERT/UPDATE/DELETE)
async function q(sql, params) { return (await pool.query(sql, params))[0]; }

async function init() {
  // online MySQL hosts need an encrypted connection: set DB_SSL=true (and DB_SSL_CA with the host's certificate text if they give one)
  if (process.env.DB_SSL === 'true')
    cfg.ssl = { minVersion: 'TLSv1.2', rejectUnauthorized: true, ...(process.env.DB_SSL_CA ? { ca: process.env.DB_SSL_CA.replace(/\\n/g, '\n') } : {}) };
  try {                                  // on a hosted MySQL the database usually exists already and this may be refused: that is fine
    const first = await mysql.createConnection(cfg);
    await first.query(`CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4`);
    await first.end();
  } catch (e) { if (e.code === 'ECONNREFUSED' || e.code === 'ER_ACCESS_DENIED_ERROR') throw e; }
  pool = mysql.createPool({ ...cfg, database: DB_NAME, dateStrings: true, connectionLimit: 10 });
  const sql = fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf8')
    .split(/\r?\n/).filter(l => !l.trim().startsWith('--')).join('\n');
  for (const stmt of sql.split(';').map(s => s.trim()).filter(Boolean)) await pool.query(stmt);
  await require('./seed')(q);
}

module.exports = { init, q, DB_NAME };
