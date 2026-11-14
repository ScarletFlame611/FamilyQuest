# Квест 7. Миграции и бэкапы проекта FamilyQuest

**Проект:** FamilyQuest — веб-сервис, в котором домашние дела семьи становятся задачами с ценой в баллах
**Дата:** 14 ноября 2026
**Участники, работавшие очно:** Суслова Анастасия, Урясьева Ксения

**СУБД:** PostgreSQL 16 в Docker Compose. **Инструмент миграций:** Alembic (SQLAlchemy 2.0).

## Что проверено, а что подготовлено

| | Статус |
|---|---|
| Схема пустой БД из миграций, новая миграция на заполненной БД, повторный запуск, откат на шаг | **проверено локально** |
| Копия БД и `exports/`, проверка копии, восстановление в отдельную пустую БД со сверкой записей | **проверено локально** |
| Восстановление рабочей БД из копии | **проверено локально** |
| Очистка старых копий: сначала список, потом удаление, свежая копия остаётся | **проверено локально** |
| Копия во второй каталог (`BACKUP_MIRROR_DIR`) | **проверено локально** на другом каталоге того же диска |
| Сообщение об ошибке, если копия не создана | **проверено локально**: база остановлена → код выхода 1 и сообщение в stderr |
| Ежедневное расписание через cron, письмо на `MAILTO`, внешний диск на VPS | **подготовлено** для развёртывания, не запускалось |
| Новый порядок в [`deploy/up.sh`](deploy/up.sh): база → миграции → приложение | **подготовлено**, на стенде не запускалось |

Все проверки проходили в отдельном проекте Docker Compose `fq-check`, у которого свой пустой том БД. Рабочая база разработки не менялась. После проверок окружение удалено.

---

## 1. Политика миграций

### Инструмент, файлы, порядок

- Инструмент — **Alembic**, настройки в [`backend/alembic.ini`](backend/alembic.ini), окружение в [`backend/migrations/env.py`](backend/migrations/env.py).
- Файлы миграций лежат в [`backend/migrations/versions/`](backend/migrations/versions/). Имя файла строится как `ГГГГММДД_<ревизия>_<описание>.py`, шаблон задан в `file_template` в `alembic.ini`.
- Порядок применения определяет не имя файла, а цепочка `down_revision` внутри файлов: каждая миграция ссылается на предыдущую. Ревизии пронумерованы по порядку `0001…0007`, чтобы цепочку было легко читать.

| Ревизия | Файл | Что делает |
|---|---|---|
| 0001 | [`20261014_0001_init.py`](backend/migrations/versions/20261014_0001_init.py) | пустая стартовая точка |
| 0002 | [`20261014_0002_schema.py`](backend/migrations/versions/20261014_0002_schema.py) | основные таблицы: `families`, `users`, `members`, `accounts`, `ledger_entries`, `tasks`, `rewards`, `reward_purchases`, `goals`, `child_sessions`, `idempotency_keys` |
| 0003 | [`20261014_0003_auth.py`](backend/migrations/versions/20261014_0003_auth.py) | `refresh_tokens`, поля блокировки входа |
| 0004 | [`20261014_0004_child_events.py`](backend/migrations/versions/20261014_0004_child_events.py) | журнал действий ребёнка `child_events` |
| 0005 | [`20261016_0005_child_profile.py`](backend/migrations/versions/20261016_0005_child_profile.py) | возрастная группа и согласие родителя: поле добавляется, заполняется `UPDATE` у существующих детей, только потом включается ограничение |
| 0006 | [`20261016_0006_task_description.py`](backend/migrations/versions/20261016_0006_task_description.py) | описание задачи |
| **0007** | [`20261114_0007_tasks_family_status.py`](backend/migrations/versions/20261114_0007_tasks_family_status.py) | **новая в этом квесте:** составной индекс `tasks(family_id, status)` для выборок «общая доска» и «ждут проверки» |

Правила:

- Миграции не импортируют модели приложения. Каждая миграция описывает схему такой, какой она была в момент изменения, поэтому её не ломают будущие правки моделей.
- Применённые миграции не редактируются. Любое следующее изменение оформляется новым файлом. Так 0007 добавлена отдельной ревизией, а не правкой 0002, где создаётся `tasks`.
- После `--autogenerate` файл правится вручную: Alembic теряет частичные индексы и индексы по выражениям. Примеры из 0002: `uq_users_email_lower` по `lower(email)` и `uq_goals_active_family` с условием `WHERE is_active`.
- Изменение схемы вносится одновременно в модель (`backend/app/modules/*/models.py`) и в миграцию. Совпадение проверяет `alembic check`.

### Команды

Все команды выполняются из корня репозитория. Для окружения разработки:

```bash
docker compose run --rm backend alembic revision --autogenerate -m "описание"  # создать миграцию
docker compose run --rm backend alembic upgrade head --sql                     # посмотреть SQL, не применяя
docker compose run --rm backend alembic current                                # текущая ревизия БД
docker compose run --rm backend alembic history                                # цепочка ревизий
docker compose run --rm backend alembic upgrade head                           # применить
docker compose run --rm backend alembic check                                  # модели == миграции?
docker compose run --rm backend alembic downgrade -1                           # откатить на шаг
```

### Таблица учёта `alembic_version`

Alembic хранит в БД **не список всех применённых миграций, а текущую ревизию**:

| Поле | Тип | Смысл |
|---|---|---|
| `version_num` | `varchar(32)`, первичный ключ | идентификатор ревизии, до которой доведена схема |

При линейной истории, как у нас, в таблице всегда **одна строка**. При `upgrade` Alembic выполняет шаги, которые идут в цепочке после этой ревизии, и обновляет строку. При `downgrade` строка меняется на предыдущую ревизию. Если таблица пустая или её нет, база ещё не размечена, и `upgrade head` применит все миграции с начала. Пример из нашей БД до и после новой миграции:

```
 version_num          version_num
-------------   →    -------------
 0006                 0007
```

### Кто и когда запускает, порядок

| Где | Кто | Когда и как |
|---|---|---|
| Локально | разработчик | после `git pull`, если в `versions/` появились новые файлы, и после создания своей миграции: `docker compose run --rm backend alembic upgrade head` |
| CI (GitLab CI [`.gitlab-ci.yml`](.gitlab-ci.yml), GitHub Actions [`.github/workflows/ci.yml`](.github/workflows/ci.yml)) | автоматически при каждом push | `alembic upgrade head` на пустой БД, затем `alembic check`, затем тесты |
| Тесты ([`backend/tests/conftest.py`](backend/tests/conftest.py)) | автоматически | тестовая БД создаётся, если её нет, затем `downgrade base` и `upgrade head`. Так каждый прогон проверяет и откат, и применение |
| Стенд ([`deploy/up.sh`](deploy/up.sh)) | тот, кто обслуживает стенд | один скрипт: **БД** (`up -d db`, ждёт `pg_isready`) → **миграции** → демо-данные → **приложение** (`up -d`) |

Порядок «БД → миграции → приложение» обеспечивают `healthcheck` с `pg_isready` в [`docker-compose.yml`](docker-compose.yml) и `depends_on: condition: service_healthy`. Без них миграции стартовали бы раньше, чем база начнёт принимать соединения.

### Проверка новой миграции и ошибки

1. Прочитать сгенерированный файл, вернуть потерянные частичные индексы и выражения.
2. `alembic upgrade head` локально на базе **с данными**, затем `alembic check`: ответ должен быть `No new upgrade operations detected`.
3. `alembic downgrade -1` и снова `upgrade head`: откат должен проходить.
4. Тесты (`pytest`). В CI то же самое повторяется на чистой базе.

**Если миграция упала.** В PostgreSQL DDL выполняется в транзакции, поэтому упавшая миграция откатывается целиком, а `alembic_version` остаётся на прошлой ревизии. Если миграция ещё нигде не применена, исправляем файл и запускаем снова. Если она уже применена у кого-то ещё, файл не трогаем и пишем следующую миграцию.

**Ограничения отката.** `downgrade` есть у каждой ревизии, но он восстанавливает **только схему, не данные**. Откат 0006 удалит описания задач, откат 0005 удалит возрастные группы, откат 0002 удалит все таблицы. Поэтому на стенде откат делается не через `downgrade`, а восстановлением копии, снятой **перед** миграцией: `./deploy/backup.sh`, затем `./deploy/up.sh`. `downgrade` используется в тестах и при локальной разработке.

---

## 2. Политика резервного копирования

### Что копируется

| Данные | Где живут | Копируются |
|---|---|---|
| База PostgreSQL: семьи, задачи, журнал баллов, детские сессии | том Docker `db-data` | да, `pg_dump -Fc` |
| Журналы детских сессий (CSV для исследования интерфейса с детьми) | каталог `exports/` на диске | да, `tar.gz` |
| Секреты (`.env.prod`) | только у команды | **нет**: хранятся отдельно, в копии их нет, и в git они не попадают |
| Код, миграции, скрипты | git | нет, восстанавливаются из репозитория |

**Согласованность БД и файлов.** Одна копия состоит из двух файлов с общей меткой времени: `familyquest-<время>.dump` и `familyquest-<время>-exports.tar.gz`. Файлы в `exports/` пишет только скрипт демо-данных: перед пересозданием семьи он выгружает её журналы. Новые файлы появляются там только во время `reset-demo.sh`, а не по ходу работы API. Поэтому копия, снятая между сбросами, согласована. Скрипт очистки удаляет пару целиком, а восстановление возвращает оба файла.

### RPO и RTO

- **RPO — 24 часа на VPS, одна сессия с ребёнком во время тестов.** Копия делается раз в сутки по расписанию, а во время тестов с детьми ещё и вручную после каждой сессии, до `reset-demo.sh`. Это PoC с демо-данными. Потерю дня демонстрационных действий можно восстановить сидом. Нельзя терять только результаты тестов с детьми, поэтому их копируем после каждой сессии.
- **RTO — 30 минут.** Само восстановление (`restore.sh`) занимает меньше минуты, база весит около 40 КБ. Остальное время уходит на то, чтобы заметить проблему и выбрать копию. На PoC нет пользователей, которым сервис нужен постоянно: при сбое тест с ребёнком переносится, поэтому дольше держать время восстановления в минутах нет смысла.

### Частота, хранилище, доступ, ошибки

- **Частота:** раз в сутки в 03:30 через cron на VPS (подготовлено). Вручную — после каждой сессии с ребёнком и **перед каждой миграцией** на стенде.
- **Где:** `backups/` рядом с проектом и копия в `BACKUP_MIRROR_DIR`. На VPS это отдельный подключённый диск `/mnt/backup/familyquest`, на ноутбуке — внешний USB-диск. Копия, лежащая только рядом с исходной базой, при отказе диска пропадает вместе с ней.
- **Доступ:** только участники команды с доступом к стенду. В копиях есть имена детей и хеши паролей, поэтому `backups/` закрыт в [`.gitignore`](.gitignore), а копии не выкладываются в общие облака без шифрования.
- **Как узнаём об ошибке:** `backup.sh` при любой ошибке завершается с ненулевым кодом и пишет в stderr `FamilyQuest: копия не создана, ошибка в строке N`. В crontab обычный вывод идёт в `backups/backup.log`, а stderr cron отправляет письмом на `MAILTO` (подготовлено).

### Хранение и очистка

- Храним **14 последних копий** (`BACKUP_KEEP=14`). При ежедневных копиях это две недели: столько длится цикл «тест с детьми → правки → следующий тест». Ошибку в баллах, которую родитель заметит через несколько дней, можно разобрать по копии. Копия весит около 40 КБ, так что место не ограничивает. Хранить дольше мы не хотим: это лишние персональные данные детей.
- Удаляются копии старше 14-й по метке времени вместе с архивом `exports`, а также незавершённые файлы `*.part` старше часа (остатки упавших запусков).
- **Как сохраняется свежая пригодная копия:**
  1. Имя `.dump` получает только копия, которую прочитал `pg_restore -l`. Пока копия не проверена, она лежит как `.part`, а очистка такие файлы не считает копиями.
  2. Очистка запускается только после успешного создания новой копии.
  3. `BACKUP_KEEP` меньше 1 скрипт не принимает, так что самая свежая копия не удаляется никогда.
  4. Перед восстановлением `restore.sh` снимает копию текущего состояния без очистки, поэтому не может удалить копию, которую восстанавливает.
- Восстановление проверяет `./deploy/restore-check.sh` раз в неделю и после каждого изменения скриптов копирования. Это делает участник, который обслуживает стенд.

### Файлы и команды

| Файл | Назначение |
|---|---|
| [`deploy/backup.sh`](deploy/backup.sh) | копия БД и `exports/` → проверка → второй каталог → очистка |
| [`deploy/backup-clean.sh`](deploy/backup-clean.sh) | очистка, `--dry-run` печатает список без удаления |
| [`deploy/restore-check.sh`](deploy/restore-check.sh) | восстановление в **отдельную пустую БД** `familyquest_restore_check` и сверка записей с рабочей |
| [`deploy/restore.sh`](deploy/restore.sh) | замена рабочей БД копией, с подтверждением и страховочной копией |
| [`deploy/README.md`](deploy/README.md) | инструкция для стенда, раздел «Резервные копии» |

```bash
./deploy/backup.sh                                    # создать копию (и очистить старые)
./deploy/backup-clean.sh --dry-run                    # что будет удалено
./deploy/backup-clean.sh                              # очистка
./deploy/restore-check.sh [файл.dump]                 # проверить копию в отдельной БД
./deploy/restore.sh backups/familyquest-<время>.dump  # восстановить рабочую БД
```

Переменные: `COMPOSE` (по умолчанию используется стенд `docker-compose.prod.yml`, для разработки задайте `COMPOSE="docker compose"`), `BACKUP_KEEP` (14), `BACKUP_MIRROR_DIR` (второй каталог), `BACKUP_DIR` (каталог для очистки).

---

## 3. Проверки на данных проекта

### Как повторить

Нужны Docker и Git Bash (на Windows) или bash. Используется отдельный проект Compose `fq-check`, поэтому ваша база разработки не пострадает. Файл `.env` нужен тот же, что для разработки (`cp .env.example .env`).

```bash
export COMPOSE="docker compose -p fq-check"
# если образ бэкенда уже собран для основного проекта, сборку можно пропустить:
docker tag familyquest-backend fq-check-backend
sql() { $COMPOSE exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<< "$1"; }
$COMPOSE up -d db
```

В конце окружение удаляется:

```bash
docker compose -p fq-check down -v && rm -rf backups
```

### 3.1. Миграция заполненной БД

```bash
$COMPOSE run --rm backend alembic current        # пусто: база не размечена
$COMPOSE run --rm backend alembic upgrade 0006   # схема до новой миграции
$COMPOSE run --rm backend python -m app.seed     # тестовые записи
sql "select * from alembic_version"
sql "select status, count(*) from tasks group by status order by 1"
sql "select m.name, a.balance from accounts a join members m on m.id = a.member_id order by 1"
```

Результат:

```
Running upgrade  -> 0001, init
Running upgrade 0001 -> 0002, schema
... 
Running upgrade 0005 -> 0006, task_description
Демо-семья создана. Вход: mama@familyquest.local, papa@familyquest.local

 version_num        status   | count       name | balance
-------------      ----------+------      ------+---------
 0006               assigned  |  3         Мама |     110
                    confirmed | 14         Маша |      35
                    open      |  3         Папа |      85
                                           Петя |      30
```

Новая миграция с индексом:

```bash
$COMPOSE run --rm backend alembic upgrade head
sql "select * from alembic_version"
sql "select indexname, indexdef from pg_indexes where tablename = 'tasks' order by 1"
```

```
Running upgrade 0006 -> 0007, tasks_family_status

 version_num
-------------
 0007

 ix_tasks_assignee_member_id | CREATE INDEX ... (assignee_member_id)
 ix_tasks_family_id          | CREATE INDEX ... (family_id)
 ix_tasks_family_id_status   | CREATE INDEX ix_tasks_family_id_status ON public.tasks USING btree (family_id, status)   ← новый
 pk_tasks                    | CREATE UNIQUE INDEX pk_tasks ... (id)
```

**Сохранность данных:** запросы по задачам и балансам после миграции вернули те же значения: 3 / 14 / 3 задачи и балансы 110 / 35 / 85 / 30.

**Повторный запуск:**

```bash
$COMPOSE run --rm backend alembic upgrade head   # ни одной строки "Running upgrade"
$COMPOSE run --rm backend alembic current        # 0007 (head)
$COMPOSE run --rm backend alembic check          # No new upgrade operations detected.
```

Выполненные шаги заново не применяются: Alembic видит в `alembic_version` значение `0007`, а после неё в цепочке ничего нет.

**Откат на шаг:**

```bash
$COMPOSE run --rm backend alembic downgrade -1   # Running downgrade 0007 -> 0006
$COMPOSE run --rm backend alembic current        # 0006
$COMPOSE run --rm backend alembic upgrade head   # Running upgrade 0006 -> 0007
```

### 3.2. Копия и восстановление в отдельную пустую БД

```bash
./deploy/backup.sh --no-clean
./deploy/restore-check.sh
```

Скрипт создаёт пустую базу `familyquest_restore_check` на том же сервере, восстанавливает в неё самую свежую копию и выполняет одни и те же запросы к ней и к рабочей базе:

```
Копия backups/familyquest-20261114-100535.dump, восстановлена в базу familyquest_restore_check:
  версия схемы | 0007
  семей | 1
  участников | 4
  задач | 20
  строк журнала | 15
  баланс Маша | 35, сумма журнала 35
  баланс Петя | 30, сумма журнала 30
  журналов детских сессий в архиве: 12
Записи совпадают с рабочей базой
Сверка: баланс всех счетов равен сумме журнала
```

Чтобы показать, что копия независима от рабочей базы, мы удалили в рабочей базе задачи с общей доски (`delete from tasks where status='open'`, 3 строки) и запустили проверку ещё раз. В восстановленной базе остались 20 задач, скрипт показал расхождение:

```
Отличия от рабочей базы (нормально, если после копии были изменения):
  < задач | 20
  > задач | 17
Сверка: баланс всех счетов равен сумме журнала
```

После этого рабочая база восстановлена из той же копии:

```bash
echo yes | ./deploy/restore.sh backups/familyquest-20261114-100535.dump
sql "select count(*) from tasks"   # 20
```

```
Копия: backups/familyquest-20261114-100618.dump ...      ← страховочная копия перед заменой
Сверка: баланс всех счетов равен сумме журнала
База восстановлена из backups/familyquest-20261114-100535.dump
```

Если на вопрос ответить `no`, скрипт печатает «Отменено», завершается с кодом 1 и не трогает базу.

### 3.3. Очистка на тестовых копиях

Создали 4 копии и один «оборванный» файл старше часа:

```bash
for i in 1 2 3 4; do ./deploy/backup.sh --no-clean; sleep 1; done
touch -d '2 hours ago' backups/familyquest-20261114-000000.part
```

Сначала список (`BACKUP_KEEP=2`, чтобы на четырёх копиях было что удалить):

```
$ BACKUP_KEEP=2 ./deploy/backup-clean.sh --dry-run
Сохраняются копии (2):
  backups/familyquest-20261114-100535.dump
  backups/familyquest-20261114-100533.dump
К удалению:
  backups/familyquest-20261114-100530.dump
  backups/familyquest-20261114-100530-exports.tar.gz
  backups/familyquest-20261114-100527.dump
  backups/familyquest-20261114-100527-exports.tar.gz
  backups/familyquest-20261114-000000.part
Пробный запуск: ничего не удалено
```

После пробного запуска в каталоге осталось 9 файлов, как и было. Затем очистка:

```
$ BACKUP_KEEP=2 ./deploy/backup-clean.sh
...
Удалено файлов: 5
$ ls backups
familyquest-20261114-100533-exports.tar.gz
familyquest-20261114-100533.dump
familyquest-20261114-100535-exports.tar.gz
familyquest-20261114-100535.dump
```

**Удалены** две старые пары и файл `.part`. **Сохранены** две последние пары. Самая свежая копия `100535` после очистки успешно восстановлена (`restore-check.sh`, `restore.sh` выше), то есть она пригодна.

Защита от ошибки в настройке:

```
$ BACKUP_KEEP=0 ./deploy/backup-clean.sh
BACKUP_KEEP должен быть не меньше 1        (код выхода 1, ничего не удалено)
```

### 3.4. Второй каталог и ошибка копирования

```
$ BACKUP_MIRROR_DIR=<другой каталог> BACKUP_KEEP=2 ./deploy/backup.sh
Копия: backups/familyquest-20261114-100614.dump (40K), backups/familyquest-20261114-100614-exports.tar.gz
Скопировано в <другой каталог>
...                                   ← очистка в backups/ и во втором каталоге
```

Остановили базу и запустили копирование:

```
$ docker compose -p fq-check stop db && ./deploy/backup.sh
service "db" is not running
FamilyQuest: копия не создана, ошибка в строке 14      (код выхода 1)
```

Готовая копия `.dump` при этом не появилась. Остался только `familyquest-…-100635.part`, и очистка удалит его через час.

### 3.5. Тесты и линтер после изменения модели

```bash
$COMPOSE run --rm backend sh -c "ruff check && ruff format --check && pytest -q"
```

```
All checks passed!
83 files already formatted
122 passed
```

---

## Что изменено в репозитории

- [`backend/migrations/versions/20261114_0007_tasks_family_status.py`](backend/migrations/versions/20261114_0007_tasks_family_status.py) — новая миграция;
- [`backend/app/modules/tasks/models.py`](backend/app/modules/tasks/models.py) — индекс в модели, чтобы `alembic check` оставался пустым;
- [`deploy/backup.sh`](deploy/backup.sh), [`deploy/backup-clean.sh`](deploy/backup-clean.sh), [`deploy/restore-check.sh`](deploy/restore-check.sh), [`deploy/restore.sh`](deploy/restore.sh) — новые скрипты;
- [`deploy/up.sh`](deploy/up.sh) — миграции теперь применяются до запуска API;
- [`deploy/README.md`](deploy/README.md) — раздел «Резервные копии»;
- [`.gitignore`](.gitignore) — каталог `backups/`: дампы и секреты в git не попадают.
