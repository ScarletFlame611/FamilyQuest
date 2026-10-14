# Один проход основного сценария — 6 запросов: дела ребёнка, отметка, очередь взрослого,
# подтверждение, повторная очередь, баланс ребёнка. Каждый виртуальный пользователь —
# отдельная семья из подготовленных app.seed_load.

import itertools
import secrets
import time

from locust import HttpUser, LoadTestShape, between, events, task

PIN = "2580"
P95_LIMIT_MS = 1000
FAIL_LIMIT = 0.01

_numbers = itertools.count(1)


@events.init_command_line_parser.add_listener
def add_options(parser):
    parser.add_argument("--load-password", required=True, help="пароль взрослых нагрузочных семей")
    parser.add_argument("--load-families", type=int, default=400)
    parser.add_argument("--step-users", type=int, default=20)
    parser.add_argument("--step-seconds", type=int, default=30)


class Family(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        self.number = next(_numbers)
        options = self.environment.parsed_options
        if self.number > options.load_families:
            raise RuntimeError("Подготовлено меньше семей, чем пользователей в тесте")
        self.email = f"load-{self.number:04d}@familyquest.local"
        self.adult = self._login()
        response = self.client.post(
            "/api/child-mode/start",
            json={"child_id": self._child_id()},
            headers=self._auth(self.adult),
            name="подготовка: детский режим",
        )
        self.child = response.json()

    def _login(self) -> dict:
        response = self.client.post(
            "/api/auth/login",
            json={"email": self.email, "password": self.environment.parsed_options.load_password},
            name="подготовка: вход",
        )
        return response.json()

    def _child_id(self) -> str:
        members = self.client.get(
            "/api/family", headers=self._auth(self.adult), name="подготовка: семья"
        ).json()["members"]
        return next(m["id"] for m in members if m["role"] == "child")

    @staticmethod
    def _auth(tokens: dict, key: bool = False) -> dict:
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        if key:
            headers["Idempotency-Key"] = secrets.token_hex(16)
        return headers

    @task
    def critical_path(self):
        my = self.client.get("/api/tasks/my", headers=self._auth(self.child), name="1 дела ребёнка")
        todo = [t for t in my.json() if t["status"] == "assigned"] if my.ok else []
        if not todo:
            return
        task_id = todo[0]["id"]
        self.client.post(
            f"/api/tasks/{task_id}/mark",
            headers=self._auth(self.child, key=True),
            name="2 отметка",
        )
        self.client.get("/api/tasks/pending", headers=self._auth(self.adult), name="3 очередь")
        self.client.post(
            f"/api/tasks/{task_id}/confirm",
            headers=self._auth(self.adult, key=True),
            name="4 подтверждение",
        )
        self.client.get(
            "/api/tasks/pending", headers=self._auth(self.adult), name="5 очередь снова"
        )
        self.client.get("/api/balance", headers=self._auth(self.child), name="6 баланс")


# Каждые --step-seconds добавляет --step-users семей, пока ответы укладываются в бюджет.
# Весь тест короче 15 минут, чтобы не истекли access-токены виртуальных семей.
class StepUntilSlow(LoadTestShape):
    over_limit = 0
    last_logged = -1

    def tick(self):
        stats = self.runner.environment.stats.total
        options = self.runner.environment.parsed_options
        families, step_users, step_seconds = (
            options.load_families,
            options.step_users,
            options.step_seconds,
        )
        run_time = self.get_run_time()
        p95 = stats.get_current_response_time_percentile(0.95) or 0
        # История Locust хранит перцентили с начала теста; для поиска момента, когда
        # ответы вышли за бюджет, нужен перцентиль последних секунд, его пишем сами
        if int(run_time) != self.last_logged:
            self.last_logged = int(run_time)
            with open("results/window.csv", "a", encoding="utf-8") as file:
                if file.tell() == 0:
                    file.write("time,seconds,users,rps,p95_ms,failures\n")
                file.write(
                    f"{time.time():.0f},{int(run_time)},{self.runner.user_count},"
                    f"{stats.current_rps:.1f},{p95},{stats.num_failures}\n"
                )
        if run_time > step_seconds:
            failing = stats.num_requests and stats.num_failures / stats.num_requests > FAIL_LIMIT
            # Два окна подряд выше порога, чтобы не останавливаться из-за одного всплеска
            self.over_limit = self.over_limit + 1 if (p95 > P95_LIMIT_MS or failing) else 0
            if self.over_limit >= 2:
                return None
        users = min(families, step_users * (1 + int(run_time // step_seconds)))
        if users >= families and run_time > step_seconds * (families // step_users + 2):
            return None
        return users, step_users


@events.quitting.add_listener
def report(environment, **_):
    stats = environment.stats.total
    print(
        f"ИТОГ: пользователей {environment.runner.user_count}, "
        f"запросов {stats.num_requests}, ошибок {stats.num_failures}, "
        f"p95 {stats.get_response_time_percentile(0.95)} мс, "
        f"текущий RPS {stats.current_rps:.1f}"
    )
