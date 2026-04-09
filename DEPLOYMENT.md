# Deployment Guide — CRM App

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Variable Configuration](#environment-variable-configuration)
3. [Database Setup (PostgreSQL)](#database-setup-postgresql)
4. [Static Files with WhiteNoise](#static-files-with-whitenoise)
5. [Celery and Redis Setup](#celery-and-redis-setup)
6. [Build Script Usage](#build-script-usage)
7. [Vercel Deployment](#vercel-deployment)
8. [Docker Containerization](#docker-containerization)
9. [Kubernetes Orchestration](#kubernetes-orchestration)
10. [CI/CD with GitHub Actions](#cicd-with-github-actions)
11. [Troubleshooting Guide](#troubleshooting-guide)

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Docker 24+ (for containerized deployments)
- kubectl and a Kubernetes cluster (for orchestrated deployments)
- A GitHub account (for CI/CD)

---

## Environment Variable Configuration

All environment variables must be set in the deployment environment. **Never hardcode secrets in source code.**

| Variable | Description | Required | Default |
|---|---|---|---|
| `SECRET_KEY` | Django secret key for cryptographic signing | Yes | — |
| `DEBUG` | Enable debug mode (`True`/`False`) | No | `False` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hostnames | Yes | — |
| `DATABASE_URL` | PostgreSQL connection string | Yes | — |
| `REDIS_URL` | Redis connection string for Celery broker | Yes | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL (defaults to `REDIS_URL`) | No | Value of `REDIS_URL` |
| `CELERY_RESULT_BACKEND` | Celery result backend URL | No | Value of `REDIS_URL` |
| `EMAIL_HOST` | SMTP server hostname | No | — |
| `EMAIL_PORT` | SMTP server port | No | `587` |
| `EMAIL_HOST_USER` | SMTP username | No | — |
| `EMAIL_HOST_PASSWORD` | SMTP password | No | — |
| `SENTRY_DSN` | Sentry error tracking DSN | No | — |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins | No | — |

### Example `.env` file

```bash
SECRET_KEY=your-very-long-random-secret-key-here
DEBUG=False
ALLOWED_HOSTS=crm.example.com,www.crm.example.com
DATABASE_URL=postgres://crm_user:password@db-host:5432/crm_db
REDIS_URL=redis://redis-host:6379/0
CELERY_BROKER_URL=redis://redis-host:6379/0
CELERY_RESULT_BACKEND=redis://redis-host:6379/1
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=noreply@example.com
EMAIL_HOST_PASSWORD=smtp-password
```

> **Security Note:** Never commit `.env` files to version control. The `.gitignore` file should include `.env`.

---

## Database Setup (PostgreSQL)

### 1. Create the Database and User

```sql
CREATE USER crm_user WITH PASSWORD 'your-secure-password';
CREATE DATABASE crm_db OWNER crm_user;
ALTER ROLE crm_user SET client_encoding TO 'utf8';
ALTER ROLE crm_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE crm_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE crm_db TO crm_user;
```

### 2. Configure the Connection

Set the `DATABASE_URL` environment variable:

```bash
export DATABASE_URL=postgres://crm_user:your-secure-password@localhost:5432/crm_db
```

In `settings.py`, the database is configured via `dj-database-url`:

```python
import dj_database_url
import os

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}
```

### 3. Run Migrations

```bash
python manage.py migrate
```

### 4. Create a Superuser

```bash
python manage.py createsuperuser
```

### 5. Backup and Restore

**Backup:**

```bash
pg_dump -U crm_user -h localhost -d crm_db -F c -f crm_backup_$(date +%Y%m%d).dump
```

**Restore:**

```bash
pg_restore -U crm_user -h localhost -d crm_db -c crm_backup_20240101.dump
```

---

## Static Files with WhiteNoise

WhiteNoise serves static files directly from the WSGI application without requiring a separate web server like Nginx for static assets.

### Configuration in `settings.py`

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Must be after SecurityMiddleware
    # ... other middleware
]

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

### Collect Static Files

```bash
python manage.py collectstatic --noinput
```

WhiteNoise will automatically:
- Serve compressed (gzip/brotli) versions of static files
- Add far-future cache headers to versioned files
- Serve files with efficient caching

---

## Celery and Redis Setup

### 1. Install Redis

**Ubuntu/Debian:**

```bash
sudo apt update && sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

**macOS (Homebrew):**

```bash
brew install redis
brew services start redis
```

### 2. Celery Configuration

The Celery application is configured in `crm/celery.py`:

```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')

app = Celery('crm')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

Ensure `crm/__init__.py` loads the Celery app:

```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

### 3. Running Celery Workers

**Worker (task processing):**

```bash
celery -A crm worker --loglevel=info --concurrency=4
```

**Beat (periodic task scheduler):**

```bash
celery -A crm beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**Combined (development only):**

```bash
celery -A crm worker --beat --loglevel=info
```

### 4. Production Celery with systemd

Create `/etc/systemd/system/celery-worker.service`:

```ini
[Unit]
Description=CRM Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/opt/crm-app
EnvironmentFile=/opt/crm-app/.env
ExecStart=/opt/crm-app/venv/bin/celery -A crm worker --loglevel=info --concurrency=4 --detach --pidfile=/var/run/celery/worker.pid --logfile=/var/log/celery/worker.log
ExecStop=/bin/kill -s TERM $MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-worker
sudo systemctl start celery-worker
```

### 5. Monitoring with Flower

```bash
celery -A crm flower --port=5555
```

Access the Flower dashboard at `http://localhost:5555`.

---

## Build Script Usage

The project includes a `build.sh` script for automated build and deployment preparation.

### Running the Build Script

```bash
chmod +x build.sh
./build.sh
```

### What the Build Script Does

1. Installs Python dependencies from `requirements.txt`
2. Collects static files via `python manage.py collectstatic --noinput`
3. Runs database migrations via `python manage.py migrate`
4. Runs the test suite via `python manage.py test`

### Example `build.sh`

```bash
#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Running tests..."
python manage.py test --verbosity=2

echo "==> Build complete."
```

---

## Vercel Deployment

> **Note:** Vercel is primarily designed for frontend/serverless deployments. For a Django application, Vercel can be used with its Python runtime, but it has limitations (no persistent filesystem, no background workers). Consider using Docker-based deployments for full-featured production environments.

### 1. Project Configuration

Create `vercel.json` in the project root:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "crm/wsgi.py",
      "use": "@vercel/python"
    },
    {
      "src": "build.sh",
      "use": "@vercel/static-build",
      "config": {
        "distDir": "staticfiles"
      }
    }
  ],
  "routes": [
    {
      "src": "/static/(.*)",
      "dest": "/staticfiles/$1"
    },
    {
      "src": "/(.*)",
      "dest": "crm/wsgi.py"
    }
  ]
}
```

### 2. Set Environment Variables

In the Vercel dashboard:

1. Navigate to your project → **Settings** → **Environment Variables**
2. Add all required environment variables listed in the [Environment Variable Configuration](#environment-variable-configuration) section
3. Set `ALLOWED_HOSTS` to include your Vercel domain (e.g., `crm-app.vercel.app`)

### 3. Deploy

```bash
# Install Vercel CLI
npm install -g vercel

# Login and deploy
vercel login
vercel --prod
```

### Vercel Limitations for Django

- **No Celery workers:** Use an external Celery worker host or switch to a task queue service
- **No persistent filesystem:** Use external storage (S3, Cloudinary) for media files
- **Cold starts:** Serverless functions may have latency on first request
- **Execution timeout:** Functions have a maximum execution time (default 10s, max 60s on Pro)

For production Django deployments, Docker or a PaaS like Railway, Render, or Fly.io is recommended.

---

## Docker Containerization

### Dockerfile

```dockerfile
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "crm.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2"]
```

### docker-compose.yml

```yaml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: crm_db
      POSTGRES_USER: crm_user
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U crm_user -d crm_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    build: .
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      DATABASE_URL: postgres://crm_user:${DB_PASSWORD:-changeme}@db:5432/crm_db
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: >
      sh -c "python manage.py migrate --noinput &&
             gunicorn crm.wsgi:application --bind 0.0.0.0:8000 --workers 4 --threads 2"

  celery-worker:
    build: .
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATABASE_URL: postgres://crm_user:${DB_PASSWORD:-changeme}@db:5432/crm_db
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A crm worker --loglevel=info --concurrency=4

  celery-beat:
    build: .
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATABASE_URL: postgres://crm_user:${DB_PASSWORD:-changeme}@db:5432/crm_db
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A crm beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

volumes:
  postgres_data:
```

### Docker Commands

```bash
# Build and start all services
docker compose up --build -d

# View logs
docker compose logs -f web

# Run migrations manually
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser

# Run tests
docker compose exec web python manage.py test

# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes database data)
docker compose down -v
```

---

## Kubernetes Orchestration

### Overview

The Kubernetes deployment consists of the following resources:

| Resource | Purpose |
|---|---|
| `Namespace` | Isolates CRM resources |
| `ConfigMap` | Non-sensitive configuration |
| `Secret` | Sensitive credentials |
| `Deployment` (web) | Django application pods |
| `Deployment` (celery-worker) | Celery worker pods |
| `Deployment` (celery-beat) | Celery beat scheduler (single replica) |
| `Service` | Internal load balancer for web pods |
| `Ingress` | External HTTP(S) routing |
| `HorizontalPodAutoscaler` | Auto-scaling for web pods |
| `PersistentVolumeClaim` | Database storage (if self-hosted) |

### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: crm
```

### ConfigMap and Secret

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: crm-config
  namespace: crm
data:
  ALLOWED_HOSTS: "crm.example.com"
  DEBUG: "False"
  CELERY_BROKER_URL: "redis://redis-service:6379/0"
  CELERY_RESULT_BACKEND: "redis://redis-service:6379/1"
```

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: crm-secret
  namespace: crm
type: Opaque
stringData:
  SECRET_KEY: "your-production-secret-key"
  DATABASE_URL: "postgres://crm_user:password@postgres-service:5432/crm_db"
```

### Web Deployment

```yaml
# k8s/web-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crm-web
  namespace: crm
  labels:
    app: crm
    component: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: crm
      component: web
  template:
    metadata:
      labels:
        app: crm
        component: web
    spec:
      containers:
        - name: web
          image: your-registry/crm-app:latest
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: crm-config
            - secretRef:
                name: crm-secret
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          readinessProbe:
            httpGet:
              path: /health/
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health/
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 30
      initContainers:
        - name: migrate
          image: your-registry/crm-app:latest
          command: ["python", "manage.py", "migrate", "--noinput"]
          envFrom:
            - configMapRef:
                name: crm-config
            - secretRef:
                name: crm-secret
```

### Service and Ingress

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: crm-web-service
  namespace: crm
spec:
  selector:
    app: crm
    component: web
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP
```

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: crm-ingress
  namespace: crm
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - crm.example.com
      secretName: crm-tls
  rules:
    - host: crm.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: crm-web-service
                port:
                  number: 80
```

### HorizontalPodAutoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: crm-web-hpa
  namespace: crm
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: crm-web
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### Deploying to Kubernetes

```bash
# Apply all manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/web-deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml

# Check status
kubectl get pods -n crm
kubectl get services -n crm
kubectl get ingress -n crm

# View logs
kubectl logs -f deployment/crm-web -n crm

# Scale manually
kubectl scale deployment crm-web --replicas=5 -n crm
```

---

## CI/CD with GitHub Actions

### Workflow File

Create `.github/workflows/ci-cd.yml`:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.11"
  DOCKER_IMAGE: your-registry/crm-app

jobs:
  test:
    name: Run Tests
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: test_crm_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run linting
        run: |
          pip install flake8
          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

      - name: Run migrations
        env:
          DATABASE_URL: postgres://test_user:test_password@localhost:5432/test_crm_db
          SECRET_KEY: test-secret-key-for-ci
          REDIS_URL: redis://localhost:6379/0
        run: python manage.py migrate --noinput

      - name: Run tests
        env:
          DATABASE_URL: postgres://test_user:test_password@localhost:5432/test_crm_db
          SECRET_KEY: test-secret-key-for-ci
          REDIS_URL: redis://localhost:6379/0
        run: python manage.py test --verbosity=2

      - name: Check for missing migrations
        env:
          DATABASE_URL: postgres://test_user:test_password@localhost:5432/test_crm_db
          SECRET_KEY: test-secret-key-for-ci
          REDIS_URL: redis://localhost:6379/0
        run: python manage.py makemigrations --check --dry-run

  build-and-push:
    name: Build and Push Docker Image
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ secrets.DOCKER_REGISTRY }}
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ${{ env.DOCKER_IMAGE }}:latest
            ${{ env.DOCKER_IMAGE }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: build-and-push
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment: production

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up kubectl
        uses: azure/setup-kubectl@v3

      - name: Configure kubectl
        run: |
          echo "${{ secrets.KUBE_CONFIG }}" | base64 -d > $HOME/.kube/config

      - name: Update deployment image
        run: |
          kubectl set image deployment/crm-web \
            web=${{ env.DOCKER_IMAGE }}:${{ github.sha }} \
            -n crm

      - name: Wait for rollout
        run: |
          kubectl rollout status deployment/crm-web -n crm --timeout=300s

      - name: Verify deployment
        run: |
          kubectl get pods -n crm -l app=crm,component=web
```

### Required GitHub Secrets

Configure these in your repository under **Settings** → **Secrets and variables** → **Actions**:

| Secret | Description |
|---|---|
| `DOCKER_REGISTRY` | Container registry URL (e.g., `ghcr.io`) |
| `DOCKER_USERNAME` | Registry username |
| `DOCKER_PASSWORD` | Registry password or token |
| `KUBE_CONFIG` | Base64-encoded kubeconfig file |

---

## Troubleshooting Guide

### Database Connection Issues

**Symptom:** `django.db.utils.OperationalError: could not connect to server`

**Solutions:**
1. Verify PostgreSQL is running: `sudo systemctl status postgresql`
2. Check the `DATABASE_URL` environment variable is set correctly
3. Ensure the database user has proper permissions
4. Check firewall rules allow connections on port 5432
5. For Docker: ensure the `db` service is healthy before `web` starts

```bash
# Test database connectivity
python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')"
```

### Migration Errors

**Symptom:** `django.db.utils.ProgrammingError: relation "..." does not exist`

**Solutions:**
1. Run pending migrations: `python manage.py migrate`
2. Check for unapplied migrations: `python manage.py showmigrations`
3. If migrations are out of sync, check for conflicts: `python manage.py makemigrations --check`
4. Never manually edit migration files — regenerate if needed

### Static Files Not Loading

**Symptom:** 404 errors for CSS/JS files in production

**Solutions:**
1. Ensure `collectstatic` has been run: `python manage.py collectstatic --noinput`
2. Verify `whitenoise.middleware.WhiteNoiseMiddleware` is in `MIDDLEWARE` (after `SecurityMiddleware`)
3. Check `STATIC_ROOT` is set and the directory exists
4. Verify `STATICFILES_STORAGE` is set to `whitenoise.storage.CompressedManifestStaticFilesStorage`

### Celery Workers Not Processing Tasks

**Symptom:** Tasks remain in the queue, never executed

**Solutions:**
1. Verify Redis is running: `redis-cli ping` (should return `PONG`)
2. Check `CELERY_BROKER_URL` is correct
3. Ensure the Celery app is loaded in `crm/__init__.py`
4. Check worker logs: `celery -A crm worker --loglevel=debug`
5. Verify task modules are discovered: `celery -A crm inspect registered`
6. Test Redis connectivity: `redis-cli -u $REDIS_URL ping`

### Docker Build Failures

**Symptom:** `docker compose build` fails

**Solutions:**
1. Clear Docker cache: `docker compose build --no-cache`
2. Ensure `requirements.txt` is up to date: `pip freeze > requirements.txt`
3. Check for system dependencies in the Dockerfile (e.g., `libpq-dev` for `psycopg2`)
4. Verify Docker has sufficient disk space: `docker system df`
5. Prune unused resources: `docker system prune -a`

### Kubernetes Pod CrashLoopBackOff

**Symptom:** Pods restart repeatedly

**Solutions:**
1. Check pod logs: `kubectl logs <pod-name> -n crm --previous`
2. Describe the pod for events: `kubectl describe pod <pod-name> -n crm`
3. Verify ConfigMap and Secret values: `kubectl get configmap crm-config -n crm -o yaml`
4. Check resource limits — pods may be OOMKilled if memory limits are too low
5. Ensure the health check endpoint (`/health/`) returns 200
6. Verify init containers (migrations) complete successfully

### High Memory Usage

**Symptom:** Application consumes excessive memory

**Solutions:**
1. Reduce Gunicorn workers: `--workers 2` instead of `--workers 4`
2. Use `--preload` flag with Gunicorn to share memory across workers
3. Add `select_related()` and `prefetch_related()` to ORM queries to reduce N+1 queries
4. Monitor with: `kubectl top pods -n crm` (Kubernetes) or `docker stats` (Docker)

### CORS Errors

**Symptom:** Browser console shows `Access-Control-Allow-Origin` errors

**Solutions:**
1. Set `CORS_ALLOWED_ORIGINS` environment variable with your frontend domain
2. Ensure `django-cors-headers` is installed and `corsheaders` is in `INSTALLED_APPS`
3. Verify `corsheaders.middleware.CorsMiddleware` is placed before `CommonMiddleware` in `MIDDLEWARE`

### SSL/TLS Certificate Issues

**Symptom:** HTTPS not working or certificate errors

**Solutions:**
1. For Kubernetes with cert-manager: check certificate status with `kubectl get certificates -n crm`
2. Verify the Ingress annotation `cert-manager.io/cluster-issuer` matches your ClusterIssuer name
3. Check cert-manager logs: `kubectl logs -n cert-manager deployment/cert-manager`
4. Ensure DNS records point to your Ingress controller's external IP

### Performance Optimization Checklist

- [ ] `DEBUG = False` in production
- [ ] Database connection pooling enabled (`conn_max_age=600`)
- [ ] `select_related()` / `prefetch_related()` used in list views
- [ ] Static files served via WhiteNoise with compression
- [ ] Celery used for long-running tasks (email sending, report generation)
- [ ] Database indexes added for frequently queried fields
- [ ] Redis caching configured for expensive queries
- [ ] Gunicorn configured with appropriate worker count (`2 * CPU cores + 1`)
- [ ] Sentry configured for error tracking in production