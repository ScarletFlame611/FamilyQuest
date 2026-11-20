import { useState } from "react";

import { api } from "../shared/api/endpoints";
import type { InviteLink } from "../shared/api/types";
import { useAction } from "../shared/lib/useAction";
import { ActionButton } from "../shared/ui/ActionButton";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

export function InviteScreen() {
  const [link, setLink] = useState<InviteLink | null>(null);
  const [copied, setCopied] = useState(false);
  const create = useAction(() => api.createInvite());
  const url = link ? `${window.location.origin}/join/${link.token}` : "";

  async function makeLink() {
    const result = await create.run();
    if (!result.ok) return;
    setLink(result.value);
    setCopied(false);
  }

  async function copy() {
    // Без https буфер обмена недоступен: тогда ссылку можно выделить и скопировать вручную
    await navigator.clipboard?.writeText(url).then(() => setCopied(true), () => undefined);
  }

  return (
    <AdultLayout>
      <Title text="Пригласить взрослого" hint="Второй родитель, бабушка или няня — со своим входом" />
      <section className="panel">
        <div className="note">
          Ссылка работает 48 часов и только один раз. Детей приглашать не нужно — их профиль
          заводит взрослый.
        </div>
        {link && (
          <>
            <input className="pass small" readOnly value={url} onFocus={(e) => e.target.select()} />
            <div className="note">
              Действует до{" "}
              {new Date(link.expires_at).toLocaleString("ru-RU", {
                day: "numeric",
                month: "long",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
            <button className="cta" onClick={() => void copy()}>
              {copied ? "Скопировано ✓" : "Скопировать ссылку"}
            </button>
          </>
        )}
        <ActionButton
          state={create.state}
          className={link ? "cta soft" : "cta violet"}
          onClick={() => void makeLink()}
        >
          {link ? "Создать новую ссылку" : "Создать ссылку"}
        </ActionButton>
      </section>
    </AdultLayout>
  );
}
