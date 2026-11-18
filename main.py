from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import joblib, pandas as pd, sqlite3, hashlib, secrets, json, os, time

model, cols = joblib.load("severity_model.pkl")

# hide /docs, /redoc and /openapi.json from the public
app = FastAPI(title="Road Risk API", docs_url=None, redoc_url=None, openapi_url=None)

# secret code only approved officers know (set INVITE_CODE on Render > Environment)
INVITE_CODE = os.getenv("INVITE_CODE", "change-me-123")
SESSION_SECONDS = 60 * 60          # sessions expire after 1 hour

# ---- database ----
db = sqlite3.connect("app.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, pw TEXT)")
db.execute("""CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY, username TEXT,
              inputs TEXT, severity INT, confidence REAL, note TEXT DEFAULT '',
              created TEXT DEFAULT CURRENT_TIMESTAMP)""")
sessions = {}

# ---- register / login ----
class Auth(BaseModel):
    username: str
    password: str
    invite: str = ""               # only needed for register

def hp(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex()

def who(token):
    s = sessions.get(token)
    if not s or time.time() > s["expires"]:
        sessions.pop(token, None)
        raise HTTPException(401, "Please login first")
    return s["user"]

@app.post("/register")
def register(a: Auth):
    if a.invite != INVITE_CODE:
        raise HTTPException(403, "Invalid invite code. Only approved officers can register")
    salt = secrets.token_hex(8)
    try:
        db.execute("INSERT INTO users VALUES(?,?)", (a.username, salt + "$" + hp(a.password, salt)))
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Username already taken")
    return {"message": "Registered"}

@app.post("/login")
def login(a: Auth):
    row = db.execute("SELECT pw FROM users WHERE username=?", (a.username,)).fetchone()
    if not row or row[0].split("$")[1] != hp(a.password, row[0].split("$")[0]):
        raise HTTPException(401, "Wrong username or password")
    t = secrets.token_hex(16)
    sessions[t] = {"user": a.username, "expires": time.time() + SESSION_SECONDS}
    return {"token": t}

# ---- prediction (saved to database unless save=0) ----
class Accident(BaseModel):
    hour: int
    day_of_week: int          # 0=Mon ... 6=Sun
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
    save: int = 1             # 0 = what-if only, do not store in history

@app.post("/predict")
def predict(a: Accident, token: str = Header(None)):
    user = who(token)
    r = dict.fromkeys(cols, 0)
    road = a.junction + a.traffic_signal + a.crossing + a.stop + a.railway
    bad = int(any(w in a.weather.lower() for w in
              ["rain", "snow", "fog", "storm", "haze", "thunder", "drizzle", "sleet"]))
    r.update({"Temperature(F)": a.temperature, "Humidity(%)": a.humidity,
              "Visibility(mi)": a.visibility, "Wind_Speed(mph)": a.wind_speed,
              "Precipitation(in)": a.precipitation, "Junction": a.junction,
              "Traffic_Signal": a.traffic_signal, "Crossing": a.crossing,
              "Stop": a.stop, "Railway": a.railway, "Hour": a.hour,
              "DayOfWeek": a.day_of_week, "Is_Night": a.is_night,
              "Is_Weekend": int(a.day_of_week >= 5),
              "Is_Rush_Hour": int(a.hour in [7, 8, 9, 16, 17, 18, 19]),
              "Low_Visibility": int(a.visibility < 2), "Bad_Weather": bad,
              "Night_Bad_Weather": a.is_night * bad, "Road_Complexity": road})
    s = "State_" + a.state
    r[s if s in r else "State_CA"] = 1
    w = "Weather_Condition_" + a.weather
    r[w if w in r else "Weather_Condition_Other"] = 1
    p = model.predict_proba(pd.DataFrame([r])[cols])[0]
    out = {"severity": int(model.classes_[p.argmax()]),
           "confidence": round(float(p.max()), 2),
           "probabilities": {int(c): round(float(x), 2) for c, x in zip(model.classes_, p)},
           "low_confidence": bool(p.max() < 0.5)}
    if a.save:
        db.execute("INSERT INTO history(username,inputs,severity,confidence) VALUES(?,?,?,?)",
                   (user, a.model_dump_json(), out["severity"], out["confidence"]))
        db.commit()
    return out

# ---- read / update / delete / dashboard ----
class Note(BaseModel):
    note: str

@app.get("/history")
def history(token: str = Header(None)):
    rows = db.execute("SELECT id,inputs,severity,confidence,note,created FROM history "
                      "WHERE username=? ORDER BY id DESC", (who(token),)).fetchall()
    return [{"id": r[0], "inputs": json.loads(r[1]), "severity": r[2],
             "confidence": r[3], "note": r[4], "created": r[5]} for r in rows]

@app.put("/history/{hid}")
def update(hid: int, n: Note, token: str = Header(None)):
    db.execute("UPDATE history SET note=? WHERE id=? AND username=?", (n.note, hid, who(token)))
    db.commit()
    return {"message": "Updated"}

@app.delete("/history/{hid}")
def delete(hid: int, token: str = Header(None)):
    db.execute("DELETE FROM history WHERE id=? AND username=?", (hid, who(token)))
    db.commit()
    return {"message": "Deleted"}

@app.get("/stats")
def stats(token: str = Header(None)):
    rows = db.execute("SELECT severity, COUNT(*) FROM history WHERE username=? GROUP BY severity",
                      (who(token),)).fetchall()
    return {"by_severity": {r[0]: r[1] for r in rows}}
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="road_risk_app", html=True), name="site")



