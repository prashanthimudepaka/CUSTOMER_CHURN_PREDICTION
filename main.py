"""Churn risk scoring API - Minimal working version."""

import io
import json
import pathlib

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from common import ID_COL, TARGET_COL, clean_dataframe, missing_columns

MODEL_PATH = pathlib.Path("model/model.pkl")
METRICS_PATH = pathlib.Path("model/metrics.json")
SAMPLE_PATH = pathlib.Path("data/sample_customers.csv")
MAX_ROWS = 5000

app = FastAPI(title="Churn Risk API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if not MODEL_PATH.exists():
    raise RuntimeError("model/model.pkl not found — run `python train_model.py` first.")

model = joblib.load(MODEL_PATH)
metrics = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else {}

_prep = model.named_steps["prep"]
_clf = model.named_steps["clf"]
_coefs = _clf.coef_[0]
_feature_names = _prep.get_feature_names_out()


def _pretty(name: str) -> str:
    if name.startswith("cat__"):
        rest = name[len("cat__"):]
        for col_len in range(len(rest), 0, -1):
            col, sep, val = rest[:col_len], rest[col_len:col_len + 1], rest[col_len + 1:]
            if sep == "_" and val:
                return f"{col} = {val}"
        return rest
    return name.removeprefix("num__")


def _band(p: float) -> str:
    if p >= 0.66:
        return "High"
    if p >= 0.33:
        return "Medium"
    return "Low"


def score_dataframe(df: pd.DataFrame) -> dict:
    df = clean_dataframe(df)

    missing = missing_columns(df)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required columns: {', '.join(missing)}",
        )
    if len(df) == 0:
        raise HTTPException(status_code=400, detail="CSV has no data rows.")
    if len(df) > MAX_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"CSV has {len(df)} rows; the limit is {MAX_ROWS}.",
        )

    probs = model.predict_proba(df)[:, 1]

    X_t = _prep.transform(df)
    X_t = X_t.toarray() if hasattr(X_t, "toarray") else np.asarray(X_t)
    contributions = X_t * _coefs

    ids = (
        df[ID_COL].astype(str).tolist()
        if ID_COL in df.columns
        else [f"row {i + 1}" for i in range(len(df))]
    )

    rows = []
    for i, p in enumerate(probs):
        top = np.argsort(contributions[i])[::-1][:3]
        drivers = []
        for j in top:
            if contributions[i][j] <= 0:
                continue
            name = _pretty(_feature_names[j])
            if _feature_names[j].startswith("num__"):
                name += " (low)" if X_t[i][j] < 0 else " (high)"
            drivers.append(name)
        rows.append({
            "customer_id": ids[i],
            "probability": round(float(p), 4),
            "band": _band(float(p)),
            "drivers": drivers,
        })

    rows.sort(key=lambda r: r["probability"], reverse=True)
    bands = [r["band"] for r in rows]
    return {
        "summary": {
            "customers": len(rows),
            "high": bands.count("High"),
            "medium": bands.count("Medium"),
            "low": bands.count("Low"),
            "median_probability": round(float(np.median(probs)), 4),
        },
        "model": {"roc_auc": metrics.get("roc_auc")},
        "rows": rows,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": True, "metrics": metrics}


@app.get("/sample")
def sample() -> FileResponse:
    if not SAMPLE_PATH.exists():
        raise HTTPException(status_code=404, detail="Sample file not found.")
    return FileResponse(SAMPLE_PATH, media_type="text/csv", filename="sample_customers.csv")


@app.post("/predict")
async def predict(file: UploadFile = None) -> dict:
    if file is None:
        raise HTTPException(status_code=400, detail="No file provided.")
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")
    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse that file as CSV.")
    df = df.drop(columns=["Churn"], errors="ignore")
    return score_dataframe(df)


@app.get("/")
def index() -> FileResponse:
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
