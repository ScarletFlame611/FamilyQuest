import { afterEach, describe, expect, it, vi } from "vitest";

import { CHILD_SESSION, closeApp, openApp, stubApi } from "../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const ADULT_SESSION = { role: "adult", accessToken: "adult-access", refreshToken: "adult-refresh" };

const member = (id: string, name: string, role: string, points: number) => ({
  member_id: id,
  name,
  avatar: role === "adult" ? "woman" : "fox",
  role,
  points,
});

const GOAL = {
  id: "g1",
  title: "Поход с палатками",
  icon: "tent",
  target: 300,
  progress: 260,
  reached: false,
  reached_at: null,
  contributions: [
    member("mama", "Мама", "adult", 110),
    member("papa", "Папа", "adult", 85),
    member("masha", "Маша", "child", 35),
    member("petya", "Петя", "child", 30),
  ].reverse(),
  feed: [],
};

function open(session: object, path: string) {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(session));
  stubApi((_, url) => {
    return {
      "/api/me": { id: "mama", name: "Мама", role: "adult", avatar: "woman", family: { id: "f", name: "Демо" } },
      "/api/family": { id: "f", name: "Демо", members: [] },
      "/api/balance": { balance: 0, reserved: 0, available: 0 },
      "/api/goal": GOAL,
    }[url];
  });
  return openApp(path);
}

afterEach(closeApp);

describe("US-36: таблица вклада семьи", () => {
  it("у взрослого строки по убыванию с долей, а итог равен прогрессу", async () => {
    const container = await open(ADULT_SESSION, "/goal");
    const rows = [...container.querySelectorAll(".members .mem")].map((row) => [
      row.querySelector(".who")?.textContent,
      Number(row.querySelector(".n")?.textContent),
    ]);
    expect(rows).toEqual([
      ["Ты · 42%", 110],
      ["Папа · 33%", 85],
      ["Маша · 13%", 35],
      ["Петя · 12%", 30],
      ["Всего", 260],
    ]);
    expect(rows.at(-1)?.[1]).toBe(GOAL.progress);
  });

  it("у ребёнка без итоговой строки и долей", async () => {
    const container = await open(CHILD_SESSION, "/kid/goal");
    expect(container.textContent).not.toContain("Всего");
    expect(container.textContent).not.toContain("%");
  });
});
