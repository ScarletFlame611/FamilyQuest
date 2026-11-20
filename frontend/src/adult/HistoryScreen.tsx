import { useEffect, useState } from "react";

import { api } from "../shared/api/endpoints";
import type { Entry } from "../shared/api/types";
import { avatar } from "../shared/catalog";
import { useLoad } from "../shared/lib/useLoad";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

type Filter = "all" | "earned" | "spent" | "revoked";

const FILTERS: [Filter, string][] = [
  ["all", "Все"],
  ["earned", "Начисления"],
  ["spent", "Траты"],
  ["revoked", "Отмены"],
];

const GROUP: Record<Entry["kind"], Filter> = {
  accrual: "earned",
  reserve: "spent",
  release: "spent",
  spend: "spent",
  reversal: "revoked",
  write_off: "revoked",
};

// Строка так, как её прочтёт родитель: что случилось и с чем
const DESCRIBE: Record<Entry["kind"], (label: string) => string> = {
  accrual: (label) => label,
  reserve: (label) => `Отложено на «${label}»`,
  release: (label) => `Покупка «${label}» отменена`,
  spend: (label) => `Выдана награда «${label}»`,
  reversal: (label) => `Отменено «${label}»`,
  write_off: () => "Минус списан",
};

const when = (iso: string) =>
  new Date(iso).toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

async function downloadCsv(memberId: string, name: string) {
  const url = URL.createObjectURL(await api.memberLedgerCsv(memberId));
  const link = document.createElement("a");
  link.href = url;
  link.download = `История баллов — ${name}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export function HistoryScreen() {
  const { data: family } = useLoad(api.family);
  const { data: balances } = useLoad(api.balances);
  const [memberId, setMemberId] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState("");
  const members = family?.members ?? [];
  const selected = members.find((m) => m.id === memberId) ?? members.find((m) => m.role === "child");

  useEffect(() => {
    if (!selected) return;
    setEntries(null);
    setError("");
    api
      .memberLedger(selected.id)
      .then(setEntries)
      .catch((reason: Error) => setError(reason.message));
  }, [selected?.id]);

  const balance = balances?.find((b) => b.member_id === selected?.id);
  const shown = (entries ?? []).filter((e) => filter === "all" || GROUP[e.kind] === filter);

  return (
    <AdultLayout>
      <Title text="История баллов" hint="Каждое начисление, трата и отмена — отдельной строкой" />
      <div className="choices">
        {members.map((m) => (
          <button
            key={m.id}
            className={m.id === selected?.id ? "on" : ""}
            onClick={() => setMemberId(m.id)}
          >
            {avatar(m.avatar)} {m.name}
          </button>
        ))}
      </div>
      {balance && (
        <div className="row">
          <b>Можно потратить</b>
          <span className="chip me">{balance.available} ⭐</span>
          {balance.reserved > 0 && <span className="chip grey">ещё {balance.reserved} отложено</span>}
        </div>
      )}
      <div className="choices">
        {FILTERS.map(([id, label]) => (
          <button key={id} className={id === filter ? "on" : ""} onClick={() => setFilter(id)}>
            {label}
          </button>
        ))}
      </div>
      {error && <div className="err">{error}</div>}
      {!entries && !error && <div className="note">Загружаем историю…</div>}
      {entries && !shown.length && <div className="note">Таких записей пока нет.</div>}
      <div className="list">
        {shown.map((e) => (
          <div key={e.id} className="kcard">
            <span className="chip me">
              {e.available_delta > 0 ? "+" : ""}
              {e.available_delta}
            </span>
            <div>
              <div className="ktitle">{DESCRIBE[e.kind](e.label)}</div>
              <div className="kmeta">
                <span>{when(e.created_at)}</span>
                {e.reason && <span>· {e.reason}</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
      {selected && entries && entries.length > 0 && (
        <button
          className="cta soft"
          onClick={() =>
            void downloadCsv(selected.id, selected.name).catch((reason: Error) => setError(reason.message))
          }
        >
          Скачать CSV для Excel
        </button>
      )}
    </AdultLayout>
  );
}
