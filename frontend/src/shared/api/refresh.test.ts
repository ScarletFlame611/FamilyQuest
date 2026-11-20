import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getSession, setSession } from "../session/session";
import { NetworkError } from "./client";
import { api } from "./endpoints";

const OLD = { role: "adult", accessToken: "old-access", refreshToken: "old-refresh" } as const;
const NEW = { role: "adult", accessToken: "new-access", refreshToken: "new-refresh" } as const;
const ME = { id: "mama", name: "Мама", role: "adult", avatar: "woman" };

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// Так соседняя вкладка сохраняет новую сессию: запись в хранилище и событие storage
function otherTabStores(session: object | null) {
  if (session) localStorage.setItem("fq.session", JSON.stringify(session));
  else localStorage.removeItem("fq.session");
  window.dispatchEvent(new StorageEvent("storage", { key: "fq.session" }));
}

function stubServer(refresh: () => Response) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/refresh") return refresh();
    const auth = new Headers(init?.headers).get("Authorization");
    return auth === `Bearer ${NEW.accessToken}` ? json(200, ME) : json(401, { detail: "Нужно войти" });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  localStorage.clear();
  setSession({ ...OLD });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("обновление токенов не выкидывает из аккаунта зря", () => {
  it("временная ошибка сервера показывается как «нет связи», сессия остаётся", async () => {
    stubServer(() => json(502, {}));
    await expect(api.me()).rejects.toBeInstanceOf(NetworkError);
    expect(getSession()).toEqual(OLD);
  });

  it("если соседняя вкладка уже обменяла токен, запрос повторяется с её токеном", async () => {
    const fetchMock = stubServer(() => {
      otherTabStores(NEW);
      return json(401, { detail: "Сессия истекла, войдите заново" });
    });
    await expect(api.me()).resolves.toEqual(ME);
    expect(getSession()).toEqual(NEW);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("соседняя вкладка сохранила токен чуть позже отказа — тоже не выход", async () => {
    stubServer(() => {
      setTimeout(() => otherTabStores(NEW), 100);
      return json(401, { detail: "Сессия истекла, войдите заново" });
    });
    await expect(api.me()).resolves.toEqual(ME);
    expect(getSession()).toEqual(NEW);
  });

  it("если сервер отказал и сессию никто не менял, это выход", async () => {
    stubServer(() => json(401, { detail: "Сессия истекла, войдите заново" }));
    await expect(api.me()).rejects.toMatchObject({ status: 401 });
    expect(getSession()).toBeNull();
  });

  it("детский режим, включённый в соседней вкладке, доходит и до этой", () => {
    const child = { role: "child", accessToken: "child-access", refreshToken: "child-refresh" };
    otherTabStores(child);
    expect(getSession()).toEqual(child);
  });
});

describe("запрос без ответа", () => {
  it("через 15 секунд считается обрывом связи, а не висит вечно", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_: string, init?: RequestInit) =>
          new Promise<Response>((_, reject) => {
            init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
          }),
      ),
    );
    const pending = expect(api.me()).rejects.toBeInstanceOf(NetworkError);
    await vi.advanceTimersByTimeAsync(15_000);
    await pending;
    vi.useRealTimers();
  });
});
