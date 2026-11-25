"""Member 1: alerts from the Road Safety Officer to a traffic police station.
Tables read: alerts, junctions, locations, police_stations (joined together)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from database import db

router = APIRouter()
STATUSES = ["Sent", "Acknowledged", "Cleared"]


@router.get("/stations", tags=["Alerts"])
def stations():
    rows = db.execute("""SELECT s.id, s.name, l.area, l.district FROM police_stations s
                         JOIN locations l ON l.id = s.location_id ORDER BY s.id""").fetchall()
    return [{"id": r[0], "name": r[1], "area": r[2], "district": r[3]} for r in rows]


class Alert(BaseModel):
    junction_id: int
    priority: str = "High"
    message: str = Field(min_length=3)


@router.post("/alerts", tags=["Alerts"], summary="Send an alert to the traffic police station of the junction's area")
def send_alert(a: Alert):
    if a.priority not in ("High", "Medium", "Low"):
        raise HTTPException(400, "Priority must be High, Medium or Low")
    row = db.execute("""SELECT s.id, s.name FROM junctions j
                        JOIN police_stations s ON s.location_id = j.location_id
                        WHERE j.id=?""", (a.junction_id,)).fetchone()
    if not row:
        raise HTTPException(404, "No police station found for this junction")
    db.execute("INSERT INTO alerts(junction_id,station_id,priority,message) VALUES(?,?,?,?)",
               (a.junction_id, row[0], a.priority, a.message))
    db.commit()
    return {"message": "Alert sent", "station": row[1]}


@router.get("/alerts", tags=["Alerts"], summary="Alerts shown on one station's dashboard")
def alerts(station_id: int):
    rows = db.execute("""SELECT a.id, j.name, l.area, s.name, a.priority, a.message, a.status, a.created
                         FROM alerts a
                         JOIN junctions j ON j.id = a.junction_id
                         JOIN locations l ON l.id = j.location_id
                         JOIN police_stations s ON s.id = a.station_id
                         WHERE a.station_id=? ORDER BY a.id DESC""", (station_id,)).fetchall()
    keys = ["id", "junction", "area", "station", "priority", "message", "status", "created"]
    return [dict(zip(keys, r)) for r in rows]


class Status(BaseModel):
    status: str


@router.put("/alerts/{aid}", tags=["Alerts"], summary="Station marks an alert Acknowledged or Cleared")
def set_status(aid: int, s: Status):
    if s.status not in STATUSES:
        raise HTTPException(400, "Status must be Sent, Acknowledged or Cleared")
    db.execute("UPDATE alerts SET status=? WHERE id=?", (s.status, aid))
    db.commit()
    return {"message": "Updated"}


@router.delete("/alerts/{aid}", tags=["Alerts"])
def delete_alert(aid: int):
    db.execute("DELETE FROM alerts WHERE id=?", (aid,))
    db.commit()
    return {"message": "Deleted"}
