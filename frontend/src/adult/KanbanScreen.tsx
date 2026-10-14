import { api } from "../shared/api/endpoints";
import { useLoad } from "../shared/lib/useLoad";
import { Kanban } from "../shared/ui/Kanban";
import { AdultLayout } from "./AdultLayout";

export function KanbanScreen() {
  const { data: me } = useLoad(api.me);
  return (
    <AdultLayout wide>
      <div className="title">
        <h1>Все дела семьи</h1>
        <p>Кто что делает сейчас и что уже готово сегодня</p>
      </div>
      <Kanban viewerId={me?.id ?? null} viewerIsAdult />
    </AdultLayout>
  );
}
