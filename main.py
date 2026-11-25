from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import joblib, pandas as pd, json, os
import features as F
from database import db                       # shared database (tables + sample data)
import traffic, route_advice, emergency, alerts, incidents, nearby

model, cols = joblib.load("severity_model.pkl")
WEATHERS = F.known(cols, "Weather_Condition_")
STATES = F.known(cols, "State_")

DESCRIPTION = """
Predicts how serious a road accident is likely to be (**Severity 1 = minor to 4 = most serious**)
from the time, weather, location and road features.

Severity means the impact on traffic: **1 = short delay ... 4 = long delay** (as defined in the US Accidents dataset).

* **Predict / Dashboard / Analysis** - the ML model, saved predictions and results from the training run.
* **Traffic** - weekday, Saturday and Sunday traffic by junction, and a driver claim check.
* **Route Advice** - which route to take in rain, fog or storm.
* **Emergency** - nearby hospitals, doctors, ambulances and police station.
* **Alerts** - the Road Safety Officer sends alerts to a traffic police station.
* **Incidents / Drivers** - report construction, accidents or road damage; nearby drivers get a message.
* **Trip** - for long drives: restaurants and hotels along the route, plus warnings.
* **Nearby** - nearest area, restaurants, hotels and mechanics to a GPS position.

The model was trained on US accident data (50,000 records). Scores are relative risk, not real-world probabilities.
"""
app = FastAPI(title="Road Accident Severity Prediction API", description=DESCRIPTION, version="2.0.0")
for r in (traffic.router, route_advice.router, emergency.router, alerts.router,
          incidents.router, nearby.router):
    app.include_router(r)

# ---- home page + health check ----
@app.get("/", include_in_schema=False)
def home():
    return FileResponse("index.html")

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "model_classes": [int(c) for c in model.classes_]}


# ---- prediction (saved to history unless save=0) ----
class Accident(BaseModel):
    hour: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)          # 0=Mon ... 6=Sun
    temperature: float
    humidity: float
    visibility: float
    state: str = "CA"
    weather: str = "Fair"
    wind_speed: float = 0
    precipitation: float = 0
    junction: int = 0
    traffic_signal: int = 0
    crossing: int = 0
    stop: int = 0
    railway: int = 0
    is_night: int = 0
    location_id: int | None = None                # area the prediction is for (optional)
    save: int = 1                                 # 0 = what-if only, do not store

    model_config = {"json_schema_extra": {"example": {
        "hour": 23, "day_of_week": 5, "temperature": 60, "humidity": 70, "visibility": 10,
        "weather": "Fog", "state": "CA", "is_night": 1, "junction": 0, "traffic_signal": 0, "save": 0}}}

@app.post("/predict", tags=["Prediction"], summary="Predict accident severity")
def predict(a: Accident):
    raw = pd.DataFrame([{
        "Hour": a.hour, "DayOfWeek": a.day_of_week, "Temperature(F)": a.temperature,
        "Humidity(%)": a.humidity, "Visibility(mi)": a.visibility,
        "Wind_Speed(mph)": a.wind_speed, "Precipitation(in)": a.precipitation,
        "Junction": a.junction, "Traffic_Signal": a.traffic_signal, "Crossing": a.crossing,
        "Stop": a.stop, "Railway": a.railway, "Is_Night": a.is_night,
        "Weather_Condition": a.weather, "State": a.state}])
    if len(a.state) != 2:
        # not a US state code (for example an Indian state): the model has no data for it,
        # so ignore location and average the score over the US locations it knows
        raw = pd.concat([raw] * len(STATES), ignore_index=True)
        raw["State"] = STATES
    x = F.prepare(raw, {}, WEATHERS, STATES, cols)      # same feature code as training
    p = model.predict_proba(x).mean(axis=0)
    probs = {int(c): round(float(v), 2) for c, v in zip(model.classes_, p)}
    out = {"severity": int(model.classes_[p.argmax()]),
           "confidence": round(float(p.max()), 2),
           "probabilities": probs,
           "high_severity_risk": round(probs.get(3, 0) + probs.get(4, 0), 2),
           "low_confidence": bool(p.max() < 0.5)}
    if a.save:
        if a.location_id and not db.execute("SELECT 1 FROM locations WHERE id=?", (a.location_id,)).fetchone():
            raise HTTPException(400, "Unknown area")
        db.execute("INSERT INTO predictions(location_id,inputs,severity,confidence) VALUES(?,?,?,?)",
                   (a.location_id, a.model_dump_json(), out["severity"], out["confidence"]))
        db.commit()
    return out


# ---- read / update / delete / dashboard ----
class Note(BaseModel):
    note: str

@app.get("/history", tags=["Dashboard"])
def history():
    rows = db.execute("""SELECT p.id, p.inputs, p.severity, p.confidence, p.note, p.created, l.area, l.district
                         FROM predictions p LEFT JOIN locations l ON l.id = p.location_id
                         ORDER BY p.id DESC""").fetchall()
    return [{"id": r[0], "inputs": json.loads(r[1]), "severity": r[2], "confidence": r[3],
             "note": r[4], "created": r[5], "area": r[6], "district": r[7]} for r in rows]

@app.put("/history/{hid}", tags=["Dashboard"])
def update(hid: int, n: Note):
    db.execute("UPDATE predictions SET note=? WHERE id=?", (n.note, hid))
    db.commit()
    return {"message": "Updated"}

@app.delete("/history/{hid}", tags=["Dashboard"])
def delete(hid: int):
    db.execute("DELETE FROM predictions WHERE id=?", (hid,))
    db.commit()
    return {"message": "Deleted"}

@app.get("/stats", tags=["Dashboard"])
def stats():
    rows = db.execute("SELECT severity, COUNT(*) FROM predictions GROUP BY severity").fetchall()
    return {"by_severity": {r[0]: r[1] for r in rows}}


# ---- analysis page data (made by train_model.py from the notebook's analysis) ----
@app.get("/analysis", tags=["Analysis"])
def analysis():
    if not os.path.exists("analysis.json"):
        raise HTTPException(404, "Run train_model.py first")
    return json.load(open("analysis.json"))
