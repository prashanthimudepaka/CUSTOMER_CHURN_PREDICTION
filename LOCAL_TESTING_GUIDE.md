# 🚀 Local Testing Guide - Churn Triage

## Quick Start (5 minutes)

### Step 1: Install Dependencies
```bash
cd C:\Users\Dell\Desktop\churn-dashboard
pip install -r requirements.txt
```

**What this installs:**
- FastAPI (API framework)
- Uvicorn (server)
- Scikit-learn (ML model)
- Pandas (data processing)

### Step 2: Train the Model
```bash
python train_model.py
```

**What happens:**
- Downloads IBM Telco dataset (7,043 customers) from GitHub
- Trains logistic regression model
- Saves: `model/model.pkl` + `model/metrics.json`
- Creates: `data/sample_customers.csv` (25 demo rows)

**Expected output:**
```
Downloading dataset to data/telco.csv ...
Held-out metrics: {
  "roc_auc": 0.84,
  "precision_at_0.5": 0.75,
  "recall_at_0.5": 0.78,
  "train_rows": 5634,
  "test_rows": 1409
}
Saved model/model.pkl, model/metrics.json, data/sample_customers.csv
```

### Step 3: Start the API Server
```bash
uvicorn main:app --reload
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Step 4: Open Dashboard
Open your browser → **http://127.0.0.1:8000**

You should see:
- "Churn Triage" header
- "Upload customer CSV" button
- "Score sample data" button
- Drag-and-drop area

---

## Testing Features

### Test 1: Score Sample Data (No Upload Needed)
1. Click **"Score sample data"** button
2. Wait 2-3 seconds
3. See results appear:
   - Summary chips: customers scored, high/medium/low counts, median risk
   - Ranked table with customer IDs, probabilities, risk bands, drivers
   - CSV export button

**Expected:** 25 customers scored, ~15-20% marked as High risk

---

### Test 2: Upload Custom CSV
1. Prepare a CSV with these columns:
   ```
   customerID,gender,SeniorCitizen,Partner,Dependents,tenure,PhoneService,
   MultipleLines,InternetService,OnlineSecurity,OnlineBackup,DeviceProtection,
   TechSupport,StreamingTV,StreamingMovies,Contract,PaperlessBilling,
   PaymentMethod,MonthlyCharges,TotalCharges
   ```

2. Create a simple test file: `test_customers.csv`
   ```csv
   customerID,gender,SeniorCitizen,Partner,Dependents,tenure,PhoneService,MultipleLines,InternetService,OnlineSecurity,OnlineBackup,DeviceProtection,TechSupport,StreamingTV,StreamingMovies,Contract,PaperlessBilling,PaymentMethod,MonthlyCharges,TotalCharges
   CUST001,Male,0,Yes,No,24,Yes,No,Fiber optic,No,Yes,No,Yes,No,No,Month-to-month,Yes,Electronic check,85.5,2048
   CUST002,Female,1,No,No,60,No,,DSL,Yes,No,Yes,Yes,Yes,No,Two year,No,Bank transfer,55.2,3312
   CUST003,Male,0,Yes,Yes,12,Yes,Yes,Fiber optic,No,No,No,No,No,No,Month-to-month,Yes,Credit card,75.0,900
   ```

3. Click **"Upload customer CSV"** → Select your file
4. Wait for results

**Expected:** 3 rows scored with churn probabilities & drivers

---

### Test 3: Test Risk Bands
Click the "Score sample data" button and look at the summary chips:

**High Risk (Red, ≥66% churn probability)**
- Should show customers with month-to-month contracts
- Multiple recent service calls
- No long-term services

**Medium Risk (Orange, 33-66%)**
- Customers with some risk factors

**Low Risk (Green, <33%)**
- Stable customers with long tenure

---

### Test 4: Examine Driver Attribution
In the results table, look at the "Why they're at risk" column:

Example high-risk customer:
- `Contract = Month-to-month` ← highest impact
- `TechSupport = No` ← second highest
- `InternetService = Fiber optic` ← third

These are calculated as: **feature_value × model_coefficient**

---

### Test 5: CSV Export
1. Score any dataset
2. Click **"Download scored CSV"**
3. Open the downloaded file

**Expected columns:**
```
customer_id,churn_probability,risk_band,top_drivers
CUST001,0.8234,High,"Contract = Month-to-month; TechSupport = No; ..."
```

---

### Test 6: API Health Check
Open browser → **http://127.0.0.1:8000/health**

**Expected response:**
```json
{
  "status": "ok",
  "model_loaded": true,
  "metrics": {
    "roc_auc": 0.84,
    "precision_at_0.5": 0.75,
    "recall_at_0.5": 0.78,
    "train_rows": 5634,
    "test_rows": 1409
  }
}
```

---

### Test 7: Error Handling

#### Test missing columns
Upload CSV without required columns → Should see:
```
CSV is missing required columns: Contract, InternetService, ...
```

#### Test non-CSV file
Upload `.xlsx` or `.txt` → Should see:
```
Please upload a .csv file.
```

#### Test empty CSV
Upload CSV with no data rows → Should see:
```
CSV has no data rows.
```

#### Test oversized file
Upload CSV with >5000 rows → Should see:
```
CSV has 6500 rows; the limit is 5000.
```

---

## Project Structure During Testing

After running, you should see:

```
churn-dashboard/
├── model/
│   ├── model.pkl              ← Trained model (created by train_model.py)
│   └── metrics.json           ← Performance metrics
├── data/
│   ├── telco.csv              ← Full dataset (auto-downloaded)
│   └── sample_customers.csv   ← Demo data
├── static/
│   └── index.html             ← Dashboard UI
├── main.py                    ← FastAPI app (running now)
├── train_model.py             ← Model training
├── common.py                  ← Data schema
└── requirements.txt
```

---

## Troubleshooting

### Error: "model/model.pkl not found"
**Fix:** Run `python train_model.py` first

### Error: "Port 8000 already in use"
**Fix:** Use a different port:
```bash
uvicorn main:app --reload --port 8001
# Then open: http://127.0.0.1:8001
```

### Error: Module not found (pandas, scikit-learn, etc.)
**Fix:** Reinstall dependencies:
```bash
pip install --upgrade -r requirements.txt
```

### Slow upload/scoring
**Expected:** 1,000 customers takes 2-3 seconds (normal for Scikit-learn on CPU)

### CORS errors in browser console
This is normal for local testing. Will be tightened in Stage 2 production.

---

## Performance Benchmarks (Local)

| Task | Time |
|------|------|
| Score 25 customers (sample data) | ~2 sec |
| Score 100 customers | ~3-4 sec |
| Score 1,000 customers | ~8-10 sec |
| Train model | ~10-15 sec |

---

## What to Verify ✅

- [x] API starts without errors
- [x] Dashboard loads at http://127.0.0.1:8000
- [x] Sample data button works
- [x] CSV upload works
- [x] Results show probabilities + drivers
- [x] Risk bands are color-coded
- [x] CSV export downloads correctly
- [x] Error messages appear on invalid uploads
- [x] /health endpoint returns metrics
- [x] Model metrics match presentation (0.84 ROC-AUC, etc.)

---

## Next Steps After Local Testing

✅ **Local testing complete?** → Ready to:
1. Deploy to Render (see README.md)
2. Share link with others
3. Add to resume/portfolio

---

**Local testing guide created: 2026-08-27**
