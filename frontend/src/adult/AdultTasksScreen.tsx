import { api } from "../shared/api/endpoints";
import { navigate } from "../shared/lib/router";
import { useLoad } from "../shared/lib/useLoad";
import { useAvatars } from "../shared/ui/Kanban";
import { TaskCard } from "../shared/ui/TaskCard";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

export function AdultTasksScreen() {
  const my = useLoad(api.myTasks);
  const board = useLoad(api.board);
  const { data: me } = useLoad(api.me);
  const avatars = useAvatars();

  function reloadAll() {
    my.reload();
    board.reload();
  }

  const card = (task: NonNullable<typeof my.data>[number]) => (
    <TaskCard
      key={task.id}
      task={task}
      viewerId={me?.id ?? null}
      viewerIsAdult
      avatars={avatars}
      onChanged={reloadAll}
    />
  );

  return (
    <AdultLayout>
      <Title text="Мои дела" hint="Своё дело засчитывается сразу, без подтверждения" />
      {my.error && <div className="err">{my.error}</div>}
      {my.data && !my.data.length && <div className="note">Своих дел нет. Возьмите дело ниже.</div>}
      <div className="list">{my.data?.map(card)}</div>
      <div className="sub">Можно взять</div>
      {board.error && <div className="err">{board.error}</div>}
      {board.data && !board.data.length && <div className="note">На общей доске пусто.</div>}
      <div className="list">{board.data?.map(card)}</div>
      <button className="cta violet" onClick={() => navigate("/tasks/new")}>
        ➕ Новое дело
      </button>
    </AdultLayout>
  );
}
