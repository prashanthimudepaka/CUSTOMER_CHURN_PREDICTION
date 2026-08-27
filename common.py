"""Shared data preparation used by both train_model.py and main.py.

Keeping this in one place means the API cleans incoming CSVs exactly
the way the training data was cleaned.
"""

import pandas as pd

ID_COL = "customerID"
TARGET_COL = "Churn"

NUMERIC_COLS = ["SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"]

CATEGORICAL_COLS = [
    "gender", "Partner", "Dependents", "PhoneService", "MultipleLines",
    "InternetService", "OnlineSecurity", "OnlineBackup", "DeviceProtection",
    "TechSupport", "StreamingTV", "StreamingMovies", "Contract",
    "PaperlessBilling", "PaymentMethod",
]

FEATURE_COLS = NUMERIC_COLS + CATEGORICAL_COLS


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise types and handle the known quirks of this schema."""
    df = df.copy()

    # Strip stray whitespace in text columns (TotalCharges has blank strings
    # for brand-new customers in the original dataset).
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip()

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def missing_columns(df: pd.DataFrame) -> list[str]:
    """Which columns the model needs that this upload doesn't have."""
    return [c for c in FEATURE_COLS if c not in df.columns]
