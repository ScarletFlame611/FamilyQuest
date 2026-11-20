import { useState, type FormEvent } from "react";

import { ApiError, NetworkError } from "../shared/api/client";
import { api } from "../shared/api/endpoints";
import type { AcceptInvite } from "../shared/api/types";
import { avatar } from "../shared/catalog";
import { navigate, usePath } from "../shared/lib/router";
import { useLoad } from "../shared/lib/useLoad";
import "../shared/styles/adult.css";

const AVATARS: AcceptInvite["avatar"][] = ["woman", "man"];

// Открывается без входа: человек ещё не зарегистрирован, а семью сервер возьмёт из ссылки
export function JoinScreen() {
  const token = decodeURIComponent(usePath().slice("/join/".length));
  const invite = useLoad(() => api.invite(token));
  const [name, setName] = useState("");
  const [face, setFace] = useState<AcceptInvite["avatar"]>("woman");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    if (password.length < 8) return setError("Пароль — не короче 8 символов");
    setPending(true);
    setError("");
    try {
      await api.acceptInvite(token, { name: name.trim(), avatar: face, email: email.trim(), password });
      navigate("/", { replace: true });
    } catch (reason) {
      if (reason instanceof NetworkError || reason instanceof ApiError) setError(reason.message);
      else throw reason;
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="app notabs adult">
      <div className="title">
        <h1>FamilyQuest</h1>
        <p>
          {invite.data
            ? `${invite.data.invited_by} зовёт вас в семью «${invite.data.family_name}»`
            : "Приглашение в семью"}
        </p>
      </div>
      {invite.error && (
        <section className="panel">
          <div className="err">{invite.error}</div>
          <button className="cta soft" onClick={() => navigate("/login", { replace: true })}>
            У меня уже есть аккаунт
          </button>
        </section>
      )}
      {!invite.data && !invite.error && <div className="note">Проверяем ссылку…</div>}
      {invite.data && (
        <form className="panel" onSubmit={submit}>
          <label className="field">
            Как вас называть в семье
            <input
              className="pass"
              value={name}
              maxLength={100}
              onChange={(e) => setName(e.target.value)}
              placeholder="Например: Бабушка"
              required
            />
          </label>
          <div className="field">
            Аватар
            <div className="choices">
              {AVATARS.map((id) => (
                <button
                  key={id}
                  type="button"
                  className={id === face ? "on" : ""}
                  onClick={() => setFace(id)}
                  aria-pressed={id === face}
                >
                  {avatar(id)}
                </button>
              ))}
            </div>
          </div>
          <label className="field">
            Почта
            <input
              className="pass"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="field">
            Пароль
            <small>Не короче 8 символов</small>
            <input
              className="pass"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <div className="err">{error}</div>
          <button className="cta violet" disabled={pending}>
            {pending ? "Присоединяемся…" : "Присоединиться к семье"}
          </button>
        </form>
      )}
    </div>
  );
}
