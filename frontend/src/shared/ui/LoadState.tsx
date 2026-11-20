type Loaded = { data: unknown; error: string | null; reload: () => void };

// Одинаковые состояния на всех экранах: пока данных нет — «Загружаем», при сбое —
// текст ошибки и кнопка повтора, чтобы экран не оставался молча пустым
export function LoadState({ state, child }: { state: Loaded; child?: boolean }) {
  if (state.error) {
    return (
      <div className="panel" role="alert">
        <div className="err">{state.error}</div>
        <button className="cta soft" onClick={state.reload}>
          {child ? "Ещё раз" : "Повторить"}
        </button>
      </div>
    );
  }
  if (state.data === null) return <div className="note">Загружаем…</div>;
  return null;
}
