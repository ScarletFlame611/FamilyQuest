import { useState } from "react";

import { api } from "../shared/api/endpoints";
import type { RewardAdmin, RewardIcon } from "../shared/api/types";
import { REWARD_ICONS } from "../shared/catalog";
import { useAction } from "../shared/lib/useAction";
import { useLoad } from "../shared/lib/useLoad";
import { LoadState } from "../shared/ui/LoadState";
import { ActionButton } from "../shared/ui/ActionButton";
import { CardAction, CardShell } from "../shared/ui/TaskCard";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

const ICONS = Object.keys(REWARD_ICONS) as RewardIcon[];
const MAX_PRICE = 10000;

// Те же правила, что проверяет сервер, чтобы подсказка появлялась до отправки
function problem(title: string, price: string): string {
  const value = Number(price);
  if (!title.trim()) return "Напишите, что получит ребёнок";
  if (!Number.isInteger(value) || value < 1 || value > MAX_PRICE)
    return `Цена — целое число баллов от 1 до ${MAX_PRICE}`;
  return "";
}

function NewReward({ onCreated }: { onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [icon, setIcon] = useState<RewardIcon>("ice_cream");
  const [price, setPrice] = useState("20");
  const [hint, setHint] = useState("");
  const create = useAction((key) =>
    api.createReward(key, { title: title.trim(), icon, price: Number(price) }),
  );

  async function submit() {
    const found = problem(title, price);
    setHint(found);
    if (found || !(await create.run()).ok) return;
    setTitle("");
    onCreated();
  }

  return (
    <section className="panel">
      <h2>Новая награда</h2>
      <label className="field">
        Что получит ребёнок
        <input
          className="pass"
          value={title}
          maxLength={60}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Например: Поход в кино"
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
              <span className="tile" style={{ ["--tint" as string]: REWARD_ICONS[id].tint }}>
                {REWARD_ICONS[id].emoji}
              </span>
              {REWARD_ICONS[id].label}
            </button>
          ))}
        </div>
      </div>
      <label className="field">
        Цена в баллах
        <input
          className="pass"
          inputMode="numeric"
          value={price}
          onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))}
        />
      </label>
      <div className="err">{hint}</div>
      <ActionButton state={create.state} className="cta violet" onClick={() => void submit()}>
        Добавить награду
      </ActionButton>
    </section>
  );
}

function RewardRow({ reward, onChanged }: { reward: RewardAdmin; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(reward.title);
  const [price, setPrice] = useState(String(reward.price));
  const [hint, setHint] = useState("");
  const save = useAction((key) =>
    api.updateReward(key, reward.id, { title: title.trim(), price: Number(price) }),
  );
  const toggle = useAction((key) => api.updateReward(key, reward.id, { hidden: !reward.hidden }));

  async function submit() {
    const found = problem(title, price);
    setHint(found);
    if (found || !(await save.run()).ok) return;
    setEditing(false);
    onChanged();
  }

  if (editing) {
    return (
      <section className="panel">
        <label className="field">
          Название
          <input
            className="pass"
            value={title}
            maxLength={60}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label className="field">
          Цена в баллах
          <small>Уже купленные награды останутся по прежней цене</small>
          <input
            className="pass"
            inputMode="numeric"
            value={price}
            onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))}
          />
        </label>
        <div className="err">{hint}</div>
        <ActionButton state={save.state} className="cta violet" onClick={() => void submit()}>
          Сохранить
        </ActionButton>
        <button className="cta soft" onClick={() => setEditing(false)}>
          Не менять
        </button>
      </section>
    );
  }

  return (
    <CardShell
      icon={REWARD_ICONS[reward.icon]}
      title={reward.title}
      done={reward.hidden}
      meta={
        <>
          <span className="chip me">{reward.price} ⭐</span>
          {reward.hidden && <span className="chip grey">Скрыта от детей</span>}
        </>
      }
    >
      <button className="kact soft" onClick={() => setEditing(true)}>
        Изменить
      </button>
      <CardAction
        label={reward.hidden ? "Вернуть" : "Скрыть"}
        tone="soft"
        state={toggle.state}
        onClick={async () => (await toggle.run()).ok && onChanged()}
      />
    </CardShell>
  );
}

export function RewardsScreen() {
  const rewards = useLoad(api.manageRewards);
  const shown = rewards.data?.filter((r) => !r.hidden) ?? [];
  const hidden = rewards.data?.filter((r) => r.hidden) ?? [];

  return (
    <AdultLayout>
      <Title text="Награды" hint="Что дети могут купить за баллы" />
      <NewReward onCreated={rewards.reload} />
      <div className="sub">В каталоге у детей</div>
      <LoadState state={rewards} />
      {rewards.data && !shown.length && (
        <div className="note">Пока нет наград. Добавьте первую — дети увидят её сразу.</div>
      )}
      <div className="list">
        {shown.map((r) => (
          <RewardRow key={`${r.id}:${r.title}:${r.price}`} reward={r} onChanged={rewards.reload} />
        ))}
      </div>
      {hidden.length > 0 && (
        <>
          <div className="sub">Скрытые</div>
          <div className="list">
            {hidden.map((r) => (
              <RewardRow key={r.id} reward={r} onChanged={rewards.reload} />
            ))}
          </div>
        </>
      )}
    </AdultLayout>
  );
}
