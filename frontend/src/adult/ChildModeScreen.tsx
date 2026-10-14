import { useState } from "react";

import { ApiError } from "../shared/api/client";
import { api } from "../shared/api/endpoints";
import { avatar } from "../shared/catalog";
import { navigate } from "../shared/lib/router";
import { useAction } from "../shared/lib/useAction";
import { useLoad } from "../shared/lib/useLoad";
import { ActionButton } from "../shared/ui/ActionButton";
import { clearHandoverHint, showHandoverHint } from "../child/handoverHint";
import { AdultLayout } from "./AdultLayout";

export function ChildModeScreen() {
  const { data: family } = useLoad(api.family);
  const children = family?.members.filter((m) => m.role === "child") ?? [];
  const [childId, setChildId] = useState<string | null>(null);
  const selected = childId ?? children[0]?.id ?? null;
  const start = useAction(() => api.startChildMode(selected ?? ""));
  const noPin = start.state.kind === "error" && start.state.error instanceof ApiError && start.state.error.status === 409;

  async function begin() {
    if (!selected) return;
    // Флаг ставится до запроса: детский экран появляется сразу, как только
    // сменилась сессия, и читает флаг при первом же рендере
    showHandoverHint();
    if ((await start.run()).ok) navigate("/kid", { replace: true });
    else clearHandoverHint();
  }

  return (
    <AdultLayout>
      <div className="title">
        <h1>Детский режим</h1>
        <p>Ребёнок увидит только свои дела, баланс, награды и копилку. Вернуться можно по PIN-коду.</p>
      </div>
      <section className="panel">
        <h2>Кто будет играть</h2>
        <div className="choices">
          {children.map((child) => (
            <button
              key={child.id}
              className={selected === child.id ? "on" : ""}
              onClick={() => setChildId(child.id)}
            >
              {avatar(child.avatar)} {child.name}
            </button>
          ))}
        </div>
        <ActionButton state={start.state} className="cta violet" onClick={() => void begin()}>
          Включить детский режим
        </ActionButton>
        {noPin && (
          <button className="btn soft" onClick={() => navigate("/pin")}>
            Задать PIN-код
          </button>
        )}
      </section>
    </AdultLayout>
  );
}
