import { useEffect } from "react";

import { AdultGoalScreen } from "./adult/AdultGoalScreen";
import { AdultTasksScreen } from "./adult/AdultTasksScreen";
import { ChildModeScreen } from "./adult/ChildModeScreen";
import { HomeScreen } from "./adult/HomeScreen";
import { KanbanScreen } from "./adult/KanbanScreen";
import { LoginScreen } from "./adult/LoginScreen";
import { MoreScreen } from "./adult/MoreScreen";
import { NewTaskScreen } from "./adult/NewTaskScreen";
import { PinScreen } from "./adult/PinScreen";
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
  const allowed =
    role === "child" ? path.startsWith("/kid") : role === "adult" ? path in ADULT_SCREENS : path === "/login";

  useEffect(() => {
    if (!allowed) navigate(homeOf(role), { replace: true });
  }, [allowed, role]);

  if (role === "child") return <ChildApp />;
  if (role === null) return <LoginScreen />;
  const Screen = ADULT_SCREENS[path] ?? HomeScreen;
  return <Screen />;
}
