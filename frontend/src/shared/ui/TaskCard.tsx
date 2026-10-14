import { useState, type ReactNode } from "react";

import { api } from "../api/endpoints";
import type { Purchase, Task } from "../api/types";
import { REWARD_ICONS, TASK_ICONS, avatar } from "../catalog";
import { errorText, useAction, type ActionState } from "../lib/useAction";
import { Tile } from "./layout";
import "../styles/kanban.css";

function CardShell({
  icon,
  title,
  meta,
  done,
  children,
}: {
  icon: { emoji: string; tint: string };
  title: string;
  meta: ReactNode;
  done?: boolean;
  children?: ReactNode;
}) {
  return (
    <div className={`kcard ${done ? "done" : ""}`}>
      <Tile emoji={icon.emoji} tint={icon.tint} />
      <div>
        <div className="ktitle">{title}</div>
        <div className="kmeta">{meta}</div>
      </div>
      {children}
    </div>
  );
}

function CardAction({
  label,
  state,
  onClick,
  tone = "green",
}: {
  label: string;
  state: ActionState;
  onClick: () => void;
  tone?: "green" | "violet" | "soft";
}) {
  const failure = errorText(state);
  return (
    <>
      <button className={`kact ${tone}`} disabled={state.kind === "pending"} onClick={onClick}>
        {state.kind === "pending" ? "…" : label}
      </button>
      {failure && <div className="err">{failure}</div>}
    </>
  );
}

// Одна карточка дела на всех экранах: на доске, в своих делах и в очереди проверки.
// Кнопка видна только тому, кому действие разрешено; права всё равно проверяет сервер.
export function TaskCard({
  task,
  viewerId,
  viewerIsAdult,
  avatars,
  onChanged,
}: {
  task: Task;
  viewerId: string | null;
  viewerIsAdult: boolean;
  avatars: Map<string, string>;
  onChanged: () => void;
}) {
  const take = useAction((key) => api.take(key, task.id));
  const mark = useAction((key) => api.mark(key, task.id));
  const confirm = useAction((key) => api.confirm(key, task.id));
  const mine = task.assignee_member_id === viewerId;
  const run = async (action: typeof take) => (await action.run()).ok && onChanged();

  let action: ReactNode = null;
  if (task.status === "open")
    action = <CardAction label="🙋 Беру" tone="violet" state={take.state} onClick={() => void run(take)} />;
  else if (task.status === "assigned" && mine)
    action = <CardAction label="✓ Сделал" state={mark.state} onClick={() => void run(mark)} />;
  else if (task.status === "marked" && viewerIsAdult)
    action = <CardAction label="Подтвердить" state={confirm.state} onClick={() => void run(confirm)} />;

  return (
    <CardShell
      icon={TASK_ICONS[task.icon]}
      title={task.title}
      done={task.status === "confirmed"}
      meta={
        <>
          <span className="chip me">+{task.points} ⭐</span>
          {task.assignee_member_id ? (
            <span>
              {avatar(avatars.get(task.assignee_member_id) ?? "")} {mine ? "Ты" : task.assignee_name}
            </span>
          ) : (
            <span>от: {task.created_by_name}</span>
          )}
        </>
      }
    >
      {action}
    </CardShell>
  );
}

export function PurchaseCard({ purchase, onChanged }: { purchase: Purchase; onChanged: () => void }) {
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState("");
  const give = useAction((key) => api.give(key, purchase.id));
  const cancel = useAction((key) => api.cancelPurchase(key, purchase.id, reason.trim()));
  return (
    <CardShell
      icon={REWARD_ICONS[purchase.icon]}
      title={purchase.title}
      meta={
        <>
          <span className="chip me">{purchase.price} ⭐</span>
          <span>{purchase.child_name} ждёт награду</span>
        </>
      }
    >
      {cancelling ? (
        <>
          <input
            className="pass small kfield"
            value={reason}
            maxLength={300}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Почему отменяете"
          />
          <CardAction
            label="Отменить покупку"
            tone="soft"
            state={cancel.state}
            onClick={async () => reason.trim() && (await cancel.run()).ok && onChanged()}
          />
        </>
      ) : (
        <>
          <CardAction
            label="Выдана"
            state={give.state}
            onClick={async () => (await give.run()).ok && onChanged()}
          />
          <button className="kact soft" onClick={() => setCancelling(true)}>
            Отменить
          </button>
        </>
      )}
    </CardShell>
  );
}

export { CardAction, CardShell };
