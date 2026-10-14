import type { ReactNode } from "react";

import { errorText, type ActionState } from "../lib/useAction";

type Props = {
  state: ActionState;
  onClick: () => void;
  className?: string;
  children: ReactNode;
};

// Кнопка блокируется сразу после нажатия, а ошибка показывается рядом с ней
export function ActionButton({ state, onClick, className = "btn", children }: Props) {
  const message = errorText(state);
  return (
    <>
      <button className={className} disabled={state.kind === "pending"} onClick={onClick}>
        {state.kind === "pending" ? "Сохраняем…" : children}
      </button>
      {message && <div className="err">{message}</div>}
    </>
  );
}
