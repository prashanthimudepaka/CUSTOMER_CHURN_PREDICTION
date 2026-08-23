"""Central configuration: paths and constants used across the project.

Everything that could otherwise be hard-coded in three different places
lives here instead. Import from this module, never redefine.
"""

from pathlib import Path

# --- Paths ---
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_PATH = DATA_DIR / "raw" / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = ROOT_DIR / "models"
MODEL_PATH = MODEL_DIR / "churn_model.joblib"

# --- Modeling constants ---
RANDOM_STATE = 42
TARGET_COLUMN = "Churn"
ID_COLUMN = "customerID"
TEST_SIZE = 0.2
