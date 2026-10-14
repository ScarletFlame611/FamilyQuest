import type { ReactNode } from "react";

import { api } from "../shared/api/endpoints";
import { navigate, usePath } from "../shared/lib/router";
import "../shared/styles/adult.css";

const LINKS = [
  ["/", "Главная"],
  ["/tasks/new", "Новое дело"],
  ["/pin", "PIN-код"],
] as const;

export function AdultLayout({ children }: { children: ReactNode }) {
  const path = usePath();
  return (
    <div className="app notabs adult">
      <header className="hd">
        <b>FamilyQuest</b>
        <button className="grown" onClick={() => void api.logout()}>
          Выйти
        </button>
      </header>
      <nav className="nav">
        {LINKS.map(([href, label]) => (
          <button key={href} className={path === href ? "on" : ""} onClick={() => navigate(href)}>
            {label}
          </button>
        ))}
      </nav>
      {children}
    </div>
  );
}
