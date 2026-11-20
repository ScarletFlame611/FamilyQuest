import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { click, closeApp, openApp, stubApi } from "../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const ADULT_SESSION = { role: "adult", accessToken: "adult-access", refreshToken: "adult-refresh" };

const MEMBERS = [
  { id: "mama", name: "Мама", role: "adult", avatar: "woman", age_group: null },
  { id: "masha", name: "Маша", role: "child", avatar: "fox", age_group: "6-7" },
];

let lastId = 0;
const entry = (kind: string, delta: number, label: string, reason: string | null = null) => ({
  id: `e${(lastId += 1)}`,
  kind,
  amount: delta,
  available_delta: delta,
  label,
  reason,
  created_at: "2026-11-20T10:00:00Z",
});

const MASHA_HISTORY = [
  entry("release", 20, "Мороженое"),
  entry("reversal", -10, "Убрать игрушки", "Игрушки снова на полу"),
  entry("reserve", -20, "Мороженое"),
  entry("spend", 0, "Мороженое"),
  entry("reserve", -20, "Мороженое"),
  entry("accrual", 10, "Убрать игрушки"),
  entry("accrual", 35, "Стартовые баллы"),
];

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(ADULT_SESSION));
  stubApi((_, path) => {
    return {
      "/api/me": { id: "mama", name: "Мама", role: "adult", avatar: "woman" },
      "/api/family": { id: "f", name: "Демо-семья", members: MEMBERS },
      "/api/balance": { balance: 0, reserved: 0, available: 0 },
      "/api/balances": [
        { member_id: "mama", balance: 0, reserved: 0, available: 0 },
        { member_id: "masha", balance: 15, reserved: 0, available: 15 },
      ],
      "/api/members/masha/ledger": MASHA_HISTORY,
    }[path];
  });
});

afterEach(closeApp);

const button = (container: HTMLElement, text: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent === text) ?? null;

describe("US-28: история начислений и списаний", () => {
  it("по умолчанию открыта история ребёнка, и её итог равен балансу для трат", async () => {
    const container = await openApp("/history");
    const rows = [...container.querySelectorAll(".list .kcard")];
    expect(rows).toHaveLength(MASHA_HISTORY.length);
    const total = rows.reduce((sum, row) => sum + Number(row.querySelector(".chip")?.textContent), 0);
    expect(container.textContent).toContain(`Можно потратить${total} ⭐`);
    expect(container.textContent).toContain("Отменено «Убрать игрушки»");
    expect(container.textContent).toContain("Игрушки снова на полу");
    expect(button(container, "Скачать CSV для Excel")).not.toBeNull();
  });

  it("фильтр «Отмены» оставляет только отмены", async () => {
    const container = await openApp("/history");
    await click(button(container, "Отмены"));
    const titles = [...container.querySelectorAll(".list .ktitle")].map((t) => t.textContent);
    expect(titles).toEqual(["Отменено «Убрать игрушки»"]);
  });
});
