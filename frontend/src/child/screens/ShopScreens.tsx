import { api } from "../../shared/api/endpoints";
import { ApiError } from "../../shared/api/client";
import type { RewardOffer } from "../../shared/api/types";
import { REWARD_ICONS } from "../../shared/catalog";
import { navigate } from "../../shared/lib/router";
import { errorText, useAction } from "../../shared/lib/useAction";
import { useLoad } from "../../shared/lib/useLoad";
import { stars, useChild } from "../context";
import { MainHeader, SubHeader, Tile, Title } from "../parts";

function OfferChip({ offer }: { offer: RewardOffer }) {
  if (offer.waiting) return <span className="chip wait">⏳ Ждёт выдачи</span>;
  return <span className={`chip ${offer.affordable ? "me" : "grey"}`}>{offer.price} ⭐</span>;
}

export function ShopScreen() {
  const { data: offers } = useLoad(api.rewards);
  return (
    <>
      <MainHeader />
      <Title text="Награды" hint="Выбирай, что хочешь, и покупай за звёздочки" />
      <div className="shop">
        {offers?.map((offer) => {
          const look = REWARD_ICONS[offer.icon];
          return (
            <button
              key={offer.id}
              className={`rcard ${offer.affordable || offer.waiting ? "" : "no"}`}
              onClick={() => navigate(`/kid/reward/${offer.id}`)}
              aria-label={`${offer.title}, ${offer.price} ${stars(offer.price)}`}
            >
              <Tile emoji={look.emoji} tint={look.tint} />
              <span className="rname">{offer.title}</span>
              <OfferChip offer={offer} />
            </button>
          );
        })}
      </div>
    </>
  );
}

export function RewardScreen({ id }: { id: string }) {
  const { data: offers, reload } = useLoad(api.rewards);
  const { refreshBalance } = useChild();
  const buy = useAction((key) => api.buy(key, id));
  const offer = offers?.find((o) => o.id === id);
  if (!offer) return <SubHeader back="/kid/shop" />;
  const look = REWARD_ICONS[offer.icon];
  // Баланс мог измениться с другого телефона: тогда сервер сам скажет, сколько не хватает
  const shortBy =
    buy.state.kind === "error" && buy.state.error instanceof ApiError
      ? buy.state.error.body.missing
      : undefined;
  const failure = shortBy === undefined ? errorText(buy.state) : null;

  async function purchase() {
    const result = await buy.run();
    refreshBalance();
    if (result.ok) navigate(`/kid/bought/${id}`, { replace: true });
    else reload();
  }

  let action;
  if (offer.waiting) action = <div className="state wait">⏳ Ждём взрослых</div>;
  else if (offer.affordable && shortBy === undefined)
    action = (
      <button className="cta" disabled={buy.pending} onClick={() => void purchase()}>
        🛒 Купить
      </button>
    );
  else action = <div className="state need">ещё {shortBy ?? offer.missing} ⭐</div>;

  return (
    <>
      <SubHeader back="/kid/shop" />
      <div className="focus">
        <Tile emoji={look.emoji} tint={look.tint} hero />
        <h1>{offer.title}</h1>
        <span className="chip me">{offer.price} ⭐</span>
        {failure && <div className="err">{failure}</div>}
      </div>
      {action}
    </>
  );
}
