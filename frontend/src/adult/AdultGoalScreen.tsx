import { api } from "../shared/api/endpoints";
import { useLoad } from "../shared/lib/useLoad";
import { GoalView } from "../shared/ui/GoalView";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

export function AdultGoalScreen() {
  const { data: me } = useLoad(api.me);
  return (
    <AdultLayout>
      <Title text="Копилка семьи" hint="Баллы за дела всей семьи сами засчитываются в копилку" />
      <GoalView viewerId={me?.id ?? null} />
    </AdultLayout>
  );
}
