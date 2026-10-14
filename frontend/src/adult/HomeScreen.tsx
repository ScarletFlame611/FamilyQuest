import { useRef, useState } from "react";

import { ApiError, NetworkError } from "../shared/api/client";
import { api } from "../shared/api/endpoints";
import { KeyedAction } from "../shared/lib/keyedAction";
import { navigate } from "../shared/lib/router";
import { useLoad } from "../shared/lib/useLoad";
import { useAvatars } from "../shared/ui/Kanban";
import { PurchaseCard, TaskCard } from "../shared/ui/TaskCard";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

export function HomeScreen() {
  const tasks = useLoad(api.pendingTasks);
  const purchases = useLoad(api.pendingPurchases);
  const { data: me } = useLoad(api.me);
  const avatars = useAvatars();
  // У каждого дела свой ключ: при повторе после обрыва связи уже засчитанные
  // дела вернут сохранённый ответ, а не начислят баллы второй раз
  const actions = useRef(new Map<string, KeyedAction>());
  const [allPending, setAllPending] = useState(false);
  const [allError, setAllError] = useState("");

  async function confirmAll() {
    if (!tasks.data || allPending) return;
    setAllPending(true);
    setAllError("");
    try {
      for (const task of tasks.data) {
        const action = actions.current.get(task.id) ?? new KeyedAction();
        actions.current.set(task.id, action);
        try {
          await action.run((key) => api.confirm(key, task.id));
          actions.current.delete(task.id);
        } catch (reason) {
          // Дело могли подтвердить с другого телефона: остальные это не останавливает
          if (reason instanceof ApiError && reason.status === 409) continue;
          setAllError(
            reason instanceof NetworkError
              ? "Не сохранилось, нет связи. Нажмите ещё раз, чтобы повторить"
              : reason instanceof Error
                ? reason.message
                : "Ошибка",
          );
          return;
        }
      }
    } finally {
      setAllPending(false);
      tasks.reload();
    }
  }

  return (
    <AdultLayout>
      <Title text="Проверка" hint="Дела детей ждут вашего подтверждения, награды — выдачи" />
      <div className="sub">Ждут подтверждения</div>
      {tasks.error && <div className="err">{tasks.error}</div>}
      {tasks.data && !tasks.data.length && <div className="note">Нет дел, которые ждут проверки.</div>}
      <div className="list">
        {tasks.data?.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            viewerId={me?.id ?? null}
            viewerIsAdult
            avatars={avatars}
            onChanged={tasks.reload}
          />
        ))}
      </div>
      {tasks.data && tasks.data.length > 1 && (
        <>
          <button className="cta" disabled={allPending} onClick={() => void confirmAll()}>
            {allPending ? "Сохраняем…" : `Подтвердить всё (${tasks.data.length})`}
          </button>
          {allError && <div className="err">{allError}</div>}
        </>
      )}
      <div className="sub">Купленные награды</div>
      {purchases.error && <div className="err">{purchases.error}</div>}
      {purchases.data && !purchases.data.length && (
        <div className="note">Нет покупок, которые нужно выдать.</div>
      )}
      <div className="list">
        {purchases.data?.map((p) => (
          <PurchaseCard key={p.id} purchase={p} onChanged={purchases.reload} />
        ))}
      </div>
      <button className="cta violet" onClick={() => navigate("/child-mode")}>
        🧒 Включить детский режим
      </button>
    </AdultLayout>
  );
}
