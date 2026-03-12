# Resinly Deployment (EC2, Isolated from FastAPI)

This bot is deployed as a separate Docker Compose project in its own EC2 directory.
It does not share a Compose stack with `fastapi_project`.

## Why This Layout
- Isolation: bot updates cannot break API services.
- Simplicity: one folder, one compose project, one lifecycle.
- Security: `.env` stays on EC2 and is not written by CI.

## One-Time EC2 Setup

```bash
# 1) SSH into EC2
ssh -i /path/to/key.pem ubuntu@<EC2_HOST>

# 2) Install docker + compose plugin (Ubuntu)
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin git
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
newgrp docker

# 3) Clone bot repo into isolated folder
mkdir -p /home/ubuntu/resinly
cd /home/ubuntu
if [ ! -d /home/ubuntu/resinly/.git ]; then
  git clone https://github.com/ecgregorio/Resinly.git resinly
fi

# 4) Create runtime directories/files
cd /home/ubuntu/resinly
mkdir -p data
touch discord.log

# 5) Create local-only env file
cp .env.example .env
nano .env
```

Required `.env` values:
- `DISCORD_TOKEN`
- `ENCRYPTION_KEY`
- `GENSHIN_UID` (optional fallback)
- `LTUID_V2` (optional fallback)
- `LTOKEN_V2` (optional fallback)
- `CHECK_INTERVAL_SECONDS`

## First Manual Test (on EC2)

```bash
cd /home/ubuntu/resinly

docker compose build
docker compose up -d
docker compose ps
docker compose logs -f --tail=100 bot
```

## GitHub Actions Deploy Flow
- Trigger: push to `main` or manual workflow dispatch.
- Workflow SSHs into EC2.
- Goes to `EC2_BOT_REPO_DIR` (fallback `/home/ubuntu/resinly`).
- Runs `git fetch` + `git pull origin main`.
- Fails if `.env` is missing.
- Runs `docker compose up -d --build`.
- Prints `docker compose ps` and recent bot logs.

## Required GitHub Secrets
- `EC2_HOST`
- `EC2_USER`
- `EC2_SSH_KEY`
- `EC2_BOT_REPO_DIR`

## Operations Commands

```bash
# Status
cd /home/ubuntu/resinly && docker compose ps

# Logs
cd /home/ubuntu/resinly && docker compose logs -f --tail=200 bot

# Restart bot container
cd /home/ubuntu/resinly && docker compose restart bot

# Pull latest + rebuild manually
cd /home/ubuntu/resinly && git pull origin main && docker compose up -d --build

# Stop/start
cd /home/ubuntu/resinly && docker compose stop
cd /home/ubuntu/resinly && docker compose start
```

## Verify After Deploy

```bash
cd /home/ubuntu/resinly

docker compose ps
docker compose logs --tail=100 bot
```

Healthy signs:
- Container state is `Up`.
- Logs show Discord login and command sync.

## Rollback

```bash
cd /home/ubuntu/resinly

# list recent commits
git log --oneline -n 10

# rollback to previous commit
git reset --hard HEAD~1

# rebuild + restart
docker compose up -d --build
```

Alternative rollback to specific commit:

```bash
cd /home/ubuntu/resinly
git reset --hard <commit_sha>
docker compose up -d --build
```

## Critical Warning
`ENCRYPTION_KEY` must remain stable for the lifetime of stored encrypted cookie data.
If you change it, existing encrypted user cookies in `data/subscriptions.json` become unreadable.
