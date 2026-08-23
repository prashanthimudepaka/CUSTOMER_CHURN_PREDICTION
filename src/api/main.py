"""FastAPI service for churn predictions.

Run locally with:  uvicorn src.api.main:app --reload
Interactive docs:  http://127.0.0.1:8000/docs

/health works today (so tests and CI are green from day 1).
/predict is implemented in Phase 4, after a model exists.
"""

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Telco Churn Prediction API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Liveness probe — used by tests, Docker healthchecks, and the cloud platform."""
    return {"status": "ok"}


@app.post("/predict")
def predict() -> dict:
    """Return churn probability for one customer.

    TODO (Phase 4):
      1. Define a pydantic model `CustomerFeatures` mirroring the training
         columns, e.g.:

         class CustomerFeatures(BaseModel):
             tenure: int
             MonthlyCharges: float
             TotalCharges: float
             Contract: str
             # ... the rest of the categorical/numeric features

      2. Load the trained pipeline ONCE at startup (joblib.load(MODEL_PATH)
         inside a lifespan handler or module-level cache) — never per request.
      3. Convert the validated payload to a one-row DataFrame and call
         pipeline.predict_proba(); return {"churn_probability": ..., "churn": bool}.
      4. Add tests: valid payload -> 200 with a probability in [0, 1];
         missing/invalid field -> 422.
    """
    raise HTTPException(status_code=501, detail="Not implemented yet — see Phase 4 in README.")
