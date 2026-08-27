"""Train the churn model and save everything the API needs.

Run:  python train_model.py

Outputs:
  model/model.pkl            trained sklearn pipeline
  model/metrics.json         held-out evaluation metrics
  data/sample_customers.csv  25 unlabeled rows for demoing the app
"""

import json
import pathlib
import urllib.request

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import (CATEGORICAL_COLS, FEATURE_COLS, NUMERIC_COLS, TARGET_COL,
                    clean_dataframe)

DATA_URL = (
    "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
    "master/data/Telco-Customer-Churn.csv"
)
DATA_PATH = pathlib.Path("data/telco.csv")
MODEL_DIR = pathlib.Path("model")


def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        print(f"Downloading dataset to {DATA_PATH} ...")
        DATA_PATH.parent.mkdir(exist_ok=True)
        urllib.request.urlretrieve(DATA_URL, DATA_PATH)
    return pd.read_csv(DATA_PATH)


def main() -> None:
    df = clean_dataframe(load_data())
    df[TARGET_COL] = (df[TARGET_COL] == "Yes").astype(int)

    X = df[FEATURE_COLS]
    y = df[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    pipeline = Pipeline([
        ("prep", ColumnTransformer([
            ("num", StandardScaler(), NUMERIC_COLS),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLS),
        ])),
        ("clf", LogisticRegression(
            max_iter=2000, class_weight="balanced", C=1.0
        )),
    ])

    pipeline.fit(X_train, y_train)

    probs = pipeline.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.5).astype(int)
    metrics = {
        "roc_auc": round(float(roc_auc_score(y_test, probs)), 4),
        "precision_at_0.5": round(float(precision_score(y_test, preds)), 4),
        "recall_at_0.5": round(float(recall_score(y_test, preds)), 4),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
    }
    print("Held-out metrics:", json.dumps(metrics, indent=2))

    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(pipeline, MODEL_DIR / "model.pkl")
    (MODEL_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # A small unlabeled sample so anyone visiting the app can try it
    # without hunting for a CSV.
    sample = df.drop(columns=[TARGET_COL]).sample(25, random_state=7)
    sample.to_csv("data/sample_customers.csv", index=False)

    print("Saved model/model.pkl, model/metrics.json, data/sample_customers.csv")


if __name__ == "__main__":
    main()
