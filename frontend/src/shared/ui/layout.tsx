import { navigate } from "../lib/router";

export function Title({ text, hint }: { text: string; hint?: string }) {
  return (
    <div className="title">
      <h1>{text}</h1>
      {hint && <p>{hint}</p>}
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
