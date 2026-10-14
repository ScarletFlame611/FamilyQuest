import { useSyncExternalStore } from "react";

export type Role = "adult" | "child";

export type Session = {
  role: Role;
  accessToken: string;
  refreshToken: string;
};

const STORAGE_KEY = "fq.session";

function load(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

function persist(session: Session | null) {
  try {
    if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Без хранилища сессия живёт только до перезагрузки, приложение продолжает работать
  }
}

let current: Session | null = load();
const listeners = new Set<() => void>();

export function getSession(): Session | null {
  return current;
}

// Старая сессия полностью заменяется: при входе в детский режим токены взрослого
// не остаются ни в памяти, ни в хранилище, вернуть их может только ответ на PIN
export function setSession(next: Session | null) {
  current = next;
  persist(next);
  listeners.forEach((listener) => listener());
}

export function useSession(): Session | null {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => current,
  );
}
