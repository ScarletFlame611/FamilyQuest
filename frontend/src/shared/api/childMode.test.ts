import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getSession, setSession } from "../session/session";
import { KeyedAction } from "../lib/keyedAction";
import { NetworkError } from "./client";
import { api } from "./endpoints";

const ADULT = { access: "adult-access-token", refresh: "adult-refresh-token" };
const CHILD = { access: "child-access-token", refresh: "child-refresh-token" };

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function everythingStored(): string {
  const dump: string[] = [];
  for (const storage of [localStorage, sessionStorage]) {
    for (let i = 0; i < storage.length; i += 1) {
      const key = storage.key(i)!;
      dump.push(key, storage.getItem(key) ?? "");
    }
  }
  return dump.join("\n");
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  setSession({ role: "adult", accessToken: ADULT.access, refreshToken: ADULT.refresh });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("включение детского режима", () => {
  it("не оставляет токенов взрослого ни в памяти, ни в хранилищах", async () => {
    const fetchMock = vi.fn(async () =>
      json(200, { access_token: CHILD.access, refresh_token: CHILD.refresh, token_type: "bearer" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.startChildMode("child-id");

    const session = getSession();
    expect(session).toEqual({
      role: "child",
      accessToken: CHILD.access,
      refreshToken: CHILD.refresh,
    });
    const stored = everythingStored();
    expect(stored).not.toContain(ADULT.access);
    expect(stored).not.toContain(ADULT.refresh);
    expect(JSON.stringify(session)).not.toContain("adult-");

    // Сервер получил refresh-токен взрослого, чтобы сразу его отозвать
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      child_id: "child-id",
      adult_refresh_token: ADULT.refresh,
    });
  });

  it("после перезагрузки страницы остаётся детским", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json(200, { access_token: CHILD.access, refresh_token: CHILD.refresh, token_type: "bearer" }),
      ),
    );
    await api.startChildMode("child-id");
    vi.resetModules();
    const reloaded = await import("../session/session");
    expect(reloaded.getSession()?.role).toBe("child");
  });

  it("неверный PIN не сбрасывает детскую сессию", async () => {
    setSession({ role: "child", accessToken: CHILD.access, refreshToken: CHILD.refresh });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json(401, { detail: "Неверный PIN-код", attempts_left: 4 })),
    );
    await expect(api.exitChildMode("9999")).rejects.toMatchObject({
      status: 401,
      body: { attempts_left: 4 },
    });
    expect(getSession()?.role).toBe("child");
  });
});

describe("повтор после обрыва связи", () => {
  it("уходит с тем же Idempotency-Key, а после ответа ключ новый", async () => {
    const keys: string[] = [];
    let online = false;
    const action = new KeyedAction();
    const send = async (key: string) => {
      keys.push(key);
      if (!online) throw new NetworkError();
      return "ok";
    };
    await expect(action.run(send)).rejects.toBeInstanceOf(NetworkError);
    online = true;
    await action.run(send);
    await action.run(send);
    expect(keys[0]).toBe(keys[1]);
    expect(keys[2]).not.toBe(keys[1]);
  });
});

describe("истёкший access-токен", () => {
  it("обновляется по refresh-токену, и запрос повторяется", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(401, { detail: "Нужно войти заново" }))
      .mockResolvedValueOnce(
        json(200, { access_token: "new-access", refresh_token: "new-refresh", token_type: "bearer" }),
      )
      .mockResolvedValueOnce(json(200, { balance: 1, reserved: 0, available: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.balance()).resolves.toEqual({ balance: 1, reserved: 0, available: 1 });
    expect(getSession()?.accessToken).toBe("new-access");
    const [, retry] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect((retry.headers as Record<string, string>).Authorization).toBe("Bearer new-access");
  });

  it("если обновить не вышло, сессия сбрасывается и ведёт на вход", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(401, { detail: "Сессия истекла" })));
    await expect(api.balance()).rejects.toMatchObject({ status: 401 });
    expect(getSession()).toBeNull();
  });
});
