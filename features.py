"""Shared feature code: train_model.py, the notebook and main.py all use these
functions, so training and the live app always build the features the same way."""
import pandas as pd

NUM = ["Temperature(F)", "Humidity(%)", "Visibility(mi)", "Wind_Speed(mph)", "Precipitation(in)"]
BOOL = ["Junction", "Traffic_Signal", "Crossing", "Stop", "Railway"]
BAD_WEATHER = "Rain|Snow|Fog|Storm|Haze|Thunder|Drizzle|Sleet"
RUSH_HOURS = [7, 8, 9, 16, 17, 18, 19]


def clean(raw):
    """Raw US Accidents rows -> the few tidy columns the model uses."""
    t = pd.to_datetime(raw["Start_Time"], format="mixed")
    d = pd.DataFrame({"Hour": t.dt.hour, "DayOfWeek": t.dt.dayofweek})
    for c in NUM:
        d[c] = pd.to_numeric(raw[c], errors="coerce")
    d["Precipitation(in)"] = d["Precipitation(in)"].fillna(0)   # blank = no rain recorded
    for c in BOOL:
        d[c] = raw[c].astype(str).str.lower().eq("true").astype(int)
    d["Is_Night"] = (raw["Sunrise_Sunset"] == "Night").astype(int)
    d["Weather_Condition"] = raw["Weather_Condition"].fillna("Other")
    d["State"] = raw["State"].fillna("Other")
    return d


def add_features(d):
    """Our 6 engineered features."""
    d = d.copy()
    d["Is_Weekend"] = (d["DayOfWeek"] >= 5).astype(int)
    d["Is_Rush_Hour"] = d["Hour"].isin(RUSH_HOURS).astype(int)
    d["Low_Visibility"] = (d["Visibility(mi)"] < 2).astype(int)
    d["Bad_Weather"] = d["Weather_Condition"].str.contains(BAD_WEATHER, case=False).astype(int)
    d["Night_Bad_Weather"] = d["Is_Night"] * d["Bad_Weather"]
    d["Road_Complexity"] = d[BOOL].sum(axis=1)
    return d


def prepare(d, medians, weathers, states, cols=None):
    """fill gaps -> engineered features -> rare weather/state = 'Other' -> one-hot.
    If cols is given, the result has exactly those columns in that order."""
    d = add_features(d.fillna(medians))
    d["Weather_Condition"] = d["Weather_Condition"].where(d["Weather_Condition"].isin(weathers), "Other")
    d["State"] = d["State"].where(d["State"].isin(states), "Other")
    d = pd.get_dummies(d, columns=["Weather_Condition", "State"], dtype=int)
    return d if cols is None else d.reindex(columns=cols, fill_value=0)


def known(cols, prefix):
    """Weather / state names the saved model knows, read from its column list."""
    return [c[len(prefix):] for c in cols if c.startswith(prefix)]


# ---------- extra analysis (from Analysis.ipynb) ----------
def rules(raw, min_support=0.01, min_conf=0.60, top=10):
    """Simple association rules 'if A then B' (same idea as the Apriori cell, no extra library)."""
    it = pd.DataFrame({c: raw[c].astype(str).str.lower().eq("true")
                       for c in ["Junction", "Traffic_Signal", "Crossing", "Stop", "Railway", "Station"]})
    it["Night"] = raw["Sunrise_Sunset"].eq("Night")
    it["Day"] = raw["Sunrise_Sunset"].eq("Day")
    for w in raw["Weather_Condition"].value_counts().head(6).index:
        it["Weather: " + w] = raw["Weather_Condition"].eq(w)
    n, X = len(it), it.values.astype(float)
    cnt, both = X.sum(axis=0), X.T @ X
    out = []
    for i, a in enumerate(it.columns):
        for j, b in enumerate(it.columns):
            if i == j or cnt[i] == 0:
                continue
            sup, conf = both[i, j] / n, both[i, j] / cnt[i]
            if sup >= min_support and conf >= min_conf:
                out.append({"if": a, "then": b, "support": round(sup, 3),
                            "confidence": round(conf, 3), "lift": round(conf / (cnt[j] / n), 2)})
    return sorted(out, key=lambda r: -r["lift"])[:top]


def insights(raw):
    """Numbers for the Analysis page (all plain Python types so they save as JSON)."""
    t = pd.to_datetime(raw["Start_Time"], format="mixed")
    dn = raw.dropna(subset=["Sunrise_Sunset", "Weather_Condition"])
    top_w = raw["Weather_Condition"].value_counts().head(8).index
    dn = dn[dn["Weather_Condition"].isin(top_w)]
    share = (pd.crosstab(dn["Weather_Condition"], dn["Sunrise_Sunset"], normalize="index") * 100).round(1)
    return {
        "rows": int(len(raw)),
        "severity": {str(k): int(v) for k, v in raw["Severity"].value_counts().sort_index().items()},
        "by_hour": {str(k): int(v) for k, v in t.dt.hour.value_counts().sort_index().items()},
        "top_states": {k: int(v) for k, v in raw["State"].value_counts().head(10).items()},
        "timezones": {k: int(v) for k, v in raw["Timezone"].fillna("Unknown").value_counts().items()},
        "top_weather": {k: int(v) for k, v in raw["Weather_Condition"].value_counts().head(10).items()},
        "top_streets": {k: int(v) for k, v in raw["Street"].value_counts().head(10).items()},
        "night_share_by_weather": {k: float(v) for k, v in share.get("Night", pd.Series(dtype=float)).items()},
        "rules": rules(raw),
    }
