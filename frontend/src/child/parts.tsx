import type { ReactNode } from "react";

import type { Task } from "../shared/api/types";
import { TASK_ICONS, avatar } from "../shared/catalog";
import { navigate } from "../shared/lib/router";
import { useChild } from "./context";
import { KeyIcon } from "./HandoverSheet";

const ARROW = (
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
);

function BalanceChip() {
  const { balance } = useChild();
  const value = balance?.available ?? 0;
  return (
    <button className="bal" onClick={() => navigate("/kid/shop")} aria-label={`Мои звёздочки: ${value}`}>
      <i>⭐</i>
      {balance ? value : ""}
    </button>
  );
}

export function MainHeader() {
  const { me } = useChild();
  return (
    <header className="hd">
      <div className="player">
        <div className="av">{me ? avatar(me.avatar) : ""}</div>
        <b>{me?.name}</b>
      </div>
      <BalanceChip />
      <button
        className="grown"
        onClick={() => navigate("/kid/pin")}
        aria-label="Режим взрослого, нужен PIN-код"
      >
        <KeyIcon />
        <span>Взрослым</span>
      </button>
    </header>
  );
}

export function SubHeader({ back, withBalance = true }: { back: string; withBalance?: boolean }) {
  return (
    <header className="hd">
      <button className="back" onClick={() => navigate(back)} aria-label="Назад">
        {ARROW}
      </button>
      <span className="spacer" />
      {withBalance && <BalanceChip />}
    </header>
  );
}

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

export function PointsChip({ points }: { points: number }) {
  return <span className="chip me">+{points} ⭐</span>;
}

export function TaskCard({ task, onBoard }: { task: Task; onBoard?: boolean }) {
  const { members } = useChild();
  const look = TASK_ICONS[task.icon];
  const done = task.status === "confirmed";
  let side: ReactNode = <PointsChip points={task.points} />;
  if (task.status === "marked") side = <span className="chip wait">⏳ Проверяют</span>;
  if (done)
    side = (
      <span className="chip ok" aria-label="Готово">
        ✅
      </span>
    );
  const author = members.find((m) => m.id === task.created_by_member_id);
  // Глагол по аватару взрослого; если его не знаем, обходимся без рода
  const added =
    author?.avatar === "woman" ? "Добавила" : author?.avatar === "man" ? "Добавил" : "Добавлено:";
  return (
    <button
      className={`tcard ${done ? "done" : ""}`}
      onClick={() => navigate(`/kid/task/${task.id}`)}
      aria-label={task.title}
    >
      <Tile emoji={look.emoji} tint={look.tint} />
      <span className="tname">
        {task.title}
        {onBoard && (
          <span className="who-gave">
            {added} {task.created_by_name}
          </span>
        )}
      </span>
      {side}
    </button>
  );
}

export function AutoReturnTimer() {
  return (
    <div className="timer" aria-hidden="true">
      <i />
    </div>
  );
}
