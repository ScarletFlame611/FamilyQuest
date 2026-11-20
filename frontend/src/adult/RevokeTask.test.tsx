import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { click, closeApp, openApp, stubApi } from "../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const ADULT_SESSION = { role: "adult", accessToken: "adult-access", refreshToken: "adult-refresh" };

const DISHES = {
  id: "t1",
  title: "Помыть посуду",
  description: null,
  icon: "dishes",
  points: 20,
  status: "confirmed",
  assignee_member_id: "masha",
  assignee_name: "Маша",
  created_by_member_id: "mama",
  created_by_name: "Мама",
  reject_reason: null,
  marked_at: "2026-11-20T10:00:00Z",
  confirmed_at: "2026-11-20T10:05:00Z",
};

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(ADULT_SESSION));
  stubApi((method, path) => {
    if (method === "POST" && path === "/api/tasks/t1/revoke") {
      return { task: { ...DISHES, status: "assigned" }, cancelled_purchases: ["Фломастеры"] };
    }
    return {
      "/api/me": { id: "mama", name: "Мама", role: "adult", avatar: "woman" },
      "/api/family": { id: "f", name: "Демо-семья", members: [] },
      "/api/balance": { balance: 0, reserved: 0, available: 0 },
      "/api/tasks/family": [DISHES],
    }[path];
  });
});

afterEach(closeApp);

const button = (container: HTMLElement, text: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent === text) ?? null;

async function type(input: Element | null, value: string) {
  if (!(input instanceof HTMLInputElement)) throw new Error("Нет поля");
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
  await act(async () => {
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

const revokeCalls = () =>
  vi
    .mocked(fetch)
    .mock.calls.filter(([url, init]) => String(url).endsWith("/revoke") && init?.method === "POST");

describe("US-26: отмена подтверждения", () => {
  it("предупреждает о последствиях и отправляет причину", async () => {
    const container = await openApp("/kanban");
    await click(button(container, "Отменить подтверждение"));
    expect(container.textContent).toContain("Маша: −20 ⭐");
    await type(container.querySelector('input[placeholder^="Почему отменяете"]'), "Не помыта");
    await click(button(container, "Отменить подтверждение"));
    const [[, init]] = revokeCalls();
    expect(JSON.parse(String(init?.body))).toEqual({ reason: "Не помыта" });
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBeTruthy();
    expect(container.textContent).toContain(
      "Подтверждение «Помыть посуду» отменено. Покупки отменены: Фломастеры",
    );
  });

  it("без причины ничего не отправляет", async () => {
    const container = await openApp("/kanban");
    await click(button(container, "Отменить подтверждение"));
    await click(button(container, "Отменить подтверждение"));
    expect(revokeCalls()).toHaveLength(0);
  });
});
