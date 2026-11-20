import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CHILD_SESSION, closeApp, openApp, stubApi } from "../testing/app";

vi.setConfig({ testTimeout: 30_000 });

const MASHA = { id: "masha", name: "Маша", role: "child", avatar: "fox", age_group: "6-7" };

function task(id: string, title: string, status: string, reason: string | null) {
  return {
    id,
    title,
    description: null,
    icon: "bed",
    points: 7,
    status,
    assignee_member_id: "masha",
    assignee_name: "Маша",
    created_by_member_id: "mama",
    created_by_name: "Мама",
    reject_reason: reason,
    marked_at: null,
    confirmed_at: null,
  };
}

const ago = (days: number) => new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("fq.session", JSON.stringify(CHILD_SESSION));
  stubApi((_, path) => {
    return {
      "/api/me": { ...MASHA, family: { id: "f", name: "Демо-семья" } },
      "/api/family": { id: "f", name: "Демо-семья", members: [MASHA] },
      "/api/balance": { balance: 38, reserved: 0, available: 38 },
      "/api/tasks/my": [
        task("t1", "Заправить кровать", "assigned", "Кровать не заправлена"),
        task("t2", "Полить фикус", "marked", null),
      ],
      "/api/ledger": [
        {
          id: "e1",
          kind: "reversal",
          amount: -7,
          label: "Заправить кровать",
          reason: "Кровать не заправлена",
          created_at: ago(0),
        },
        { id: "e2", kind: "accrual", amount: 7, label: "Заправить кровать", reason: null, created_at: ago(0) },
        {
          id: "e3",
          kind: "reversal",
          amount: -5,
          label: "Собрать рюкзак",
          reason: "Давно было",
          created_at: ago(10),
        },
      ],
    }[path];
  });
});

afterEach(closeApp);

describe("US-27: ребёнок видит, почему дело вернули", () => {
  it("на карточке в «Моих делах» есть строка с причиной", async () => {
    const container = await openApp("/kid");
    const bed = container.querySelector('[aria-label="Заправить кровать"]');
    expect(bed?.textContent).toContain("↩️ Вернули: Кровать не заправлена");
    const fikus = container.querySelector('[aria-label="Полить фикус"]');
    expect(fikus?.textContent).not.toContain("Вернули");
  });

  it("на экране звёздочек видно списание за последнюю неделю с причиной", async () => {
    const container = await openApp("/kid/stars");
    expect(container.textContent).toContain("-7 ⭐ за «Заправить кровать»: Кровать не заправлена");
    expect(container.textContent).not.toContain("Давно было");
  });
});
