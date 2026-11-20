import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CHILD_SESSION, click, closeApp, openApp, stubApi } from "../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const ADULT_SESSION = { role: "adult", accessToken: "adult-access", refreshToken: "adult-refresh" };

function goal(reached: boolean) {
  return {
    id: "g1",
    title: "Поход с палатками",
    icon: "tent",
    target: 300,
    progress: reached ? 300 : 260,
    reached,
    reached_at: reached ? "2026-11-20T12:00:00Z" : null,
    contributions: [],
    feed: [],
  };
}

function open(session: object, reached: boolean, path: string) {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(session));
  stubApi((method, url) => {
    if (method === "POST" && url === "/api/goal") return goal(false);
    return {
      "/api/me": { id: "mama", name: "Мама", role: "adult", avatar: "woman" },
      "/api/family": { id: "f", name: "Демо-семья", members: [] },
      "/api/balance": { balance: 0, reserved: 0, available: 0 },
      "/api/goal": goal(reached),
    }[url];
  });
  return openApp(path);
}

async function type(input: Element | null, value: string) {
  if (!(input instanceof HTMLInputElement)) throw new Error("Нет поля");
  // React следит за значением через собственный сеттер, поэтому событие нужно настоящее
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
  await act(async () => {
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

const button = (container: HTMLElement, text: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent === text) ?? null;

afterEach(closeApp);

describe("US-16, US-33: общая цель", () => {
  it("пока цель копится, новую создать нельзя", async () => {
    const container = await open(ADULT_SESSION, false, "/goal");
    expect(container.textContent).toContain("260");
    expect(container.textContent).not.toContain("Копилка полная");
    expect(container.textContent).not.toContain("Новая цель");
  });

  it("после достижения взрослый видит форму и создаёт новую цель", async () => {
    const container = await open(ADULT_SESSION, true, "/goal");
    expect(container.textContent).toContain("Копилка полная");
    await type(container.querySelector('input[placeholder^="Например"]'), "Море");
    await click(button(container, "🌊Море"));
    await click(button(container, "Начать копить"));
    const [, init] = vi
      .mocked(fetch)
      .mock.calls.find(([url, req]) => String(url).endsWith("/api/goal") && req?.method === "POST")!;
    expect(JSON.parse(String(init?.body))).toEqual({ title: "Море", icon: "sea", target: 300 });
  });

  it("ребёнок видит, что копилка полная", async () => {
    const container = await open(CHILD_SESSION, true, "/kid/goal");
    expect(container.textContent).toContain("Копилка полная");
    expect(container.textContent).not.toContain("Новая цель");
  });
});
