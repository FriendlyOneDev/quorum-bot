#!/bin/bash
set -e

# Contabo VPS. The old home-lab target (192.168.3.15) was retired in Oct 2026
# when the bots moved here; .15/.16 may come back but are no longer production.
SERVER="root@13.140.132.119"
APP_DIR="/root/apps/quorum-bot"
IMAGE="friendlyone/quorum-bot:latest"

echo "==> Building image locally..."
docker build -t "$IMAGE" .

echo "==> Transferring image to $SERVER..."
docker save "$IMAGE" | gzip | ssh "$SERVER" "gunzip | docker load"

echo "==> Syncing compose..."
# .env and db.env stay server-side only: they hold the prod secrets and point
# DATABASE_URL at the in-compose db host. A dev checkout must never clobber them.
rsync -az docker-compose.yml "$SERVER:$APP_DIR/"

echo "==> Restarting bot on $SERVER..."
# --no-deps leaves Postgres alone; its data lives in $APP_DIR/pgdata on the host.
ssh "$SERVER" "cd $APP_DIR && docker compose up -d --force-recreate --no-deps bot"

echo "==> Done."
ssh "$SERVER" "docker ps --filter name=quorum --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'"
