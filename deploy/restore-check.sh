#!/usr/bin/env bash
# Проверка копии: восстанавливает её в отдельную пустую базу familyquest_restore_check
# и сравнивает известные записи с рабочей базой. Рабочая база не меняется.
# Без аргумента берётся самая свежая копия.
# Для локального окружения: COMPOSE="docker compose" ./deploy/restore-check.sh
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE=${COMPOSE:-docker compose -f docker-compose.prod.yml --env-file .env.prod}
file=${1:-$(find backups -maxdepth 1 -name 'familyquest-*.dump' | sort -r | head -1)}
[ -n "$file" ] && [ -f "$file" ] || { echo "Нет копии для проверки" >&2; exit 1; }
check_db=familyquest_restore_check
$COMPOSE exec -T db sh -c "dropdb -U \"\$POSTGRES_USER\" --if-exists --force $check_db && createdb -U \"\$POSTGRES_USER\" $check_db"
$COMPOSE exec -T db sh -c "pg_restore -U \"\$POSTGRES_USER\" -d $check_db --no-owner --exit-on-error --single-transaction" < "$file"
query="
select 'версия схемы', version_num from alembic_version
union all select 'семей', count(*)::text from families
union all select 'участников', count(*)::text from members
union all select 'задач', count(*)::text from tasks
union all select 'строк журнала', count(*)::text from ledger_entries
union all (
  select 'баланс ' || m.name, a.balance || ', сумма журнала ' || coalesce(sum(e.amount), 0)
  from members m
  join accounts a on a.member_id = m.id
  left join ledger_entries e on e.account_id = a.id
  where m.role = 'child'
  group by m.name, a.balance
  order by m.name
);"
records() {
  $COMPOSE exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d $1 -tA -F ' | ' -v ON_ERROR_STOP=1" <<< "$query"
}
restored=$(records "$check_db")
current=$(records '"$POSTGRES_DB"')
echo "Копия $file, восстановлена в базу $check_db:"
echo "$restored" | sed 's/^/  /'
archive="${file%.dump}-exports.tar.gz"
if [ -f "$archive" ]; then
  echo "  журналов детских сессий в архиве: $(tar -tzf "$archive" | grep -c '\.csv$' || true)"
fi
if [ "$restored" = "$current" ]; then
  echo "Записи совпадают с рабочей базой"
else
  echo "Отличия от рабочей базы (нормально, если после копии были изменения):"
  diff <(echo "$restored") <(echo "$current") | sed 's/^/  /' || true
fi
# Баланс каждого счёта должен совпасть с суммой его строк журнала и в копии
$COMPOSE run --rm backend sh -c "DATABASE_URL=\"\${DATABASE_URL%/*}/$check_db\" python -m app.reconcile"
