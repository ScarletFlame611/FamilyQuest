import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const CHILD_SESSION = { role: "child", accessToken: "child-access", refreshToken: "child-refresh" };
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

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement;

// Отдельный импорт на каждый тест — как новая вкладка: модули читают сессию из хранилища заново
async function openApp(path: string) {
  window.history.replaceState(null, "", path);
  vi.resetModules();
  const { App } = await import("./App");
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  await act(async () => root!.render(<App />));
  await settle();
}

async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

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
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const path = new URL(url, "http://localhost").pathname;
      const body = path in RESPONSES ? RESPONSES[path] : [];
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

afterEach(() => {
  act(() => root?.unmount());
  root = null;
  container.remove();
  vi.unstubAllGlobals();
});

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
      await openApp(path);
      expect(inChildMode()).toBe(true);
      expect(container.textContent).not.toContain("Новое дело");
    },
  );

  it("кнопка «Назад» на взрослый адрес оставляет в детском режиме", async () => {
    await openApp("/kid");
    await goBackTo("/child-mode");
    expect(inChildMode()).toBe(true);
    await goBackTo("/");
    expect(inChildMode()).toBe(true);
  });

  it("новая вкладка и перезагрузка открываются в детском режиме", async () => {
    await openApp("/kid/shop");
    act(() => root?.unmount());
    await openApp("/");
    expect(inChildMode()).toBe(true);
    expect(JSON.parse(localStorage.getItem("fq.session")!).role).toBe("child");
  });
});

describe("US-10: баланс ребёнка", () => {
  it("на экране ребёнка число из ответа сервера о балансе", async () => {
    await openApp("/kid");
    const chip = container.querySelector(".bal");
    expect(chip?.textContent).toContain(String(BALANCE.available));
    expect(chip?.getAttribute("aria-label")).toBe(`Мои звёздочки: ${BALANCE.available}`);
  });
});
