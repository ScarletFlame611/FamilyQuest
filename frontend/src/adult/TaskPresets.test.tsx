import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TASK_PRESETS } from "../shared/catalog";
import { click, closeApp, openApp, stubApi } from "../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const ADULT_SESSION = { role: "adult", accessToken: "adult-access", refreshToken: "adult-refresh" };
const MEMBERS = [
  { id: "mama", name: "Мама", role: "adult", avatar: "woman", age_group: null },
  { id: "masha", name: "Маша", role: "child", avatar: "fox", age_group: "6-7" },
  { id: "petya", name: "Петя", role: "child", avatar: "panda", age_group: "8-10" },
];

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(ADULT_SESSION));
  stubApi((_, path) => ({
    "/api/me": { id: "mama", name: "Мама", role: "adult", avatar: "woman" },
    "/api/family": { id: "f", name: "Демо-семья", members: MEMBERS },
    "/api/tasks": {},
  })[path]);
});

afterEach(closeApp);

const button = (container: HTMLElement, text: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent?.includes(text)) ?? null;
const presets = (container: HTMLElement) =>
  [...container.querySelectorAll(".presets .name")].map((n) => n.textContent);

describe("US-13: готовые дела по возрасту ребёнка", () => {
  it("подборка появляется только для ребёнка и зависит от его возраста", async () => {
    const container = await openApp("/tasks/new");
    expect(container.textContent).not.toContain("Готовые дела");

    await click(button(container, "Маша"));
    expect(container.textContent).toContain("Готовые дела для 6-7 лет");
    expect(presets(container)).toEqual(TASK_PRESETS["6-7"].slice(0, 6).map((p) => p.title));

    await click(button(container, "Показать все"));
    expect(presets(container)).toHaveLength(TASK_PRESETS["6-7"].length);

    await click(button(container, "Петя"));
    expect(container.textContent).toContain("Готовые дела для 8-10 лет");
    expect(presets(container)).toContain("Покормить кота");

    await click(button(container, "Мама"));
    expect(container.textContent).not.toContain("Готовые дела");
  });

  it("выбранное дело заполняет форму и уходит на сервер с её значениями", async () => {
    const container = await openApp("/tasks/new");
    await click(button(container, "Маша"));
    await click(button(container, "Заправить кровать"));

    const [title, price] = container.querySelectorAll<HTMLInputElement>("input.pass");
    expect(title.value).toBe("Заправить кровать");
    expect(price.value).toBe("5");
    expect(container.querySelector('.icons [aria-pressed="true"]')?.textContent).toContain("Кровать");

    await click(button(container, "Добавить дело"));
    const call = vi.mocked(fetch).mock.calls.find(([url, init]) => url === "/api/tasks" && init?.method === "POST");
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      title: "Заправить кровать",
      icon: "bed",
      points: 5,
      assignee_id: "masha",
    });
  });
});
