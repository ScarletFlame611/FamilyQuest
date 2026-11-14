#!/usr/bin/env bash
# Копия базы и журналов детских сессий (exports/) в backups/ с общей меткой времени,
# затем очистка старых копий. --no-clean — без очистки.
# Для локального окружения: COMPOSE="docker compose" ./deploy/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# Сообщение уходит в stderr: cron пришлёт его на MAILTO, а обычный вывод останется в логе
trap 'echo "FamilyQuest: копия не создана, ошибка в строке $LINENO" >&2' ERR
COMPOSE=${COMPOSE:-docker compose -f docker-compose.prod.yml --env-file .env.prod}
mkdir -p backups exports
name="backups/familyquest-$(date -u +%Y%m%d-%H%M%S)"
# Пишем во временные файлы, чтобы оборванная копия не выглядела готовой.
# Имя базы и пользователя берутся из окружения контейнера, пароль наружу не попадает
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$name.part"
# Копия, которую pg_restore не может прочитать, хуже, чем никакой
$COMPOSE exec -T db pg_restore -l < "$name.part" > /dev/null
tar -czf "$name-exports.tar.gz.part" exports
# Имя .dump получает только проверенная копия: по нему очистка отличает пригодные
mv "$name-exports.tar.gz.part" "$name-exports.tar.gz"
mv "$name.part" "$name.dump"
echo "Копия: $name.dump ($(du -h "$name.dump" | cut -f1)), $name-exports.tar.gz"
if [ -n "${BACKUP_MIRROR_DIR:-}" ]; then
  mkdir -p "$BACKUP_MIRROR_DIR"
  cp "$name.dump" "$name-exports.tar.gz" "$BACKUP_MIRROR_DIR/"
  echo "Скопировано в $BACKUP_MIRROR_DIR"
fi
[ "${1:-}" = "--no-clean" ] && exit 0
./deploy/backup-clean.sh
if [ -n "${BACKUP_MIRROR_DIR:-}" ]; then
  BACKUP_DIR="$BACKUP_MIRROR_DIR" ./deploy/backup-clean.sh
fi
