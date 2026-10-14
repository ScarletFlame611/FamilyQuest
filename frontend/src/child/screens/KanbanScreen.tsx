import { Kanban } from "../../shared/ui/Kanban";
import { useChild } from "../context";
import { MainHeader, Title } from "../parts";

export function KanbanScreen() {
  const { me, refreshBalance } = useChild();
  return (
    <>
      <MainHeader />
      <Title text="Все дела семьи" hint="Кто что делает сейчас и что уже готово сегодня" />
      <Kanban viewerId={me?.id ?? null} viewerIsAdult={false} onChanged={refreshBalance} />
    </>
  );
}
