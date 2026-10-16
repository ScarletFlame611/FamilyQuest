import { useCallback, useEffect, useState } from "react";

import { api } from "../shared/api/endpoints";
import { usePath } from "../shared/lib/router";
import { useLoad } from "../shared/lib/useLoad";
import { TabBar } from "../shared/ui/layout";
import { ChildContext } from "./context";
import { track } from "./events";
import { HandoverSheet } from "./HandoverSheet";
import { BoardScreen } from "./screens/BoardScreen";
import { BoughtScreen, DoneScreen, StarsScreen } from "./screens/CelebrationScreens";
import { GoalScreen } from "./screens/GoalScreen";
import { PinScreen } from "./screens/PinScreen";
import { RewardScreen, ShopScreen } from "./screens/ShopScreens";
import { TaskScreen } from "./screens/TaskScreen";
import { TasksScreen } from "./screens/TasksScreen";

const TABS = [
  ["/kid", "📋", "Мои дела"],
  ["/kid/board", "🙋", "Можно взять"],
  ["/kid/shop", "🎁", "Награды"],
  ["/kid/goal", "👨‍👩‍👧", "Семья"],
] as const;

// Дело и звёздочки открываются поверх вкладки, с которой пришёл ребёнок: она остаётся выделенной
function tabOf(screen: string): string | null {
  if (screen === "task" || screen === "stars" || screen === "pin") return null;
  if (screen === "board") return "/kid/board";
  if (screen === "shop" || screen === "reward" || screen === "bought") return "/kid/shop";
  if (screen === "goal") return "/kid/goal";
  return "/kid";
}

function Screen({ screen, id, tab }: { screen: string; id: string; tab: string }) {
  switch (screen) {
    case "board":
      return <BoardScreen />;
    case "task":
      return <TaskScreen key={id} id={id} />;
    case "done":
      return <DoneScreen key={id} id={id} />;
    case "shop":
      return <ShopScreen />;
    case "reward":
      return <RewardScreen key={id} id={id} />;
    case "bought":
      return <BoughtScreen key={id} id={id} />;
    case "goal":
      return <GoalScreen />;
    case "stars":
      return <StarsScreen />;
    case "pin":
      return <PinScreen back={tab} />;
    default:
      return <TasksScreen />;
  }
}

export function ChildApp() {
  const path = usePath();
  const [, , screen = "", id = ""] = path.split("/");
  const { data: me } = useLoad(api.me);
  const { data: family } = useLoad(api.family);
  const { data: balance, reload: refreshBalance } = useLoad(api.balance);
  const [tabsHidden, setTabsHidden] = useState(false);
  const [lastTab, setLastTab] = useState("/kid");
  const tab = tabOf(screen) ?? lastTab;
  if (tab !== lastTab) setLastTab(tab);
  const hide = useCallback((hidden: boolean) => setTabsHidden(hidden), []);
  // Баллы могли начислить с телефона взрослого, пока ребёнок ходил по экранам
  useEffect(refreshBalance, [path, refreshBalance]);
  useEffect(() => {
    if (path.startsWith("/kid")) track("screen_opened", path);
  }, [path]);

  return (
    <ChildContext.Provider
      value={{
        me,
        members: family?.members ?? [],
        balance,
        refreshBalance,
        setTabsHidden: hide,
      }}
    >
      <div
        className={`app ${tabsHidden ? "notabs" : ""}`}
        key={path}
        onClickCapture={(event) => {
          const button = (event.target as HTMLElement).closest("button");
          // Клавиши PIN не пишутся: по ним можно восстановить код
          if (button && !button.closest("[data-secret]")) {
            track("button_pressed", button.getAttribute("aria-label") ?? button.textContent);
          }
        }}
      >
        <Screen screen={screen} id={id} tab={lastTab} />
      </div>
      {!tabsHidden && (
        <TabBar
          tabs={TABS}
          active={tab}
          onPress={(label) => track("button_pressed", `Вкладка: ${label}`)}
        />
      )}
      <HandoverSheet balance={balance?.available ?? null} />
    </ChildContext.Provider>
  );
}
