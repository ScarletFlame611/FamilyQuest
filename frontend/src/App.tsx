import { useEffect, useState } from "react";

import type { components } from "./shared/api/schema";

type Health = components["schemas"]["HealthOut"];

export function App() {
  const [health, setHealth] = useState<Health["status"] | "loading">("loading");

  useEffect(() => {
    fetch("/api/health")
      .then((response) => response.json() as Promise<Health>)
      .then((body) => setHealth(body.status))
      .catch(() => setHealth("unavailable"));
  }, []);

  return (
    <main style={{ maxWidth: 440, margin: "0 auto", padding: 16 }}>
      <h1 style={{ fontFamily: "var(--head)" }}>FamilyQuest</h1>
      <p>Сервер: {health === "ok" ? "работает" : health === "loading" ? "проверяем…" : "недоступен"}</p>
    </main>
  );
}
