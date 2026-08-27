# Churn Triage

Upload a customer CSV, get back every customer scored for churn risk, ranked,
and tagged with the top reasons they're at risk — so a retention team knows who
to call first.

Live demo: <add your URL here after deploying>

## What it does

- **POST /predict** — accepts a CSV (Telco customer schema), returns per-customer
  churn probability, a High/Medium/Low band, and the top 3 drivers pushing that
  specific customer toward churn
- **GET /sample** — a 25-row sample CSV so anyone can try the app instantly
- **GET /health** — service status plus held-out model metrics
- **GET /** — the dashboard UI (drag-and-drop upload, ranked table, CSV export)

## Model

Logistic regression with one-hot encoding and standardized numerics
(scikit-learn pipeline), trained on the IBM Telco churn dataset (7,043 customers).

Held-out (20%) performance: **ROC-AUC 0.84**, recall 0.78 at the 0.5 threshold
with balanced class weights — tuned toward catching leavers, since missing a
churner costs more than a wasted retention call.

Per-customer drivers come from the logistic regression itself: each transformed
feature's contribution to the churn logit is its value times its coefficient,
and the top positive contributions are reported. No SHAP dependency needed;
fully explainable in an interview.

## Run locally

```bash
pip install -r requirements.txt
python train_model.py        # downloads data, trains, saves model + sample
uvicorn main:app --reload
# open http://127.0.0.1:8000
```

## Deploy (free tier)

1. Push this folder to a public GitHub repo.
2. On https://render.com → New → Web Service → connect the repo.
3. Build command: `pip install -r requirements.txt && python train_model.py`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Deploy. Your URL is live — put it at the top of this README and on your resume.

Training runs in the build step, so the model is rebuilt from source on every
deploy — no pickle files in git, no version-mismatch surprises.

Note: Render's free tier sleeps after inactivity; the first request after a
while takes ~30s to wake. Mention this to anyone you send the link to, or add
a free uptime pinger.

## Roadmap

- [ ] **Stage 2 — accounts:** Next.js frontend on Vercel, Supabase auth
      (email magic link), saved scoring history per user
- [ ] **Stage 3 — MLOps signal:** Dockerfile, request logging, a model
      version stamp in responses, retraining script with metric comparison
- [ ] Threshold tuning UI (precision/recall trade-off slider)

## Project structure

```
common.py            shared data cleaning (training and API stay in sync)
train_model.py       trains, evaluates, saves model + sample data
main.py              FastAPI app: scoring API + serves the UI
static/index.html    dashboard frontend (vanilla JS, no build step)
requirements.txt     pinned dependencies
```
