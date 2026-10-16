import { useEffect } from "react";

import { api } from "../../shared/api/endpoints";
import { TASK_ICONS } from "../../shared/catalog";
import { navigate } from "../../shared/lib/router";
import { errorText, useAction } from "../../shared/lib/useAction";
import { useLoad } from "../../shared/lib/useLoad";
import { setToast, useChild } from "../context";
import { track } from "../events";
import { PointsChip, SubHeader, Tile } from "../parts";

export function TaskScreen({ id }: { id: string }) {
  const { data: task, reload } = useLoad(() => api.task(id));
  const { setTabsHidden } = useChild();
  const take = useAction((key) => api.take(key, id));
  const mark = useAction((key) => api.mark(key, id));

  const title = task?.title;
  useEffect(() => {
    if (title) track("task_opened", title);
  }, [title]);

  useEffect(() => {
    setTabsHidden(mark.pending);
    return () => setTabsHidden(false);
  }, [mark.pending, setTabsHidden]);

  if (mark.pending)
    return (
      <div className="focus">
        <div className="spinner" role="status" aria-label="Отправляем" />
        <div className="note">Отправляем…</div>
      </div>
    );
  if (!task) return <SubHeader back="/kid" />;

  const look = TASK_ICONS[task.icon];
  const failure = errorText(take.state) ?? errorText(mark.state);

  async function takeTask() {
    if ((await take.run()).ok) {
      setToast(`«${task!.title}» теперь в твоих делах`);
      reload();
    }
  }

  async function markDone() {
    if ((await mark.run()).ok) navigate(`/kid/done/${id}`, { replace: true });
  }

  return (
    <>
      <SubHeader back={task.status === "open" ? "/kid/board" : "/kid"} />
      <div className="focus">
        <Tile emoji={look.emoji} tint={look.tint} hero />
        <h1>{task.title}</h1>
        <PointsChip points={task.points} />
        {task.description && <div className="note">{task.description}</div>}
        {task.status === "assigned" && task.reject_reason && (
          <div className="note">Взрослые вернули дело: {task.reject_reason}</div>
        )}
        {failure && <div className="err">{failure}</div>}
      </div>
      {task.status === "open" && (
        <button className="cta" disabled={take.pending} onClick={() => void takeTask()}>
          🙋 Беру!
        </button>
      )}
      {task.status === "assigned" && (
        <button className="cta" onClick={() => void markDone()}>
          ✓ Сделал!
        </button>
      )}
      {task.status === "marked" && <div className="state wait">⏳ Проверяют</div>}
      {task.status === "confirmed" && (
        <div className="state ok">✅ Готово, звёздочки начислены</div>
      )}
    </>
  );
}
