import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { vi } from "vitest";

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

export const CHILD_SESSION = {
  role: "child",
  accessToken: "child-access",
  refreshToken: "child-refresh",
};

type Handler = (method: string, path: string) => unknown;

let root: Root | null = null;
let host: HTMLDivElement | null = null;

// Ответ API по методу и пути; неизвестный адрес отвечает пустым списком
export function stubApi(handler: Handler) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = new URL(url, "http://localhost").pathname;
      const body = handler(init?.method ?? "GET", path) ?? [];
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
}

// Отдельный импорт на каждый вызов — как новая вкладка: модули читают сессию из хранилища заново
export async function openApp(path: string): Promise<HTMLDivElement> {
  window.history.replaceState(null, "", path);
  vi.resetModules();
  const { App } = await import("../App");
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root!.render(<App />));
  await settle();
  return host;
}

export async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

export async function click(element: Element | null) {
  if (!element) throw new Error("Нечего нажать");
  await act(async () => {
    (element as HTMLElement).click();
  });
  await settle();
}

export function closeApp() {
  act(() => root?.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.unstubAllGlobals();
}
