import { api } from "../shared/api/endpoints";
import { navigate } from "../shared/lib/router";
import { useLoad } from "../shared/lib/useLoad";
import { LoadState } from "../shared/ui/LoadState";
import { useAvatars } from "../shared/ui/Kanban";
import { TaskCard } from "../shared/ui/TaskCard";
import { Block, Empty, Title } from "../shared/ui/layout";
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

  const toNewTask = () => navigate("/tasks/new");

  return (
    <AdultLayout>
      <Title
        text="Мои дела"
        hint="Своё дело засчитывается сразу, без подтверждения"
        action={<button onClick={toNewTask}>➕ Новое дело</button>}
      />
      <div className="cols">
        <Block title="Свои дела" count={my.data?.length}>
          <LoadState state={my} />
          {my.data && !my.data.length && (
            <Empty emoji="🙌" text="Своих дел нет. Возьмите дело с общей доски." />
          )}
          <div className="list">{my.data?.map(card)}</div>
        </Block>
        <Block title="Можно взять" count={board.data?.length}>
          <LoadState state={board} />
          {board.data && !board.data.length && <Empty emoji="📭" text="На общей доске пусто." />}
          <div className="list">{board.data?.map(card)}</div>
        </Block>
      </div>
      <button className="cta violet has-head-action" onClick={toNewTask}>
        ➕ Новое дело
      </button>
    </AdultLayout>
  );
}
