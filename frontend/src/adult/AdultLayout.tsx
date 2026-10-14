import { useEffect, type ReactNode } from "react";

import { api } from "../shared/api/endpoints";
import { avatar } from "../shared/catalog";
import { usePath } from "../shared/lib/router";
import { useLoad } from "../shared/lib/useLoad";
import { BackButton, TabBar } from "../shared/ui/layout";
import "../shared/styles/adult.css";

// Те же разделы внизу, что и в детском режиме, но со своими экранами взрослого
const TABS = [
  ["/", "📥", "Проверка"],
  ["/tasks", "📋", "Мои дела"],
  ["/kanban", "🗂️", "Все дела"],
  ["/goal", "🐷", "Копилка"],
  ["/more", "⚙️", "Ещё"],
] as const;

const SECTION_OF: Record<string, string> = {
  "/tasks/new": "/more",
  "/pin": "/more",
  "/sessions": "/more",
  "/child-mode": "/more",
};

export function AdultLayout({ children, wide }: { children: ReactNode; wide?: boolean }) {
  const path = usePath();
  const { data: me } = useLoad(api.me);
  const { data: balance, reload } = useLoad(api.balance);
  useEffect(reload, [path, reload]);
  const section = SECTION_OF[path];

  return (
    <>
      <div className={`app adult ${wide ? "wide" : ""}`}>
        <header className="hd">
          {section ? (
            <>
              <BackButton to={section} />
              <span className="spacer" />
            </>
          ) : (
            <div className="player">
              <div className="av">{me ? avatar(me.avatar) : ""}</div>
              <b>{me?.name}</b>
            </div>
          )}
          <span className="bal" aria-label={`Мои баллы: ${balance?.balance ?? 0}`}>
            <i>⭐</i>
            {balance?.balance ?? ""}
          </span>
        </header>
        {children}
      </div>
      <TabBar tabs={TABS} active={section ?? path} />
    </>
  );
}
