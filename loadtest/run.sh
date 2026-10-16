#!/usr/bin/env bash
# Полный прогон нагрузочного теста: подготовка семей, Locust, замеры, сверка.
set -euo pipefail
cd "$(dirname "$0")/.."

FAMILIES="${LOAD_FAMILIES:-400}"
RESULTS=loadtest/results
rm -rf "$RESULTS" && mkdir -p "$RESULTS"

docker compose run --rm -q backend python -m app.seed_load "$FAMILIES"

# Дважды в секунду: сколько соединений пула SQLAlchemy занято у API
(
  echo "time,checked_out,limit" > "$RESULTS/pool.csv"
  while true; do
    now=$(date +%s.%N | cut -c1-14)
    curl -sf http://localhost:8000/api/health/pool \
      | sed -E "s/.*\"checked_out\":([0-9]+),\"limit\":([0-9]+).*/$now,\1,\2\n/" \
      >> "$RESULTS/pool.csv" || true
    sleep 0.5
  done
) &
POOL_SAMPLER=$!

# Раз в 2 секунды: загрузка процессора контейнеров и запросы, ждущие блокировку в базе
(
  echo "time,container,cpu,mem" > "$RESULTS/cpu.csv"
  echo "time,waiting_for_lock,active" > "$RESULTS/locks.csv"
  while true; do
    now=$(date +%s)
    docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}}" \
      | grep -E "backend|db" | sed "s/^/$now,/" >> "$RESULTS/cpu.csv" || true
    docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAF, -c \
      "select count(*) filter (where wait_event_type = '"'"'Lock'"'"'), count(*) filter (where state = '"'"'active'"'"') from pg_stat_activity where datname = current_database()"' \
      | sed "s/^/$now,/" >> "$RESULTS/locks.csv" || true
    sleep 2
  done
) &
SAMPLER=$!
trap 'kill $SAMPLER $POOL_SAMPLER 2>/dev/null || true' EXIT

LOAD_FAMILIES="$FAMILIES" docker compose --profile loadtest run --rm locust
kill $SAMPLER $POOL_SAMPLER 2>/dev/null || true
wait $SAMPLER $POOL_SAMPLER 2>/dev/null || true

docker compose run --rm -q backend python -m app.reconcile
python3 loadtest/summarize.py "$RESULTS"
