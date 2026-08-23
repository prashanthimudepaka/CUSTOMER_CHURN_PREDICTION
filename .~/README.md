# Telco Churn Prediction API

An end-to-end machine learning project: predict which telecom customers are likely to churn,
and serve that model as a production-grade REST API — with experiment tracking, tests,
Docker, CI/CD, cloud deployment, and drift monitoring.

> **Status:** Phase 0 complete (scaffolding). Currently working on: Phase 1 (EDA).

---

## Architecture (target state)

```
                ┌─────────────┐
 Kaggle CSV ──▶ │  data/raw   │
                └──────┬──────┘
                       ▼
              ┌─────────────────┐     ┌──────────┐
              │ train.py        │────▶│  MLflow  │  (experiment tracking)
              │ (sklearn/XGB)   │     └──────────┘
              └────────┬────────┘
                       ▼
              models/churn_model.joblib
                       ▼
              ┌─────────────────┐
              │ FastAPI /predict│ ◀── pytest + ruff (CI via GitHub Actions)
              └────────┬────────┘
                       ▼
                Docker image ──▶ Cloud (Render / AWS ECS)
                       ▼
              Evidently drift reports (monitoring)
```

## Roadmap

- [x] **Phase 0 — Scaffolding:** repo structure, requirements, README, smoke tests
- [ ] **Phase 1 — EDA:** profile the data, fix `TotalCharges`, visualize churn drivers, write hypotheses
- [ ] **Phase 2 — Baseline model:** sklearn Pipeline + logistic regression, stratified split, ROC-AUC / recall / precision
- [ ] **Phase 3 — Improve + track:** XGBoost / RandomForest, cross-validation, class imbalance handling, MLflow logging
- [ ] **Phase 4 — Serve:** FastAPI `/predict` with pydantic validation, pytest coverage
- [ ] **Phase 5 — Containerize:** multi-stage Dockerfile, run + test the container locally
- [ ] **Phase 6 — CI/CD:** GitHub Actions — lint + test on push, build image
- [ ] **Phase 7 — Deploy:** Render / Hugging Face Spaces (free), then AWS ECR + ECS as upgrade
- [ ] **Phase 8 — Monitor:** structured prediction logging + Evidently data-drift reports
- [ ] **Phase 9 — Stretch:** Streamlit dashboard, retraining script, model versioning

## Quickstart

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies (dev set includes notebooks, MLflow, testing tools)
pip install -r requirements-dev.txt

# 3. Freeze a lockfile for reproducibility (re-run after adding deps)
pip freeze > requirements.lock.txt

# 4. Get the dataset (see data/README.md) and place it at:
#    data/raw/WA_Fn-UseC_-Telco-Customer-Churn.csv

# 5. Verify everything is wired up
pytest
ruff check .

# 6. Run the API skeleton (health check works already)
uvicorn src.api.main:app --reload
# → open http://127.0.0.1:8000/health  and  http://127.0.0.1:8000/docs
```

Or with make: `make setup`, `make test`, `make lint`, `make api`.

## Dataset

**Telco Customer Churn** — https://www.kaggle.com/datasets/blastchar/telco-customer-churn

~7,000 customers, 21 columns, target = `Churn` (Yes/No, ~27% positive → imbalanced).
Known gotcha: `TotalCharges` contains blank strings and is typed as `object`, not float.
Raw data is **git-ignored** — never commit it.

## Project structure

```
telco-churn-api/
├── data/
│   ├── raw/                # original CSV (git-ignored)
│   └── processed/          # cleaned/split data (git-ignored)
├── models/                 # trained model artifacts (git-ignored)
├── notebooks/
│   └── 01_eda.ipynb        # Phase 1 starts here
├── src/
│   ├── config.py           # paths, constants, random seed
│   ├── data.py             # load + clean functions
│   ├── train.py            # training pipeline (Phase 2–3)
│   └── api/
│       └── main.py         # FastAPI app (Phase 4)
├── tests/
│   └── test_smoke.py       # keeps the repo green from day 1
├── requirements.txt        # runtime deps (what the Docker image needs)
├── requirements-dev.txt    # runtime + notebooks, tracking, test tooling
├── pyproject.toml          # ruff + pytest config
├── Makefile
└── README.md
```

## Conventions

- Notebooks are numbered: `01_eda.ipynb`, `02_baseline.ipynb`, ...
- Notebooks explore; **`src/` is the source of truth.** Promote working code out of notebooks.
- Commit small and often; message style: `phase1: fix TotalCharges dtype`.
- `RANDOM_STATE = 42` everywhere (see `src/config.py`) so results are reproducible.
- Add a LICENSE (MIT is a fine default) before making the repo public.

## Definition of done (per phase)

A phase is done when: code lives in `src/` (not just a notebook), `pytest` and
`ruff check .` pass, the roadmap checkbox above is ticked, and the README's
**Status** line is updated. That habit is the whole point of this project.
