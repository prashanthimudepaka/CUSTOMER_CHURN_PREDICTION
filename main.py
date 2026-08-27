"""Churn risk scoring API.

Run locally:  uvicorn main:app --reload
Then open:    http://127.0.0.1:8000
"""

import io
import json
import pathlib
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common import ID_COL, TARGET_COL, clean_dataframe, missing_columns
from database import ScoringResult, RetentionFeedback, get_db

MODEL_PATH = pathlib.Path("model/model.pkl")
METRICS_PATH = pathlib.Path("model/metrics.json")
SAMPLE_PATH = pathlib.Path("data/sample_customers.csv")
MAX_ROWS = 5000

app = FastAPI(title="Churn Risk API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend's domain in stage 2
    allow_methods=["*"],
    allow_headers=["*"],
)

if not MODEL_PATH.exists():
    raise RuntimeError("model/model.pkl not found — run `python train_model.py` first.")

model = joblib.load(MODEL_PATH)
metrics = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else {}

# Pre-compute what we need for per-customer explanations.
_prep = model.named_steps["prep"]
_clf = model.named_steps["clf"]
_coefs = _clf.coef_[0]
_feature_names = _prep.get_feature_names_out()


def _pretty(name: str) -> str:
    """'cat__Contract_Month-to-month' -> 'Contract = Month-to-month'."""
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


# Pydantic models for feedback API
class FeedbackRequest(BaseModel):
    customer_id: str
    call_made: bool = False
    call_successful: bool = None
    actual_churn: bool = None
    notes: str = None


def score_dataframe(df: pd.DataFrame, db: Session = None) -> dict:
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

    # Per-row drivers: each transformed feature's contribution to the
    # churn logit is (feature value x coefficient). The top positive
    # contributions are what push this customer toward leaving.
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
                # X_t is standardized, so the sign says low vs high.
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

    # Save to database if db is provided
    if db:
        for row in rows:
            result = ScoringResult(
                customer_id=row["customer_id"],
                churn_probability=row["probability"],
                risk_band=row["band"],
                top_drivers=json.dumps(row["drivers"])
            )
            db.add(result)
        db.commit()

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
async def predict(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")
    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse that file as CSV.")
    # A labeled export is fine — just ignore the target column.
    df = df.drop(columns=[TARGET_COL], errors="ignore")
    return score_dataframe(df, db=db)


@app.post("/feedback")
def submit_feedback(feedback: FeedbackRequest, db: Session = Depends(get_db)) -> dict:
    """Record retention call outcome for a customer."""
    # Find the most recent score for this customer
    last_score = db.query(ScoringResult).filter(
        ScoringResult.customer_id == feedback.customer_id
    ).order_by(ScoringResult.timestamp.desc()).first()

    retention = RetentionFeedback(
        customer_id=feedback.customer_id,
        churn_probability=last_score.churn_probability if last_score else None,
        call_made=feedback.call_made,
        call_successful=feedback.call_successful,
        actual_churn=feedback.actual_churn,
        notes=feedback.notes
    )
    db.add(retention)
    db.commit()
    return {"status": "feedback recorded", "customer_id": feedback.customer_id}


@app.get("/analytics")
def get_analytics(days: int = 30, db: Session = Depends(get_db)) -> dict:
    """Get analytics and insights from historical data."""
    since = datetime.utcnow() - timedelta(days=days)

    # Scoring statistics
    scores = db.query(ScoringResult).filter(
        ScoringResult.timestamp >= since
    ).all()

    feedback_data = db.query(RetentionFeedback).filter(
        RetentionFeedback.timestamp >= since
    ).all()

    if not scores:
        return {"error": "No data available"}

    # Prepare data for frontend
    probabilities = [s.churn_probability for s in scores]
    risk_bands = [s.risk_band for s in scores]
    tenures = [s.tenure for s in scores if s.tenure is not None]

    # Retention metrics
    calls_made = [f for f in feedback_data if f.call_made]
    calls_successful = [f for f in calls_made if f.call_successful]
    success_rate = len(calls_successful) / len(calls_made) * 100 if calls_made else 0

    # Churn vs prediction accuracy
    actual_churns = [f for f in feedback_data if f.actual_churn]
    correct_predictions = [f for f in actual_churns if f.churn_probability >= 0.5]
    prediction_accuracy = len(correct_predictions) / len(actual_churns) * 100 if actual_churns else 0

    return {
        "period_days": days,
        "total_scored": len(scores),
        "summary": {
            "high_risk": risk_bands.count("High"),
            "medium_risk": risk_bands.count("Medium"),
            "low_risk": risk_bands.count("Low"),
            "avg_probability": round(float(np.mean(probabilities)), 4),
            "median_probability": round(float(np.median(probabilities)), 4),
        },
        "retention": {
            "calls_made": len(calls_made),
            "calls_successful": len(calls_successful),
            "success_rate": round(success_rate, 2),
        },
        "prediction_accuracy": round(prediction_accuracy, 2),
        "chart_data": {
            "probabilities": [round(p, 4) for p in probabilities],
            "risk_bands": risk_bands,
            "tenures": [round(t, 0) for t in tenures],
            "timestamps": [str(s.timestamp) for s in scores],
        }
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
