import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CHILD_SESSION, closeApp, openApp, settle, stubApi } from "./testing/app";

const BALANCE = { balance: 45, reserved: 20, available: 25 };

const RESPONSES: Record<string, unknown> = {
  "/api/me": {
    id: "masha",
    name: "Маша",
    role: "child",
    avatar: "fox",
    age_group: "6-7",
    family: { id: "f", name: "Демо-семья" },
  },
  "/api/family": { id: "f", name: "Демо-семья", members: [] },
  "/api/balance": BALANCE,
};

// Каждый тест заново собирает модули приложения, первый импорт бывает дольше 5 секунд
vi.setConfig({ testTimeout: 30_000 });

let container: HTMLDivElement;

async function goBackTo(path: string) {
  window.history.pushState(null, "", path);
  await act(async () => {
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await settle();
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(CHILD_SESSION));
  stubApi((_, path) => RESPONSES[path]);
});

afterEach(closeApp);

function inChildMode(): boolean {
  return (
    window.location.pathname.startsWith("/kid") &&
    container.querySelector('[aria-label="Режим взрослого, нужен PIN-код"]') !== null
  );
}

describe("US-07: детский режим не обходится", () => {
  it.each(["/", "/tasks/new", "/child-mode", "/pin", "/login"])(
    "прямой адрес взрослой страницы %s ведёт обратно в детский режим",
    async (path) => {
      container = await openApp(path);
      expect(inChildMode()).toBe(true);
      expect(container.textContent).not.toContain("Новое дело");
    },
  );

  it("кнопка «Назад» на взрослый адрес оставляет в детском режиме", async () => {
    container = await openApp("/kid");
    await goBackTo("/child-mode");
    expect(inChildMode()).toBe(true);
    await goBackTo("/");
    expect(inChildMode()).toBe(true);
  });

  it("новая вкладка и перезагрузка открываются в детском режиме", async () => {
    await openApp("/kid/shop");
    closeApp();
    stubApi((_, path) => RESPONSES[path]);
    container = await openApp("/");
    expect(inChildMode()).toBe(true);
    expect(JSON.parse(localStorage.getItem("fq.session")!).role).toBe("child");
  });
});

describe("US-10: баланс ребёнка", () => {
  it("на экране ребёнка число из ответа сервера о балансе", async () => {
    container = await openApp("/kid");
    const chip = container.querySelector(".bal");
    expect(chip?.textContent).toContain(String(BALANCE.available));
    expect(chip?.getAttribute("aria-label")).toBe(`Мои звёздочки: ${BALANCE.available}`);
  });
});
