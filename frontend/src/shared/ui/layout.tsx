import type { ReactNode } from "react";

import { navigate } from "../lib/router";

// action — главная кнопка экрана: на ноутбуке она стоит справа от заголовка,
// на телефоне экран показывает её крупно внизу, как раньше
export function Title({ text, hint, action }: { text: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="title-row">
      <div className="title">
        <h1>{text}</h1>
        {hint && <p>{hint}</p>}
      </div>
      {action && <div className="head-action">{action}</div>}
    </div>
  );
}

// Раздел экрана: на телефоне подзаголовок над списком, на ноутбуке — колонка с подложкой
export function Block({ title, count, children }: { title: string; count?: number; children: ReactNode }) {
  return (
    <section className="block">
      <h2>
        {title}
        {count !== undefined && count > 0 && <span className="chip">{count}</span>}
      </h2>
      {children}
    </section>
  );
}

export function Empty({ emoji, text }: { emoji: string; text: string }) {
  return (
    <div className="empty">
      <span aria-hidden="true">{emoji}</span>
      {text}
    </div>
  );
}

export function Tile({ emoji, tint, hero }: { emoji: string; tint: string; hero?: boolean }) {
  return (
    <span className={hero ? "hero" : "tile"} style={{ ["--tint" as string]: tint }}>
      {emoji}
    </span>
  );
}

export function BackButton({ to }: { to: string }) {
  return (
    <button className="back" onClick={() => navigate(to)} aria-label="Назад">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M15 5l-7 7 7 7" />
      </svg>
    </button>
  );
}

export type TabItem = readonly [href: string, emoji: string, label: string];

export function TabBar({
  tabs,
  active,
  onPress,
}: {
  tabs: readonly TabItem[];
  active: string;
  onPress?: (label: string) => void;
}) {
  return (
    <nav className="tabs" aria-label="Разделы">
      <div className="tabs-in" style={{ gridTemplateColumns: `repeat(${tabs.length}, 1fr)` }}>
        {tabs.map(([href, emoji, label]) => (
          <button
            key={href}
            className={`tab ${active === href ? "on" : ""}`}
            aria-current={active === href ? "page" : undefined}
            onClick={() => {
              onPress?.(label);
              navigate(href);
            }}
          >
            <span className="ind">{emoji}</span>
            {label}
          </button>
        ))}
      </div>
    </nav>
  );
}
