import { useEffect, useState } from "react";

import { api } from "../shared/api/endpoints";
import type { FamilyExport } from "../shared/api/types";
import { useAction } from "../shared/lib/useAction";
import { useLoad } from "../shared/lib/useLoad";
import { ActionButton } from "../shared/ui/ActionButton";
import { LoadState } from "../shared/ui/LoadState";
import { CardShell } from "../shared/ui/TaskCard";
import { Block, Empty, Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

const POLL_MS = 2000;

const when = (iso: string) =>
  new Date(iso).toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

const day = (iso: string) => new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long" });

function size(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} КБ`
    : `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

// Что видит взрослый: сначала задание ждёт свободного обработчика, потом собирается;
// повторная попытка видна, чтобы долгое ожидание не выглядело зависанием
function stateText(e: FamilyExport): string {
  if (e.status === "ready") return `Готово, ${size(e.file_size ?? 0)}, хранится до ${day(e.expires_at ?? e.created_at)}`;
  if (e.status === "expired") return "Срок хранения истёк";
  if (e.status === "failed") return e.error ?? "Не удалось собрать";
  if (e.job_status === "running") {
    return e.attempts > 1 ? `Собираем, попытка ${e.attempts} из ${e.max_attempts}` : "Собираем архив";
  }
  return e.attempts > 0 ? `Повторим через несколько секунд, попытка ${e.attempts} из ${e.max_attempts}` : "В очереди";
}

async function download(id: string, createdAt: string) {
  const url = URL.createObjectURL(await api.familyExportFile(id));
  const link = document.createElement("a");
  link.href = url;
  link.download = `FamilyQuest, данные семьи на ${day(createdAt)}.zip`;
  link.click();
  URL.revokeObjectURL(url);
}

function ExportRow({ item }: { item: FamilyExport }) {
  const [failure, setFailure] = useState("");
  return (
    <CardShell
      icon={{ emoji: "📦", tint: "#ece6ff" }}
      title={`Выгрузка от ${when(item.created_at)}`}
      done={item.status === "expired"}
      meta={<span>{stateText(item)}</span>}
    >
      {item.status === "ready" && (
        <button
          className="kact violet"
          onClick={() => void download(item.id, item.created_at).catch((e: Error) => setFailure(e.message))}
        >
          Скачать
        </button>
      )}
      {failure && <div className="err">{failure}</div>}
    </CardShell>
  );
}

export function FamilyDataScreen() {
  const exports = useLoad(api.familyExports);
  const request = useAction((key) => api.requestFamilyExport(key));
  const preparing = exports.data?.some((e) => e.status === "pending") ?? false;

  // Пока архив собирается, список обновляется сам: обработчик работает в фоне
  useEffect(() => {
    if (!preparing) return;
    const timer = setInterval(exports.reload, POLL_MS);
    return () => clearInterval(timer);
  }, [preparing, exports.reload]);

  async function start() {
    if ((await request.run()).ok) exports.reload();
  }

  return (
    <AdultLayout>
      <Title text="Данные семьи" hint="Всё, что FamilyQuest хранит о семье, одним архивом для Excel" />
      <div className="cols">
        <section className="panel">
          <h2>Что войдёт в архив</h2>
          <p>
            Участники семьи, все дела, история баллов каждого, награды и покупки, общие цели и журнал
            детского режима. Каждый раздел лежит отдельным файлом, его можно открыть в Excel.
          </p>
          <p>
            Пароли, PIN-код и ключи входа в архив не попадают. Готовый файл хранится 7 дней, потом
            его нужно подготовить заново.
          </p>
          <p>
            Архив собирается в фоне, обычно за несколько секунд. Экран можно закрыть: файл появится в
            списке, когда будет готов.
          </p>
          <ActionButton state={request.state} className="cta violet" onClick={() => void start()}>
            {preparing ? "Архив уже готовится" : "Подготовить архив"}
          </ActionButton>
        </section>
        <Block title="Выгрузки" count={exports.data?.length}>
          <LoadState state={exports} />
          {exports.data && !exports.data.length && (
            <Empty emoji="📦" text="Выгрузок пока не было. Подготовьте первую." />
          )}
          <div className="list rows">
            {exports.data?.map((item) => (
              <ExportRow key={item.id} item={item} />
            ))}
          </div>
        </Block>
      </div>
    </AdultLayout>
  );
}
