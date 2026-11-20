import { api } from "../../shared/api/endpoints";
import { useLoad } from "../../shared/lib/useLoad";
import { LoadState } from "../../shared/ui/LoadState";
import { GoalView } from "../../shared/ui/GoalView";
import { useChild } from "../context";
import { MainHeader, Title } from "../parts";

export function GoalScreen() {
  const { me } = useChild();
  const loaded = useLoad(api.goal);
  const goal = loaded.data;
  return (
    <>
      <MainHeader />
      <Title text="Семья" hint="Тут видно, сколько звёздочек мы заработали вместе" />
      {!goal && <LoadState state={loaded} child />}
      {goal && <GoalView goal={goal} viewerId={me?.id ?? null} child />}
    </>
  );
}
