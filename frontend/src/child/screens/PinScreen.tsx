import { useEffect, useState } from "react";

import { ApiError, NetworkError } from "../../shared/api/client";
import { api } from "../../shared/api/endpoints";
import { useChild } from "../context";
import { SubHeader } from "../parts";

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"];

function message(reason: unknown): string {
  if (reason instanceof NetworkError) return "Нет связи с сервером. Попробуйте ещё раз";
  if (reason instanceof ApiError) return reason.message;
  return "Что-то пошло не так";
}

export function PinScreen({ back }: { back: string }) {
  const { setTabsHidden } = useChild();
  const [pin, setPin] = useState("");
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState("");
  const [shake, setShake] = useState(false);
  const [busy, setBusy] = useState(false);
  const [password, setPassword] = useState("");

  useEffect(() => {
    setTabsHidden(true);
    return () => setTabsHidden(false);
  }, [setTabsHidden]);

  async function submit(code: string) {
    setBusy(true);
    try {
      // При успехе сессия становится взрослой, и приложение само откроет экран взрослого
      await api.exitChildMode(code);
    } catch (reason) {
      setPin("");
      if (reason instanceof ApiError && reason.status === 429) {
        setLocked(true);
        setError("");
      } else {
        const left = reason instanceof ApiError ? reason.body.attempts_left : undefined;
        setError(left ? `Неверный код. Осталось попыток: ${left}` : message(reason));
        setShake(true);
      }
    } finally {
      setBusy(false);
    }
  }

  // Состояние обновляется функцией: быстрые нажатия подряд приходят до перерисовки,
  // и цифра из старого значения затёрла бы предыдущую
  function press(key: string) {
    if (busy) return;
    setShake(false);
    setPin((current) => (key === "⌫" ? current.slice(0, -1) : (current + key).slice(0, 4)));
  }

  useEffect(() => {
    if (pin.length === 4 && !busy) void submit(pin);
    // Зависимость только от введённого кода: отправка срабатывает на четвёртую цифру
  }, [pin]);

  async function submitPassword() {
    if (!password || busy) return;
    setBusy(true);
    try {
      await api.exitChildModeWithPassword(password);
    } catch (reason) {
      setPassword("");
      setError(
        reason instanceof ApiError && reason.status === 422
          ? "Пароль не подошёл. Попросите взрослого ввести пароль от аккаунта."
          : message(reason),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <SubHeader back={back} withBalance={false} />
      <div className="pinwrap">
        <h1>Только для взрослых</h1>
        <div className="note">
          {locked
            ? ""
            : "Введите 4 цифры PIN-кода, который вы задали при включении детского режима. "}
          Если ты ребёнок, позови маму или папу.
        </div>
        {locked ? (
          <>
            <div className="err">PIN-код введён неверно 5 раз, поэтому вход по PIN временно закрыт.</div>
            <div className="note">
              Войдите паролем от аккаунта FamilyQuest, тем же, что при входе в приложение.
            </div>
            <input
              className="pass"
              type="password"
              placeholder="Пароль от аккаунта"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <div className="err">{error}</div>
            <button
              className="cta violet"
              style={{ fontSize: 20, minHeight: 60 }}
              disabled={busy}
              onClick={() => void submitPassword()}
            >
              Войти по паролю
            </button>
          </>
        ) : (
          <>
            <div className={`dots ${shake ? "shake" : ""}`} aria-label={`Введено цифр: ${pin.length}`}>
              {[0, 1, 2, 3].map((i) => (
                <i key={i} className={i < pin.length ? "on" : ""} />
              ))}
            </div>
            <div className="err">{error}</div>
            <div className="pad">
              {KEYS.map((key, i) =>
                key ? (
                  <button key={key} onClick={() => press(key)} aria-label={key === "⌫" ? "Стереть" : key}>
                    {key}
                  </button>
                ) : (
                  <span key={i} />
                ),
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}
