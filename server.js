// Road Accident Severity Prediction - Node.js (Express) + MySQL.
// Start:  npm install   then   node server.js      (and start predict_service.py for the ML model)
const path = require('path');
const express = require('express');
const db = require('./db');

const app = express();
app.use(express.json());
app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'index.html')));
for (const f of ['predict', 'traffic', 'routeAdvice', 'locations', 'alerts', 'incidents'])
  app.use(require('./' + f));

// errors are sent as {"detail": "..."} - the web page reads this field
app.use((err, req, res, next) => {
  if (err.type === 'entity.parse.failed') return res.status(422).json({ detail: 'Request body is not valid JSON' });
  if (err.status) return res.status(err.status).json({ detail: err.detail || err.message });
  console.error(err);
  res.status(500).json({ detail: 'Server error: ' + err.message });
});

const PORT = Number(process.env.PORT || 8000);
db.init().then(() => app.listen(PORT, () => console.log(`App running:  http://127.0.0.1:${PORT}`)))
  .catch(e => {
    console.error('\nCould not start. ' + (
      e.code === 'ECONNREFUSED' ? 'MySQL is not running (or the port is wrong). Start the MySQL service, then try again.' :
      e.code === 'ER_ACCESS_DENIED_ERROR' ? 'MySQL refused the user name/password. Copy .env.example to .env and put your MySQL password.' :
      e.message));
    process.exit(1);
  });
