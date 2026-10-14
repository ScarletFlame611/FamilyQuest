import { useEffect, useState } from "react";

import { api } from "../../shared/api/endpoints";
import { useLoad } from "../../shared/lib/useLoad";
import { clearToast, peekToast } from "../context";
import { MainHeader, TaskCard, Title } from "../parts";

export function TasksScreen() {
  const { data: tasks } = useLoad(api.myTasks);
  const [toast] = useState(peekToast);
  useEffect(clearToast, []);
  const open = tasks?.filter((t) => t.status !== "confirmed") ?? [];
  const done = tasks?.filter((t) => t.status === "confirmed") ?? [];
  return (
    <>
      <MainHeader />
      <Title text="Мои дела" hint="Сделал дело? Нажми на него" />
      {toast && <div className="toast">{toast}</div>}
      <div className="list">
        {open.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
      </div>
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
