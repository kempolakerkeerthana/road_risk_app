"""Member 4: location features - nearest area, and nearest restaurants / hotels / mechanics.
Tables read: services joined with locations. Distances come from geo.haversine_km."""
from fastapi import APIRouter, HTTPException
from database import db
from geo import haversine_km

router = APIRouter()
KINDS = ["Restaurant", "Hotel", "Mechanic"]


@router.get("/nearest-area", tags=["Nearby"], summary="Which area is closest to this GPS position")
def nearest_area(lat: float, lon: float):
    rows = db.execute("SELECT id, state, district, area, lat, lon FROM locations").fetchall()
    best = min(rows, key=lambda r: haversine_km(lat, lon, r[4], r[5]))
    d = round(haversine_km(lat, lon, best[4], best[5]), 1)
    return {"id": best[0], "state": best[1], "district": best[2], "area": best[3], "lat": best[4], "lon": best[5],
            "distance_km": d, "outside_coverage": d > 40}


@router.get("/nearby", tags=["Nearby"], summary="Nearest restaurants, hotels or mechanics to a position")
def nearby(lat: float, lon: float, kind: str, limit: int = 5):
    if kind not in KINDS:
        raise HTTPException(400, "kind must be Restaurant, Hotel or Mechanic")
    rows = db.execute("""SELECT s.id, s.name, s.phone, s.rating, s.price, s.open_24x7, s.lat, s.lon, l.area, l.district
                         FROM services s JOIN locations l ON l.id = s.location_id WHERE s.kind=?""", (kind,)).fetchall()
    out = [{"id": r[0], "name": r[1], "kind": kind, "phone": r[2], "rating": r[3], "price": r[4], "open_24x7": bool(r[5]),
            "lat": r[6], "lon": r[7], "area": r[8], "district": r[9],
            "distance_km": round(haversine_km(lat, lon, r[6], r[7]), 1)} for r in rows]
    out.sort(key=lambda x: x["distance_km"])
    return out[:max(1, min(limit, 20))]
