# Сводка прогона: на каком RPS ответы вышли за бюджет, кто тратил процессор,
# были ли ожидания блокировок и сколько процессора уходит на запрос и запись.
import csv
import statistics
import sys
from pathlib import Path

P95_LIMIT_MS = 1000
# Порог ступени 2 плана деградации: с какой загрузки пула p95 выходит за этот бюджет
DEGRADE_P95_MS = 200
# Первые секунды ступени перцентиль Locust ещё помнит предыдущую ступень
WARMUP_SECONDS = 10
REQUESTS_PER_PASS = 7
WRITES_PER_PASS = 3


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


def number(value: str) -> float:
    return float(value.rstrip("%").replace("N/A", "0") or 0)


def main(results: Path) -> None:
    window = [r for r in rows(results / "window.csv") if number(r["rps"]) > 0]
    breach = next((r for r in window if number(r["p95_ms"]) > P95_LIMIT_MS), None)
    cpu = rows(results / "cpu.csv")
    locks = rows(results / "locks.csv")

    def cpu_of(name: str, start: float, end: float) -> list[float]:
        return [
            number(r["cpu"])
            for r in cpu
            if name in r["container"] and start <= float(r["time"]) <= end
        ]

    # Стоимость запроса считаем по последней минуте до выхода за бюджет
    # (или до конца теста), пока сервер ещё отвечает вовремя
    end = float((breach or window[-1])["time"])
    last_minute = [r for r in window if end - 60 <= float(r["time"]) <= end]
    rps = statistics.mean(number(r["rps"]) for r in last_minute)
    api = statistics.mean(cpu_of("backend", end - 60, end) or [0])
    db = statistics.mean(cpu_of("db", end - 60, end) or [0])
    writes_per_second = rps * WRITES_PER_PASS / REQUESTS_PER_PASS

    total = next(r for r in rows(results / "locust_stats.csv") if r["Name"] == "Aggregated")
    print("Итог нагрузочного теста")
    print(f"  запросов: {total['Request Count']}, ошибок: {total['Failure Count']}")
    print(f"  максимум: {max(number(r['rps']) for r in window):.0f} RPS")
    if breach:
        print(
            f"  p95 за последние секунды впервые выше {P95_LIMIT_MS} мс: "
            f"на {breach['seconds']} с теста, {breach['users']} семей, "
            f"{number(breach['rps']):.0f} RPS"
        )
    else:
        print(f"  p95 за последние секунды не превышал {P95_LIMIT_MS} мс")
    under = [r for r in window if number(r["p95_ms"]) <= P95_LIMIT_MS / 2]
    if under:
        best = max(under, key=lambda r: number(r["rps"]))
        print(
            f"  с запасом (p95 до {P95_LIMIT_MS // 2} мс): "
            f"до {number(best['rps']):.0f} RPS, {best['users']} семей"
        )
    print(
        f"  минута перед этим: {rps:.0f} RPS, процессор API {api:.0f}%, "
        f"базы {db:.0f}% (100% = одно ядро)"
    )
    print(f"  процессор API на запрос: {api * 10 / rps:.1f} мс")
    db_per_write = db * 10 / writes_per_second
    print(f"  процессор базы на запись (верхняя оценка, вместе с чтениями): {db_per_write:.1f} мс")
    waiting = [int(r["waiting_for_lock"]) for r in locks if r["waiting_for_lock"].isdigit()]
    print(
        f"  запросов в базе, ждущих блокировку: максимум {max(waiting, default=0)}, "
        f"в {sum(1 for w in waiting if w)} из {len(waiting)} замеров"
    )


def pool_by_step(results: Path, window: list[dict[str, str]]) -> None:
    path = results / "pool.csv"
    if not path.exists():
        return
    pool = [(float(r["time"]), int(r["checked_out"]) / int(r["limit"])) for r in rows(path)]
    steps: dict[int, list[dict[str, str]]] = {}
    for r in window:
        steps.setdefault(int(r["users"]), []).append(r)

    print()
    print(f"Ступени нагрузки и загрузка пула (p95 и пул — после {WARMUP_SECONDS} с ступени)")
    print("  семей | RPS | p95, мс | пул ср. | пул p95 | пул макс")
    table = []
    for users, part in sorted(steps.items()):
        start = float(part[0]["time"]) + WARMUP_SECONDS
        end = float(part[-1]["time"])
        settled = [r for r in part if float(r["time"]) >= start] or part
        used = sorted(u for t, u in pool if start <= t <= end)
        if not used:
            continue
        p95 = statistics.median(number(r["p95_ms"]) for r in settled)
        row = (
            users,
            statistics.mean(number(r["rps"]) for r in settled),
            p95,
            statistics.mean(used),
            used[int(0.95 * (len(used) - 1))],
            used[-1],
        )
        table.append(row)
        print(
            f"  {row[0]:5d} | {row[1]:3.0f} | {row[2]:7.0f} | {row[3]:6.0%} | "
            f"{row[4]:6.0%} | {row[5]:6.0%}"
        )
    over = next((i for i, row in enumerate(table) if row[2] > DEGRADE_P95_MS), None)
    if over is None:
        print(f"  p95 ни на одной ступени не превысил {DEGRADE_P95_MS} мс")
        return
    breach = table[over]
    print(
        f"  p95 впервые выше {DEGRADE_P95_MS} мс на ступени {breach[0]} семей: "
        f"{breach[2]:.0f} мс, пул занят в среднем на {breach[3]:.0%}"
    )
    if over:
        last_ok = table[over - 1]
        print(
            f"  последняя ступень в бюджете: {last_ok[0]} семей, p95 {last_ok[2]:.0f} мс, "
            f"пул в среднем {last_ok[3]:.0%}, p95 загрузки {last_ok[4]:.0%}"
        )


if __name__ == "__main__":
    results = Path(sys.argv[1] if len(sys.argv) > 1 else "loadtest/results")
    main(results)
    pool_by_step(results, [r for r in rows(results / "window.csv") if number(r["rps"]) > 0])
