import type { ReactNode } from "react";

import type { Task } from "../shared/api/types";
import { TASK_ICONS, avatar } from "../shared/catalog";
import { navigate } from "../shared/lib/router";
import { Tile } from "../shared/ui/layout";
import { openStars, useChild } from "./context";
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
    <button
      className="bal"
      onClick={() => openStars(window.location.pathname)}
      aria-label={`Мои звёздочки: ${value}`}
    >
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

export function PointsChip({ points }: { points: number }) {
  return <span className="chip me">+{points} ⭐</span>;
}

export function TaskCard({
  task,
  onBoard,
  fresh,
}: {
  task: Task;
  onBoard?: boolean;
  fresh?: boolean;
}) {
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
      className={`tcard ${done ? "done" : ""} ${fresh ? "fresh" : ""}`}
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

export function AutoReturnTimer({ seconds }: { seconds?: number }) {
  return (
    <div className="timer" aria-hidden="true">
      <i style={seconds ? { animationDuration: `${seconds}s` } : undefined} />
    </div>
  );
}

export function JumpCard({
  to,
  emoji,
  text,
  hint,
  label,
}: {
  to: string;
  emoji: string;
  text: string;
  hint: string;
  label: string;
}) {
  return (
    <button className="jump" onClick={() => navigate(to)} aria-label={label}>
      <span className="tile">{emoji}</span>
      <span>
        {text}
        <small>{hint}</small>
      </span>
      <span className="go" aria-hidden="true">
        →
      </span>
    </button>
  );
}

export { Title, Tile } from "../shared/ui/layout";
