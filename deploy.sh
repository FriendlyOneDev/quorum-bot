#!/bin/bash
set -e

SERVER="192.168.3.15"
APP_DIR="/home/friendlyone/quorum-bot"
IMAGE="friendlyone/quorum-bot:latest"

echo "==> Building image locally..."
docker build -t "$IMAGE" .

echo "==> Transferring image to $SERVER..."
docker save "$IMAGE" | ssh "$SERVER" "docker load"

echo "==> Syncing compose + env files..."
ssh "$SERVER" "mkdir -p $APP_DIR"
rsync -az docker-compose.yml .env "$SERVER:$APP_DIR/"

echo "==> Restarting container on $SERVER..."
ssh "$SERVER" "cd $APP_DIR && docker compose up -d --force-recreate"

echo "==> Done."
ssh "$SERVER" "docker ps --filter name=quorum-bot --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'"
