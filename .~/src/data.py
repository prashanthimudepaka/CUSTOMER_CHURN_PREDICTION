"""Data loading and cleaning.

Phase 1 workflow: explore in notebooks/01_eda.ipynb first, then promote
your cleaning logic into `clean()` here so the whole pipeline can reuse it.
"""

import pandas as pd

from src.config import RAW_DATA_PATH


def load_raw() -> pd.DataFrame:
    """Load the raw Telco churn CSV.

    Download it from:
    https://www.kaggle.com/datasets/blastchar/telco-customer-churn
    and place it at data/raw/WA_Fn-UseC_-Telco-Customer-Churn.csv
    """
    if not RAW_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at {RAW_DATA_PATH}. See data/README.md for download steps."
        )
    return pd.read_csv(RAW_DATA_PATH)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned copy of the raw dataframe.

    TODO (Phase 1) — implement, in this order:
      1. `TotalCharges` is typed as object and contains blank strings.
         Convert to numeric (hint: pd.to_numeric with errors="coerce"),
         then decide how to handle the resulting NaNs — look at those
         rows first; they have something in common. Justify your choice
         in the EDA notebook.
      2. Drop or set aside the `customerID` column (it's an identifier,
         not a feature).
      3. Map the target `Churn` from Yes/No to 1/0.
      4. Anything else your EDA uncovers.
    """
    df = df.copy()
    # TODO(Phase 1): implement cleaning steps described above.
    return df
