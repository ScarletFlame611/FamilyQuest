# Сводка прогона: на каком RPS ответы вышли за бюджет, кто тратил процессор,
# были ли ожидания блокировок и сколько процессора уходит на запрос и запись.
import csv
import statistics
import sys
from pathlib import Path

P95_LIMIT_MS = 1000
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


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "loadtest/results"))
