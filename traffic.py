"""Member 2: traffic patterns (weekday / Saturday / Sunday) and the driver claim check.
Tables read: traffic_records, junctions, locations (joined together) and claims."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from database import db

router = APIRouter()
DAYS = ["Weekday", "Saturday", "Sunday"]


@router.get("/junctions", tags=["Traffic"])
def junctions(location_id: int):
    rows = db.execute("SELECT id, name FROM junctions WHERE location_id=? ORDER BY id", (location_id,)).fetchall()
    return [{"id": r[0], "name": r[1]} for r in rows]


@router.get("/traffic", tags=["Traffic"], summary="Typical delay by hour for weekday, Saturday and Sunday")
def traffic(junction_id: int):
    rows = db.execute("""SELECT j.name, l.area, l.district, t.day_type, t.hour, t.avg_delay_min
                         FROM traffic_records t
                         JOIN junctions j ON j.id = t.junction_id
                         JOIN locations l ON l.id = j.location_id
                         WHERE t.junction_id=? ORDER BY t.day_type, t.hour""", (junction_id,)).fetchall()
    if not rows:
        raise HTTPException(404, "Junction not found")
    series = {d: [0.0] * 24 for d in DAYS}
    for _, _, _, day, hour, delay in rows:
        series[day][hour] = delay
    summary = {}
    for d in DAYS:
        peak = max(range(24), key=lambda h: series[d][h])
        summary[d] = {"peak_hour": peak, "peak_delay": series[d][peak], "average": round(sum(series[d]) / 24, 1)}
    return {"junction": rows[0][0], "area": rows[0][1], "district": rows[0][2], "series": series, "summary": summary}


class Claim(BaseModel):
    junction_id: int
    driver: str = Field(min_length=2)
    day_type: str
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=23)
    claimed_delay_min: float = Field(ge=0)


@router.post("/claims", tags=["Traffic"], summary="Check a driver's claimed delay against typical traffic")
def add_claim(c: Claim):
    if c.day_type not in DAYS or c.end_hour < c.start_hour:
        raise HTTPException(400, "Check the day type and the hours")
    typical = db.execute("""SELECT AVG(avg_delay_min) FROM traffic_records
                            WHERE junction_id=? AND day_type=? AND hour BETWEEN ? AND ?""",
                         (c.junction_id, c.day_type, c.start_hour, c.end_hour)).fetchone()[0]
    if typical is None:
        raise HTTPException(404, "Junction not found")
    typical = round(typical, 1)
    # claimed delay up to 1.5 x the typical delay (+3 min) is accepted as consistent
    ok = c.claimed_delay_min <= typical * 1.5 + 3
    verdict = "Consistent with typical traffic" if ok else "Higher than typical traffic - verify the claim"
    db.execute("""INSERT INTO claims(junction_id,driver,day_type,start_hour,end_hour,claimed_delay_min,typical_delay_min,verdict)
                  VALUES(?,?,?,?,?,?,?,?)""", (c.junction_id, c.driver, c.day_type, c.start_hour, c.end_hour,
                                                c.claimed_delay_min, typical, verdict))
    db.commit()
    return {"typical_delay_min": typical, "claimed_delay_min": c.claimed_delay_min, "verdict": verdict, "consistent": ok}


@router.get("/claims", tags=["Traffic"])
def claims():
    rows = db.execute("""SELECT c.id, c.driver, j.name, l.area, c.day_type, c.start_hour, c.end_hour,
                                c.claimed_delay_min, c.typical_delay_min, c.verdict, c.created
                         FROM claims c JOIN junctions j ON j.id = c.junction_id
                         JOIN locations l ON l.id = j.location_id ORDER BY c.id DESC""").fetchall()
    keys = ["id", "driver", "junction", "area", "day_type", "start_hour", "end_hour", "claimed", "typical", "verdict", "created"]
    return [dict(zip(keys, r)) for r in rows]


@router.delete("/claims/{cid}", tags=["Traffic"])
def delete_claim(cid: int):
    db.execute("DELETE FROM claims WHERE id=?", (cid,))
    db.commit()
    return {"message": "Deleted"}
