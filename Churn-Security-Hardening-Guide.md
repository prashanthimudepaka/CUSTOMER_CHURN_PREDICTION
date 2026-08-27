# Churn Triage Security Hardening — Complete Implementation Guide

## PART 1: THREAT MODEL (What We're Protecting Against)

### Current State (Unsecured)
Churn Triage as built in Week 1-2 is:
- Fully open (no login, anyone can use it)
- Stateless (no data persistence across sessions)
- Unmetered (unlimited free API calls)
- Unaudited (no logging of who did what)

### Threats We're Defending Against

| Threat | Risk | Impact | Likelihood |
|--------|------|--------|------------|
| **DOS Attack** | Attacker sends 10k searches in 1 minute | Server crashes, service down | HIGH |
| **Data Exposure** | Attacker's CSV data visible to next user (temp file not cleaned) | PII leak (customer names, emails) | MEDIUM |
| **Model Theft** | Attacker downloads model.pkl file | Competitor gets our trained model | LOW (if hosted right) |
| **Injection Attacks** | Malicious CSV with formula bombs or code | Model crashes, server vulnerable | MEDIUM |
| **Unauthorized API Access** | Scripts scrape the API for free without using UI | Cost spike (Claude API charges add up) | HIGH |
| **Credential Leaks** | API keys hardcoded in git, exposed in error messages | Attackers use our Claude quota, bill us | HIGH |
| **Invalid File Upload** | Attacker uploads 1GB zip file | Disk fills, service down | MEDIUM |
| **SQL Injection (if DB added)** | Attacker passes `'; DROP TABLE users; --` as search query | Database corruption | CRITICAL |

---

## PART 2: SECURITY SOLUTIONS BY LAYER

### Layer 1: Input Validation & Sanitization

**Threat Addressed:** Injection attacks, DOS via oversized uploads

**Technology: Python validators + FastAPI built-ins**

```python
# In main.py

from fastapi import FastAPI, UploadFile, File, HTTPException
import os

# 1. File size limit
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {'.csv', '.pdf', '.txt', '.docx'}
MAX_UPLOAD_PER_DAY = 100  # per user

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    # 1. Check file size before reading
    file_size = 0
    chunk_size = 1024  # 1KB chunks
    temp_file = f"/tmp/{uuid.uuid4()}.tmp"
    
    with open(temp_file, 'wb') as f:
        while chunk := await file.read(chunk_size):
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Max {MAX_FILE_SIZE / 1024 / 1024:.1f}MB"
                )
            f.write(chunk)
    
    # 2. Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # 3. Parse and validate data
    try:
        df = pd.read_csv(temp_file)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="Could not parse CSV. Ensure it's valid UTF-8, no binary data."
        )
    
    # 4. Check for required columns (prevents silent failures)
    missing = missing_columns(df)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing columns: {', '.join(missing)}"
        )
    
    # 5. Sanitize: remove any special characters that could be formula bombs
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].str.replace(r'^[=+@-]', '', regex=True)
    
    # 6. Clean up temp file
    os.remove(temp_file)
    
    return score_dataframe(df)
```

**Why This:**
- FastAPI's `UploadFile` handles multipart uploads safely
- Chunked reading prevents loading entire 1GB file into RAM
- File extension whitelist (not just checking MIME type, which is spoofable)
- Sanitize formulas (Excel injection: `=cmd|'/c powershell'!A1`)
- Immediate cleanup (no leftover files on disk)

**Interview Angle:**
*"I implemented chunked file reading to prevent memory exhaustion attacks. I sanitize data against formula injection (Excel bombs). I validate file types against a whitelist, not MIME headers (which are user-controlled)."*

---

### Layer 2: Rate Limiting & Quota Management

**Threat Addressed:** DOS, unauthorized API scraping, cost control

**Technology: Redis + Slowapi (or in-memory dict for MVP)**

**MVP Option (No Redis):**
```python
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

# In-memory rate limit store (works for single-instance Render free tier)
RATE_LIMITS = defaultdict(lambda: {'count': 0, 'reset_at': None})
REQUESTS_PER_HOUR = 10  # Free tier
REQUESTS_PER_DAY = 50

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    # Get client IP (or user_id if authenticated later)
    client_ip = request.client.host
    now = datetime.utcnow()
    
    # Check hourly limit
    limit_key = f"{client_ip}:hourly"
    if limit_key not in RATE_LIMITS:
        RATE_LIMITS[limit_key] = {'count': 0, 'reset_at': now + timedelta(hours=1)}
    
    if RATE_LIMITS[limit_key]['reset_at'] < now:
        # Reset hour
        RATE_LIMITS[limit_key] = {'count': 0, 'reset_at': now + timedelta(hours=1)}
    
    if RATE_LIMITS[limit_key]['count'] >= REQUESTS_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {REQUESTS_PER_HOUR} requests per hour. Try again in {RATE_LIMITS[limit_key]['reset_at']}"
        )
    
    RATE_LIMITS[limit_key]['count'] += 1
    
    # ... rest of predict logic
```

**Production Option (With Redis):**
```python
import redis
from slowapi import Limiter
from slowapi.util import get_remote_address

redis_client = redis.Redis(
    host=os.getenv("REDIS_URL", "localhost"),
    decode_responses=True
)

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("REDIS_URL")
)

@app.post("/predict")
@limiter.limit("10/hour")  # 10 requests per hour per IP
async def predict(file: UploadFile = File(...), request: Request):
    # Slowapi handles the rate limiting
    return score_dataframe(df)
```

**Why This:**
- MVP: No external dependency, works on free Render
- Production: Redis is stateless, works across multiple instances
- Slides are standard: 429 Too Many Requests (HTTP standard)
- Client gets reset time (so they know when they can retry)

**Interview Angle:**
*"I implemented rate limiting at the API level to prevent DOS and unmetered API calls. The MVP uses in-memory tracking (sufficient for a single-instance Render free tier), but I designed it to swap to Redis for multi-instance deployments without code changes."*

---

### Layer 3: Secrets Management

**Threat Addressed:** API key leaks, credential exposure in git

**Technology: Environment variables + Render Secrets**

**Current (WRONG):**
```python
# ❌ DON'T DO THIS
CLAUDE_API_KEY = "sk-ant-..."  # Hardcoded in main.py
```

**Secure (RIGHT):**
```python
# ✅ DO THIS
import os
from dotenv import load_dotenv

load_dotenv()  # Load from .env locally
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not CLAUDE_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

client = Anthropic(api_key=CLAUDE_API_KEY)
```

**Setup Steps:**

1. **Local Development (.env file):**
```
# .env (add to .gitignore)
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://user:pass@localhost/churn
REDIS_URL=redis://localhost:6379
```

2. **Production (Render Secrets Dashboard):**
   - Go to Render Service → Environment
   - Click "Add Secret"
   - Enter: `ANTHROPIC_API_KEY` = your actual key
   - Render injects it at runtime (never stored in git)

3. **In .gitignore:**
```
.env
.env.local
*.pkl
model/
__pycache__/
```

**GitHub Actions (CI/CD with secrets):**
```yaml
# .github/workflows/deploy.yml
name: Deploy to Render
on: [push]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy
        run: |
          curl https://api.render.com/deploy/srv-${{ secrets.RENDER_SERVICE_ID }}?key=${{ secrets.RENDER_API_KEY }}
```

**Why This:**
- `.env` never in git (checked by `.gitignore`)
- Secrets stored in Render (encrypted at rest)
- No one can read your keys from GitHub
- Easy rotation (change secret, redeploy)

**Interview Angle:**
*"I use environment variables for all secrets. Locally, I load from .env (which is gitignored). In production, Render injects secrets at runtime, so they never touch the filesystem or git history. API keys are never hardcoded."*

---

### Layer 4: HTTPS & Secure Transport

**Threat Addressed:** Man-in-the-middle attacks, credential sniffing

**Technology: Render auto-TLS + CORS**

**Automatic (Render handles):**
- Render auto-provisions Let's Encrypt SSL certificate
- All traffic is HTTPS-only
- Redirects http:// → https://

**Manual Configuration (FastAPI):**
```python
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Force HTTPS redirect
app.add_middleware(HTTPSRedirectMiddleware)

# CORS: Only your frontend can call your API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",  # Production
        "http://localhost:3000",    # Local dev only
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

**Why This:**
- HTTPS = encrypted transport (prevents packet sniffing)
- CORS = only your frontend can call your API (prevents cross-site requests)
- Tight whitelist (not `allow_origins=["*"]`, which is insecure)

**Interview Angle:**
*"I enforced HTTPS-only communication. I configured CORS to only allow requests from my own domain, preventing cross-site request attacks. Render auto-manages TLS certificates, so there's no manual renewal burden."*

---

### Layer 5: Authentication & User Isolation

**Threat Addressed:** Data leakage between users, unauthorized access

**Technology: Supabase Auth (easiest MVP) or Auth0**

**MVP Setup (Supabase Email + Password):**

```python
# pip install supabase

from supabase import create_client, Client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.post("/auth/signup")
async def signup(email: str, password: str):
    """Register a new user."""
    response = supabase.auth.sign_up({
        "email": email,
        "password": password,
    })
    return {"user_id": response.user.id}

@app.post("/auth/login")
async def login(email: str, password: str):
    """Login and get a session token."""
    response = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password,
    })
    return {"access_token": response.session.access_token}

@app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    authorization: str = Header(None)
):
    """Require a valid JWT token from Supabase."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing auth token")
    
    # Verify token with Supabase
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Store/fetch data isolated by user_id
    df = clean_dataframe(pd.read_csv(file.file))
    
    # Save search to DB with user_id
    supabase.table("searches").insert({
        "user_id": user_id,
        "query": df.to_json(),
        "results": score_dataframe(df),
        "timestamp": datetime.utcnow().isoformat(),
    })
    
    return score_dataframe(df)
```

**Frontend (HTML login page):**
```html
<form id="loginForm">
  <input type="email" id="email" required>
  <input type="password" id="password" required>
  <button type="submit">Login</button>
</form>

<script>
const supabase = supabaseClient;

document.getElementById('loginForm').onsubmit = async (e) => {
  e.preventDefault();
  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;
  
  const { data, error } = await supabase.auth.signInWithPassword({
    email, password
  });
  
  if (error) {
    alert(error.message);
  } else {
    localStorage.setItem('token', data.session.access_token);
    window.location.href = '/app';  // Redirect to main app
  }
};

// Subsequent API calls include token
const predict = async (file) => {
  const token = localStorage.getItem('token');
  const response = await fetch('/predict', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: file
  });
  return response.json();
};
</script>
```

**Why This:**
- Supabase is free for MVP (up to 50k users)
- Handles password hashing, token generation, storage
- No passwords in your code
- Users are isolated (can only see their own data)
- JWT tokens are stateless (don't need a session database)

**Interview Angle:**
*"I implemented multi-tenant isolation using Supabase Auth. Users log in with email/password. Every API call requires a valid JWT token. The database enforces row-level security (User A's searches are only visible to User A). This prevents data leakage and scales to multiple concurrent users."*

---

### Layer 6: Logging & Audit Trail

**Threat Addressed:** Inability to detect abuse, forensic investigation**

**Technology: Python logging + Sentry (optional, free tier)**

**Basic Logging:**
```python
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/churn.log'),  # Save to file
        logging.StreamHandler()  # Also print to console
    ]
)
logger = logging.getLogger(__name__)

@app.post("/predict")
async def predict(file: UploadFile = File(...), user_id: str = Header(None)):
    """Log every prediction request."""
    logger.info(f"[PREDICT] user={user_id} file={file.filename} size={file.size}")
    
    try:
        df = clean_dataframe(pd.read_csv(file.file))
        result = score_dataframe(df)
        
        logger.info(f"[PREDICT_SUCCESS] user={user_id} rows={len(df)} matches={len(result['rows'])}")
        return result
    
    except Exception as e:
        logger.error(f"[PREDICT_ERROR] user={user_id} error={str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
```

**Production Logging (Sentry):**
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1  # 10% of requests (for perf monitoring)
)

@app.post("/predict")
async def predict(...):
    # Sentry auto-captures exceptions
    # Plus manual logging
    logger.info(f"[PREDICT] user={user_id}")
```

**Audit Table (in Database):**
```python
# Track sensitive operations
supabase.table("audit_log").insert({
    "user_id": user_id,
    "action": "uploaded_csv",
    "resource": file.filename,
    "ip_address": request.client.host,
    "timestamp": datetime.utcnow().isoformat(),
    "status": "success"
})
```

**Query audit log for security incidents:**
```sql
-- Who accessed User X's data?
SELECT * FROM audit_log 
WHERE resource_owner_id = 'user_X' 
  AND action = 'view' 
  AND user_id != 'user_X';

-- DOS attack detection
SELECT user_id, COUNT(*) as attempts 
FROM audit_log 
WHERE action = 'predict' 
  AND timestamp > NOW() - INTERVAL 1 HOUR
GROUP BY user_id 
HAVING COUNT(*) > 50;
```

**Why This:**
- Audit trail for compliance (who did what, when, why)
- Forensics (investigate after a breach)
- Sentry alerts you to errors in real-time
- Performance monitoring (find slow queries)

**Interview Angle:**
*"I implemented comprehensive audit logging. Every API call is logged with user ID, timestamp, and result. Errors are captured in Sentry with full stack traces. If there's a security incident, I can query the audit log to see exactly what happened and who was affected."*

---

### Layer 7: SQL Injection Prevention

**Threat Addressed:** Database corruption, unauthorized data access**

**Technology: SQLAlchemy ORM (parameterized queries)**

**WRONG (Vulnerable):**
```python
# ❌ DON'T DO THIS
user_id = request.query_params.get("user_id")
query = f"SELECT * FROM searches WHERE user_id = '{user_id}'"
results = db.execute(query)  # SQL INJECTION!
# Attacker passes: user_id = "' OR '1'='1"
# Query becomes: SELECT * FROM searches WHERE user_id = '' OR '1'='1'
# Returns ALL searches (including other users'!)
```

**CORRECT (Safe):**
```python
# ✅ DO THIS
from sqlalchemy import select
from models import Search

user_id = request.query_params.get("user_id")

# Parameterized query (SQLAlchemy handles escaping)
stmt = select(Search).where(Search.user_id == user_id)
results = db.execute(stmt).scalars().all()

# Even if user_id = "' OR '1'='1'", SQLAlchemy escapes it
# Query becomes: SELECT * FROM searches WHERE user_id = '\' OR \'1\'=\'1'
# Treated as literal string, not SQL code
```

**Why This:**
- SQLAlchemy ORM automatically parameterizes queries
- Database driver escapes special characters
- Impossible to inject SQL through user input
- Works across all databases (PostgreSQL, MySQL, SQLite)

**Interview Angle:**
*"I use SQLAlchemy ORM for all database queries. It parameterizes everything automatically, making SQL injection impossible. I never concatenate user input into query strings."*

---

## PART 3: IMPLEMENTATION ROADMAP (By Week)

### Week 1: Add Input Validation + Rate Limiting
**Files to modify:** `main.py`
**Time:** 2-3 hours
**Deliverable:** 
- ✅ File size limits
- ✅ Extension whitelist
- ✅ Rate limiting (in-memory, 10 req/hr)
- ✅ Formula injection prevention

### Week 2: Add Secrets Management + HTTPS
**Files to modify:** `.env`, `.gitignore`, `main.py`
**Time:** 1-2 hours
**Deliverable:**
- ✅ Move all keys to environment variables
- ✅ CORS policy configured
- ✅ Verify HTTPS on Render (automatic)
- ✅ `.env` never committed to git

### Week 3: Add Authentication (Supabase)
**Files to modify:** `main.py`, `index.html`, database schema
**Time:** 4-6 hours
**Deliverable:**
- ✅ Supabase signup/login form
- ✅ JWT token validation on every API call
- ✅ User isolation in database
- ✅ Protected routes (require login)

### Week 4: Add Logging + Audit Trail
**Files to modify:** `main.py`, database schema
**Time:** 2-3 hours
**Deliverable:**
- ✅ Audit log table
- ✅ Every action logged (predict, upload, login)
- ✅ Sentry integration (error tracking)
- ✅ Query audit log for forensics

---

## PART 4: TECHNOLOGIES COMPARISON

| Security Layer | MVP Option | Enterprise Option | Cost | Effort |
|---|---|---|---|---|
| **Input Validation** | FastAPI built-ins | Same | Free | 2 hrs |
| **Rate Limiting** | Dict + datetime | Redis | Free/5mo | 1 hr MVP, 3 hrs Redis |
| **Secrets** | .env file | Render Secrets | Free | 30 min |
| **HTTPS** | Render auto-TLS | Same | Free | 0 (automatic) |
| **Auth** | Supabase (free tier) | Auth0 / Okta | Free/$100/mo | 4-6 hrs Supabase, 8+ hrs Auth0 |
| **Logging** | Python logging | Sentry + ELK | Free/20/mo | 2 hrs logging, 1 hr Sentry |
| **SQL Injection** | SQLAlchemy | Same | Free | 0 (already using) |

### Why These Choices:
- **MVP**: Free/cheap, easy to implement, 0 external dependencies beyond what you have
- **Enterprise**: More features (SSO, MFA, advanced analytics) but overkill for Week 4

---

## PART 5: DEPLOYMENT & VERIFICATION

### Before Deploying (Checklist)

```bash
# 1. Verify secrets aren't in code
grep -r "sk-ant-" . --exclude-dir=.git
grep -r "postgres://" . --exclude-dir=.git
# Should return: nothing

# 2. Verify .gitignore works
git status
# Should NOT show .env or __pycache__

# 3. Test rate limiting locally
for i in {1..15}; do curl http://localhost:8000/predict; done
# 15th request should get 429 (Too Many Requests)

# 4. Test auth required
curl -X POST http://localhost:8000/predict \
  -F "file=@sample.csv" \
  # Should get 401 (Unauthorized)

curl -X POST http://localhost:8000/predict \
  -F "file=@sample.csv" \
  -H "Authorization: Bearer $TOKEN" \
  # Should work if token is valid

# 5. Check HTTPS enforced
curl -v http://yourdomain.com
# Should redirect to https://
```

### Deploy to Render (With Secrets)

1. **Set environment variables in Render dashboard:**
   - `ANTHROPIC_API_KEY` = your key
   - `SUPABASE_URL` = your project URL
   - `SUPABASE_KEY` = your project key
   - `SENTRY_DSN` = your Sentry DSN

2. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Add security hardening"
   git push
   ```

3. **Render auto-deploys** (via GitHub integration)

4. **Verify live:**
   ```bash
   curl https://yourdomain.com/health
   # Should work without errors
   
   curl -X POST https://yourdomain.com/predict -F "file=@sample.csv"
   # Should return 401 (Unauthorized, needs token)
   ```

---

## PART 6: INTERVIEW STORY (How to Explain This)

### Short Version (2 min):
*"I hardened the Churn Triage API with security best practices. I added rate limiting to prevent DOS attacks, input validation to block malicious files, and authentication via Supabase so users can only see their own data. All secrets are in environment variables, never hardcoded. Every action is logged for audit purposes."*

### Medium Version (5 min):
*"I identified seven key security threats for this API: DOS, data leakage, injection attacks, credential exposure, and unauthorized access. For each, I implemented a targeted solution:*

1. *Rate limiting (in-memory dict, but architected to swap to Redis)*
2. *File validation: size limits, extension whitelisting, formula injection prevention*
3. *Secrets management: all API keys and DB credentials in environment variables, never in git*
4. *HTTPS enforcement and strict CORS policy*
5. *Authentication via Supabase (easy for MVP, scales to enterprise)*
6. *Audit logging: every action logged with user ID, timestamp, and status*
7. *SQLAlchemy ORM for automatic SQL injection prevention*

*The MVP is fully functional on free tiers (Supabase, Sentry, Render). If it grows, it scales to Redis for rate limiting and Auth0 for enterprise SSO without code changes."*

### Long Version (10 min, technical deep dive):
*[Tell the story above, then answer these likely questions]*

**Q: Why Supabase instead of Auth0?**
*"Auth0 is $1k/month minimum for enterprise features we don't need yet. Supabase is free for 50k users, includes JWT tokens, handles password hashing. If we need SSO later, we swap it out in one day without touching the API."*

**Q: What about rate limiting at the CDN level?**
*"Render doesn't offer that on the free tier. In-memory rate limiting is fine for a single instance. If we scale to multiple instances, I'd add Redis (stateless, shared across all instances) or move to a provider with built-in CDN rate limiting (Cloudflare Workers, AWS CloudFront)."*

**Q: How do you prevent brute-force login attacks?**
*"Good question. Supabase includes built-in protection: after 5 failed attempts, an account is temporarily locked. I'd add a second layer: log failed attempts to the audit table and alert via Sentry if someone tries >10 times from the same IP in 1 hour."*

**Q: What if someone gets a user's JWT token?**
*"Tokens expire after 1 hour (configurable in Supabase). Even if compromised, it's only valid for 1 hour. Long-term refresh tokens are stored in httpOnly cookies (never accessible to JavaScript), so XSS can't steal them. For high-risk ops (deleting data), I'd require re-authentication."*

---

## PART 7: SECURITY CHECKLIST FOR LAUNCH

Before deploying to production, verify every point:

### Code Security
- [ ] No hardcoded API keys (grep for credentials)
- [ ] `.env` in `.gitignore`
- [ ] All passwords hashed (Supabase handles this)
- [ ] SQL queries parameterized (SQLAlchemy)
- [ ] Error messages don't leak stack traces or DB schema

### API Security
- [ ] HTTPS enforced (redirect http → https)
- [ ] CORS policy restrictive (only your frontend)
- [ ] Rate limiting enabled (10 req/hour test)
- [ ] Auth required on `/predict` (401 without token)
- [ ] Input validation: file size, extension, formula injection

### Secrets & Credentials
- [ ] All secrets in environment variables (Render)
- [ ] Secrets not in git (verified with git log)
- [ ] API keys rotated (have a plan)
- [ ] Database password not shown in URLs (uses connection pooling)

### Data & Privacy
- [ ] User data isolated (User A can't see User B's uploads)
- [ ] Data deleted after 30 days (free tier policy)
- [ ] Audit log captures all sensitive actions
- [ ] GDPR compliance: users can request deletion

### Monitoring & Incident Response
- [ ] Logs written to file (for forensics)
- [ ] Sentry configured (error alerts)
- [ ] Rate limit alerts set (DOS detection)
- [ ] Runbook written (how to respond to a breach)

---

## CONCLUSION

You're taking a **4-week ML project and adding professional-grade security.** That's not something most freshers do. It transforms the resume story from:

❌ *"I built a churn model"* (everyone does)

✅ *"I built a secure, multi-tenant ML API with authentication, audit logging, rate limiting, and input validation. I handle secrets securely via environment variables. Users are isolated at the database level. All sensitive actions are logged for compliance."*

This is enterprise-level thinking. Interview gold.

---

**Next step:** Pick ONE security layer to implement this week (I recommend starting with Layer 1 + 2: Input Validation + Rate Limiting). Once it's working, commit and push. Then layer 3 the next week.

Which layer do you want to start with?
