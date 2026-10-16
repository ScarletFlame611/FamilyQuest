import { api } from "../api/endpoints";
import { GOAL_ICONS, avatar } from "../catalog";
import { useLoad } from "../lib/useLoad";
import { Tile } from "./layout";

// Для ребёнка подписи короче и лента в виде «Мама: приготовить ужин, +20»
export function GoalView({ viewerId, child }: { viewerId: string | null; child?: boolean }) {
  const { data: goal, error } = useLoad(api.goal);
  if (error && !goal) return <div className="note">{error}</div>;
  if (!goal) return null;
  const max = Math.max(1, ...goal.contributions.map((c) => c.points));
  const look = GOAL_ICONS[goal.icon];
  return (
    <>
      <div className="goal">
        <Tile emoji={look.emoji} tint={look.tint} hero />
        <h2>{goal.title}</h2>
        <div className="bar">
          <div style={{ width: `${Math.min(100, Math.round((goal.progress / goal.target) * 100))}%` }} />
        </div>
        <div className="nums">
          {goal.progress} <small>из {goal.target} ⭐</small>
        </div>
      </div>
      <div className="sub">{child ? "Кто сколько заработал" : "Кто сколько положил"}</div>
      <div className="members">
        {goal.contributions.map((c) => {
          const mine = c.member_id === viewerId;
          return (
            <div key={c.member_id} className={`mem ${mine ? "me" : ""}`}>
              <div className="av">{avatar(c.avatar)}</div>
              <div>
                <div className="who">{mine ? "Ты" : c.name}</div>
                <div className="bar thin">
                  <div style={{ width: `${Math.round((c.points / max) * 100)}%` }} />
                </div>
              </div>
              <span className="n">{c.points}</span>
            </div>
          );
        })}
      </div>
      <div className="sub">Недавно</div>
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
    </>
  );
}
