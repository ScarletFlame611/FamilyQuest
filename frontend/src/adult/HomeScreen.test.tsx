import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { click, closeApp, openApp, stubApi } from "../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const ADULT_SESSION = { role: "adult", accessToken: "adult-access", refreshToken: "adult-refresh" };

function task(id: string, title: string, points: number, child: string) {
  return {
    id,
    title,
    description: null,
    icon: "bed",
    points,
    status: "marked",
    assignee_member_id: child,
    assignee_name: child === "masha" ? "Маша" : "Петя",
    created_by_member_id: "mama",
    created_by_name: "Мама",
    reject_reason: null,
    marked_at: "2026-11-20T10:00:00Z",
    confirmed_at: null,
  };
}

const PENDING = [
  task("t1", "Заправить кровать", 7, "masha"),
  task("t2", "Почистить зубы", 3, "petya"),
  task("t3", "Собрать рюкзак", 5, "masha"),
];

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(ADULT_SESSION));
  stubApi((method, path) => {
    if (method === "POST" && path === "/api/tasks/confirm-all") {
      return {
        confirmed: [PENDING[0], PENDING[2]],
        skipped: [{ task_id: "t2", title: "Почистить зубы", reason: "Дело уже засчитано" }],
      };
    }
    return {
      "/api/me": { id: "mama", name: "Мама", role: "adult", avatar: "woman" },
      "/api/family": { id: "f", name: "Демо-семья", members: [] },
      "/api/balance": { balance: 0, reserved: 0, available: 0 },
      "/api/tasks/pending": PENDING,
    }[path];
  });
});

afterEach(closeApp);

const button = (container: HTMLElement, text: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent === text) ?? null;

describe("US-58: подтвердить всю очередь", () => {
  it("показывает итог по детям и отправляет все дела одним запросом", async () => {
    const container = await openApp("/");
    await click(button(container, "Подтвердить всё (3)"));
    const text = container.textContent ?? "";
    expect(text).toContain("Засчитать все дела (3)?");
    expect(text).toMatch(/Маша\+12 ⭐/);
    expect(text).toMatch(/Петя\+3 ⭐/);

    await click(button(container, "Да, засчитать всё"));
    const posts = vi
      .mocked(fetch)
      .mock.calls.filter(([, init]) => init?.method === "POST");
    expect(posts).toHaveLength(1);
    const [url, init] = posts[0];
    expect(String(url)).toMatch(/\/api\/tasks\/confirm-all$/);
    expect(JSON.parse(String(init?.body))).toEqual({ task_ids: ["t1", "t2", "t3"] });
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBeTruthy();
    expect(container.textContent).toContain("«Почистить зубы» — дело уже засчитано");
  });

  it("«Не сейчас» закрывает итог без запроса", async () => {
    const container = await openApp("/");
    await click(button(container, "Подтвердить всё (3)"));
    await click(button(container, "Не сейчас"));
    expect(container.textContent).not.toContain("Засчитать все дела (3)?");
    expect(vi.mocked(fetch).mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });
});
