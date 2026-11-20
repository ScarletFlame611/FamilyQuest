import { useState } from "react";

import { api } from "../shared/api/endpoints";
import type { ConfirmAll, Task } from "../shared/api/types";
import { navigate } from "../shared/lib/router";
import { useAction } from "../shared/lib/useAction";
import { useLoad } from "../shared/lib/useLoad";
import { ActionButton } from "../shared/ui/ActionButton";
import { useAvatars } from "../shared/ui/Kanban";
import { PurchaseCard, TaskCard } from "../shared/ui/TaskCard";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

function totalsByChild(tasks: Task[]): [string, number][] {
  const totals = new Map<string, number>();
  for (const task of tasks) {
    const name = task.assignee_name ?? "Без исполнителя";
    totals.set(name, (totals.get(name) ?? 0) + task.points);
  }
  return [...totals];
}

// Все дела очереди засчитываются одним запросом: при обрыве связи повтор уходит
// с тем же ключом, и сервер вернёт сохранённый ответ вместо второго начисления
function ConfirmAllPanel({ tasks, onDone }: { tasks: Task[]; onDone: () => void }) {
  const [reviewing, setReviewing] = useState(false);
  const [skipped, setSkipped] = useState<ConfirmAll["skipped"]>([]);
  const confirm = useAction((key) =>
    api.confirmAll(
      key,
      tasks.map((t) => t.id),
    ),
  );

  async function submit() {
    const result = await confirm.run();
    if (!result.ok) return;
    setSkipped(result.value.skipped);
    setReviewing(false);
    onDone();
  }

  return (
    <>
      {skipped.length > 0 && (
        <div className="note">
          Не засчитаны: {skipped.map((s) => `«${s.title}» — ${s.reason.toLowerCase()}`).join("; ")}
        </div>
      )}
      {tasks.length > 1 && !reviewing && (
        <button className="cta" onClick={() => setReviewing(true)}>
          Подтвердить всё ({tasks.length})
        </button>
      )}
      {reviewing && (
        <section className="panel">
          <h2>Засчитать все дела ({tasks.length})?</h2>
          <div className="list">
            {totalsByChild(tasks).map(([name, points]) => (
              <div key={name} className="row">
                <b>{name}</b>
                <span className="chip me">+{points} ⭐</span>
              </div>
            ))}
          </div>
          <ActionButton state={confirm.state} className="cta" onClick={() => void submit()}>
            Да, засчитать всё
          </ActionButton>
          <button className="cta soft" onClick={() => setReviewing(false)}>
            Не сейчас
          </button>
        </section>
      )}
    </>
  );
}

export function HomeScreen() {
  const tasks = useLoad(api.pendingTasks);
  const purchases = useLoad(api.pendingPurchases);
  const { data: me } = useLoad(api.me);
  const avatars = useAvatars();

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
      {tasks.data && <ConfirmAllPanel tasks={tasks.data} onDone={tasks.reload} />}
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
