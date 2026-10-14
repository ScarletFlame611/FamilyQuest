#!/usr/bin/env bash
# Перед каждым ребёнком: журналы прошлых сессий уходят в exports/, демо-семья создаётся заново.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm backend python -m app.seed
