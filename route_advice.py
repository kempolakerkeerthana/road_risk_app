"""Member 3: weather based route advice.
Tables read: route_options, locations and weather_rules (joined in one query).
It does not use the ML model: it only reads stored data and applies the weather rule."""
from fastapi import APIRouter, HTTPException
from database import db

router = APIRouter()


@router.get("/weather-types", tags=["Route Advice"])
def weather_types():
    return [r[0] for r in db.execute("SELECT weather FROM weather_rules ORDER BY rowid").fetchall()]


@router.get("/route-advice", tags=["Route Advice"], summary="Which route to take in this weather")
def route_advice(location_id: int, weather: str):
    rows = db.execute("""SELECT l.area, l.district, r.route_name, r.via, r.is_main, r.waterlogging_prone,
                                r.extra_minutes, w.avoid_prone, w.advice
                         FROM route_options r
                         JOIN locations l ON l.id = r.location_id
                         JOIN weather_rules w ON w.weather = ?
                         WHERE r.location_id = ? ORDER BY r.is_main DESC, r.extra_minutes""",
                      (weather, location_id)).fetchall()
    if not rows:
        raise HTTPException(404, "Unknown location or weather")
    routes = []
    for area, district, name, via, is_main, prone, extra, avoid_rule, advice in rows:
        avoid = bool(avoid_rule and prone)          # rule says avoid prone roads AND this road is prone
        routes.append({"route": name, "via": via, "is_main": bool(is_main), "extra_minutes": extra,
                       "waterlogging_prone": bool(prone), "status": "Avoid" if avoid else "OK"})
    best = min((r for r in routes if r["status"] == "OK"), key=lambda r: r["extra_minutes"])
    return {"area": rows[0][0], "district": rows[0][1], "weather": weather, "advice": rows[0][8],
            "recommended": best["route"], "routes": routes}
