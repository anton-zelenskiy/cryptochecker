# Cryptochecker

Crypto screener + Telegram bot (aiogram) + FastAPI + Celery + TimescaleDB.


## Run locally (Docker Compose)

1. Copy env:

```bash
cp .env.example .env
```

2. Fill required variables in `.env` (Telegram + webhook base URL + DB/Redis).

3. Start:

```bash
docker compose up -d --build
```

4. Health check: `http://localhost:8000/health`

## CI/CD (GitHub Actions + GHCR + SSH deploy)

Workflow builds and pushes `ghcr.io/<owner>/<repo>:latest`, then deploys over SSH by running:

```bash
export GHCR_IMAGE="ghcr.io/<owner>/<repo>:latest"
docker compose pull
docker compose up -d
```

### Required GitHub Secrets

- `SSH_HOST`
- `SSH_USER`
- `SSH_KEY` (private key)
- `DEPLOY_PATH` (path on VPS containing `docker-compose.yml` and `.env`)
