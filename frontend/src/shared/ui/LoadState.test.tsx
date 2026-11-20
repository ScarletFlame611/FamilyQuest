import { afterEach, describe, expect, it, vi } from "vitest";

import { CHILD_SESSION, click, closeApp, openApp } from "../../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const ADULT_SESSION = { role: "adult", accessToken: "adult-access", refreshToken: "adult-refresh" };
const MASHA = { id: "masha", name: "Маша", role: "child", avatar: "fox", age_group: "6-7" };

const TOYS = {
  id: "t1",
  title: "Убрать игрушки",
  description: null,
  icon: "toys",
  points: 10,
  status: "assigned",
  assignee_member_id: "masha",
  assignee_name: "Маша",
  created_by_member_id: "mama",
  created_by_name: "Мама",
  reject_reason: null,
  marked_at: null,
  confirmed_at: null,
};

const ANSWERS: Record<string, unknown> = {
  "/api/me": { ...MASHA, family: { id: "f", name: "Демо" } },
  "/api/family": { id: "f", name: "Демо", members: [MASHA] },
  "/api/balance": { balance: 0, reserved: 0, available: 0 },
  "/api/tasks/my": [TOYS],
  "/api/tasks/pending": [],
  "/api/purchases/pending": [],
  "/api/balances": [],
};

// Первый запрос к указанному адресу падает без связи, следующие отвечают нормально
function offlineOnceFor(path: string, session: object) {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(session));
  let failed = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const pathname = new URL(url, "http://localhost").pathname;
      if (pathname === path && !failed) {
        failed = true;
        throw new TypeError("Failed to fetch");
      }
      return new Response(JSON.stringify(ANSWERS[pathname] ?? []), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
}

const button = (container: HTMLElement, text: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent === text) ?? null;

afterEach(closeApp);

describe("экраны не остаются молча пустыми", () => {
  it("у ребёнка без связи видно ошибку и кнопку «Ещё раз», повтор загружает дела", async () => {
    offlineOnceFor("/api/tasks/my", CHILD_SESSION);
    const container = await openApp("/kid");
    expect(container.textContent).toContain("Нет связи с сервером");
    await click(button(container, "Ещё раз"));
    expect(container.querySelector('[aria-label="Убрать игрушки"]')).not.toBeNull();
    expect(container.textContent).not.toContain("Нет связи с сервером");
  });

  it("у взрослого то же с кнопкой «Повторить»", async () => {
    offlineOnceFor("/api/tasks/pending", ADULT_SESSION);
    const container = await openApp("/");
    expect(container.textContent).toContain("Нет связи с сервером");
    await click(button(container, "Повторить"));
    expect(container.textContent).toContain("Нет дел, которые ждут проверки.");
  });
});
