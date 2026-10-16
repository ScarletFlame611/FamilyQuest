import { useEffect, useState } from "react";

import { api } from "../../shared/api/endpoints";
import { REWARD_ICONS, TASK_ICONS } from "../../shared/catalog";
import { navigate } from "../../shared/lib/router";
import { useLoad } from "../../shared/lib/useLoad";
import { starsReturnPath, useChild } from "../context";
import { AutoReturnTimer, PointsChip, Tile } from "../parts";

const BURST = [
  ["-110px", "-80px"],
  ["110px", "-80px"],
  ["-120px", "40px"],
  ["120px", "40px"],
  ["0", "-130px"],
  ["-60px", "120px"],
  ["60px", "120px"],
];

// Праздничный экран сам возвращает к списку за то же время, что идёт полоска таймера
function useAutoReturn(path: string, ms = 2600) {
  useEffect(() => {
    const timer = setTimeout(() => navigate(path, { replace: true }), ms);
    return () => clearTimeout(timer);
  }, [path, ms]);
}

export function DoneScreen({ id }: { id: string }) {
  const { data: task } = useLoad(() => api.task(id));
  useAutoReturn("/kid");
  const look = task ? TASK_ICONS[task.icon] : null;
  return (
    <div className="focus" onClick={() => navigate("/kid", { replace: true })}>
      <div className="burst">
        {look && <Tile emoji={look.emoji} tint={look.tint} hero />}
        {BURST.map(([dx, dy]) => (
          <span key={dx + dy} style={{ ["--dx" as string]: dx, ["--dy" as string]: dy }}>
            ⭐
          </span>
        ))}
      </div>
      <h1>Молодец!</h1>
      {task && <PointsChip points={task.points} />}
      <div className="note">Взрослые проверят дело, и звёздочки появятся</div>
      <AutoReturnTimer />
    </div>
  );
}

export function BoughtScreen({ id }: { id: string }) {
  const { data: offers } = useLoad(api.rewards);
  const { balance } = useChild();
  useAutoReturn("/kid/shop");
  const reward = offers?.find((offer) => offer.id === id);
  const look = reward ? REWARD_ICONS[reward.icon] : null;
  return (
    <div className="focus" onClick={() => navigate("/kid/shop", { replace: true })}>
      {look && <Tile emoji={look.emoji} tint={look.tint} hero />}
      <h1>Куплено!</h1>
      <div className="note">
        Взрослые увидят покупку и выдадут награду. У тебя осталось {balance?.available ?? ""} ⭐
      </div>
      <AutoReturnTimer />
    </div>
  );
}

export function StarsScreen() {
  const { balance } = useChild();
  const [back] = useState(starsReturnPath);
  useAutoReturn(back, 3500);
  return (
    <div className="focus" onClick={() => navigate(back, { replace: true })}>
      <div className="burst">
        <Tile emoji="⭐" tint="var(--amber-soft)" hero />
        {BURST.map(([dx, dy]) => (
          <span key={dx + dy} style={{ ["--dx" as string]: dx, ["--dy" as string]: dy }}>
            ⭐
          </span>
        ))}
      </div>
      <div className="bignum">{balance?.available ?? ""}</div>
      <h1>Столько звёздочек у тебя</h1>
      <div className="note">Делай дела, и звёздочек станет больше</div>
      <AutoReturnTimer seconds={3.5} />
    </div>
  );
}
