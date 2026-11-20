import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { click, closeApp, openApp, stubApi } from "../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const ADULT_SESSION = { role: "adult", accessToken: "adult-access", refreshToken: "adult-refresh" };

const REWARDS = [
  { id: "r1", title: "Мороженое", icon: "ice_cream", price: 20, hidden: false },
  { id: "r2", title: "Поход в парк", icon: "park", price: 80, hidden: true },
];

const RESPONSES: Record<string, unknown> = {
  "/api/me": { id: "mama", name: "Мама", role: "adult", avatar: "woman" },
  "/api/balance": { balance: 0, reserved: 0, available: 0 },
  "/api/rewards/manage": REWARDS,
};

function sent(method: string, path: string) {
  const fetchMock = vi.mocked(fetch);
  return fetchMock.mock.calls.filter(
    ([url, init]) => String(url).endsWith(path) && (init?.method ?? "GET") === method,
  );
}

function buttonWith(container: HTMLElement, text: string) {
  return [...container.querySelectorAll("button")].find((b) => b.textContent === text) ?? null;
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(ADULT_SESSION));
  stubApi((_, path) => RESPONSES[path]);
});

afterEach(closeApp);

describe("US-15: взрослый управляет наградами", () => {
  it("показывает награды в каталоге и скрытые отдельно", async () => {
    const container = await openApp("/rewards");
    const text = container.textContent ?? "";
    expect(text).toContain("В каталоге у детей");
    expect(text).toContain("Мороженое");
    expect(text.indexOf("Скрытые")).toBeLessThan(text.indexOf("Поход в парк"));
    expect(text).toContain("Скрыта от детей");
  });

  it("скрытие уходит на сервер с ключом идемпотентности", async () => {
    const container = await openApp("/rewards");
    await click(buttonWith(container, "Скрыть"));
    const [call] = sent("PATCH", "/api/rewards/r1");
    expect(JSON.parse(String(call[1]?.body))).toEqual({ hidden: true });
    expect(new Headers(call[1]?.headers).get("Idempotency-Key")).toBeTruthy();
  });

  it("пустое название не отправляется", async () => {
    const container = await openApp("/rewards");
    await click(buttonWith(container, "Добавить награду"));
    expect(container.textContent).toContain("Напишите, что получит ребёнок");
    expect(sent("POST", "/api/rewards")).toHaveLength(0);
  });
});
