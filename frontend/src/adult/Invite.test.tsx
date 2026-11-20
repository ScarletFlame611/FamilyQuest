import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CHILD_SESSION, click, closeApp, openApp, stubApi } from "../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const ADULT_SESSION = { role: "adult", accessToken: "adult-access", refreshToken: "adult-refresh" };
const TOKEN = "Abc123_secret-link-token-0000000000000000000";

function open(session: object | null, path: string) {
  localStorage.clear();
  if (session) localStorage.setItem("fq.session", JSON.stringify(session));
  stubApi((method, url) => {
    if (method === "POST" && url === `/api/auth/invites/${TOKEN}/accept`)
      return { access_token: "grandma-access", refresh_token: "grandma-refresh", token_type: "bearer" };
    if (method === "POST" && url === "/api/family/invites")
      return { token: TOKEN, expires_at: "2026-11-22T12:00:00Z" };
    return {
      [`/api/auth/invites/${TOKEN}`]: {
        family_name: "Демо-семья",
        invited_by: "Мама",
        expires_at: "2026-11-22T12:00:00Z",
      },
      "/api/me": { id: "mama", name: "Мама", role: "adult", avatar: "woman" },
      "/api/balance": { balance: 0, reserved: 0, available: 0 },
      "/api/family": { id: "f", name: "Демо-семья", members: [] },
    }[url];
  });
  return openApp(path);
}

async function type(input: Element | null, value: string) {
  if (!(input instanceof HTMLInputElement)) throw new Error("Нет поля");
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
  await act(async () => {
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

const button = (container: HTMLElement, text: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent === text) ?? null;

afterEach(closeApp);

describe("US-11: приглашение взрослого по ссылке", () => {
  it("взрослый создаёт одноразовую ссылку", async () => {
    const container = await open(ADULT_SESSION, "/invite");
    await click(button(container, "Создать ссылку"));
    const link = container.querySelector("input[readonly]") as HTMLInputElement;
    expect(link.value).toBe(`${window.location.origin}/join/${TOKEN}`);
    expect(container.textContent).toContain("48 часов и только один раз");
  });

  it("по ссылке без входа открывается форма и после неё — взрослая часть", async () => {
    const container = await open(null, `/join/${TOKEN}`);
    expect(container.textContent).toContain("Мама зовёт вас в семью «Демо-семья»");
    await type(container.querySelector('input[placeholder="Например: Бабушка"]'), "Бабушка");
    await click(button(container, "👨"));
    await type(container.querySelector('input[type="email"]'), "babushka@example.org");
    await type(container.querySelector('input[type="password"]'), "babushka-password");
    await act(async () => {
      container.querySelector("form")!.requestSubmit();
    });
    const [, init] = vi
      .mocked(fetch)
      .mock.calls.find(([url]) => String(url).endsWith(`/invites/${TOKEN}/accept`))!;
    expect(JSON.parse(String(init?.body))).toEqual({
      name: "Бабушка",
      avatar: "man",
      email: "babushka@example.org",
      password: "babushka-password",
    });
    // Модули приложения пересобраны в openApp, поэтому сессию смотрим в хранилище
    const stored = JSON.parse(localStorage.getItem("fq.session") ?? "null");
    expect(stored).toMatchObject({ role: "adult", accessToken: "grandma-access" });
    expect(window.location.pathname).toBe("/");
  });

  it("в детском режиме ссылка не уводит из него", async () => {
    await open(CHILD_SESSION, `/join/${TOKEN}`);
    expect(window.location.pathname.startsWith("/kid")).toBe(true);
  });
});
