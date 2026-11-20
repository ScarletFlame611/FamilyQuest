import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CHILD_SESSION, click, closeApp, openApp, stubApi } from "../testing/app";
import { minusNote } from "./context";

vi.setConfig({ testTimeout: 30_000 });

const ADULT_SESSION = { role: "adult", accessToken: "adult-access", refreshToken: "adult-refresh" };
const MASHA = { id: "masha", name: "Маша", role: "child", avatar: "fox", age_group: "6-7" };

function open(session: object, path: string) {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(session));
  stubApi((method, url) => {
    if (method === "POST" && url === "/api/members/masha/write-off")
      return { balance: 0, reserved: 0, available: 0 };
    return {
      "/api/me": { ...MASHA, family: { id: "f", name: "Демо-семья" } },
      "/api/family": { id: "f", name: "Демо-семья", members: [MASHA] },
      "/api/balance": { balance: -5, reserved: 0, available: -5 },
      "/api/balances": [{ member_id: "masha", balance: -5, reserved: 0, available: -5 }],
    }[url];
  });
  return openApp(path);
}

afterEach(closeApp);

describe("US-94: минус на балансе", () => {
  it.each([
    [0, null],
    [-1, "Следующая звёздочка закроет минус"],
    [-3, "Следующие 3 звёздочки закроют минус"],
    [-5, "Следующие 5 звёздочек закроют минус"],
    [-11, "Следующие 11 звёздочек закроют минус"],
    [-21, "Следующая 21 звёздочка закроет минус"],
  ])("баланс %i: %s", (balance, text) => {
    expect(minusNote(balance)).toBe(text);
  });

  it("ребёнок видит ноль и фразу про минус, а не долг", async () => {
    const container = await open(CHILD_SESSION, "/kid/stars");
    expect(container.querySelector(".bignum")?.textContent).toBe("0");
    expect(container.textContent).toContain("Следующие 5 звёздочек закроют минус");
    expect(container.textContent?.toLowerCase()).not.toContain("долг");
  });

  it("на счётчике в шапке ребёнок видит ноль, а не отрицательное число", async () => {
    const container = await open(CHILD_SESSION, "/kid/tasks");
    expect(container.querySelector('[aria-label="Мои звёздочки: 0"]')).not.toBeNull();
  });

  it("взрослый списывает минус с причиной", async () => {
    const container = await open(ADULT_SESSION, "/");
    expect(container.textContent).toContain("Минус на балансе");
    expect(container.textContent).toContain("−5 ⭐");
    const button = (text: string) =>
      [...container.querySelectorAll("button")].find((b) => b.textContent === text) ?? null;
    await click(button("Списать минус…"));
    const input = container.querySelector('input[placeholder="Почему списываете"]') as HTMLInputElement;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "Прощаем");
    await act(async () => {
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await click(button("Списать минус"));
    const [, init] = vi
      .mocked(fetch)
      .mock.calls.find(([url]) => String(url).endsWith("/api/members/masha/write-off"))!;
    expect(JSON.parse(String(init?.body))).toEqual({ reason: "Прощаем" });
  });
});
