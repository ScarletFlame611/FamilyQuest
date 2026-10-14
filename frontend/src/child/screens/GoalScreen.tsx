import { GoalView } from "../../shared/ui/GoalView";
import { useChild } from "../context";
import { MainHeader, Title } from "../parts";

export function GoalScreen() {
  const { me } = useChild();
  return (
    <>
      <MainHeader />
      <Title text="Копилка семьи" hint="Звёздочки за дела сами засчитываются в копилку" />
      <GoalView viewerId={me?.id ?? null} />
    </>
  );
}
