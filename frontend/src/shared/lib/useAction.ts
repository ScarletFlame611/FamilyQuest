import { useRef, useState } from "react";

import { ApiError, NetworkError } from "../api/client";
import { KeyedAction } from "./keyedAction";

export type ActionState =
  | { kind: "idle" }
  | { kind: "pending" }
  | { kind: "offline" }
  | { kind: "error"; error: ApiError | Error };

export function useAction<T>(send: (key: string) => Promise<T>) {
  const action = useRef(new KeyedAction());
  const [state, setState] = useState<ActionState>({ kind: "idle" });

  async function run(): Promise<{ ok: true; value: T } | { ok: false }> {
    if (state.kind === "pending") return { ok: false };
    setState({ kind: "pending" });
    try {
      const value = await action.current.run(send);
      setState({ kind: "idle" });
      return { ok: true, value };
    } catch (error) {
      setState(
        error instanceof NetworkError
          ? { kind: "offline" }
          : { kind: "error", error: error instanceof Error ? error : new Error(String(error)) },
      );
      return { ok: false };
    }
  }

  return { state, run, pending: state.kind === "pending" };
}

export function errorText(state: ActionState): string | null {
  if (state.kind === "offline") return "Не сохранилось, нет связи. Нажмите ещё раз, чтобы повторить";
  if (state.kind === "error") return state.error.message;
  return null;
}
