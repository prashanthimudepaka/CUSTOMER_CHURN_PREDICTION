<div align="center">

# 📉 Churn Triage

**Know who's leaving before they leave.**

An end-to-end machine learning app that scores telecom customers for churn risk,
explains *why* each one is at risk, and gives retention teams an AI-generated
action plan for saving them.

🔴 **[Live demo → churn-triage.onrender.com](https://churn-triage.onrender.com)**
*(free tier — first load after 15 min idle takes ~30–50 s to wake up)*

`Python` · `FastAPI` · `scikit-learn` · `PostgreSQL` · `Plotly` · `Claude AI`

</div>

---

## ✨ What it does

Upload a customer CSV → every customer comes back **scored, ranked, and explained**.

| Feature | Description |
|---|---|
| 🎯 **Churn scoring** | Logistic regression scores every customer 0–100% and sorts riskiest-first |
| 💡 **Explainability** | Each customer gets their top 3 churn drivers, straight from the model's coefficients — no black box |
| 🤖 **AI explanations** | Click *Explain* on any row and Claude writes a plain-English analysis of that customer |
| 🎯 **AI action plans** | Enter a customer ID and get a tailored retention plan: urgency, channel, offers, and a call script |
| 📊 **Analytics** | Live charts — probability distribution, risk breakdown, tenure vs. churn, top drivers |
| 📞 **Retention tracker** | Log call outcomes and measure your real success rate over time |
| 📜 **History** | Every score and every call is stored in PostgreSQL — nothing resets |

## 🧠 The model

Logistic regression on the IBM Telco churn dataset (7,043 customers), with
one-hot encoded categoricals and standardized numerics in a single
scikit-learn pipeline.

**Held-out performance: ROC-AUC 0.84 · recall 0.78 · precision 0.75** (at the
0.5 threshold, with balanced class weights — tuned to catch leavers, since a
missed churner costs more than a wasted call).

**Why logistic regression instead of XGBoost?** For retention work,
explainability beats a few points of AUC. Every driver shown in the app is
just `feature value × coefficient` — exact, defensible, and explainable to a
customer on the phone in one sentence.

## 🚀 Run it locally

```bash
pip install -r requirements.txt
python train_model.py        # downloads data, trains, saves the model
uvicorn main:app --reload    # then open http://127.0.0.1:8000
```

That's it. Locally the app uses SQLite automatically; no configuration needed.

## 🔌 API

| Endpoint | Method | What it does |
|---|---|---|
| `/` | GET | The dashboard UI |
| `/predict` | POST | Score a CSV — returns probabilities, bands, and drivers |
| `/explain` | POST | AI explanation for one customer |
| `/suggest` | POST | AI retention action plan for one scored customer |
| `/analytics` | GET | Aggregated stats and chart data |
| `/history` | GET | Every stored score and retention call |
| `/feedback` | POST | Record a retention call outcome |
| `/sample` | GET | A 25-row demo CSV |
| `/health` | GET | Service status and model metrics |

## 📁 Project structure

```
churn-dashboard/
├── main.py               FastAPI app — scoring, explanations, analytics, history
├── train_model.py        Trains and evaluates the model, saves artifacts
├── common.py             Shared data cleaning (training and API stay in sync)
├── database.py           SQLAlchemy models — SQLite locally, PostgreSQL in prod
├── static/index.html     The entire frontend (vanilla JS, no build step)
├── model/                Trained pipeline + held-out metrics
├── data/                 Sample CSV for the demo button
└── requirements.txt      Pinned dependencies
```

## ☁️ Deploy (Render free tier)

1. Fork/push this repo to GitHub.
2. On [render.com](https://render.com): **New → PostgreSQL** → copy the Internal Database URL.
3. **New → Web Service** → connect the repo:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables:
   - `DATABASE_URL` — the PostgreSQL URL from step 2 *(required for persistent history)*
   - `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com) *(optional — enables AI explanations; without it the app falls back to built-in templates)*
5. Deploy. Done.

## 🗺️ Roadmap

- [ ] User accounts and per-team scoring history
- [ ] Threshold tuning UI (precision/recall trade-off slider)
- [ ] Scheduled retraining with metric comparison
- [ ] CRM webhooks (auto-push high-risk customers to Salesforce/HubSpot)

---

<div align="center">
Built with FastAPI + scikit-learn + Claude · MIT-friendly · PRs welcome
</div>
