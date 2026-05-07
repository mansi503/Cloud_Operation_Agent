# GitHub Actions Quick Reference

## What are GitHub Actions?

GitHub Actions are automated workflows that run in response to repository events (push, PR, release, manual trigger). They help with:

- **Automated Testing** - Run tests on every push
- **Code Quality** - Lint and format checks
- **Security Scanning** - Vulnerability detection
- **Automated Deployment** - Deploy to cloud platforms
- **Notifications** - Slack, email, etc.

---

## Workflow Files in This Project

### 1. `.github/workflows/test.yml`
**When it runs:** On every push and pull request

**What it does:**
- Tests on Python 3.10 and 3.11
- Runs linting (ruff)
- Type checking (mypy)
- Pytest with coverage
- Security checks (Bandit, Trivy)

**Status:** Required to pass before merging to main

---

### 2. `.github/workflows/docker-build.yml`
**When it runs:** On push to main/develop or when tags are pushed

**What it does:**
- Builds Docker image
- Pushes to GitHub Container Registry (ghcr.io)
- Optionally pushes to Docker Hub
- Scans image for vulnerabilities

**Docker Image Tags:**
- `main` branch → `latest` tag
- `develop` branch → branch name tag
- Git tag `v1.0.0` → version tags

---

### 3. `.github/workflows/deploy-gcp.yml`
**When it runs:** On push to main or manual trigger

**What it does:**
- Builds Docker image
- Pushes to Google Container Registry
- Deploys to Google Cloud Run
- Sends Slack notification

**Requirements:**
- GCP Service Account
- GitHub Secrets: `GCP_PROJECT_ID`, `GCP_SA_KEY`

---

### 4. `.github/workflows/deploy-aws.yml`
**When it runs:** On push to main or manual trigger

**What it does:**
- Builds Docker image
- Pushes to Amazon ECR
- Deploys to ECS Fargate
- Updates task definition

**Requirements:**
- AWS IAM Role
- GitHub Secrets: `AWS_ROLE_TO_ASSUME`

---

### 5. `.github/workflows/deploy-heroku.yml`
**When it runs:** On push to main or manual trigger

**What it does:**
- Builds Docker image
- Pushes to Heroku Registry
- Releases to Heroku
- Runs smoke tests

**Requirements:**
- GitHub Secrets: `HEROKU_API_KEY`

---

## Setting Up GitHub Secrets

### Step 1: Go to Repository Settings
1. Click **Settings** tab
2. Click **Secrets and variables** → **Actions**

### Step 2: Click "New repository secret"
1. Enter **Name** (e.g., `GCP_PROJECT_ID`)
2. Enter **Value** (e.g., your project ID)
3. Click **Add secret**

### Secrets Checklist

**For Docker:**
- [ ] `DOCKERHUB_USERNAME` (optional)
- [ ] `DOCKERHUB_TOKEN` (optional)

**For GCP:**
- [ ] `GCP_PROJECT_ID`
- [ ] `GCP_SA_KEY` (JSON file contents)

**For AWS:**
- [ ] `AWS_ROLE_TO_ASSUME` (IAM role ARN)

**For Heroku:**
- [ ] `HEROKU_API_KEY`

**For Environment Vars:**
- [ ] `GROQ_API_KEY`
- [ ] `GOOGLE_SHEETS_ID`
- [ ] `MCP_GRAFANA_TOKEN`
- [ ] `SLACK_WEBHOOK` (optional)

---

## Understanding Workflow Files

### Basic Structure

```yaml
name: Workflow Name

on:
  push:                    # Trigger on push
    branches: [ main ]
  pull_request:            # Trigger on PR
    branches: [ main ]
  workflow_dispatch:       # Manual trigger

jobs:
  my-job:                  # Job name
    runs-on: ubuntu-latest # Machine type
    steps:
      - uses: actions/checkout@v4  # Use existing action
        
      - run: echo "Hello"          # Run command
```

### Key Concepts

- **Trigger:** When the workflow runs (push, PR, manual, schedule)
- **Job:** A collection of steps
- **Step:** Individual task (checkout code, run tests, etc.)
- **Action:** Reusable code blocks (like actions/checkout)

---

## Common Workflow Patterns

### Pattern 1: Run Tests

```yaml
- name: Run tests
  run: pytest tests/ -v --cov=src
```

### Pattern 2: Build Docker Image

```yaml
- name: Build Docker image
  run: docker build -t myapp:latest .

- name: Push to registry
  run: docker push myapp:latest
```

### Pattern 3: Deploy with Environment Variables

```yaml
- name: Deploy
  run: deploy_command
  env:
    API_KEY: ${{ secrets.API_KEY }}
    DEBUG: true
```

### Pattern 4: Conditional Steps

```yaml
- name: Notify on success
  if: success()
  run: echo "Success!"

- name: Notify on failure
  if: failure()
  run: echo "Failed!"
```

---

## Monitoring Workflows

### View Workflow Status

1. Click **Actions** tab in your repository
2. See list of recent workflow runs
3. Click a workflow to see details
4. Click a job to see step-by-step output

### Color Codes
- ✅ **Green** = Success
- ❌ **Red** = Failed
- ⏳ **Yellow** = In progress
- ⊘ **Skipped** = Conditionally skipped

### Real-time Logs

Click any step to expand and see full logs:
```
Run: npm install
npm notice create a new lockfile
npm notice up to date in 0.254s
```

---

## Debugging Workflows

### 1. Check Step Logs
- Expand red ❌ steps to see errors
- Look for error messages at bottom

### 2. Common Issues

**"Command not found"**
- Install dependencies first
- Check working directory

**"Permission denied"**
- Check secrets are set
- Verify service account permissions

**"Timeout"**
- Increase timeout value
- Check if service is responding

### 3. Enable Debug Logging

Create GitHub secret:
```
Name: ACTIONS_STEP_DEBUG
Value: true
```

Re-run workflow for verbose output.

---

## Best Practices

✅ **Do:**
- Keep workflows simple and focused
- Use existing GitHub Actions when possible
- Test workflows locally with act
- Document secrets needed
- Use environments for staging/production
- Set reasonable timeouts

❌ **Don't:**
- Hardcode secrets in workflow files
- Run long-running tasks in workflows
- Make workflows too complex
- Forget to update documentation
- Ignore workflow failures

---

## Useful Commands

### Test Locally (using act)

```bash
# Install act
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run specific workflow
act -j test

# Run with secrets
act -s GROQ_API_KEY=test-key
```

---

## Next Steps

1. ✅ Review each workflow file
2. ✅ Add required GitHub Secrets
3. ✅ Choose deployment platform (GCP/AWS/Heroku)
4. ✅ Follow platform-specific setup
5. ✅ Push code and monitor workflow
6. ✅ Check Actions tab for results

For more info, visit: https://docs.github.com/en/actions
