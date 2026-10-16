import { createContext, useContext } from "react";

import type { Balance, Member, Me } from "../shared/api/types";
import { navigate } from "../shared/lib/router";

export type ChildContextValue = {
  me: Me | null;
  members: Member[];
  balance: Balance | null;
  refreshBalance: () => void;
  setTabsHidden: (hidden: boolean) => void;
};

export const ChildContext = createContext<ChildContextValue | null>(null);

export function useChild(): ChildContextValue {
  const value = useContext(ChildContext);
  if (!value) throw new Error("useChild вне детского режима");
  return value;
}

// Сообщение для следующего экрана, например «дело теперь в твоих делах»
let toast = "";

export function setToast(message: string) {
  toast = message;
}

// Чтение и сброс разделены: React в режиме разработки вызывает инициализатор состояния дважды
export function peekToast(): string {
  return toast;
}

export function clearToast() {
  toast = "";
}

// Только что взятое дело: в «Моих делах» оно выделено один раз, при первом показе
let fresh = "";

export function setFresh(taskId: string) {
  fresh = taskId;
}

export function peekFresh(): string {
  return fresh;
}

export function clearFresh() {
  fresh = "";
}

// Экран звёздочек возвращает туда, откуда ребёнок нажал на счётчик
let starsReturn = "/kid";

export function openStars(from: string) {
  starsReturn = from;
  navigate("/kid/stars");
}

export function starsReturnPath(): string {
  return starsReturn;
}

export function stars(n: number): string {
  const a = n % 10;
  const b = n % 100;
  if (a === 1 && b !== 11) return "звёздочка";
  if (a >= 2 && a <= 4 && (b < 12 || b > 14)) return "звёздочки";
  return "звёздочек";
}
