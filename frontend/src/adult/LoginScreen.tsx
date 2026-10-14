import { useState, type FormEvent } from "react";

import { ApiError, NetworkError } from "../shared/api/client";
import { api } from "../shared/api/endpoints";
import "../shared/styles/adult.css";

export function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError("");
    try {
      await api.login(email, password);
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
        <p>Вход для взрослых</p>
      </div>
      <form className="panel" onSubmit={submit}>
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
          <input
            className="pass"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <div className="err">{error}</div>
        <button className="cta violet" disabled={pending}>
          {pending ? "Входим…" : "Войти"}
        </button>
      </form>
    </div>
  );
}
