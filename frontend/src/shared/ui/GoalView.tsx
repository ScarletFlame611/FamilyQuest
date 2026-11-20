import type { Goal } from "../api/types";
import { GOAL_ICONS, avatar } from "../catalog";
import { Tile } from "./layout";

// Цель загружает экран: взрослому по ней нужно решить, показывать ли форму новой цели.
// Для ребёнка подписи короче и лента в виде «Мама: приготовить ужин, +20»
export function GoalView({
  goal,
  viewerId,
  child,
}: {
  goal: Goal;
  viewerId: string | null;
  child?: boolean;
}) {
  const max = Math.max(1, ...goal.contributions.map((c) => c.points));
  // Взрослому — таблица вклада от большего к меньшему с долей; ребёнку — порядок семьи, как в прототипе
  const rows = child ? goal.contributions : [...goal.contributions].sort((a, b) => b.points - a.points);
  const total = goal.contributions.reduce((sum, c) => sum + c.points, 0);
  const look = GOAL_ICONS[goal.icon];
  return (
    <div className="cols">
      <div className="goal">
        <Tile emoji={look.emoji} tint={look.tint} hero />
        <h2>{goal.title}</h2>
        <div className="bar">
          <div style={{ width: `${Math.min(100, Math.round((goal.progress / goal.target) * 100))}%` }} />
        </div>
        <div className="nums">
          {goal.progress} <small>из {goal.target} ⭐</small>
        </div>
        {goal.reached && <span className="chip ok">🎉 Копилка полная!</span>}
      </div>
      <div className="col">
        <div className="sub">{child ? "Кто сколько заработал" : "Кто сколько положил"}</div>
        <div className="members">
          {rows.map((c) => {
            const mine = c.member_id === viewerId;
            return (
              <div key={c.member_id} className={`mem ${mine ? "me" : ""}`}>
                <div className="av">{avatar(c.avatar)}</div>
                <div>
                  <div className="who">
                    {mine ? "Ты" : c.name}
                    {!child && total > 0 && ` · ${Math.round((c.points / total) * 100)}%`}
                  </div>
                  <div className="bar thin">
                    <div style={{ width: `${Math.round((c.points / max) * 100)}%` }} />
                  </div>
                </div>
                <span className="n">{c.points}</span>
              </div>
            );
          })}
          {!child && (
            <div className="mem">
              <span />
              <div className="who">Всего</div>
              <span className="n">{total}</span>
            </div>
          )}
        </div>
        <div className="sub">Недавно</div>
        {!goal.feed.length && (
          <div className="note">
            {child ? "Сделай дело — и звёздочки появятся тут" : "Пока никто ничего не положил"}
          </div>
        )}
        <div className="feed">
          {goal.feed.slice(0, 4).map((item) => (
            <div key={item.created_at + item.member_id}>
              <span>{avatar(item.avatar)}</span>
              {child ? `${item.name}: ${item.title.toLowerCase()}` : `${item.name} · ${item.title}`},{" "}
              {item.points > 0 ? "+" : ""}
              {item.points}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
