"""Member 3: trip planner for long drives.
Tables read: locations, services (joined with locations), incidents (joined with junctions).
It suggests restaurants and hotels along the route and warns about active road work / accidents."""
from fastapi import APIRouter, HTTPException
from database import db
from geo import haversine_km, along_route

router = APIRouter()
ROUTE_WIDTH_KM = 15      # a stop within this distance of the route counts as "on the way"
WARN_WIDTH_KM = 8        # an incident within this distance of the route is shown as a warning


def _area(aid):
    r = db.execute("SELECT id, area, district, lat, lon FROM locations WHERE id=?", (aid,)).fetchone()
    if not r:
        raise HTTPException(404, "Unknown area")
    return r


@router.get("/trip", tags=["Trip"], summary="Plan a trip: stops, hotels and warnings along the route")
def trip(from_id: int, to_id: int, hours: float = 0):
    a, b = _area(from_id), _area(to_id)
    dist = round(haversine_km(a[3], a[4], b[3], b[4]) * 1.2, 1)     # x1.2: roads are longer than a straight line
    est_hours = round(dist / 50, 1)                                   # about 50 km/h on average
    total = max(est_hours, hours)
    long_drive = total >= 2
    out = {"from": a[1], "to": b[1], "from_lat": a[3], "from_lon": a[4], "to_lat": b[3], "to_lon": b[4],
           "distance_km": dist, "estimated_hours": est_hours, "long_drive": long_drive,
           "breaks": int(total // 2) if long_drive else 0}
    out["advice"] = (f"Long drive of about {round(total, 1)} hours. Take a break every 2 hours, do not drive when sleepy, "
                     "and check the stops below." if long_drive else
                     "Short trip. No long break needed, but the nearby places below may still help.")
    for kind, key in (("Restaurant", "restaurants"), ("Hotel", "hotels")):
        rows = db.execute("""SELECT s.name, s.phone, s.rating, s.price, s.lat, s.lon, l.area
                             FROM services s JOIN locations l ON l.id = s.location_id WHERE s.kind=?""", (kind,)).fetchall()
        items = []
        for name, phone, rating, price, lat, lon, area in rows:
            d, t = along_route(lat, lon, a[3], a[4], b[3], b[4])
            items.append({"name": name, "kind": kind, "phone": phone, "rating": rating, "price": price, "lat": lat, "lon": lon,
                          "area": area, "km_from_route": round(d, 1), "along": round(t, 2)})
        near = [i for i in items if i["km_from_route"] <= ROUTE_WIDTH_KM] or sorted(items, key=lambda i: i["km_from_route"])[:3]
        near.sort(key=lambda i: (i["km_from_route"], -i["rating"]))
        out[key] = near[:4]
    warn = []
    for kind, desc, jname, area, lat, lon, created in db.execute(
            """SELECT i.kind, i.description, j.name, l.area, j.lat, j.lon, i.created
               FROM incidents i JOIN junctions j ON j.id = i.junction_id JOIN locations l ON l.id = j.location_id
               WHERE i.status='Active'""").fetchall():
        d, _ = along_route(lat, lon, a[3], a[4], b[3], b[4])
        if d <= WARN_WIDTH_KM:
            warn.append({"kind": kind, "description": desc, "junction": jname, "area": area, "km_from_route": round(d, 1)})
    out["warnings"] = warn
    return out
