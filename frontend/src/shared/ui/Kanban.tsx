import { api } from "../api/endpoints";
import type { Task } from "../api/types";
import { useLoad } from "../lib/useLoad";
import "../styles/kanban.css";
import { TaskCard } from "./TaskCard";

const COLUMNS: { status: Task["status"]; title: string; empty: string }[] = [
  { status: "open", title: "Можно взять", empty: "Свободных дел нет" },
  { status: "assigned", title: "В работе", empty: "Никто ничего не делает" },
  { status: "marked", title: "На проверке", empty: "Проверять нечего" },
  { status: "confirmed", title: "Готово сегодня", empty: "Пока ничего" },
];

export function useAvatars(): Map<string, string> {
  const { data: family } = useLoad(api.family);
  return new Map(family?.members.map((m) => [m.id, m.avatar]) ?? []);
}

export function Kanban({
  viewerId,
  viewerIsAdult,
  onChanged,
}: {
  viewerId: string | null;
  viewerIsAdult: boolean;
  onChanged?: () => void;
}) {
  const { data: tasks, error, reload } = useLoad(api.familyTasks);
  const avatars = useAvatars();

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
                <TaskCard
                  key={task.id}
                  task={task}
                  viewerId={viewerId}
                  viewerIsAdult={viewerIsAdult}
                  avatars={avatars}
                  onChanged={changed}
                />
              ))}
            </section>
          );
        })}
      </div>
    </>
  );
}
