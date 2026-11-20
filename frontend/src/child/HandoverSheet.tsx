import { useEffect, useState } from "react";

import { clearHandoverHint, isHandoverHintPending } from "./handoverHint";

export function HandoverSheet({ balance }: { balance: number | null }) {
  // Чтение флага без сброса: React в режиме разработки вызывает инициализатор дважды
  const [open, setOpen] = useState(isHandoverHintPending);
  useEffect(clearHandoverHint, []);
  if (!open) return null;
  return (
    <div className="sheet">
      <div className="sheet-card" role="dialog" aria-labelledby="hintT">
        <h2 id="hintT">Детский режим включён</h2>
        <p>
          Ребёнок видит только свои дела, дела, которые можно взять, награды и общую цель семьи.
          Подтверждать дела и выдавать награды он не может.
        </p>
        <div className="demo">
          <span className="bal">
            <i>⭐</i>
            {balance ?? ""}
          </span>
          <span className="grown">
            <KeyIcon />
            <span>Взрослым</span>
          </span>
        </div>
        <p>
          Чтобы вернуться в режим взрослого, нажмите <b>«Взрослым»</b> в правом верхнем углу и
          введите PIN-код.
        </p>
        <button
          className="cta violet"
         
          onClick={() => setOpen(false)}
        >
          Понятно, передаю ребёнку
        </button>
      </div>
    </div>
  );
}

export function KeyIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="8" cy="15" r="4" />
      <path d="M11 12l9-9M17 6l3 3M15 8l2 2" />
    </svg>
  );
}
