import { ApiError } from "../shared/api/client";
import { api } from "../shared/api/endpoints";
import type { ChildEventType } from "../shared/api/types";

type Pending = { type: ChildEventType; detail: string | null; at: number };

const STORAGE_KEY = "fq.childEvents";
const BATCH = 100;

function load(): Pending[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as Pending[];
  } catch {
    return [];
  }
}

let queue: Pending[] = load();
let sending: Promise<void> | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;

function save() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
  } catch {
    // Без хранилища события живут до перезагрузки; интерфейсу это не мешает
  }
}

function schedule() {
  if (timer || !queue.length) return;
  timer = setTimeout(() => {
    timer = null;
    void flushEvents();
  }, 3000);
}

// События уходят пачками и только в фоне: обрыв связи не должен мешать ребёнку,
// поэтому неотправленное остаётся в очереди и уйдёт со следующей попыткой
export function track(type: ChildEventType, detail: string | null = null) {
  const last = queue.at(-1);
  // Повторное открытие того же экрана подряд — это перерисовка, а не действие ребёнка;
  // повторные нажатия кнопок, наоборот, сохраняются: по ним видно, где ребёнок путался
  const reopened =
    type !== "button_pressed" && last?.type === type && last.detail === detail && Date.now() - last.at < 1000;
  if (reopened) return;
  queue.push({ type, detail: detail?.slice(0, 200) ?? null, at: Date.now() });
  save();
  schedule();
}

async function sendBatch() {
  const batch = queue.slice(0, BATCH);
  if (!batch.length) return;
  try {
    // Время передаётся как «сколько назад» по часам этого же телефона:
    // так неточные часы устройства не сдвигают журнал
    await api.sendChildEvents(
      batch.map((e) => ({ type: e.type, detail: e.detail, ago_ms: Math.max(0, Date.now() - e.at) })),
    );
    queue = queue.slice(batch.length);
  } catch (error) {
    // Ответ сервера с ошибкой не исправится повтором: пачку отбрасываем,
    // чтобы очередь не застряла. Без связи оставляем всё как есть
    if (error instanceof ApiError) queue = queue.slice(batch.length);
  }
  save();
}

export function flushEvents(): Promise<void> {
  sending ??= sendBatch().finally(() => {
    sending = null;
    schedule();
  });
  return sending;
}

export function pendingEvents(): number {
  return queue.length;
}
