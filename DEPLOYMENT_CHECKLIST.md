# ✅ Deployment Checklist - Step by Step

## Phase 1: Setup Render PostgreSQL (5 minutes)

- [ ] Go to https://render.com
- [ ] Sign in / Create account
- [ ] Click **New** → **PostgreSQL**
- [ ] Name it: `churn-db`
- [ ] Region: Choose closest to you
- [ ] Click **Create Database**
- [ ] Wait for database to initialize (~1 min)
- [ ] Copy **External Database URL** (save to notepad)
  - Looks like: `postgresql://churn_user:xxx@dpg-xyz.render.internal:5432/churn_db`

---

## Phase 2: Push Code to GitHub (3 minutes)

```bash
cd "C:\Users\Dell\Desktop\churn-dashboard"

# Initialize git if needed
git init
git add .
git commit -m "Add PostgreSQL support and analytics dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/churn-dashboard.git
git push -u origin main
```

✅ Code is now on GitHub

---

## Phase 3: Deploy to Render (5 minutes)

### Step 1: Create Web Service
- [ ] Go to Render Dashboard
- [ ] Click **New** → **Web Service**
- [ ] Select your GitHub repo (`churn-dashboard`)
- [ ] Click **Connect**

### Step 2: Configure Service
- [ ] **Name:** `churn-triage`
- [ ] **Region:** Same as PostgreSQL database ⚠️ IMPORTANT
- [ ] **Branch:** `main`
- [ ] **Runtime:** Python 3

### Step 3: Build & Start Commands
Copy exactly:

**Build Command:**
```bash
pip install -r requirements.txt && python train_model.py
```

**Start Command:**
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Step 4: Add Environment Variable
- [ ] Scroll to **Environment**
- [ ] Click **Add Environment Variable**
  - **Key:** `DATABASE_URL`
  - **Value:** (Paste from Phase 1 - your PostgreSQL URL)
- [ ] Click **Create**

### Step 5: Deploy
- [ ] Click **Create Web Service**
- [ ] Wait 2-3 minutes for deployment
- [ ] Check logs for success message

---

## Phase 4: Verify Deployment (5 minutes)

### Check Service Status
- [ ] Render dashboard shows **Live** (green)
- [ ] URL shows: `https://churn-triage.render.com`

### Test the App
- [ ] Open https://churn-triage.render.com
- [ ] Click **Score sample data**
- [ ] Wait for results
- [ ] Click **Analytics** tab
- [ ] See 4 charts load
- [ ] Click **Retention Tracker**
- [ ] Submit a test feedback

### Check API Health
- [ ] Open https://churn-triage.render.com/health
- [ ] Should return JSON with `"status": "ok"`

### Verify Database
- [ ] Open https://churn-triage.render.com/analytics
- [ ] Should return JSON with chart data
- [ ] Scroll down to see "chart_data" arrays

---

## Phase 5: Test Data Persistence (2 minutes)

### ✅ Data Survives Server Restart
1. Score 100 customers (upload CSV)
2. Go to Analytics → note the "Total Scored" number
3. Refresh page (Ctrl+R)
4. Check Analytics again → same number? ✅ Works!

### ✅ Data Survives Redeploy
1. Make a small code change (add comment in main.py)
2. Push to GitHub: `git add . && git commit -m "test" && git push`
3. Render auto-redeploys
4. Refresh your app
5. Check Analytics → still have same data? ✅ Works!

---

## 🎉 Success! You're Live

Your production app is now at:
```
https://churn-triage.render.com
```

### What you have:
✅ Model scoring (FastAPI)  
✅ Analytics dashboard (charts)  
✅ Retention tracker (feedback form)  
✅ PostgreSQL database (persistent data)  
✅ Auto-scaling (Render handles it)  
✅ SSL/HTTPS (automatic)  

---

## 📊 Post-Deployment

### Monitor Your App
- Render Dashboard → Logs
- Watch real-time requests
- Check for errors

### Share Your URL
- Copy: https://churn-triage.render.com
- Share with team/stakeholders
- Add to resume/portfolio

### Next Improvements
- [ ] Add authentication (users/teams)
- [ ] Connect to Salesforce/HubSpot CRM
- [ ] Set up automated retraining
- [ ] Add email alerts for high-risk customers

---

## ❓ Troubleshooting

### "502 Bad Gateway"
- Check Render logs
- Usually means build still running (wait 2-3 min)
- Or DATABASE_URL is wrong

### "No data in Analytics"
- Score some customers first
- Refresh page
- Check logs for errors

### "Database connection refused"
- Verify DATABASE_URL is correct
- Check PostgreSQL database is running (Render dashboard)
- Wait 30 sec for connection to establish

---

## 📝 Important Notes

⚠️ **Database URL Security:**
- DATABASE_URL is set in Render (not in code)
- Never commit credentials to GitHub
- .env file (local) is ignored by git

⚠️ **Data Backups:**
- Render PostgreSQL auto-backs up
- Manually export with: `pg_dump`
- Restore with: `psql`

⚠️ **Free Tier Limits:**
- PostgreSQL: 256 MB storage, 90 days retention
- Web Service: 0.5 GB RAM, sleeps after 15 min
- Upgrade when you need more (starts at $15/month)

---

## ✅ Final Checklist

Before you call it done:

- [ ] App deployed and live
- [ ] Can score customers
- [ ] Analytics tab shows charts
- [ ] Retention tracker records data
- [ ] Data persists after refresh
- [ ] Data persists after deploy
- [ ] /health endpoint returns 200 OK
- [ ] /analytics endpoint returns JSON
- [ ] No errors in Render logs
- [ ] URL added to resume

---

## 🚀 Congratulations!

You now have a **production-ready ML dashboard** with:
- Real-time customer churn scoring
- Persistent analytics database
- Interactive visualizations
- Retention feedback tracking
- Auto-scaling infrastructure

**Live at:** https://churn-triage.render.com ✅

---

**Time to complete:** 20-30 minutes  
**Status:** Production Ready  
**Last updated:** 2026-08-27
