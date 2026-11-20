import { useEffect } from "react";

import { AdultGoalScreen } from "./adult/AdultGoalScreen";
import { AdultTasksScreen } from "./adult/AdultTasksScreen";
import { ChildModeScreen } from "./adult/ChildModeScreen";
import { HistoryScreen } from "./adult/HistoryScreen";
import { HomeScreen } from "./adult/HomeScreen";
import { InviteScreen } from "./adult/InviteScreen";
import { JoinScreen } from "./adult/JoinScreen";
import { KanbanScreen } from "./adult/KanbanScreen";
import { LoginScreen } from "./adult/LoginScreen";
import { MoreScreen } from "./adult/MoreScreen";
import { NewTaskScreen } from "./adult/NewTaskScreen";
import { PinScreen } from "./adult/PinScreen";
import { RewardsScreen } from "./adult/RewardsScreen";
import { SessionsScreen } from "./adult/SessionsScreen";
import { ChildApp } from "./child/ChildApp";
import { navigate, usePath } from "./shared/lib/router";
import { useSession } from "./shared/session/session";

const ADULT_SCREENS: Record<string, () => JSX.Element> = {
  "/": HomeScreen,
  "/tasks": AdultTasksScreen,
  "/tasks/new": NewTaskScreen,
  "/kanban": KanbanScreen,
  "/goal": AdultGoalScreen,
  "/more": MoreScreen,
  "/rewards": RewardsScreen,
  "/history": HistoryScreen,
  "/invite": InviteScreen,
  "/pin": PinScreen,
  "/child-mode": ChildModeScreen,
  "/sessions": SessionsScreen,
};

function homeOf(role: "adult" | "child" | null): string {
  if (role === "child") return "/kid";
  return role === "adult" ? "/" : "/login";
}

export function App() {
  const session = useSession();
  const path = usePath();
  const role = session?.role ?? null;
  // Адрес из строки браузера ничего не решает: детская сессия всегда остаётся
  // в детском режиме, а взрослый экран открывается только с токеном взрослого
  // Без входа доступны только страница входа и приглашение по ссылке
  const allowed =
    role === "child"
      ? path.startsWith("/kid")
      : role === "adult"
        ? path in ADULT_SCREENS
        : path === "/login" || path.startsWith("/join/");

  useEffect(() => {
    if (!allowed) navigate(homeOf(role), { replace: true });
  }, [allowed, role]);

  if (role === "child") return <ChildApp />;
  if (role === null) return path.startsWith("/join/") ? <JoinScreen /> : <LoginScreen />;
  const Screen = ADULT_SCREENS[path] ?? HomeScreen;
  return <Screen />;
}
