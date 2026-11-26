"""Sir's testing step. Start the server first, then in a 2nd window:
   python test_api.py                              (local)
   python test_api.py https://YOUR-NGROK-DOMAIN    (public URL)
"""
import sys, requests

U = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
H0 = {"ngrok-skip-browser-warning": "1"}
sample = {"hour": 23, "day_of_week": 5, "temperature": 60, "humidity": 70,
          "visibility": 10, "weather": "Fog", "is_night": 1}
n = 0

def check(name, ok):
    global n
    n += ok
    print("PASS" if ok else "FAIL", "-", name)

r = requests.get(U + "/health", headers=H0)
check("health", r.status_code == 200 and r.json()["status"] == "ok")
r = requests.get(U + "/", headers=H0)
check("home page opens", r.status_code == 200 and "<html" in r.text.lower())
r = requests.post(U + "/predict", json=sample, headers=H0)
p = r.json().get("probabilities", {})
check("predict without login (Postman test)", r.status_code == 200 and abs(sum(p.values()) - 1) < 0.05)
r = requests.post(U + "/predict", json={**sample, "hour": 99}, headers=H0)
check("bad input rejected", r.status_code == 422)
r = requests.post(U + "/predict", json=sample, headers=H0)
check("prediction saved", r.status_code == 200)
h = requests.get(U + "/history", headers=H0).json()
check("history shows it", len(h) >= 1)
hid = h[0]["id"]
requests.put(U + f"/history/{hid}", json={"note": "checked"}, headers=H0)
check("update note", requests.get(U + "/history", headers=H0).json()[0]["note"] == "checked")
check("dashboard stats", sum(requests.get(U + "/stats", headers=H0).json()["by_severity"].values()) >= 1)
requests.delete(U + f"/history/{hid}", headers=H0)
check("delete", all(x["id"] != hid for x in requests.get(U + "/history", headers=H0).json()))
a = requests.get(U + "/analysis", headers=H0)
check("analysis data", a.status_code == 200 and "model_scores" in a.json())


# ---- new screens (joined tables, alerts, location features) ----
g = lambda path: requests.get(U + path, headers=H0)
locs = g("/locations").json()
check("locations list", len(locs) >= 10 and "lat" in locs[0])
jn = g("/junctions?location_id=1").json()
check("junctions of an area", len(jn) >= 1)
t = g(f"/traffic?junction_id={jn[0]['id']}").json()
check("traffic pattern (3 tables joined)", len(t["series"]["Weekday"]) == 24)
r = requests.post(U + "/claims", json={"junction_id": jn[0]["id"], "driver": "Test", "day_type": "Weekday",
                  "start_hour": 9, "end_hour": 10, "claimed_delay_min": 400}, headers=H0)
check("claim check flags exaggeration", r.status_code == 200 and not r.json()["consistent"])
for c in g("/claims").json():
    if c["driver"] == "Test": requests.delete(U + f"/claims/{c['id']}", headers=H0)
ra = g("/route-advice?location_id=1&weather=Heavy%20Rain").json()
check("route advice", ra["recommended"] and len(ra["routes"]) >= 2)
r = requests.post(U + "/alerts", json={"junction_id": jn[0]["id"], "priority": "High", "message": "Test alert"}, headers=H0)
check("alert to police station", r.status_code == 200)
r = requests.post(U + "/incidents", json={"junction_id": jn[0]["id"], "kind": "Construction", "description": "Test road work"}, headers=H0)
check("incident notifies nearby drivers", r.status_code == 200 and r.json()["drivers_notified"] >= 1)
iid = r.json()["incident_id"]
dr = g("/drivers").json()
inbox = [g(f"/messages?driver_id={d['id']}").json() for d in dr]
check("driver inbox has the message", any(i["unread"] >= 1 for i in inbox))
requests.put(U + f"/incidents/{iid}/clear", headers=H0)
check("incident cleared", all(i["id"] != iid for i in g("/incidents?status=Active").json()))
r = requests.post(U + "/drivers", json={"name": "Bad", "phone": "12ab", "location_id": 1}, headers=H0)
check("bad driver rejected", r.status_code in (400, 422))


print(f"\n{n} of 20 passed")
