#!/usr/bin/env bash
# Оставляет BACKUP_KEEP последних копий (по умолчанию 14), остальные удаляет вместе
# с архивом exports. --dry-run только печатает, что сохранится и что будет удалено.
# Каталог — BACKUP_DIR, по умолчанию backups/.
set -euo pipefail
cd "$(dirname "$0")/.."
dir=${BACKUP_DIR:-backups}
keep=${BACKUP_KEEP:-14}
# Свежая пригодная копия не удаляется ни при каких настройках
[ "$keep" -ge 1 ] || { echo "BACKUP_KEEP должен быть не меньше 1" >&2; exit 1; }
dry=false
[ "${1:-}" = "--dry-run" ] && dry=true
# Метка времени в имени сортируется как строка, поэтому порядок не зависит
# от даты изменения файла, которая теряется при копировании на другой диск
dumps=$(find "$dir" -maxdepth 1 -name 'familyquest-*.dump' | sort -r)
kept=$(echo "$dumps" | sed '/^$/d' | head -n "$keep")
old=$(echo "$dumps" | sed '/^$/d' | tail -n +$((keep + 1)))
victims=$(
  echo "$old" | while read -r f; do
    [ -n "$f" ] || continue
    echo "$f"
    if [ -f "${f%.dump}-exports.tar.gz" ]; then echo "${f%.dump}-exports.tar.gz"; fi
  done
  # Незавершённые копии старше часа остались от упавших запусков
  find "$dir" -maxdepth 1 -name '*.part' -mmin +60
)
echo "Сохраняются копии ($(echo "$kept" | sed '/^$/d' | wc -l)):"
echo "$kept" | sed '/^$/d; s/^/  /'
if [ -z "$victims" ]; then
  echo "Удалять нечего"
  exit 0
fi
echo "К удалению:"
echo "$victims" | sed 's/^/  /'
$dry && { echo "Пробный запуск: ничего не удалено"; exit 0; }
echo "$victims" | while read -r f; do rm -- "$f"; done
echo "Удалено файлов: $(echo "$victims" | wc -l)"
