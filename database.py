"""Database for the whole app (SQLite file app.db).
Creates 12 related tables and fills the sample tables the first time the app starts.
All places, hospitals, doctors, phone numbers and traffic numbers below are SAMPLE data
made up for the project demo - replace them with real data before any real use."""
import math
import random
import sqlite3

db = sqlite3.connect("roadsafety.db", check_same_thread=False)
db.execute("PRAGMA foreign_keys = ON")

db.executescript("""
CREATE TABLE IF NOT EXISTS locations(id INTEGER PRIMARY KEY, state TEXT, district TEXT, area TEXT, lat REAL, lon REAL);
CREATE TABLE IF NOT EXISTS junctions(id INTEGER PRIMARY KEY, location_id INT REFERENCES locations(id), name TEXT, lat REAL, lon REAL);
CREATE TABLE IF NOT EXISTS traffic_records(id INTEGER PRIMARY KEY, junction_id INT REFERENCES junctions(id),
    day_type TEXT, hour INT, avg_delay_min REAL);
CREATE TABLE IF NOT EXISTS weather_rules(weather TEXT PRIMARY KEY, avoid_prone INT, advice TEXT);
CREATE TABLE IF NOT EXISTS route_options(id INTEGER PRIMARY KEY, location_id INT REFERENCES locations(id),
    route_name TEXT, via TEXT, is_main INT, waterlogging_prone INT, extra_minutes INT);
CREATE TABLE IF NOT EXISTS police_stations(id INTEGER PRIMARY KEY, location_id INT REFERENCES locations(id),
    name TEXT, phone TEXT);
CREATE TABLE IF NOT EXISTS hospitals(id INTEGER PRIMARY KEY, location_id INT REFERENCES locations(id),
    name TEXT, phone TEXT, kind TEXT);
CREATE TABLE IF NOT EXISTS doctors(id INTEGER PRIMARY KEY, hospital_id INT REFERENCES hospitals(id),
    name TEXT, speciality TEXT, phone TEXT);
CREATE TABLE IF NOT EXISTS ambulances(id INTEGER PRIMARY KEY, hospital_id INT REFERENCES hospitals(id),
    vehicle_no TEXT, phone TEXT);
CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, junction_id INT REFERENCES junctions(id),
    station_id INT REFERENCES police_stations(id), priority TEXT, message TEXT,
    status TEXT DEFAULT 'Sent', created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS claims(id INTEGER PRIMARY KEY, junction_id INT REFERENCES junctions(id),
    driver TEXT, day_type TEXT, start_hour INT, end_hour INT, claimed_delay_min REAL,
    typical_delay_min REAL, verdict TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY, location_id INT REFERENCES locations(id),
    inputs TEXT, severity INT, confidence REAL, note TEXT DEFAULT '', created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY, location_id INT REFERENCES locations(id),
    kind TEXT, name TEXT, phone TEXT, rating REAL, price INT, open_24x7 INT, lat REAL, lon REAL);
CREATE TABLE IF NOT EXISTS drivers(id INTEGER PRIMARY KEY, name TEXT, phone TEXT, vehicle TEXT,
    location_id INT REFERENCES locations(id));
CREATE TABLE IF NOT EXISTS incidents(id INTEGER PRIMARY KEY, junction_id INT REFERENCES junctions(id),
    kind TEXT, description TEXT, reporter TEXT, status TEXT DEFAULT 'Active', created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS driver_messages(id INTEGER PRIMARY KEY, driver_id INT REFERENCES drivers(id),
    incident_id INT REFERENCES incidents(id), text TEXT, status TEXT DEFAULT 'Unread',
    created TEXT DEFAULT CURRENT_TIMESTAMP);
""")

PLACES = {
    ("Telangana", "Hyderabad"): ["Madhapur", "Gachibowli", "Kukatpally", "Secunderabad", "Ameerpet", "LB Nagar"],
    ("Telangana", "Rangareddy"): ["Shamshabad", "Ibrahimpatnam"],
    ("Karnataka", "Bengaluru Urban"): ["Whitefield", "Koramangala", "Electronic City"],
}
# approximate centre of each area (latitude, longitude) - enough for a demo map
COORDS = {"Madhapur": (17.4486, 78.3908), "Gachibowli": (17.4401, 78.3489), "Kukatpally": (17.4948, 78.3996),
          "Secunderabad": (17.4399, 78.4983), "Ameerpet": (17.4375, 78.4483), "LB Nagar": (17.3457, 78.5522),
          "Shamshabad": (17.2403, 78.4294), "Ibrahimpatnam": (17.2230, 78.6700),
          "Whitefield": (12.9698, 77.7500), "Koramangala": (12.9352, 77.6245), "Electronic City": (12.8452, 77.6602)}
SERVICES = {"Restaurant": ["Spice Kitchen", "Tiffin House"], "Hotel": ["Comfort Inn", "Grand Stay"],
            "Mechanic": ["Auto Care", "Quick Fix Garage"]}
DOCTORS = [("Dr. R. Kumar", "Trauma Surgery"), ("Dr. S. Reddy", "Emergency Medicine"),
           ("Dr. P. Nair", "Orthopaedics"), ("Dr. A. Khan", "Neurosurgery"),
           ("Dr. M. Rao", "Critical Care"), ("Dr. L. Iyer", "General Surgery")]
WEATHER = [
    ("Clear", 0, "Normal conditions. Use the fastest route."),
    ("Light Rain", 0, "Roads are slippery. Drive slowly, keep extra distance."),
    ("Heavy Rain", 1, "Water logging is likely. Avoid low-lying and water-logging-prone roads."),
    ("Storm", 1, "Fallen trees and water logging are likely. Avoid prone roads and flyover edges."),
    ("Fog", 0, "Low visibility. Use fog lights and prefer well-lit main roads."),
]


def _peak(h, centre, width):
    return math.exp(-(((h - centre) / width) ** 2))


def _delay(day, hour, factor, rnd):
    if day == "Weekday":
        base = 14 * _peak(hour, 9, 1.6) + 16 * _peak(hour, 18, 1.8) + 3 * _peak(hour, 13, 2) + 1
    elif day == "Saturday":
        base = 6 * _peak(hour, 12, 2.5) + 10 * _peak(hour, 19, 2.2) + 1
    else:
        base = 4 * _peak(hour, 11, 3) + 6 * _peak(hour, 18, 2.5) + 0.8
    return round(max(0.5, base * factor + rnd.uniform(-0.8, 0.8)), 1)


def seed():
    if db.execute("SELECT COUNT(*) FROM locations").fetchone()[0]:
        return
    rnd = random.Random(7)
    db.executemany("INSERT INTO weather_rules VALUES(?,?,?)", WEATHER)
    n_h = n_d = n_a = n_s = 0
    for (state, district), areas in PLACES.items():
        for area in areas:
            alat, alon = COORDS[area]
            lid = db.execute("INSERT INTO locations(state,district,area,lat,lon) VALUES(?,?,?,?,?)",
                             (state, district, area, alat, alon)).lastrowid
            # junctions + a year-round typical delay for each day type and hour
            for jname in (f"{area} Main Junction", f"{area} Market Junction"):
                jid = db.execute("INSERT INTO junctions(location_id,name,lat,lon) VALUES(?,?,?,?)",
                                 (lid, jname, round(alat + rnd.uniform(-0.01, 0.01), 5),
                                  round(alon + rnd.uniform(-0.01, 0.01), 5))).lastrowid
                factor = rnd.uniform(0.7, 1.4)
                for day in ("Weekday", "Saturday", "Sunday"):
                    for hour in range(24):
                        db.execute("INSERT INTO traffic_records(junction_id,day_type,hour,avg_delay_min) VALUES(?,?,?,?)",
                                   (jid, day, hour, _delay(day, hour, factor, rnd)))
            # routes: main road is water-logging prone in some areas, the others never are
            prone = rnd.random() < 0.6
            db.executemany("INSERT INTO route_options(location_id,route_name,via,is_main,waterlogging_prone,extra_minutes) VALUES(?,?,?,?,?,?)", [
                (lid, f"{area} Main Road", "Main road through the area", 1, int(prone), 0),
                (lid, f"{area} Flyover Route", "Flyover and service road", 0, 0, rnd.randint(4, 9)),
                (lid, f"{area} Ring Road Route", "Outer ring road", 0, 0, rnd.randint(10, 18))])
            db.execute("INSERT INTO police_stations(location_id,name,phone) VALUES(?,?,?)",
                       (lid, f"{area} Traffic Police Station", f"90000 {10000 + lid:05d}"))
            # restaurants, hotels and mechanics near this area (the first mechanic is open 24x7)
            for kind, names in SERVICES.items():
                for i, base in enumerate(names):
                    n_s += 1
                    price = (rnd.randint(150, 450) if kind == "Restaurant" else
                             rnd.randint(1500, 4500) if kind == "Hotel" else 0)
                    db.execute("INSERT INTO services(location_id,kind,name,phone,rating,price,open_24x7,lat,lon) VALUES(?,?,?,?,?,?,?,?,?)",
                               (lid, kind, f"Sample {base} - {area}", f"90004 {50000 + n_s:05d}",
                                round(rnd.uniform(3.8, 4.8), 1), price, int(kind == "Mechanic" and i == 0),
                                round(alat + rnd.uniform(-0.02, 0.02), 5), round(alon + rnd.uniform(-0.02, 0.02), 5)))
            for kind in ("Trauma Centre", "General Hospital"):
                n_h += 1
                hid = db.execute("INSERT INTO hospitals(location_id,name,phone,kind) VALUES(?,?,?,?)",
                                 (lid, f"Sample {kind.split()[0]} Care - {area}", f"90001 {20000 + n_h:05d}", kind)).lastrowid
                for _ in range(2):
                    n_d += 1
                    nm, sp = DOCTORS[n_d % len(DOCTORS)]
                    db.execute("INSERT INTO doctors(hospital_id,name,speciality,phone) VALUES(?,?,?,?)",
                               (hid, nm, sp, f"90002 {30000 + n_d:05d}"))
                for _ in range(rnd.randint(1, 2)):
                    n_a += 1
                    db.execute("INSERT INTO ambulances(hospital_id,vehicle_no,phone) VALUES(?,?,?)",
                               (hid, f"AMB-{n_a:03d}", f"90003 {40000 + n_a:05d}"))
    # a few sample drivers (home area) so the driver inbox can be demonstrated
    ids = {r[1]: r[0] for r in db.execute("SELECT id, area FROM locations")}
    for name, phone, vehicle, area in [("Ravi Kumar", "9876500001", "TS09 AB 1234", "Madhapur"),
                                       ("Anita Reddy", "9876500002", "TS08 CD 5678", "Gachibowli"),
                                       ("Imran Khan", "9876500003", "TS10 EF 9012", "Kukatpally"),
                                       ("Suresh Gowda", "9876500004", "KA01 GH 3456", "Whitefield")]:
        db.execute("INSERT INTO drivers(name,phone,vehicle,location_id) VALUES(?,?,?,?)", (name, phone, vehicle, ids[area]))
    db.commit()


seed()
