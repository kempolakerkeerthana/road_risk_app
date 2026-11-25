# Road Accident Severity - Node.js + MySQL

Node.js (Express) runs every screen and the MySQL database. Only the ML prediction stays in Python (predict_service.py).

## One-time setup
1. Install Node.js 18+ (nodejs.org), MySQL Server 8 (dev.mysql.com), and Python (you already have it).
2. Copy `.env.example` to `.env` and write your MySQL password in DB_PASSWORD.
3. In this folder:  `npm install`   and   `pip install -r requirements.txt`

## Every time (2 command windows)
Window 1 (ML model):   `python -m uvicorn predict_service:app --port 8001`
Window 2 (the app):    `node server.js`
Open http://127.0.0.1:8000     Tests: `python test_api.py`

The database `roadsafety` and its 12 tables are created automatically, with sample data.

## Who owns which file
- Member 1: routes/predict.js, routes/alerts.js, routes/incidents.js, predict_service.py
- Member 2: routes/traffic.js
- Member 3: routes/routeAdvice.js
- Member 4: routes/locations.js, db.js, seed.js, schema.sql, geo.js
- Shared: server.js, util.js, index.html
