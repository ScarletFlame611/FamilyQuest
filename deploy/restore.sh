#!/usr/bin/env bash
# Заменяет рабочую базу копией: ./deploy/restore.sh backups/familyquest-....dump
# Журналы детских сессий из архива той же копии возвращаются в exports/.
# Для локального окружения: COMPOSE="docker compose" ./deploy/restore.sh <файл>
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE=${COMPOSE:-docker compose -f docker-compose.prod.yml --env-file .env.prod}
file=${1:?Укажите файл копии из backups/}
[ -f "$file" ] || { echo "Нет файла $file"; exit 1; }
read -r -p "Рабочая база будет заменена копией $file. Продолжить? (yes) " answer
[ "$answer" = "yes" ] || { echo "Отменено"; exit 1; }
# Состояние до восстановления тоже сохраняем, чтобы восстановление можно было откатить.
# Без очистки: иначе она могла бы удалить ту самую копию, которую восстанавливаем
./deploy/backup.sh --no-clean
$COMPOSE stop backend
# База пересоздаётся целиком: так не остаётся таблиц из более новых миграций,
# которых нет в копии
$COMPOSE exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
$COMPOSE exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error --single-transaction' < "$file"
archive="${file%.dump}-exports.tar.gz"
if [ -f "$archive" ]; then
  tar -xzf "$archive"
fi
# Копия могла быть снята до последних миграций
$COMPOSE run --rm backend alembic upgrade head
$COMPOSE run --rm backend python -m app.reconcile
$COMPOSE up -d backend
echo "База восстановлена из $file"
