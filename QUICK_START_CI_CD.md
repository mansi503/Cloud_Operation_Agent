# 🚀 GitHub Workflows & Docker Setup - Quick Reference

## What's Included ✅

This complete CI/CD setup includes:

```
✅ Automated Testing       (Python 3.10, 3.11)
✅ Code Quality Checks     (Linting, Type Checking)
✅ Security Scanning       (Bandit, Trivy)
✅ Docker Image Build      (Multi-stage optimized)
✅ Docker Registry Push    (GHCR + Docker Hub)
✅ Multi-Platform Deploy   (GCP, AWS, Heroku)
✅ Slack Notifications     (Deployment status)
✅ Local Development       (docker-compose)
```

---

## 📂 Files Created

### GitHub Actions Workflows (`.github/workflows/`)

| File | Purpose | Triggers |
|------|---------|----------|
| `test.yml` | Run tests, linting, security checks | Every push, PR |
| `docker-build.yml` | Build and push Docker image | Push to main, tags |
| `deploy-gcp.yml` | Deploy to Google Cloud Run | Push to main, manual |
| `deploy-aws.yml` | Deploy to AWS ECS | Push to main, manual |
| `deploy-heroku.yml` | Deploy to Heroku | Push to main, manual |

### Docker Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build for Streamlit app |
| `Dockerfile.exporter` | Lightweight GCP mock exporter |
| `docker-compose.yml` | Local dev with Prometheus, Grafana, etc |
| `.dockerignore` | Optimized Docker builds |

### Configuration

| File | Purpose |
|------|---------|
| `.env.example` | Environment variables template |
| `CI_CD_SETUP.md` | Complete setup guide (start here!) |
| `DEPLOYMENT.md` | Platform-specific deployment guides |
| `GITHUB_ACTIONS_GUIDE.md` | GitHub Actions reference |

---

## 🎯 Getting Started (4 Steps)

### Step 1: Push to GitHub

```bash
cd C:\Users\mansi\COA
git remote add origin https://github.com/YOUR_ORG/COA.git
git push -u origin main
```

### Step 2: Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions**

Add these **minimum required secrets:**

```
GROQ_API_KEY              = your-groq-api-key
GOOGLE_SHEETS_ID          = your-sheet-id
MCP_GRAFANA_TOKEN         = your-grafana-token
```

### Step 3: Choose Deployment Platform

**Option A: Google Cloud Run** (if you use GCP)
```bash
# Follow instructions in DEPLOYMENT.md (GCP Section)
# Add secrets: GCP_PROJECT_ID, GCP_SA_KEY
```

**Option B: AWS ECS** (if you use AWS)
```bash
# Follow instructions in DEPLOYMENT.md (AWS Section)
# Add secrets: AWS_ROLE_TO_ASSUME
```

**Option C: Heroku** (simplest for getting started)
```bash
# Follow instructions in DEPLOYMENT.md (Heroku Section)
# Add secrets: HEROKU_API_KEY
```

### Step 4: Trigger Workflows

```bash
# Just push code - workflows run automatically!
git commit -m "Deploy application"
git push origin main

# Monitor in GitHub Actions tab
# https://github.com/YOUR_ORG/COA/actions
```

---

## 🔄 Workflow Execution Timeline

```
Your Push
    ↓
✅ TEST WORKFLOW (2-3 min)
   ├─ Install dependencies
   ├─ Run linting
   ├─ Run type checks
   ├─ Run tests with coverage
   ├─ Run security scans
   └─ Result: ✅ PASS or ❌ FAIL
    ↓ (if PASS)
✅ DOCKER BUILD (3-5 min)
   ├─ Build Docker image
   ├─ Push to registry
   ├─ Scan for vulnerabilities
   └─ Result: ✅ Image pushed
    ↓ (if main branch)
✅ DEPLOYMENT (5-10 min)
   ├─ Pull Docker image
   ├─ Deploy to cloud platform
   ├─ Run health checks
   ├─ Send Slack notification
   └─ Result: ✅ LIVE or ❌ FAILED
```

---

## 🐳 Docker Compose for Local Testing

### Quick Start
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your actual values
# Then start all services

docker-compose up -d
```

### Access Services
```
Streamlit UI:   http://localhost:8501
Prometheus:     http://localhost:9090
Grafana:        http://localhost:3000
GCP Exporter:   http://localhost:8000/metrics
```

### View Logs
```bash
# Streamlit logs
docker-compose logs -f streamlit

# All logs
docker-compose logs -f

# Specific service
docker-compose logs -f prometheus
```

### Stop Everything
```bash
docker-compose down
```

---

## 🔐 GitHub Secrets Setup

### Minimum Required (3 Secrets)
```
1. GROQ_API_KEY              ← from Groq console
2. GOOGLE_SHEETS_ID          ← from Google Sheets URL
3. MCP_GRAFANA_TOKEN         ← from Grafana settings
```

### For GCP Deployment (2 Additional)
```
1. GCP_PROJECT_ID            ← from GCP console
2. GCP_SA_KEY                ← downloaded JSON key
```

### For AWS Deployment (1 Additional)
```
1. AWS_ROLE_TO_ASSUME        ← IAM role ARN
```

### For Heroku Deployment (1 Additional)
```
1. HEROKU_API_KEY            ← from Heroku account settings
```

### Optional (For Notifications)
```
1. SLACK_WEBHOOK             ← from Slack app
```

---

## 📊 Workflow Matrix

```
Branch          Action                Status
─────────────────────────────────────────────
main            Push → Tests → Build → Deploy ✅
develop         Push → Tests → Build         ✅
feature/*       Push → Tests                 ✅
PR to main      Tests                        ✅ (required)
Tag (v1.0.0)    Tests → Build                ✅
```

---

## 🛠️ Customization Examples

### Change Docker Registry

**Current:** GHCR (GitHub Container Registry)
**To Docker Hub:**
```yaml
# In docker-build.yml, line 18:
REGISTRY: docker.io
```

### Change Python Versions

**Current:** 3.10, 3.11
**To add 3.12:**
```yaml
# In test.yml, line 13:
python-version: ['3.10', '3.11', '3.12']
```

### Change GCP Region

**Current:** us-central1
**To Europe:**
```yaml
# In deploy-gcp.yml, line 24:
GCP_REGION: europe-west1
```

---

## 📈 Monitoring Workflows

### View Real-time Status
1. Go to your GitHub repo
2. Click **Actions** tab
3. See all workflow runs
4. Click to expand and view logs

### Color Codes
- 🟢 Green = Success ✅
- 🔴 Red = Failed ❌
- 🟡 Yellow = In Progress ⏳
- ⚪ Gray = Skipped ⊘

### Check Specific Job
```bash
# Click workflow run
# Click job name (e.g., "test")
# Expand step to see logs
```

---

## 🆘 Troubleshooting

### "Tests Failed"
```bash
# Run locally to debug
python -m pytest tests/ -v --tb=short
```

### "Docker Build Failed"
```bash
# Build locally
docker build -t test . --no-cache

# Check Dockerfile
docker build --no-cache -f Dockerfile .
```

### "Deployment Timeout"
1. Check cloud platform logs
2. Verify credentials/secrets
3. Check health check configuration

### "Permission Denied"
1. Verify service account permissions
2. Check IAM roles
3. Confirm secrets are set correctly

---

## 📚 Complete Documentation

| Document | Purpose |
|----------|---------|
| **CI_CD_SETUP.md** | Start here - complete setup guide |
| **DEPLOYMENT.md** | Detailed platform-specific instructions |
| **GITHUB_ACTIONS_GUIDE.md** | GitHub Actions reference & best practices |
| **docker-compose.yml** | Local development setup |

---

## ✅ Pre-Launch Checklist

- [ ] Code pushed to GitHub
- [ ] GitHub Secrets added (minimum 3)
- [ ] Deployment platform chosen
- [ ] Platform-specific setup completed
- [ ] Workflows triggered
- [ ] Monitoring Actions tab
- [ ] Slack webhook configured (optional)

---

## 🎓 Learning Resources

### GitHub Actions
- 📖 Official Docs: https://docs.github.com/en/actions
- 📚 Tutorial: https://docs.github.com/en/actions/quickstart

### Docker
- 📖 Official Docs: https://docs.docker.com
- 🐳 Docker Hub: https://hub.docker.com
- 📚 Best Practices: https://docs.docker.com/develop/dev-best-practices

### Deployment Platforms
- **GCP**: https://cloud.google.com/run/docs
- **AWS**: https://docs.aws.amazon.com/ecs
- **Heroku**: https://devcenter.heroku.com

---

## 🚀 Next Steps

1. **Read CI_CD_SETUP.md** for detailed walkthrough
2. **Push code to GitHub** to trigger test workflow
3. **Add GitHub Secrets** following the platform guide
4. **Monitor in Actions tab** to see workflows run
5. **Deploy to your cloud platform** of choice
6. **Celebrate success! 🎉**

---

**Need help?** Check the detailed guides or refer to DEPLOYMENT.md for your chosen platform.
