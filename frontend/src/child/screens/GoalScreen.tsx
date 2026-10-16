import { GoalView } from "../../shared/ui/GoalView";
import { useChild } from "../context";
import { MainHeader, Title } from "../parts";

export function GoalScreen() {
  const { me } = useChild();
  return (
    <>
      <MainHeader />
      <Title text="Семья" hint="Тут видно, сколько звёздочек мы заработали вместе" />
      <GoalView viewerId={me?.id ?? null} child />
    </>
  );
}
