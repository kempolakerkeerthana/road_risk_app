"""Sir's step 3: train, tune, evaluate and save the model.
Run:  python train_model.py
Needs US_Accidents_50000.csv and features.py in the same folder."""
import json
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import f1_score, classification_report, confusion_matrix
from sklearn.inspection import permutation_importance
import features as F

CSV = "US_Accidents_50000.csv"

# 1. load + clean ------------------------------------------------------------
raw = pd.read_csv(CSV)
raw = raw.dropna(subset=["Severity", "Start_Time"])
print("Rows:", len(raw))
print(raw["Severity"].value_counts().sort_index())
X, y = F.clean(raw), raw["Severity"]

# 2. split BEFORE anything is learned from the data (stratified keeps class shares)
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
medians = X_tr[F.NUM].median()
weathers = list(X_tr["Weather_Condition"].value_counts().head(10).index)
states = list(X_tr["State"].value_counts().head(10).index)
X_train = F.prepare(X_tr, medians, weathers, states)
cols = list(X_train.columns)
X_test = F.prepare(X_te, medians, weathers, states, cols)

# 3. compare 3 models. Severity 1 and 4 are rare, so rare classes get a higher weight
#    (square root of "balanced": fully balanced over-predicts the rare classes)
cw = {c: (len(y_tr) / (4 * n)) ** 0.5 for c, n in y_tr.value_counts().items()}
print("Class weights:", {c: round(w, 2) for c, w in sorted(cw.items())})
models = {
    "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight=cw)),
    "Random Forest": RandomForestClassifier(n_estimators=200, min_samples_leaf=3, class_weight=cw,
                                            n_jobs=-1, random_state=42),
    "Gradient Boosting": HistGradientBoostingClassifier(random_state=42),
}
scores = {}
sw = y_tr.map(cw).values          # same weights as per-row weights (boosting needs this form)
for name, m in models.items():
    fit_args = {"sample_weight": sw} if name == "Gradient Boosting" else {}
    pred = m.fit(X_train, y_tr, **fit_args).predict(X_test)
    scores[name] = round(f1_score(y_te, pred, average="macro"), 3)
    print(f"{name}: macro-F1 = {scores[name]}")

# 4. tune the boosting model
grid = GridSearchCV(HistGradientBoostingClassifier(random_state=42),
                    {"learning_rate": [0.05, 0.1], "max_leaf_nodes": [15, 31], "max_iter": [100, 200]},
                    scoring="f1_macro", cv=3, n_jobs=-1).fit(X_train, y_tr, sample_weight=sw)
best = grid.best_estimator_
pred = best.predict(X_test)
print("Best settings:", grid.best_params_)
print(classification_report(y_te, pred, digits=2))

# 5. main risk factors (permutation importance on the test set)
sub = X_test.sample(min(3000, len(X_test)), random_state=1)
imp = permutation_importance(best, sub, y_te.loc[sub.index], scoring="f1_macro",
                             n_repeats=3, random_state=42, n_jobs=-1)
top = pd.Series(imp.importances_mean, cols).nlargest(10).round(4)
print("Top risk factors:\n", top)

# 6. save the model (+ columns) and everything the Analysis page needs
joblib.dump((best, cols), "severity_model.pkl")
report = classification_report(y_te, pred, output_dict=True)
result = {
    "model": "HistGradientBoostingClassifier",
    "train_rows": len(X_tr), "test_rows": len(X_te),
    "model_scores": scores,
    "tuned_macro_f1": round(report["macro avg"]["f1-score"], 3),
    "accuracy": round(report["accuracy"], 3),
    "best_params": grid.best_params_,
    "per_class": {k: {m: round(v[m], 2) for m in ["precision", "recall", "f1-score"]}
                  for k, v in report.items() if k in ["1", "2", "3", "4"]},
    "importance": {k: float(v) for k, v in top.items()},
    "confusion": confusion_matrix(y_te, pred).tolist(),
    **F.insights(raw),
}
json.dump(result, open("analysis.json", "w"), indent=1, default=int)

# 7. requirements.txt with your exact versions (needed for hosting)
from importlib.metadata import version
pk = ["pandas", "numpy", "scikit-learn", "joblib", "fastapi", "uvicorn"]
lines = []
for p in pk:
    try:
        lines.append(f"{p}=={version(p)}")
    except Exception:
        lines.append(p)
open("requirements.txt", "w").write("\n".join(lines) + "\n")
print("Model pipeline saved as severity_model.pkl")
