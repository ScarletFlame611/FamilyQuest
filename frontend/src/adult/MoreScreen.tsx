import { api } from "../shared/api/endpoints";
import { navigate } from "../shared/lib/router";
import { Title } from "../shared/ui/layout";
import { AdultLayout } from "./AdultLayout";

const ITEMS = [
  ["/tasks/new", "➕", "Новое дело", "Название, иконка, цена и кому"],
  ["/child-mode", "🧒", "Детский режим", "Передать телефон ребёнку"],
  ["/pin", "🔑", "PIN-код", "Чтобы выйти из детского режима"],
  ["/sessions", "📝", "Журнал детского режима", "Что делал ребёнок и когда"],
] as const;

export function MoreScreen() {
  return (
    <AdultLayout>
      <Title text="Ещё" />
      <div className="list">
        {ITEMS.map(([href, emoji, title, hint]) => (
          <button key={href} className="tcard" onClick={() => navigate(href)}>
            <span className="tile">{emoji}</span>
            <span className="tname">
              {title}
              <span className="who-gave">{hint}</span>
            </span>
            <span />
          </button>
        ))}
      </div>
      <button className="cta soft" onClick={() => void api.logout()}>
        Выйти из аккаунта
      </button>
    </AdultLayout>
  );
}
