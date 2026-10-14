import { useState } from "react";

import { api } from "../shared/api/endpoints";
import type { ChildSession, SessionEvents } from "../shared/api/types";
import { useLoad } from "../shared/lib/useLoad";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

const EVENT_NAMES: Record<SessionEvents["events"][number]["type"], string> = {
  screen_opened: "Открыт экран",
  task_opened: "Открыто дело",
  button_pressed: "Нажата кнопка",
  task_taken: "Взято дело",
  task_marked: "Отмечено дело",
  reward_bought: "Куплена награда",
  wrong_pin: "Неверный PIN",
  pin_locked: "PIN заблокирован",
  pin_exit: "Выход по PIN",
  password_exit: "Выход по паролю",
};

function time(value: string): string {
  return new Date(value).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

async function downloadCsv(session: ChildSession) {
  const blob = await api.sessionEventsCsv(session.id);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${session.child_name}-${session.started_at.slice(0, 16).replace(/[:T]/g, "-")}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function SessionRow({ session }: { session: ChildSession }) {
  const [events, setEvents] = useState<SessionEvents | null>(null);
  const [error, setError] = useState("");
  return (
    <div className="row wrap">
      <span className="t">
        {session.child_name}, {time(session.started_at)}
        <small>
          {session.ended_at ? `до ${time(session.ended_at)}` : "идёт сейчас"} · событий:{" "}
          {session.events} · включил(а) {session.started_by_name}
        </small>
      </span>
      <span className="actions">
        <button
          className="btn soft"
          onClick={() =>
            void api
              .sessionEvents(session.id)
              .then(setEvents)
              .catch((e: Error) => setError(e.message))
          }
        >
          Показать
        </button>
        <button
          className="btn"
          onClick={() => void downloadCsv(session).catch((e: Error) => setError(e.message))}
        >
          CSV
        </button>
      </span>
      {error && <div className="err">{error}</div>}
      {events && (
        <div className="field" style={{ width: "100%" }}>
          {events.events.map((e, i) => (
            <small key={i}>
              {e.seconds_from_start.toFixed(1)} с — {EVENT_NAMES[e.type]}
              {e.detail ? `: ${e.detail}` : ""}
            </small>
          ))}
        </div>
      )}
    </div>
  );
}

export function SessionsScreen() {
  const { data: sessions, error } = useLoad(api.childSessions);
  return (
    <AdultLayout>
      <Title text="Журнал детского режима" hint="Что делал ребёнок и через сколько секунд от начала сессии" />
      <section className="panel">
        {error && <div className="err">{error}</div>}
        {sessions && !sessions.length && <p>Детский режим ещё не включали.</p>}
        {sessions?.map((s) => <SessionRow key={s.id} session={s} />)}
      </section>
    </AdultLayout>
  );
}
