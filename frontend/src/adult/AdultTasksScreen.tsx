import { api } from "../shared/api/endpoints";
import type { Task } from "../shared/api/types";
import { TASK_ICONS } from "../shared/catalog";
import { useAction } from "../shared/lib/useAction";
import { useLoad } from "../shared/lib/useLoad";
import { ActionButton } from "../shared/ui/ActionButton";
import { AdultLayout } from "./AdultLayout";

function MyTaskRow({ task, onDone }: { task: Task; onDone: () => void }) {
  const mark = useAction((key) => api.mark(key, task.id));
  const done = task.status === "confirmed";
  return (
    <div className="row wrap">
      <span className="ic">{TASK_ICONS[task.icon].emoji}</span>
      <span className="t">
        {task.title}
        <small>{done ? `засчитано, +${task.points} баллов` : `+${task.points} баллов`}</small>
      </span>
      <span className="actions">
        {done ? (
          <span className="chip ok">✅</span>
        ) : (
          // Своё дело взрослый отмечает сам: баллы начисляются сразу, без подтверждения
          <ActionButton
            state={mark.state}
            className="btn green"
            onClick={async () => (await mark.run()).ok && onDone()}
          >
            Сделал
          </ActionButton>
        )}
      </span>
    </div>
  );
}

function BoardRow({ task, onTaken }: { task: Task; onTaken: () => void }) {
  const take = useAction((key) => api.take(key, task.id));
  return (
    <div className="row wrap">
      <span className="ic">{TASK_ICONS[task.icon].emoji}</span>
      <span className="t">
        {task.title}
        <small>
          +{task.points} баллов · добавил(а) {task.created_by_name}
        </small>
      </span>
      <span className="actions">
        <ActionButton
          state={take.state}
          className="btn"
          onClick={async () => (await take.run()).ok && onTaken()}
        >
          Беру
        </ActionButton>
      </span>
    </div>
  );
}

export function AdultTasksScreen() {
  const my = useLoad(api.myTasks);
  const board = useLoad(api.board);
  const balance = useLoad(api.balance);

  function reloadAll() {
    my.reload();
    board.reload();
    balance.reload();
  }

  return (
    <AdultLayout>
      <div className="title">
        <h1>Дела</h1>
        <p>Мои баллы: {balance.data?.balance ?? "…"}. Они идут и в личный счёт, и в общую цель семьи.</p>
      </div>
      <section className="panel">
        <h2>Мои дела</h2>
        {my.error && <div className="err">{my.error}</div>}
        {my.data && !my.data.length && <p>Своих дел нет. Возьмите дело с доски ниже.</p>}
        {my.data?.map((task) => <MyTaskRow key={task.id} task={task} onDone={reloadAll} />)}
      </section>
      <section className="panel">
        <h2>Можно взять</h2>
        {board.error && <div className="err">{board.error}</div>}
        {board.data && !board.data.length && <p>На общей доске пусто.</p>}
        {board.data?.map((task) => <BoardRow key={task.id} task={task} onTaken={reloadAll} />)}
      </section>
    </AdultLayout>
  );
}
