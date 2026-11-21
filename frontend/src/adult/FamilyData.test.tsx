import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { click, closeApp, openApp, stubApi } from "../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const ADULT_SESSION = { role: "adult", accessToken: "adult-access", refreshToken: "adult-refresh" };

function exported(id: string, status: string, extra: object = {}) {
  return {
    id,
    job_id: `job-${id}`,
    status,
    job_status: status === "ready" ? "done" : "queued",
    attempts: status === "ready" ? 1 : 0,
    max_attempts: 3,
    file_size: status === "ready" ? 2675 : null,
    error: null,
    created_at: "2026-11-21T09:55:00Z",
    ready_at: status === "ready" ? "2026-11-21T09:55:05Z" : null,
    expires_at: status === "ready" ? "2026-11-28T09:55:05Z" : null,
    ...extra,
  };
}

let list: object[] = [];

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(ADULT_SESSION));
  list = [];
  stubApi((method, path) => {
    if (method === "POST" && path === "/api/family/exports") {
      list = [exported("e1", "pending")];
      return list[0];
    }
    return {
      "/api/me": { id: "mama", name: "Мама", role: "adult", avatar: "woman" },
      "/api/balance": { balance: 0, reserved: 0, available: 0 },
      "/api/family/exports": list,
    }[path];
  });
});

afterEach(closeApp);

const button = (container: HTMLElement, text: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent === text) ?? null;

describe("US-48: выгрузка данных семьи", () => {
  it("архив ставится в очередь, и экран показывает, что он готовится", async () => {
    const container = await openApp("/family-data");
    expect(container.textContent).toContain("Выгрузок пока не было");

    await click(button(container, "Подготовить архив"));
    const post = vi
      .mocked(fetch)
      .mock.calls.find(([url, init]) => url === "/api/family/exports" && init?.method === "POST");
    expect(new Headers(post?.[1]?.headers).get("Idempotency-Key")).toBeTruthy();
    expect(container.textContent).toContain("В очереди");
    expect(button(container, "Архив уже готовится")).not.toBeNull();
  });

  it("готовый архив можно скачать, просроченный нельзя", async () => {
    list = [exported("e2", "ready"), exported("e1", "expired", { file_size: 1000 })];
    const container = await openApp("/family-data");
    expect(container.textContent).toContain("Готово, 3 КБ, хранится до 28 ноября");
    expect(container.textContent).toContain("Срок хранения истёк");
    expect([...container.querySelectorAll("button")].filter((b) => b.textContent === "Скачать")).toHaveLength(1);
  });
});
