import { useState } from "react";

import { api } from "../shared/api/endpoints";
import { useAction } from "../shared/lib/useAction";
import { ActionButton } from "../shared/ui/ActionButton";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

export function PinScreen() {
  const [password, setPassword] = useState("");
  const [pin, setPin] = useState("");
  const [saved, setSaved] = useState(false);
  const save = useAction(() => api.setPin(password, pin));

  async function submit() {
    setSaved(false);
    if (pin.length !== 4) return;
    if ((await save.run()).ok) {
      setSaved(true);
      setPassword("");
      setPin("");
    }
  }

  return (
    <AdultLayout>
      <Title text="PIN-код детского режима" hint="Без него ребёнок не выйдет из детского режима. Не используйте 1111 или 1234." />
      <section className="panel">
        <label className="field">
          Новый PIN-код
          <input
            className="pass"
            type="password"
            inputMode="numeric"
            autoComplete="off"
            maxLength={4}
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
          />
        </label>
        <label className="field">
          Ваш пароль
          <input
            className="pass"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {saved && <div className="toast">PIN-код сохранён</div>}
        <ActionButton state={save.state} className="cta violet" onClick={() => void submit()}>
          Сохранить PIN-код
        </ActionButton>
      </section>
    </AdultLayout>
  );
}
