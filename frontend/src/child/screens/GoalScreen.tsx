import { api } from "../../shared/api/endpoints";
import { useLoad } from "../../shared/lib/useLoad";
import { GoalView } from "../../shared/ui/GoalView";
import { useChild } from "../context";
import { MainHeader, Title } from "../parts";

export function GoalScreen() {
  const { me } = useChild();
  const { data: goal, error } = useLoad(api.goal);
  return (
    <>
      <MainHeader />
      <Title text="Семья" hint="Тут видно, сколько звёздочек мы заработали вместе" />
      {error && !goal && <div className="note">{error}</div>}
      {goal && <GoalView goal={goal} viewerId={me?.id ?? null} child />}
    </>
  );
}
