# Data

Raw and processed data live here but are **never committed** (see .gitignore).

## Getting the dataset

1. Go to: https://www.kaggle.com/datasets/blastchar/telco-customer-churn
2. Download and unzip.
3. Place the CSV at exactly:

   `data/raw/WA_Fn-UseC_-Telco-Customer-Churn.csv`

   (That path is hard-wired in `src/config.py` — change it there if you rename.)

Alternative (Kaggle CLI, after `pip install kaggle` and adding your API token):

```bash
kaggle datasets download -d blastchar/telco-customer-churn -p data/raw --unzip
```

## Folders

- `raw/` — untouched original files. Treat as read-only.
- `processed/` — outputs of `src/data.py` cleaning and train/test splits.
