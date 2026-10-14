import { api } from "../shared/api/endpoints";
import { avatar } from "../shared/catalog";
import { useLoad } from "../shared/lib/useLoad";
import { HandoverSheet, KeyIcon } from "./HandoverSheet";

export function ChildApp() {
  const { data: me } = useLoad(api.me);
  const { data: balance } = useLoad(api.balance);
  return (
    <div className="app notabs">
      <header className="hd">
        <div className="player">
          <div className="av">{me ? avatar(me.avatar) : ""}</div>
          <b>{me?.name}</b>
        </div>
        <span className="bal">
          <i>⭐</i>
          {balance?.available ?? ""}
        </span>
        <button className="grown" aria-label="Режим взрослого, нужен PIN-код">
          <KeyIcon />
          <span>Взрослым</span>
        </button>
      </header>
      <HandoverSheet balance={balance?.available ?? null} />
    </div>
  );
}
