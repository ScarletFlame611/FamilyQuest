import { useRef, useState } from "react";

import { ApiError, NetworkError } from "../shared/api/client";
import { api } from "../shared/api/endpoints";
import type { Purchase, Task } from "../shared/api/types";
import { REWARD_ICONS, TASK_ICONS } from "../shared/catalog";
import { KeyedAction } from "../shared/lib/keyedAction";
import { navigate } from "../shared/lib/router";
import { useAction } from "../shared/lib/useAction";
import { useLoad } from "../shared/lib/useLoad";
import { ActionButton } from "../shared/ui/ActionButton";
import { AdultLayout } from "./AdultLayout";

function TaskRow({ task, onDone }: { task: Task; onDone: () => void }) {
  const confirm = useAction((key) => api.confirm(key, task.id));
  return (
    <div className="row wrap">
      <span className="ic">{TASK_ICONS[task.icon].emoji}</span>
      <span className="t">
        {task.title}
        <small>
          {task.assignee_name}, +{task.points} баллов
        </small>
      </span>
      <span className="actions">
        <ActionButton
          state={confirm.state}
          className="btn green"
          onClick={async () => (await confirm.run()).ok && onDone()}
        >
          Подтвердить
        </ActionButton>
      </span>
    </div>
  );
}

function PendingTasks() {
  const { data: tasks, error, reload } = useLoad(api.pendingTasks);
  // У каждого дела свой ключ: при повторе после обрыва связи уже засчитанные
  // дела вернут сохранённый ответ, а не начислят баллы второй раз
  const actions = useRef(new Map<string, KeyedAction>());
  const [allState, setAllState] = useState<"idle" | "pending" | "offline" | "error">("idle");
  const [allError, setAllError] = useState("");

  async function confirmAll() {
    if (!tasks || allState === "pending") return;
    setAllState("pending");
    setAllError("");
    for (const task of tasks) {
      const action = actions.current.get(task.id) ?? new KeyedAction();
      actions.current.set(task.id, action);
      try {
        await action.run((key) => api.confirm(key, task.id));
        actions.current.delete(task.id);
      } catch (reason) {
        if (reason instanceof NetworkError) {
          setAllState("offline");
          return;
        }
        // Дело могли подтвердить с другого телефона: это не повод останавливать остальные
        if (!(reason instanceof ApiError && reason.status === 409)) {
          setAllState("error");
          setAllError(reason instanceof Error ? reason.message : "Ошибка");
          reload();
          return;
        }
      }
    }
    setAllState("idle");
    reload();
  }

  return (
    <section className="panel">
      <h2>Ждут подтверждения</h2>
      {error && <div className="err">{error}</div>}
      {tasks && !tasks.length && <p>Нет дел, которые ждут проверки.</p>}
      {tasks?.map((task) => <TaskRow key={task.id} task={task} onDone={reload} />)}
      {tasks && tasks.length > 1 && (
        <ActionButton
          state={
            allState === "error"
              ? { kind: "error", error: new Error(allError) }
              : { kind: allState }
          }
          className="btn"
          onClick={() => void confirmAll()}
        >
          Подтвердить всё ({tasks.length})
        </ActionButton>
      )}
    </section>
  );
}

function PurchaseRow({ purchase, onDone }: { purchase: Purchase; onDone: () => void }) {
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState("");
  const give = useAction((key) => api.give(key, purchase.id));
  const cancel = useAction((key) => api.cancelPurchase(key, purchase.id, reason.trim()));
  return (
    <div className="row wrap">
      <span className="ic">{REWARD_ICONS[purchase.icon].emoji}</span>
      <span className="t">
        {purchase.title}
        <small>
          {purchase.child_name}, {purchase.price} баллов отложено
        </small>
      </span>
      <span className="actions">
        <ActionButton
          state={give.state}
          className="btn green"
          onClick={async () => (await give.run()).ok && onDone()}
        >
          Выдана
        </ActionButton>
        {!cancelling && (
          <button className="btn soft" onClick={() => setCancelling(true)}>
            Отменить
          </button>
        )}
      </span>
      {cancelling && (
        <div className="field" style={{ width: "100%" }}>
          Почему отменяете
          <input
            className="pass small"
            value={reason}
            maxLength={300}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Например: сегодня уже было сладкое"
          />
          <ActionButton
            state={cancel.state}
            className="btn"
            onClick={async () => reason.trim() && (await cancel.run()).ok && onDone()}
          >
            Отменить покупку
          </ActionButton>
        </div>
      )}
    </div>
  );
}

function PendingPurchases() {
  const { data: purchases, error, reload } = useLoad(api.pendingPurchases);
  return (
    <section className="panel">
      <h2>Купленные награды</h2>
      {error && <div className="err">{error}</div>}
      {purchases && !purchases.length && <p>Нет покупок, которые нужно выдать.</p>}
      {purchases?.map((p) => <PurchaseRow key={p.id} purchase={p} onDone={reload} />)}
    </section>
  );
}

export function HomeScreen() {
  return (
    <AdultLayout>
      <PendingTasks />
      <PendingPurchases />
      <button
        className="cta violet"
       
        onClick={() => navigate("/child-mode")}
      >
        Включить детский режим
      </button>
    </AdultLayout>
  );
}
