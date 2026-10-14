import type { GoalIcon, RewardIcon, TaskIcon } from "./api/types";

type Look = { emoji: string; tint: string; label: string };

// Тип Record по перечню из OpenAPI: новая иконка на бэкенде без картинки здесь
// не соберётся, поэтому список иконок у фронтенда и бэкенда один
export const TASK_ICONS: Record<TaskIcon, Look> = {
  toys: { emoji: "🧸", tint: "#ffe6d2", label: "Игрушки" },
  cat: { emoji: "🐱", tint: "#fff0c2", label: "Питомец" },
  plant: { emoji: "🪴", tint: "#dcf3e2", label: "Цветы" },
  trash: { emoji: "🗑️", tint: "#e3ecff", label: "Мусор" },
  dishes: { emoji: "🍽️", tint: "#ffe2ea", label: "Посуда" },
  socks: { emoji: "🧦", tint: "#ece6ff", label: "Носки" },
  bed: { emoji: "🛏️", tint: "#e3ecff", label: "Кровать" },
  laundry: { emoji: "🧺", tint: "#ffe6d2", label: "Стирка" },
  shopping: { emoji: "🛒", tint: "#fff0c2", label: "Магазин" },
  mop: { emoji: "🧽", tint: "#dcf3e2", label: "Уборка" },
  iron: { emoji: "👕", tint: "#ece6ff", label: "Одежда" },
  tools: { emoji: "🔧", tint: "#e3ecff", label: "Ремонт" },
  vacuum: { emoji: "🧹", tint: "#ffe2ea", label: "Пылесос" },
  cooking: { emoji: "🍳", tint: "#fff0c2", label: "Готовка" },
};

export const REWARD_ICONS: Record<RewardIcon, Look> = {
  ice_cream: { emoji: "🍦", tint: "#fff0c2", label: "Мороженое" },
  cartoon: { emoji: "📺", tint: "#e3ecff", label: "Мультфильм" },
  markers: { emoji: "🖍️", tint: "#ffe2ea", label: "Фломастеры" },
  puzzle: { emoji: "🧩", tint: "#dcf3e2", label: "Пазл" },
  park: { emoji: "🎡", tint: "#ece6ff", label: "Парк" },
  construction_set: { emoji: "🧱", tint: "#ffe6d2", label: "Конструктор" },
};

export const GOAL_ICONS: Record<GoalIcon, Look> = {
  tent: { emoji: "🏕️", tint: "#ece6ff", label: "Поход" },
};

const AVATARS: Record<string, string> = { woman: "👩", man: "👨", fox: "🦊", panda: "🐼" };

export function avatar(id: string): string {
  return AVATARS[id] ?? "🙂";
}
