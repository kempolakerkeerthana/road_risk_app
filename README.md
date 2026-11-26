# Road Accident Severity - everything in JavaScript (Node.js + Express + MySQL)

The running app has NO Python. The trained model is stored as model.json and run by model.js.
Python is used only OFFLINE in the `training` folder (to train the model once in the notebook/train_model.py).

## Run on your laptop
1. Install Node.js 18+ and MySQL Server 8.
2. Copy `.env.example` to `.env`, write your MySQL password in DB_PASSWORD.
3. `npm install`
4. `node server.js`  -> open http://127.0.0.1:8000
5. Test (second window): `python test_api.py`

The database `roadsafety` and its 12 tables are created automatically, with sample data.

## Run on Render (public link)
Render has no MySQL, so use an online MySQL database (a free-tier MySQL host) and give Render its details:
- Build Command:  `npm install`
- Start Command:  `node server.js`
- Environment variables: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DB_SSL=true

## Re-training the model (only if the data/model changes)
In the `training` folder: `python train_model.py`, then `python export_model.py`,
then copy the new `model.json` and `analysis.json` next to server.js.

## Who owns which file
- Member 1: predict.js, model.js, alerts.js, incidents.js
- Member 2: traffic.js
- Member 3: routeAdvice.js
- Member 4: locations.js, db.js, seed.js, schema.sql, geo.js
- Shared: server.js, util.js, index.html
