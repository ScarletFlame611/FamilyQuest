import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setSession } from "../shared/session/session";

beforeEach(() => {
  localStorage.clear();
  setSession({ role: "child", accessToken: "child-access", refreshToken: "child-refresh" });
  vi.resetModules();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("журнал детского режима", () => {
  it("без связи не теряет события и отправляет их, когда связь вернулась", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);
    const events = await import("./events");

    events.track("screen_opened", "/kid");
    events.track("button_pressed", "✓ Сделал!");
    await events.flushEvents();
    expect(events.pendingEvents()).toBe(2);

    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await events.flushEvents();
    expect(events.pendingEvents()).toBe(0);
    const [, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    const body = JSON.parse(init.body as string) as {
      events: { type: string; detail: string; ago_ms: number }[];
    };
    expect(body.events.map((e) => e.type)).toEqual(["screen_opened", "button_pressed"]);
    expect(body.events.every((e) => e.ago_ms >= 0)).toBe(true);
  });

  it("переживает перезагрузку страницы", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    const first = await import("./events");
    first.track("task_opened", "Убрать игрушки");
    vi.resetModules();
    const reloaded = await import("./events");
    expect(reloaded.pendingEvents()).toBe(1);
  });

  it("не записывает повторное открытие того же экрана подряд", async () => {
    const events = await import("./events");
    events.track("screen_opened", "/kid");
    events.track("screen_opened", "/kid");
    events.track("button_pressed", "Купить");
    events.track("button_pressed", "Купить");
    expect(events.pendingEvents()).toBe(3);
  });
});
