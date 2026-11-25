"""The ONLY Python file in the running app: it loads the trained scikit-learn model and answers /predict.
Everything else (database, screens, alerts...) is Node.js + MySQL.
Start:  python -m uvicorn predict_service:app --port 8001      (docs: http://127.0.0.1:8001/docs)"""
from fastapi import FastAPI
from pydantic import BaseModel, Field
import joblib, pandas as pd
import features as F

model, cols = joblib.load("severity_model.pkl")
WEATHERS = F.known(cols, "Weather_Condition_")
STATES = F.known(cols, "State_")

app = FastAPI(title="Severity model service", version="1.0.0",
              description="Predicts accident severity (1 = short traffic delay ... 4 = long delay). Used by the Node.js app.")


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


@app.get("/health")
def health():
    return {"status": "ok", "model_classes": [int(c) for c in model.classes_]}


@app.post("/predict")
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
    return {"severity": int(model.classes_[p.argmax()]),
            "confidence": round(float(p.max()), 2),
            "probabilities": probs,
            "high_severity_risk": round(probs.get(3, 0) + probs.get(4, 0), 2),
            "low_confidence": bool(p.max() < 0.5)}
