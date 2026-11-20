import { api } from "../../shared/api/endpoints";
import { useLoad } from "../../shared/lib/useLoad";
import { LoadState } from "../../shared/ui/LoadState";
import { JumpCard, MainHeader, TaskCard, Title } from "../parts";

export function BoardScreen() {
  const board = useLoad(api.board);
  const tasks = board.data;
  return (
    <>
      <MainHeader />
      <Title text="Можно взять" hint="Возьми любое дело, и оно станет твоим" />
      <LoadState state={board} child />
      {tasks && !tasks.length ? (
        <div className="focus">
          <div className="hero">🙋</div>
          <div className="note">Все дела разобрали. Новые появятся, когда взрослые их добавят.</div>
        </div>
      ) : (
        <div className="list">
          {tasks?.map((task) => (
            <TaskCard key={task.id} task={task} onBoard />
          ))}
        </div>
      )}
      <JumpCard
        to="/kid"
        emoji="📋"
        text="Мои дела"
        hint="Вернуться к своим делам"
        label="Мои дела"
      />
    </>
  );
}
