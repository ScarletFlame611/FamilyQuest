import { useState } from "react";

import { api } from "../shared/api/endpoints";
import type { GoalIcon } from "../shared/api/types";
import { GOAL_ICONS } from "../shared/catalog";
import { useAction } from "../shared/lib/useAction";
import { useLoad } from "../shared/lib/useLoad";
import { ActionButton } from "../shared/ui/ActionButton";
import { GoalView } from "../shared/ui/GoalView";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

const ICONS = Object.keys(GOAL_ICONS) as GoalIcon[];
const MAX_TARGET = 100000;

function NewGoal({ onCreated }: { onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [icon, setIcon] = useState<GoalIcon>("tent");
  const [target, setTarget] = useState("300");
  const [hint, setHint] = useState("");
  const create = useAction((key) =>
    api.createGoal(key, { title: title.trim(), icon, target: Number(target) }),
  );

  async function submit() {
    const value = Number(target);
    if (!title.trim()) return setHint("Напишите, на что копит семья");
    if (!Number.isInteger(value) || value < 1 || value > MAX_TARGET)
      return setHint(`Сколько баллов нужно — целое число от 1 до ${MAX_TARGET}`);
    setHint("");
    if ((await create.run()).ok) onCreated();
  }

  return (
    <section className="panel">
      <h2>Новая цель</h2>
      <label className="field">
        На что копим
        <input
          className="pass"
          value={title}
          maxLength={60}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Например: Поход в лес"
        />
      </label>
      <div className="field">
        Иконка
        <div className="icons roomy">
          {ICONS.map((id) => (
            <button
              key={id}
              className={id === icon ? "on" : ""}
              onClick={() => setIcon(id)}
              aria-pressed={id === icon}
            >
              <span className="tile" style={{ ["--tint" as string]: GOAL_ICONS[id].tint }}>
                {GOAL_ICONS[id].emoji}
              </span>
              {GOAL_ICONS[id].label}
            </button>
          ))}
        </div>
      </div>
      <label className="field">
        Сколько баллов нужно
        <small>Считаются баллы всей семьи с этого момента</small>
        <input
          className="pass"
          inputMode="numeric"
          value={target}
          onChange={(e) => setTarget(e.target.value.replace(/\D/g, ""))}
        />
      </label>
      <div className="err">{hint}</div>
      <ActionButton state={create.state} className="cta violet" onClick={() => void submit()}>
        Начать копить
      </ActionButton>
    </section>
  );
}

export function AdultGoalScreen() {
  const { data: me } = useLoad(api.me);
  const { data: goal, error, reload } = useLoad(api.goal);
  return (
    <AdultLayout>
      <Title text="Копилка семьи" hint="Баллы за дела всей семьи сами засчитываются в копилку" />
      {!goal && !error && <div className="note">Загружаем копилку…</div>}
      {error && !goal && <div className="note">{error}</div>}
      {goal && <GoalView goal={goal} viewerId={me?.id ?? null} />}
      {/* Новую цель можно начать, только когда прежняя накоплена или её нет */}
      {(goal?.reached || (error && !goal)) && <NewGoal onCreated={reload} />}
    </AdultLayout>
  );
}
