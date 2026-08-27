"""Churn risk scoring API.

Run locally:  uvicorn main:app --reload
Then open:    http://127.0.0.1:8000
"""

import io
import json
import os
import pathlib
from datetime import datetime, timedelta
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from common import ID_COL, TARGET_COL, clean_dataframe, missing_columns

# Database is optional: the app still serves predictions if the DB is down.
try:
    from sqlalchemy.orm import Session
    from database import RetentionFeedback, ScoringResult, get_db
    DB_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    print(f"[Warning] Database unavailable, history disabled: {exc}")
    DB_AVAILABLE = False

    def get_db():  # no-op dependency so endpoints still work
        yield None

MODEL_PATH = pathlib.Path("model/model.pkl")
METRICS_PATH = pathlib.Path("model/metrics.json")
SAMPLE_PATH = pathlib.Path("data/sample_customers.csv")
MAX_ROWS = 5000

# Train on first boot if the model isn't there (e.g. fresh deploy).
if not MODEL_PATH.exists():
    print("[Startup] model/model.pkl not found — training now...")
    import train_model
    train_model.main()

model = joblib.load(MODEL_PATH)
metrics = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else {}

app = FastAPI(title="Churn Risk API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend's domain in stage 2
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pre-compute what we need for per-customer explanations.
_prep = model.named_steps["prep"]
_clf = model.named_steps["clf"]
_coefs = _clf.coef_[0]
_feature_names = _prep.get_feature_names_out()


class FeedbackRequest(BaseModel):
    customer_id: str
    call_made: bool = False
    call_successful: Optional[bool] = None
    actual_churn: Optional[bool] = None
    notes: Optional[str] = None


class ExplainRequest(BaseModel):
    customer_id: str
    probability: float
    band: str
    drivers: list[str]
    tenure: Optional[float] = None


# --- LLM explanations (optional: set ANTHROPIC_API_KEY to enable) ---
try:
    import anthropic
    _LLM_SDK = True
except ImportError:
    _LLM_SDK = False

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")
_llm_client = None


def _get_llm():
    global _llm_client
    if _llm_client is None and _LLM_SDK and os.getenv("ANTHROPIC_API_KEY"):
        _llm_client = anthropic.Anthropic()
    return _llm_client


EXPLAIN_SYSTEM = (
    "You are a customer-retention analyst for a telecom company. Given a "
    "customer's churn-risk score and the top factors driving it, explain in "
    "plain English why this customer is at risk. For each factor, write 2-3 "
    "sentences: what it means and why it raises churn risk. End with one "
    "concrete retention action for this specific customer. Plain text only, "
    "no markdown. Keep the whole answer under 180 words."
)

# Fallback used when no API key is configured or the API call fails.
DRIVER_NOTES = {
    "Contract = Month-to-month": "No contract lock-in means zero switching cost — the single strongest churn driver in the model.",
    "tenure (low)": "A new customer who hasn't built loyalty yet; short-tenure customers leave far more easily than long-time ones.",
    "InternetService = Fiber optic": "Fiber customers face high bills and heavy competition, so they comparison-shop more than DSL customers.",
    "TechSupport = No": "Customers without tech support hit frustrations with no help — a classic exit trigger.",
    "OnlineSecurity = No": "Fewer add-on services means a thinner relationship and less reason to stay.",
    "PaymentMethod = Electronic check": "Electronic-check payers churn more than auto-pay customers in the Telco data.",
    "MonthlyCharges (high)": "A high bill invites comparison shopping against competitor offers.",
    "PaperlessBilling = Yes": "Correlates with digitally-savvy customers who switch providers more readily.",
}


def _template_explanation(req: ExplainRequest) -> str:
    lines = [f"{req.customer_id} scored {req.probability:.0%} churn risk ({req.band})."]
    for d in req.drivers:
        note = DRIVER_NOTES.get(d, "This factor pushes churn risk up in the trained model.")
        lines.append(f"• {d}: {note}")
    lines.append(
        "Suggested action: call with an offer targeting the top driver "
        "(e.g., a discount for moving to a longer contract)."
    )
    return "\n".join(lines)


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


def score_dataframe(df: pd.DataFrame, db=None) -> dict:
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
    # churn logit is (feature value x coefficient).
    X_t = _prep.transform(df)
    X_t = X_t.toarray() if hasattr(X_t, "toarray") else np.asarray(X_t)
    contributions = X_t * _coefs

    ids = (
        df[ID_COL].astype(str).tolist()
        if ID_COL in df.columns
        else [f"row {i + 1}" for i in range(len(df))]
    )
    tenures = df["tenure"].tolist() if "tenure" in df.columns else [None] * len(df)

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
            "tenure": tenures[i],
        })

    # Persist scoring history when the database is up.
    if DB_AVAILABLE and db is not None:
        try:
            for row in rows:
                db.add(ScoringResult(
                    customer_id=row["customer_id"],
                    churn_probability=row["probability"],
                    risk_band=row["band"],
                    tenure=row["tenure"],
                    top_drivers=json.dumps(row["drivers"]),
                ))
            db.commit()
        except Exception as exc:
            print(f"[Warning] Could not save scoring history: {exc}")

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
    return {
        "status": "ok",
        "model_loaded": True,
        "database": "connected" if DB_AVAILABLE else "disabled",
        "metrics": metrics,
    }


@app.get("/sample")
def sample() -> FileResponse:
    if not SAMPLE_PATH.exists():
        raise HTTPException(status_code=404, detail="Sample file not found.")
    return FileResponse(SAMPLE_PATH, media_type="text/csv", filename="sample_customers.csv")


@app.post("/predict")
async def predict(file: UploadFile = File(...), db=Depends(get_db)) -> dict:
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
def submit_feedback(feedback: FeedbackRequest, db=Depends(get_db)) -> dict:
    """Record retention call outcome for a customer."""
    if not DB_AVAILABLE or db is None:
        raise HTTPException(status_code=503, detail="Database not configured.")

    last_score = (
        db.query(ScoringResult)
        .filter(ScoringResult.customer_id == feedback.customer_id)
        .order_by(ScoringResult.timestamp.desc())
        .first()
    )
    db.add(RetentionFeedback(
        customer_id=feedback.customer_id,
        churn_probability=last_score.churn_probability if last_score else None,
        call_made=feedback.call_made,
        call_successful=feedback.call_successful,
        actual_churn=feedback.actual_churn,
        notes=feedback.notes,
    ))
    db.commit()
    return {"status": "feedback recorded", "customer_id": feedback.customer_id}


@app.get("/analytics")
def get_analytics(days: int = 30, db=Depends(get_db)) -> dict:
    """Aggregated history for the analytics dashboard."""
    if not DB_AVAILABLE or db is None:
        return {"error": "Database not configured"}

    since = datetime.utcnow() - timedelta(days=days)
    scores = db.query(ScoringResult).filter(ScoringResult.timestamp >= since).all()
    feedback_rows = db.query(RetentionFeedback).filter(RetentionFeedback.timestamp >= since).all()

    if not scores:
        return {"error": "No data available"}

    probabilities = [s.churn_probability for s in scores]
    risk_bands = [s.risk_band for s in scores]
    tenures = [s.tenure for s in scores if s.tenure is not None]

    calls_made = [f for f in feedback_rows if f.call_made]
    calls_successful = [f for f in calls_made if f.call_successful]
    success_rate = len(calls_successful) / len(calls_made) * 100 if calls_made else 0

    actual_churns = [f for f in feedback_rows if f.actual_churn]
    correct = [f for f in actual_churns if (f.churn_probability or 0) >= 0.5]
    accuracy = len(correct) / len(actual_churns) * 100 if actual_churns else 0

    # Which drivers appear most often across all scored customers.
    from collections import Counter
    driver_counts: Counter = Counter()
    for s in scores:
        if s.top_drivers:
            try:
                driver_counts.update(json.loads(s.top_drivers))
            except Exception:
                pass
    top_drivers = [
        {"driver": d, "count": c} for d, c in driver_counts.most_common(6)
    ]

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
        "prediction_accuracy": round(accuracy, 2),
        "chart_data": {
            "probabilities": [round(p, 4) for p in probabilities],
            "risk_bands": risk_bands,
            "tenures": [round(t, 0) for t in tenures],
            "timestamps": [str(s.timestamp) for s in scores],
            "top_drivers": top_drivers,
        },
    }


@app.post("/explain")
def explain(req: ExplainRequest) -> dict:
    """Natural-language explanation of one customer's churn risk.

    Uses Claude when ANTHROPIC_API_KEY is set; otherwise falls back to
    built-in template explanations so the dashboard always works.
    """
    client = _get_llm()
    if client is None:
        return {"explanation": _template_explanation(req), "source": "template"}

    tenure_txt = f"{req.tenure:.0f} months" if req.tenure is not None else "unknown"
    prompt = (
        f"Customer {req.customer_id}: churn probability {req.probability:.0%}, "
        f"risk band {req.band}, tenure {tenure_txt}. "
        f"Top churn drivers from the model: {', '.join(req.drivers) or 'none identified'}."
    )
    try:
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=EXPLAIN_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        if msg.stop_reason == "refusal":
            return {"explanation": _template_explanation(req), "source": "template"}
        text = next((b.text for b in msg.content if b.type == "text"), "")
        if not text.strip():
            return {"explanation": _template_explanation(req), "source": "template"}
        return {"explanation": text, "source": "llm", "model": CLAUDE_MODEL}
    except anthropic.AuthenticationError:
        return {"explanation": _template_explanation(req), "source": "template",
                "note": "Invalid ANTHROPIC_API_KEY — using built-in explanation."}
    except anthropic.RateLimitError:
        return {"explanation": _template_explanation(req), "source": "template",
                "note": "Rate limited — using built-in explanation."}
    except (anthropic.APIStatusError, anthropic.APIConnectionError):
        return {"explanation": _template_explanation(req), "source": "template",
                "note": "LLM unavailable — using built-in explanation."}


class SuggestRequest(BaseModel):
    customer_id: str


SUGGEST_SYSTEM = (
    "You are a senior customer-retention strategist for a telecom company. "
    "Given one customer's churn-risk profile, produce a concrete action plan with "
    "four numbered sections: 1) Urgency — when and how fast to act; 2) Best channel "
    "— call, email, or SMS and why; 3) Offers — two or three specific promotions "
    "tailored to their churn drivers, with concrete terms; 4) Opening script — two "
    "sentences the retention agent can say verbatim. Be specific and practical. "
    "Plain text only, no markdown symbols. Under 220 words."
)

# Driver-specific offers used by the no-API-key fallback.
DRIVER_OFFERS = {
    "Contract = Month-to-month": "Offer 15-20% off for switching to a 1-year contract.",
    "tenure (low)": "Schedule a 10-minute onboarding check-in and offer a first-90-days perk.",
    "InternetService = Fiber optic": "Apply a loyalty credit or price-match against local competitors.",
    "TechSupport = No": "Add 3 months of free premium tech support.",
    "OnlineSecurity = No": "Bundle a free online-security add-on for 6 months.",
    "PaymentMethod = Electronic check": "Offer a small monthly discount for enrolling in auto-pay.",
    "MonthlyCharges (high)": "Review their plan for a right-sizing discount before a competitor does.",
}

BAND_URGENCY = {
    "High": "Call within 24 hours — this customer can leave at any moment.",
    "Medium": "Reach out within the week by phone or personalized email.",
    "Low": "No urgent action; include in the next loyalty campaign and monitor.",
}


def _template_suggestions(customer_id: str, probability: float, band: str,
                          drivers: list[str]) -> str:
    lines = [
        f"1) Urgency: {BAND_URGENCY.get(band, BAND_URGENCY['Medium'])}",
        "2) Channel: phone call for High risk, personalized email otherwise.",
        "3) Offers:",
    ]
    offers = [DRIVER_OFFERS[d] for d in drivers if d in DRIVER_OFFERS]
    if not offers:
        offers = ["Offer a loyalty discount tied to a longer commitment."]
    lines += [f"   - {o}" for o in offers]
    lines.append(
        f'4) Opening script: "Hi, this is [name] from [company]. You have been with us '
        f'and we want to make sure you are getting the most from your plan — I have a '
        f'couple of offers picked out just for you."'
    )
    return "\n".join(lines)


@app.post("/suggest")
def suggest_actions(req: SuggestRequest, db=Depends(get_db)) -> dict:
    """AI retention action plan for one previously scored customer."""
    if not DB_AVAILABLE or db is None:
        raise HTTPException(status_code=503, detail="Database not configured.")

    last = (
        db.query(ScoringResult)
        .filter(ScoringResult.customer_id == req.customer_id)
        .order_by(ScoringResult.timestamp.desc())
        .first()
    )
    if last is None:
        raise HTTPException(
            status_code=404,
            detail=f"Customer '{req.customer_id}' has not been scored yet — "
                   "upload a CSV containing them first.",
        )

    drivers = json.loads(last.top_drivers) if last.top_drivers else []
    profile = {
        "customer_id": last.customer_id,
        "probability": last.churn_probability,
        "band": last.risk_band,
        "tenure": last.tenure,
        "drivers": drivers,
    }

    client = _get_llm()
    if client is None:
        return {
            "suggestions": _template_suggestions(
                last.customer_id, last.churn_probability, last.risk_band, drivers),
            "source": "template", "profile": profile,
        }

    tenure_txt = f"{last.tenure:.0f} months" if last.tenure is not None else "unknown"
    prompt = (
        f"Customer {last.customer_id}: churn probability "
        f"{last.churn_probability:.0%}, risk band {last.risk_band}, tenure "
        f"{tenure_txt}. Top churn drivers: {', '.join(drivers) or 'none identified'}."
    )
    try:
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SUGGEST_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next((b.text for b in msg.content if b.type == "text"), "")
        if msg.stop_reason == "refusal" or not text.strip():
            raise ValueError("empty or refused")
        return {"suggestions": text, "source": "llm",
                "model": CLAUDE_MODEL, "profile": profile}
    except Exception:
        return {
            "suggestions": _template_suggestions(
                last.customer_id, last.churn_probability, last.risk_band, drivers),
            "source": "template", "profile": profile,
            "note": "LLM unavailable — using built-in playbook.",
        }


@app.get("/history")
def get_history(limit: int = 200, db=Depends(get_db)) -> dict:
    """Individual records: every scoring event and every retention call."""
    if not DB_AVAILABLE or db is None:
        return {"error": "Database not configured"}

    scores = (
        db.query(ScoringResult)
        .order_by(ScoringResult.timestamp.desc())
        .limit(limit)
        .all()
    )
    feedback = (
        db.query(RetentionFeedback)
        .order_by(RetentionFeedback.timestamp.desc())
        .limit(limit)
        .all()
    )

    return {
        "scores": [
            {
                "timestamp": str(s.timestamp),
                "customer_id": s.customer_id,
                "probability": s.churn_probability,
                "band": s.risk_band,
                "drivers": json.loads(s.top_drivers) if s.top_drivers else [],
            }
            for s in scores
        ],
        "feedback": [
            {
                "timestamp": str(f.timestamp),
                "customer_id": f.customer_id,
                "probability": f.churn_probability,
                "call_made": f.call_made,
                "call_successful": f.call_successful,
                "actual_churn": f.actual_churn,
                "notes": f.notes,
            }
            for f in feedback
        ],
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
