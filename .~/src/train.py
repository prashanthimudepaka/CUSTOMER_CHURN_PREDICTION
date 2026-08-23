"""Model training pipeline.

Phase 2: baseline (logistic regression in a sklearn Pipeline).
Phase 3: stronger models (RandomForest, XGBoost), cross-validation,
         class-imbalance handling, and MLflow experiment tracking.

Run with:  python -m src.train
"""


def build_pipeline():
    """Build and return the sklearn Pipeline.

    TODO (Phase 2):
      - ColumnTransformer: OneHotEncoder for categorical columns,
        StandardScaler for numeric columns (tenure, MonthlyCharges, TotalCharges).
      - Estimator: start with LogisticRegression(max_iter=1000,
        class_weight="balanced", random_state=RANDOM_STATE from src.config).
      - Return a single Pipeline([("prep", ...), ("model", ...)]) object so
        preprocessing is *inside* the artifact you save — this is what makes
        serving in Phase 4 trivial.
    """
    raise NotImplementedError("Phase 2: implement build_pipeline()")


def main() -> None:
    """Train, evaluate, and save the model.

    TODO (Phase 2):
      - Load + clean data via src.data, split with train_test_split
        (stratify on the target! use TEST_SIZE and RANDOM_STATE from config).
      - Fit the pipeline; report ROC-AUC, precision, recall, and a
        confusion matrix. Accuracy alone is misleading at ~27% churn.
      - Save the fitted pipeline to MODEL_PATH with joblib.dump.

    TODO (Phase 3):
      - Wrap the run in `with mlflow.start_run():` and log params,
        metrics, and the model artifact.
      - Compare LogisticRegression vs RandomForest vs XGBoost with
        cross_val_score before trusting any single split.
    """
    raise NotImplementedError("Phase 2: implement main()")


if __name__ == "__main__":
    main()
