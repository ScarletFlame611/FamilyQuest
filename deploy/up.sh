#!/usr/bin/env bash
# Поднимает стенд, применяет миграции и создаёт демо-семью.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env.prod ] || { echo "Нет .env.prod: скопируйте .env.prod.example и задайте секреты"; exit 1; }
[ -f deploy/certs/stand.crt ] || ./deploy/make-cert.sh
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"
# Если интернет на машине идёт через прокси, сборке его нужно передать явно:
# BUILD_PROXY=http://host.docker.internal:7890 ./deploy/up.sh
BUILD_ARGS=()
if [ -n "${BUILD_PROXY:-}" ]; then
  BUILD_ARGS=(--build-arg "HTTP_PROXY=$BUILD_PROXY" --build-arg "HTTPS_PROXY=$BUILD_PROXY")
fi
$COMPOSE build "${BUILD_ARGS[@]}"
$COMPOSE up -d
$COMPOSE run --rm backend alembic upgrade head
$COMPOSE run --rm backend python -m app.seed
echo "Стенд: https://$(ipconfig getifaddr en0 2>/dev/null || hostname -I | awk '{print $1}')"
