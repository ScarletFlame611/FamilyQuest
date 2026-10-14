import { useState } from "react";

import { api } from "../shared/api/endpoints";
import type { TaskIcon } from "../shared/api/types";
import { TASK_ICONS, avatar } from "../shared/catalog";
import { navigate } from "../shared/lib/router";
import { useAction } from "../shared/lib/useAction";
import { useLoad } from "../shared/lib/useLoad";
import { ActionButton } from "../shared/ui/ActionButton";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

const ICONS = Object.keys(TASK_ICONS) as TaskIcon[];
const BOARD = "board";

export function NewTaskScreen() {
  const { data: family } = useLoad(api.family);
  const [title, setTitle] = useState("");
  const [icon, setIcon] = useState<TaskIcon>("toys");
  const [points, setPoints] = useState("10");
  const [assignee, setAssignee] = useState<string>(BOARD);
  const [hint, setHint] = useState("");
  const create = useAction((key) =>
    api.createTask(key, {
      title: title.trim(),
      icon,
      points: Number(points),
      assignee_id: assignee === BOARD ? null : assignee,
    }),
  );

  async function submit() {
    const value = Number(points);
    if (!title.trim()) return setHint("Напишите, что нужно сделать");
    if (!Number.isInteger(value) || value < 1 || value > 1000)
      return setHint("Цена — целое число баллов от 1 до 1000");
    setHint("");
    if ((await create.run()).ok) navigate("/");
  }

  return (
    <AdultLayout>
      <Title text="Новое дело" />
      <section className="panel">
        <label className="field">
          Что сделать
          <input
            className="pass"
            value={title}
            maxLength={60}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Например: Убрать игрушки"
          />
        </label>
        <div className="field">
          Иконка
          <small>По ней дело узнает ребёнок, который ещё не читает</small>
          <div className="icons">
            {ICONS.map((id) => (
              <button
                key={id}
                className={id === icon ? "on" : ""}
                onClick={() => setIcon(id)}
                aria-pressed={id === icon}
              >
                <span className="tile" style={{ ["--tint" as string]: TASK_ICONS[id].tint }}>
                  {TASK_ICONS[id].emoji}
                </span>
                {TASK_ICONS[id].label}
              </button>
            ))}
          </div>
        </div>
        <label className="field">
          Цена в баллах
          <input
            className="pass"
            inputMode="numeric"
            value={points}
            onChange={(e) => setPoints(e.target.value.replace(/\D/g, ""))}
          />
        </label>
        <div className="field">
          Кому
          <div className="choices">
            {family?.members.map((m) => (
              <button
                key={m.id}
                className={assignee === m.id ? "on" : ""}
                onClick={() => setAssignee(m.id)}
              >
                {avatar(m.avatar)} {m.name}
              </button>
            ))}
            <button
              className={assignee === BOARD ? "on" : ""}
              onClick={() => setAssignee(BOARD)}
            >
              🙋 На общую доску
            </button>
          </div>
        </div>
        <div className="err">{hint}</div>
        <ActionButton state={create.state} className="cta violet" onClick={() => void submit()}>
          Добавить дело
        </ActionButton>
      </section>
    </AdultLayout>
  );
}
