# FactCheck AI - Deployment Guide

Complete guide for deploying FactCheck AI to production.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Migration](#database-migration)
4. [Deployment Options](#deployment-options)
5. [Monitoring Setup](#monitoring-setup)
6. [CI/CD Pipeline](#cicd-pipeline)
7. [Scaling Strategy](#scaling-strategy)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Services
- PostgreSQL 14+ (or SQLite for development)
- Redis 7+ (for caching - optional)
- Python 3.11+
- Node.js 18+ (for extension build)

### API Keys
- OpenAI API key (for AI analysis)
- Brave Search API key (for evidence gathering)
- Google OAuth credentials (for authentication)

---

## Environment Setup

### 1. Backend Configuration

Create `.env` file in `backend/` directory:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/factcheck

# API Keys
OPENAI_API_KEY=sk-...
BRAVE_API_KEY=...

# Authentication
SECRET_KEY=your-secret-key-here
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Email (for password reset)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Environment
ENVIRONMENT=production
SKIP_TRAIN_ON_STARTUP=true

# Optional: Redis
REDIS_URL=redis://localhost:6379/0
```

### 2. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Train Models

```bash
# Train TF-IDF model
python training/train.py

# Train transformer model (optional, requires GPU)
python training/train_transformer_clean.py

# Train meta-model
python training/train_meta.py
```

---

## Database Migration

### 1. Initialize Alembic

```bash
cd backend
alembic upgrade head
```

### 2. Verify Migration

```bash
alembic current
# Should show: 20260417000000 (head)
```

### 3. Create Admin User (Optional)

```python
from database import SessionLocal
from app.models import User
from app.auth import get_password_hash

db = SessionLocal()
admin = User(
    email="admin@factcheck.ai",
    name="Admin",
    hashed_pw=get_password_hash("secure-password"),
    is_active=True
)
db.add(admin)
db.commit()
```

---

## Deployment Options

### Option 1: Render.com (Recommended for MVP)

#### 1. Create `render.yaml`

```yaml
services:
  - type: web
    name: factcheck-api
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: DATABASE_URL
        fromDatabase:
          name: factcheck-db
          property: connectionString
      - key: OPENAI_API_KEY
        sync: false
      - key: BRAVE_API_KEY
        sync: false
      - key: SECRET_KEY
        generateValue: true
      - key: SKIP_TRAIN_ON_STARTUP
        value: true

databases:
  - name: factcheck-db
    databaseName: factcheck
    user: factcheck
```

#### 2. Deploy

```bash
# Connect GitHub repo to Render
# Render will auto-deploy on push to main
```

#### 3. Run Migrations

```bash
# In Render shell
alembic upgrade head
```

### Option 2: HuggingFace Spaces

#### 1. Create Space

- Go to https://huggingface.co/spaces
- Create new Space (Gradio SDK)
- Clone repository

#### 2. Add Files

```bash
# Create app.py for Gradio interface
# Copy backend files
# Add requirements.txt
```

#### 3. Configure Secrets

- Add API keys in Space settings
- Set environment variables

### Option 3: Docker Deployment

#### 1. Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run migrations
RUN alembic upgrade head

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2. Build and Run

```bash
docker build -t factcheck-api .
docker run -p 8000:8000 --env-file .env factcheck-api
```

#### 3. Docker Compose (with PostgreSQL)

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/factcheck
    depends_on:
      - db
  
  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=factcheck
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Monitoring Setup

### 1. Prometheus Configuration

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'factcheck-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### 2. Start Prometheus

```bash
docker run -d \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

### 3. Grafana Setup

```bash
# Start Grafana
docker run -d -p 3000:3000 grafana/grafana

# Login: admin/admin
# Add Prometheus data source: http://localhost:9090
# Import dashboard: backend/monitoring/grafana_dashboard.json
```

### 4. Key Metrics to Monitor

- **Request Rate**: `rate(http_requests_total[5m])`
- **Latency (p95)**: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
- **Error Rate**: `rate(errors_total[5m])`
- **Model Accuracy**: `model_accuracy{time_window="24h"}`
- **Review Queue**: `review_queue_size`

### 5. Alerts

Create `alerts.yml`:

```yaml
groups:
  - name: factcheck_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(errors_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
      
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 5
        for: 5m
        annotations:
          summary: "High latency detected (p95 > 5s)"
      
      - alert: LowModelAccuracy
        expr: model_accuracy{time_window="24h"} < 0.7
        for: 1h
        annotations:
          summary: "Model accuracy dropped below 70%"
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests
        run: |
          cd backend
          pytest tests/
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Render
        run: |
          curl -X POST ${{ secrets.RENDER_DEPLOY_HOOK }}
```

---

## Scaling Strategy

### Horizontal Scaling

#### 1. Load Balancer Setup

```nginx
upstream factcheck_api {
    least_conn;
    server api1:8000;
    server api2:8000;
    server api3:8000;
}

server {
    listen 80;
    server_name api.factcheck.ai;
    
    location / {
        proxy_pass http://factcheck_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 2. Database Connection Pooling

```python
# In database.py
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)
```

### Caching Strategy

#### 1. Redis Cache

```python
import redis
from functools import wraps

redis_client = redis.from_url(os.getenv("REDIS_URL"))

def cache_result(ttl=3600):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            result = func(*args, **kwargs)
            redis_client.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator
```

#### 2. Model Caching

```python
# Cache model predictions for identical claims
@cache_result(ttl=86400)  # 24 hours
def predict_claim(claim_text: str):
    # ... prediction logic
    pass
```

### Async Processing

#### 1. Celery Setup

```python
from celery import Celery

celery_app = Celery('factcheck', broker='redis://localhost:6379/0')

@celery_app.task
def process_claim_async(claim_text: str):
    # Long-running analysis
    pass
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

```bash
# Check connection
psql $DATABASE_URL

# Reset connections
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = 'factcheck';
```

#### 2. Model Loading Failures

```bash
# Verify model files
ls -lh backend/data/

# Retrain if corrupted
python backend/training/train.py
```

#### 3. High Memory Usage

```bash
# Monitor memory
docker stats

# Reduce worker count
uvicorn app.main:app --workers 2
```

#### 4. Slow Queries

```sql
-- Enable query logging
ALTER DATABASE factcheck SET log_statement = 'all';

-- Find slow queries
SELECT query, mean_exec_time 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Metrics health
curl http://localhost:8000/health/metrics

# Database health
curl http://localhost:8000/health/db
```

### Logs

```bash
# View logs (Docker)
docker logs -f factcheck-api

# View logs (Render)
# Use Render dashboard

# Search logs
grep "ERROR" logs/app.log
```

---

## Security Checklist

- [ ] HTTPS enabled (SSL certificate)
- [ ] API keys in environment variables (not code)
- [ ] Rate limiting configured
- [ ] CORS properly configured
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (input sanitization)
- [ ] Authentication required for sensitive endpoints
- [ ] Regular security updates
- [ ] Database backups automated
- [ ] Secrets rotation policy

---

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| API Latency (p95) | < 2s | TBD |
| Model Inference | < 500ms | TBD |
| SHAP Explanation | < 500ms | TBD |
| Uptime | > 99.5% | TBD |
| Error Rate | < 1% | TBD |
| Model Accuracy | > 85% | TBD |

---

## Maintenance

### Weekly Tasks
- Review error logs
- Check model accuracy metrics
- Review A/B test results
- Process review queue feedback

### Monthly Tasks
- Retrain models with new feedback
- Update dependencies
- Review and optimize slow queries
- Backup database

### Quarterly Tasks
- Security audit
- Performance optimization
- Cost analysis
- Feature planning

---

## Support

- **Documentation**: https://github.com/your-repo/wiki
- **Issues**: https://github.com/your-repo/issues
- **Email**: support@factcheck.ai

---

**Last Updated**: 2026-04-17
**Version**: 2.0.0
