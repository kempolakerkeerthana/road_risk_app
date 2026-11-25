"""Member 1: road incidents (construction, accident, road damage) and the driver inbox.
When an incident is reported, every registered driver whose home area is within RADIUS_KM
gets a message. Messages are stored in the app (an in-app inbox); real SMS would need an SMS provider.
Tables read: incidents, junctions, locations, drivers, driver_messages."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from database import db
from geo import haversine_km

router = APIRouter()
KINDS = ["Construction", "Accident", "Road damage"]
RADIUS_KM = 8
TIPS = {"Construction": "Expect delays and take another route if you can.",
        "Accident": "Drive carefully and expect long delays.",
        "Road damage": "Slow down and watch for damage on the road."}


def _notify(incident_id, junction_id, kind, description, cleared=False):
    j = db.execute("SELECT j.name, l.area, j.lat, j.lon FROM junctions j JOIN locations l ON l.id=j.location_id WHERE j.id=?",
                   (junction_id,)).fetchone()
    drivers = db.execute("""SELECT d.id, l.lat, l.lon FROM drivers d JOIN locations l ON l.id = d.location_id""").fetchall()
    n = 0
    for did, dlat, dlon in drivers:
        km = haversine_km(j[2], j[3], dlat, dlon)
        if km > RADIUS_KM:
            continue
        head = f"CLEARED: {kind} at {j[0]} ({j[1]})." if cleared else f"{kind.upper()} at {j[0]} ({j[1]}): {description}."
        tail = "The road is open again." if cleared else f"{km:.1f} km from your area. {TIPS[kind]}"
        db.execute("INSERT INTO driver_messages(driver_id,incident_id,text) VALUES(?,?,?)", (did, incident_id, f"{head} {tail}"))
        n += 1
    return n


class Incident(BaseModel):
    junction_id: int
    kind: str
    description: str = Field(min_length=3)
    reporter: str = "Road Safety Officer"


@router.post("/incidents", tags=["Incidents"], summary="Report construction, an accident or road damage - drivers nearby get a message")
def report(i: Incident):
    if i.kind not in KINDS:
        raise HTTPException(400, "kind must be Construction, Accident or Road damage")
    if not db.execute("SELECT 1 FROM junctions WHERE id=?", (i.junction_id,)).fetchone():
        raise HTTPException(404, "Unknown junction")
    iid = db.execute("INSERT INTO incidents(junction_id,kind,description,reporter) VALUES(?,?,?,?)",
                     (i.junction_id, i.kind, i.description, i.reporter)).lastrowid
    n = _notify(iid, i.junction_id, i.kind, i.description)
    db.commit()
    return {"incident_id": iid, "drivers_notified": n}


@router.get("/incidents", tags=["Incidents"])
def incidents(status: str = "Active"):
    rows = db.execute("""SELECT i.id, i.kind, i.description, i.reporter, i.status, i.created, j.name, l.area, j.lat, j.lon
                         FROM incidents i JOIN junctions j ON j.id = i.junction_id JOIN locations l ON l.id = j.location_id
                         WHERE i.status=? ORDER BY i.id DESC""", (status,)).fetchall()
    keys = ["id", "kind", "description", "reporter", "status", "created", "junction", "area", "lat", "lon"]
    return [dict(zip(keys, r)) for r in rows]


@router.put("/incidents/{iid}/clear", tags=["Incidents"], summary="Mark an incident cleared - drivers get a 'cleared' message")
def clear(iid: int):
    r = db.execute("SELECT junction_id, kind, description, status FROM incidents WHERE id=?", (iid,)).fetchone()
    if not r:
        raise HTTPException(404, "Unknown incident")
    n = 0
    if r[3] == "Active":
        db.execute("UPDATE incidents SET status='Cleared' WHERE id=?", (iid,))
        n = _notify(iid, r[0], r[1], r[2], cleared=True)
        db.commit()
    return {"message": "Cleared", "drivers_notified": n}


class Driver(BaseModel):
    name: str = Field(min_length=2)
    phone: str = Field(min_length=10, max_length=15)
    vehicle: str = ""
    location_id: int


@router.get("/drivers", tags=["Drivers"])
def drivers():
    rows = db.execute("""SELECT d.id, d.name, d.phone, d.vehicle, l.area FROM drivers d
                         JOIN locations l ON l.id = d.location_id ORDER BY d.id""").fetchall()
    return [{"id": r[0], "name": r[1], "phone": r[2], "vehicle": r[3], "area": r[4]} for r in rows]


@router.post("/drivers", tags=["Drivers"], summary="Register a driver to receive alerts for their area")
def register_driver(d: Driver):
    if not d.phone.isdigit():
        raise HTTPException(400, "Phone must contain digits only")
    if not db.execute("SELECT 1 FROM locations WHERE id=?", (d.location_id,)).fetchone():
        raise HTTPException(404, "Unknown area")
    did = db.execute("INSERT INTO drivers(name,phone,vehicle,location_id) VALUES(?,?,?,?)",
                     (d.name, d.phone, d.vehicle, d.location_id)).lastrowid
    db.commit()
    return {"id": did}


@router.get("/messages", tags=["Drivers"], summary="A driver's inbox")
def messages(driver_id: int):
    rows = db.execute("""SELECT m.id, m.text, m.status, m.created, i.kind, j.name, l.area
                         FROM driver_messages m
                         JOIN incidents i ON i.id = m.incident_id
                         JOIN junctions j ON j.id = i.junction_id
                         JOIN locations l ON l.id = j.location_id
                         WHERE m.driver_id=? ORDER BY m.id DESC""", (driver_id,)).fetchall()
    keys = ["id", "text", "status", "created", "kind", "junction", "area"]
    msgs = [dict(zip(keys, r)) for r in rows]
    return {"unread": sum(m["status"] == "Unread" for m in msgs), "messages": msgs}


@router.put("/messages/{mid}/read", tags=["Drivers"])
def mark_read(mid: int):
    db.execute("UPDATE driver_messages SET status='Read' WHERE id=?", (mid,))
    db.commit()
    return {"message": "Updated"}


@router.delete("/messages/{mid}", tags=["Drivers"])
def delete_message(mid: int):
    db.execute("DELETE FROM driver_messages WHERE id=?", (mid,))
    db.commit()
    return {"message": "Deleted"}
