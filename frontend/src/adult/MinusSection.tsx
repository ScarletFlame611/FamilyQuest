import { useState } from "react";

import { api } from "../shared/api/endpoints";
import type { Member } from "../shared/api/types";
import { avatar } from "../shared/catalog";
import { useAction } from "../shared/lib/useAction";
import { useLoad } from "../shared/lib/useLoad";
import { ActionButton } from "../shared/ui/ActionButton";

function MinusRow({ member, minus, onDone }: { member: Member; minus: number; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [hint, setHint] = useState("");
  const writeOff = useAction((key) => api.writeOff(key, member.id, reason.trim()));

  async function submit() {
    if (!reason.trim()) return setHint("Напишите, почему списываете минус");
    setHint("");
    if ((await writeOff.run()).ok) onDone();
  }

  return (
    <section className="panel">
      <div className="row">
        <span>{avatar(member.avatar)}</span>
        <b>{member.name}</b>
        <span className="chip grey">−{minus} ⭐</span>
      </div>
      <div className="note">
        Следующие начисления закроют минус сами. Можно и простить его — это останется в истории.
      </div>
      {open ? (
        <>
          <input
            className="pass small"
            value={reason}
            maxLength={200}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Почему списываете"
          />
          <div className="err">{hint}</div>
          <ActionButton state={writeOff.state} className="cta" onClick={() => void submit()}>
            Списать минус
          </ActionButton>
          <button className="cta soft" onClick={() => setOpen(false)}>
            Не списывать
          </button>
        </>
      ) : (
        <button className="cta soft" onClick={() => setOpen(true)}>
          Списать минус…
        </button>
      )}
    </section>
  );
}

// Раздел виден только когда у кого-то минус: в обычный день он не занимает место
export function MinusSection() {
  const balances = useLoad(api.balances);
  const { data: family } = useLoad(api.family);
  const inMinus = (balances.data ?? []).filter((b) => b.balance < 0);
  if (!family || !inMinus.length) return null;
  const byId = new Map(family.members.map((m) => [m.id, m]));
  return (
    <>
      <div className="sub">Минус на балансе</div>
      {inMinus.map((b) => {
        const member = byId.get(b.member_id);
        return member ? (
          <MinusRow key={b.member_id} member={member} minus={-b.balance} onDone={balances.reload} />
        ) : null;
      })}
    </>
  );
}
