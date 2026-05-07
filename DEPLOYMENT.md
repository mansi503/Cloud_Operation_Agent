# GitHub Actions & Deployment Setup Guide

This guide explains how to set up GitHub Actions for automated testing, Docker image building, and deployment.

## Overview

The project includes the following GitHub Actions workflows:

1. **test.yml** - Runs tests and security checks on every push/PR
2. **docker-build.yml** - Builds and pushes Docker image to GHCR
3. **deploy-gcp.yml** - Deploys to Google Cloud Run
4. **deploy-aws.yml** - Deploys to AWS ECS
5. **deploy-heroku.yml** - Deploys to Heroku

## Quick Setup

### Step 1: Create GitHub Secrets

In your GitHub repository, go to **Settings → Secrets and variables → Actions** and add:

#### For Docker & Registry (Required)
```
DOCKERHUB_USERNAME      (optional, for Docker Hub)
DOCKERHUB_TOKEN         (optional, for Docker Hub)
```

#### For Google Cloud Run
```
GCP_PROJECT_ID           (your GCP project ID)
GCP_SA_KEY               (GCP Service Account JSON key - see below)
```

#### For AWS Deployment
```
AWS_ROLE_TO_ASSUME       (AWS IAM role ARN for OIDC)
```

#### For Heroku Deployment
```
HEROKU_API_KEY           (your Heroku API key)
```

#### For Environment Variables
```
GROQ_API_KEY             (LLM API key)
GOOGLE_SHEETS_ID         (Google Sheets ID)
MCP_GRAFANA_TOKEN        (Grafana API token)
SLACK_WEBHOOK            (optional, for notifications)
```

---

## Detailed Setup by Platform

### Option A: Google Cloud Run (Recommended for GCP)

#### 1. Create GCP Service Account

```bash
# Set variables
PROJECT_ID="your-gcp-project"
SERVICE_ACCOUNT="github-actions"

# Create service account
gcloud iam service-accounts create $SERVICE_ACCOUNT \
    --display-name="GitHub Actions" \
    --project=$PROJECT_ID

# Get the service account email
SA_EMAIL=$(gcloud iam service-accounts list \
    --filter="displayName:$SERVICE_ACCOUNT" \
    --format='value(email)' \
    --project=$PROJECT_ID)

echo "Service Account Email: $SA_EMAIL"
```

#### 2. Grant Required Permissions

```bash
# Cloud Run permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/run.admin"

# Container Registry permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.admin"

# Service Account User permission
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/iam.serviceAccountUser"
```

#### 3. Create and Download Key

```bash
# Create key
gcloud iam service-accounts keys create key.json \
    --iam-account=$SA_EMAIL \
    --project=$PROJECT_ID

# Copy the contents and add to GitHub secret GCP_SA_KEY
cat key.json
```

#### 4. Update GitHub Workflow

In `.github/workflows/deploy-gcp.yml`, update:
```yaml
GCP_PROJECT_ID: your-project-id
GCP_REGION: us-central1  # Change if needed
SERVICE_NAME: cloud-operation-agent
```

#### 5. Deploy

```bash
# Push to main branch to trigger deployment
git push origin main
```

---

### Option B: AWS ECS Deployment

#### 1. Setup AWS Resources

Create the ECS cluster, service, and task definition:

```bash
# Create ECR repository
aws ecr create-repository \
    --repository-name cloud-operation-agent \
    --region us-east-1

# Create ECS cluster
aws ecs create-cluster --cluster-name coa-cluster --region us-east-1

# Create task definition (JSON below)
aws ecs register-task-definition \
    --cli-input-json file://task-definition.json \
    --region us-east-1
```

#### 2. Create IAM Role for OIDC

```bash
# Create OIDC provider
aws iam create-open-id-connect-provider \
    --url "https://token.actions.githubusercontent.com" \
    --client-id-list "sts.amazonaws.com"

# Create IAM role for GitHub Actions
ROLE_NAME="github-actions-role"
aws iam create-role \
    --role-name $ROLE_NAME \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
                },
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                        "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/COA:ref:refs/heads/main"
                    }
                }
            }
        ]
    }'

# Attach policies
aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

#### 3. Add GitHub Secret

Add to GitHub Secrets:
```
AWS_ROLE_TO_ASSUME: arn:aws:iam::YOUR_ACCOUNT_ID:role/github-actions-role
```

#### 4. Create task-definition.json

```json
{
    "family": "coa-service",
    "requiresCompatibilities": ["FARGATE"],
    "networkMode": "awsvpc",
    "cpu": "1024",
    "memory": "2048",
    "containerDefinitions": [
        {
            "name": "coa-service",
            "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/cloud-operation-agent:latest",
            "portMappings": [
                {
                    "containerPort": 8501,
                    "hostPort": 8501,
                    "protocol": "tcp"
                }
            ],
            "environment": [
                {
                    "name": "STREAMLIT_SERVER_PORT",
                    "value": "8501"
                }
            ],
            "secrets": [
                {
                    "name": "GROQ_API_KEY",
                    "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:groq-key"
                }
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/coa-service",
                    "awslogs-region": "us-east-1",
                    "awslogs-stream-prefix": "ecs"
                }
            }
        }
    ],
    "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/ecsTaskExecutionRole"
}
```

---

### Option C: Heroku Deployment

#### 1. Create Heroku App

```bash
heroku login
heroku create cloud-operation-agent
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-python
```

#### 2. Add Secrets to GitHub

```
HEROKU_API_KEY: (get from Heroku Account Settings → API Key)
```

#### 3. Configure Environment Variables

```bash
heroku config:set \
    GROQ_API_KEY="your-key" \
    GOOGLE_SHEETS_ID="your-id" \
    MCP_GRAFANA_TOKEN="your-token" \
    -a cloud-operation-agent
```

#### 4. Deploy

```bash
git push origin main
```

---

## Dockerfile Deployment

### Build Locally

```bash
# Build image
docker build -t cloud-operation-agent:latest .

# Run container
docker run -p 8501:8501 \
    -e GROQ_API_KEY="your-key" \
    -e GOOGLE_SHEETS_ID="your-id" \
    cloud-operation-agent:latest
```

### Using Docker Compose

```bash
# Create .env file
echo "GROQ_API_KEY=your-key" > .env
echo "GOOGLE_SHEETS_ID=your-id" >> .env
echo "MCP_GRAFANA_TOKEN=your-token" >> .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## Workflow Triggering

### Automatic Triggers

- **test.yml**: Runs on every push to `main` or `develop`, and on PRs
- **docker-build.yml**: Runs on push to `main`/`develop` or when tags like `v1.0.0` are pushed
- **deploy-*.yml**: Runs on push to `main` branch

### Manual Triggers

All deployment workflows can be triggered manually via GitHub Actions UI:

1. Go to **Actions** tab
2. Select the workflow
3. Click **Run workflow**
4. Select environment (staging/production)
5. Click **Run workflow**

---

## Monitoring & Notifications

### Slack Notifications

Add Slack webhook to monitor deployments:

```bash
# In GitHub Settings → Secrets
SLACK_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

## Troubleshooting

### Docker Build Fails

```bash
# Check Docker syntax
docker build -t test . --no-cache

# Check layer cache
docker system prune -a
```

### Deployment Access Denied

- Verify service account permissions
- Check API keys and tokens in GitHub Secrets
- Review IAM roles (AWS/GCP)

### Streamlit Connection Issues

```bash
# Check logs
docker logs <container-id>

# Verify environment variables
docker run -e GROQ_API_KEY=test <image> env | grep GROQ
```

---

## Security Best Practices

1. **Never commit secrets** - Always use GitHub Secrets
2. **Use short-lived credentials** - Implement token rotation
3. **Scope IAM permissions** - Apply principle of least privilege
4. **Enable branch protection** - Require checks before merge
5. **Regular dependency updates** - Use Dependabot

---

## Next Steps

1. Choose your deployment platform (GCP/AWS/Heroku)
2. Follow the setup instructions for your chosen platform
3. Add required GitHub Secrets
4. Push to main branch to trigger workflow
5. Monitor deployment in GitHub Actions tab

For questions, check the individual workflow files or consult the platform documentation.
