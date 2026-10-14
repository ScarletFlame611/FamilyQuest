import { api } from "../../shared/api/endpoints";
import { GOAL_ICONS, avatar } from "../../shared/catalog";
import { useLoad } from "../../shared/lib/useLoad";
import { useChild } from "../context";
import { MainHeader, Tile, Title } from "../parts";

export function GoalScreen() {
  const { data: goal, error } = useLoad(api.goal);
  const { me } = useChild();
  const max = Math.max(1, ...(goal?.contributions.map((c) => c.points) ?? [0]));
  return (
    <>
      <MainHeader />
      <Title text="Копилка семьи" hint="Звёздочки за дела сами засчитываются в копилку" />
      {error && !goal && <div className="note">{error}</div>}
      {goal && (
        <>
          <div className="goal">
            <Tile emoji={GOAL_ICONS[goal.icon].emoji} tint={GOAL_ICONS[goal.icon].tint} hero />
            <h2>{goal.title}</h2>
            <div className="bar">
              <div style={{ width: `${Math.min(100, Math.round((goal.progress / goal.target) * 100))}%` }} />
            </div>
            <div className="nums">
              {goal.progress} <small>из {goal.target} ⭐</small>
            </div>
          </div>
          <div className="sub">Кто сколько положил</div>
          <div className="members">
            {goal.contributions.map((c) => {
              const mine = c.member_id === me?.id;
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
                {item.name} · {item.title}, {item.points > 0 ? "+" : ""}
                {item.points}
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
