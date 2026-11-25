"""Member 4: emergency directory (state -> district -> area).
Tables read: hospitals + locations (joined), doctors and ambulances (by hospital_id), police_stations."""
from fastapi import APIRouter, HTTPException
from database import db

router = APIRouter()


@router.get("/locations", tags=["Emergency"], summary="All states, districts and areas")
def locations():
    rows = db.execute("SELECT id, state, district, area, lat, lon FROM locations ORDER BY state, district, area").fetchall()
    return [{"id": r[0], "state": r[1], "district": r[2], "area": r[3], "lat": r[4], "lon": r[5]} for r in rows]


@router.get("/emergency", tags=["Emergency"], summary="Nearby hospitals, doctors, ambulances and police station")
def emergency(location_id: int):
    hospitals = db.execute("""SELECT h.id, h.name, h.phone, h.kind, l.area, l.district
                              FROM hospitals h JOIN locations l ON l.id = h.location_id
                              WHERE h.location_id=? ORDER BY h.id""", (location_id,)).fetchall()
    if not hospitals:
        raise HTTPException(404, "No data for this area")
    out = []
    for hid, name, phone, kind, area, district in hospitals:
        docs = db.execute("SELECT name, speciality, phone FROM doctors WHERE hospital_id=?", (hid,)).fetchall()
        amb = db.execute("SELECT vehicle_no, phone FROM ambulances WHERE hospital_id=?", (hid,)).fetchall()
        out.append({"hospital": name, "kind": kind, "phone": phone,
                    "doctors": [{"name": d[0], "speciality": d[1], "phone": d[2]} for d in docs],
                    "ambulances": [{"vehicle": a[0], "phone": a[1]} for a in amb]})
    stations = db.execute("SELECT name, phone FROM police_stations WHERE location_id=?", (location_id,)).fetchall()
    return {"area": hospitals[0][4], "district": hospitals[0][5], "hospitals": out,
            "police_stations": [{"name": s[0], "phone": s[1]} for s in stations],
            "national_numbers": {"Emergency": "112", "Ambulance": "108"}}
