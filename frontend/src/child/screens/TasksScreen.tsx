import { useEffect, useState } from "react";

import { api } from "../../shared/api/endpoints";
import { useLoad } from "../../shared/lib/useLoad";
import { clearFresh, clearToast, peekFresh, peekToast } from "../context";
import { JumpCard, MainHeader, TaskCard, Title } from "../parts";

export function TasksScreen() {
  const { data: tasks } = useLoad(api.myTasks);
  const [toast] = useState(peekToast);
  const [fresh] = useState(peekFresh);
  useEffect(() => {
    clearToast();
    clearFresh();
  }, []);
  const open = tasks?.filter((t) => t.status !== "confirmed") ?? [];
  const done = tasks?.filter((t) => t.status === "confirmed") ?? [];
  return (
    <>
      <MainHeader />
      <Title text="Мои дела" hint="Сделал дело? Нажми на него" />
      {toast && <div className="toast">{toast}</div>}
      <div className="list">
        {open.map((task) => (
          <TaskCard key={task.id} task={task} fresh={task.id === fresh} />
        ))}
      </div>
      <JumpCard
        to="/kid/board"
        emoji="⭐"
        text="Хочешь ещё звёздочек?"
        hint="Возьми дело"
        label="Хочешь ещё звёздочек? Возьми дело"
      />
      {done.length > 0 && (
        <>
          <div className="sub">Сделано</div>
          <div className="list">
            {done.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
          </div>
        </>
      )}
    </>
  );
}
