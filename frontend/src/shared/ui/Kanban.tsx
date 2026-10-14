import { api } from "../api/endpoints";
import type { Task } from "../api/types";
import { TASK_ICONS, avatar } from "../catalog";
import { errorText, useAction } from "../lib/useAction";
import { useLoad } from "../lib/useLoad";
import "../styles/kanban.css";

const COLUMNS: { status: Task["status"]; title: string; empty: string }[] = [
  { status: "open", title: "Можно взять", empty: "Свободных дел нет" },
  { status: "assigned", title: "В работе", empty: "Никто ничего не делает" },
  { status: "marked", title: "На проверке", empty: "Проверять нечего" },
  { status: "confirmed", title: "Готово сегодня", empty: "Пока ничего" },
];

type Props = {
  viewerId: string | null;
  viewerIsAdult: boolean;
  onChanged?: () => void;
};

function Card({ task, viewerId, viewerIsAdult, onDone, avatars }: {
  task: Task;
  viewerId: string | null;
  viewerIsAdult: boolean;
  onDone: () => void;
  avatars: Map<string, string>;
}) {
  const take = useAction((key) => api.take(key, task.id));
  const mark = useAction((key) => api.mark(key, task.id));
  const confirm = useAction((key) => api.confirm(key, task.id));
  const look = TASK_ICONS[task.icon];
  const mine = task.assignee_member_id === viewerId;
  // Кнопка показывается только тому, кому действие разрешено; права всё равно проверяет сервер
  let action = null;
  if (task.status === "open") action = { label: "🙋 Беру", run: take, violet: true };
  else if (task.status === "assigned" && mine) action = { label: "✓ Сделал", run: mark, violet: false };
  else if (task.status === "marked" && viewerIsAdult)
    action = { label: "Подтвердить", run: confirm, violet: false };
  const failure = errorText(take.state) ?? errorText(mark.state) ?? errorText(confirm.state);

  return (
    <div className={`kcard ${task.status === "confirmed" ? "done" : ""}`}>
      <span className="tile" style={{ ["--tint" as string]: look.tint }}>
        {look.emoji}
      </span>
      <div>
        <div className="ktitle">{task.title}</div>
        <div className="kmeta">
          <span className="chip me">+{task.points} ⭐</span>
          {task.assignee_member_id && (
            <span>
              {avatar(avatars.get(task.assignee_member_id) ?? "")} {mine ? "Ты" : task.assignee_name}
            </span>
          )}
        </div>
      </div>
      {action && (
        <button
          className={`kact ${action.violet ? "violet" : ""}`}
          disabled={action.run.pending}
          onClick={async () => (await action.run.run()).ok && onDone()}
        >
          {action.run.pending ? "…" : action.label}
        </button>
      )}
      {failure && <div className="err">{failure}</div>}
    </div>
  );
}

export function Kanban({ viewerId, viewerIsAdult, onChanged }: Props) {
  const { data: tasks, error, reload } = useLoad(api.familyTasks);
  const { data: family } = useLoad(api.family);
  const avatars = new Map(family?.members.map((m) => [m.id, m.avatar]) ?? []);

  function changed() {
    reload();
    onChanged?.();
  }

  return (
    <>
      {error && <div className="err">{error}</div>}
      <div className="kanban">
        {COLUMNS.map((column) => {
          const cards = tasks?.filter((t) => t.status === column.status) ?? [];
          return (
            <section key={column.status} className="kcol" aria-label={column.title}>
              <h2>
                {column.title}
                <span className="chip">{cards.length}</span>
              </h2>
              {tasks && !cards.length && <div className="kempty">{column.empty}</div>}
              {cards.map((task) => (
                <Card
                  key={task.id}
                  task={task}
                  viewerId={viewerId}
                  viewerIsAdult={viewerIsAdult}
                  onDone={changed}
                  avatars={avatars}
                />
              ))}
            </section>
          );
        })}
      </div>
    </>
  );
}
