import { api } from "../shared/api/endpoints";
import { useLoad } from "../shared/lib/useLoad";
import { Kanban } from "../shared/ui/Kanban";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

export function KanbanScreen() {
  const { data: me } = useLoad(api.me);
  return (
    <AdultLayout wide>
      <Title text="Все дела семьи" hint="Кто что делает сейчас и что уже готово сегодня" />
      <Kanban viewerId={me?.id ?? null} viewerIsAdult />
    </AdultLayout>
  );
}
