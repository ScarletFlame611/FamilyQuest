import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CHILD_SESSION, click, closeApp, openApp, stubApi } from "../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const MEMBERS = [
  { id: "mama", name: "Мама", role: "adult", avatar: "woman", age_group: null },
  { id: "papa", name: "Папа", role: "adult", avatar: "man", age_group: null },
  { id: "masha", name: "Маша", role: "child", avatar: "fox", age_group: "6-7" },
];

function task(id: string, title: string, status: string, assignee: string | null) {
  return {
    id,
    title,
    description: null,
    icon: "trash",
    points: 10,
    status,
    assignee_member_id: assignee,
    assignee_name: assignee ? "Маша" : null,
    created_by_member_id: "papa",
    created_by_name: "Папа",
    reject_reason: null,
    marked_at: null,
    confirmed_at: null,
  };
}

const GOAL = {
  id: "goal",
  title: "Поход с палатками всей семьёй",
  icon: "tent",
  target: 300,
  progress: 260,
  reached: false,
  contributions: [
    { member_id: "mama", name: "Мама", avatar: "woman", role: "adult", points: 140 },
    { member_id: "papa", name: "Папа", avatar: "man", role: "adult", points: 85 },
    { member_id: "masha", name: "Маша", avatar: "fox", role: "child", points: 35 },
  ],
  feed: [
    {
      member_id: "papa",
      name: "Папа",
      avatar: "man",
      title: "Сходить в магазин",
      points: 15,
      created_at: "2026-10-17T09:00:00Z",
    },
  ],
};

let mine: ReturnType<typeof task>[];
let board: ReturnType<typeof task>[];
let container: HTMLDivElement;

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(CHILD_SESSION));
  mine = [task("toys", "Убрать игрушки", "assigned", "masha")];
  board = [task("trash", "Вынести мусор", "open", null)];
  stubApi((method, path) => {
    if (method === "POST" && path === "/api/tasks/trash/take") {
      const taken = { ...board[0], status: "assigned", assignee_member_id: "masha" };
      board = [];
      mine = [...mine, taken];
      return taken;
    }
    if (path === "/api/tasks/trash") return board[0] ?? mine.find((t) => t.id === "trash");
    return {
      "/api/me": { ...MEMBERS[2], family: { id: "f", name: "Демо-семья" } },
      "/api/family": { id: "f", name: "Демо-семья", members: MEMBERS },
      "/api/balance": { balance: 45, reserved: 20, available: 25 },
      "/api/tasks/my": mine,
      "/api/tasks/board": board,
      "/api/goal": GOAL,
    }[path];
  });
});

afterEach(() => {
  vi.useRealTimers();
  closeApp();
});

const find = (selector: string) => container.querySelector(selector);
const byLabel = (label: string) => find(`[aria-label="${label}"]`);

describe("экран звёздочек", () => {
  it("открывается по счётчику с балансом для трат и через 3,5 с возвращает назад", async () => {
    container = await openApp("/kid/board");
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    await act(async () => {
      (byLabel("Мои звёздочки: 25") as HTMLElement).click();
    });
    expect(window.location.pathname).toBe("/kid/stars");
    expect(find(".bignum")?.textContent).toBe("25");
    expect(find("h1")?.textContent).toBe("Столько звёздочек у тебя");

    act(() => vi.advanceTimersByTime(3400));
    expect(window.location.pathname).toBe("/kid/stars");
    act(() => vi.advanceTimersByTime(100));
    expect(window.location.pathname).toBe("/kid/board");
  });

  it("нажатие в любом месте возвращает сразу", async () => {
    container = await openApp("/kid");
    await click(byLabel("Мои звёздочки: 25"));
    await click(find(".focus"));
    expect(window.location.pathname).toBe("/kid");
  });
});

describe("«Беру!»", () => {
  it("открывает «Мои дела» с плашкой и выделенным взятым делом", async () => {
    container = await openApp("/kid/task/trash");
    const take = [...container.querySelectorAll("button")].find((b) => b.textContent === "🙋 Беру!");
    await click(take ?? null);
    expect(window.location.pathname).toBe("/kid");
    expect(find(".toast")?.textContent).toBe("«Вынести мусор» теперь в твоих делах");
    expect(byLabel("Вынести мусор")?.classList.contains("fresh")).toBe(true);
    expect(byLabel("Убрать игрушки")?.classList.contains("fresh")).toBe(false);
  });
});

describe("карточки-переходы", () => {
  it("из «Моих дел» ведёт в «Можно взять» и обратно", async () => {
    container = await openApp("/kid");
    await click(byLabel("Хочешь ещё звёздочек? Возьми дело"));
    expect(window.location.pathname).toBe("/kid/board");
    await click(find("button.jump"));
    expect(window.location.pathname).toBe("/kid");
  });

  it("на пустой доске есть подсказка и переход в «Мои дела»", async () => {
    board = [];
    container = await openApp("/kid/board");
    expect(container.textContent).toContain(
      "Все дела разобрали. Новые появятся, когда взрослые их добавят.",
    );
    expect(find("button.jump")?.getAttribute("aria-label")).toBe("Мои дела");
  });
});

describe("вкладка «Семья»", () => {
  it("четыре вкладки, на «Семье» цель и строка «Ты»", async () => {
    container = await openApp("/kid/goal");
    const tabs = [...container.querySelectorAll("nav.tabs .tab")].map((t) => t.textContent);
    expect(tabs).toEqual(["📋Мои дела", "🙋Можно взять", "🎁Награды", "👨‍👩‍👧Семья"]);
    expect(find(".title h1")?.textContent).toBe("Семья");
    expect(find(".goal h2")?.textContent).toBe("Поход с палатками всей семьёй");
    expect(find(".goal .nums")?.textContent).toBe("260 из 300 ⭐");
    expect(find(".mem.me .who")?.textContent).toBe("Ты");
    expect(find(".feed div")?.textContent).toBe("👨Папа: сходить в магазин, +15");
  });
});
