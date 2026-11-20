import type { AgeGroup, GoalIcon, RewardIcon, TaskIcon } from "./api/types";

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
  homework: { emoji: "📚", tint: "#e3ecff", label: "Уроки" },
  reading: { emoji: "📖", tint: "#dcf3e2", label: "Чтение" },
  backpack: { emoji: "🎒", tint: "#ffe6d2", label: "Рюкзак" },
  sport: { emoji: "⚽", tint: "#dcf3e2", label: "Спорт" },
  music: { emoji: "🎹", tint: "#ece6ff", label: "Музыка" },
  morning: { emoji: "⏰", tint: "#fff0c2", label: "Утро" },
  sleep: { emoji: "🌙", tint: "#ece6ff", label: "Сон" },
  teeth: { emoji: "🪥", tint: "#e3ecff", label: "Зубы" },
  walk: { emoji: "🌳", tint: "#dcf3e2", label: "Прогулка" },
  call: { emoji: "📞", tint: "#ffe2ea", label: "Звонок" },
  baby: { emoji: "👶", tint: "#ffe6d2", label: "Малыш" },
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
  bicycle: { emoji: "🚲", tint: "#dcf3e2", label: "Велосипед" },
  zoo: { emoji: "🦁", tint: "#fff0c2", label: "Зоопарк" },
  cinema: { emoji: "🎬", tint: "#e3ecff", label: "Кино" },
  pizza: { emoji: "🍕", tint: "#ffe6d2", label: "Пицца" },
  board_game: { emoji: "🎲", tint: "#ffe2ea", label: "Настолка" },
  sea: { emoji: "🌊", tint: "#e3ecff", label: "Море" },
};

const AVATARS: Record<string, string> = { woman: "👩", man: "👨", fox: "🦊", panda: "🐼" };

export function avatar(id: string): string {
  return AVATARS[id] ?? "🙂";
}

export type TaskPreset = { title: string; icon: TaskIcon; points: number };

// Готовые дела по возрасту ребёнка: взрослый выбирает одно, и форма заполняется,
// но название, иконку и цену можно поменять перед сохранением
export const TASK_PRESETS: Record<AgeGroup, TaskPreset[]> = {
  "6-7": [
    { title: "Убрать игрушки", icon: "toys", points: 10 },
    { title: "Заправить кровать", icon: "bed", points: 5 },
    { title: "Отнести грязную одежду в корзину", icon: "laundry", points: 5 },
    { title: "Разложить носки по парам", icon: "socks", points: 5 },
    { title: "Полить цветок", icon: "plant", points: 5 },
    { title: "Помочь накрыть на стол", icon: "dishes", points: 5 },
    { title: "Убрать свою тарелку со стола", icon: "dishes", points: 5 },
    { title: "Вытереть пыль", icon: "mop", points: 5 },
    { title: "Повесить куртку и поставить обувь на место", icon: "iron", points: 5 },
    { title: "Приготовить одежду на завтра", icon: "iron", points: 5 },
    { title: "Собрать рюкзак", icon: "backpack", points: 5 },
    { title: "Сделать домашнее задание", icon: "homework", points: 10 },
    { title: "Выучить стихотворение", icon: "homework", points: 10 },
    { title: "Почитать книгу", icon: "reading", points: 10 },
    { title: "Собраться утром без напоминаний", icon: "morning", points: 5 },
    { title: "Лечь спать вовремя", icon: "sleep", points: 5 },
    { title: "Почистить зубы утром и вечером", icon: "teeth", points: 5 },
    { title: "Погулять на улице", icon: "walk", points: 10 },
    { title: "Сделать зарядку", icon: "sport", points: 5 },
    { title: "Позвонить бабушке или дедушке", icon: "call", points: 5 },
  ],
  "8-10": [
    { title: "Убрать в своей комнате", icon: "toys", points: 15 },
    { title: "Покормить кота", icon: "cat", points: 5 },
    { title: "Пропылесосить свою комнату", icon: "vacuum", points: 15 },
    { title: "Вынести мусор", icon: "trash", points: 10 },
    { title: "Разложить продукты после магазина", icon: "shopping", points: 10 },
    { title: "Сложить чистое бельё", icon: "laundry", points: 10 },
    { title: "Помыть свою посуду", icon: "dishes", points: 5 },
    { title: "Помочь с готовкой", icon: "cooking", points: 10 },
    { title: "Приготовить одежду на завтра", icon: "iron", points: 5 },
    { title: "Собрать рюкзак", icon: "backpack", points: 5 },
    { title: "Сделать домашнее задание", icon: "homework", points: 15 },
    { title: "Выучить стихотворение", icon: "homework", points: 10 },
    { title: "Повторить слова или таблицу умножения", icon: "homework", points: 10 },
    { title: "Почитать книгу", icon: "reading", points: 10 },
    { title: "Позаниматься музыкой", icon: "music", points: 10 },
    { title: "Собраться утром без напоминаний", icon: "morning", points: 5 },
    { title: "Лечь спать вовремя", icon: "sleep", points: 5 },
    { title: "Погулять на улице", icon: "walk", points: 10 },
    { title: "Сделать зарядку", icon: "sport", points: 5 },
    { title: "Позвонить бабушке или дедушке", icon: "call", points: 5 },
    { title: "Поиграть с младшим братом или сестрой", icon: "baby", points: 10 },
  ],
  "11-13": [
    { title: "Сменить постельное бельё", icon: "bed", points: 15 },
    { title: "Загрузить посудомойку", icon: "dishes", points: 10 },
    { title: "Разобрать посудомойку", icon: "dishes", points: 10 },
    { title: "Помыть посуду", icon: "dishes", points: 15 },
    { title: "Запустить стирку", icon: "laundry", points: 10 },
    { title: "Погладить свою одежду", icon: "iron", points: 15 },
    { title: "Пропылесосить квартиру", icon: "vacuum", points: 20 },
    { title: "Помыть пол", icon: "mop", points: 20 },
    { title: "Приготовить завтрак", icon: "cooking", points: 20 },
    { title: "Погулять с собакой", icon: "cat", points: 15 },
    { title: "Сходить в магазин", icon: "shopping", points: 15 },
    { title: "Сделать домашнее задание", icon: "homework", points: 15 },
    { title: "Почитать книгу", icon: "reading", points: 10 },
    { title: "Позаниматься спортом", icon: "sport", points: 10 },
    { title: "Позаниматься музыкой", icon: "music", points: 10 },
    { title: "Собраться утром без напоминаний", icon: "morning", points: 5 },
    { title: "Погулять на улице", icon: "walk", points: 10 },
    { title: "Позвонить бабушке или дедушке", icon: "call", points: 5 },
    { title: "Присмотреть за младшим", icon: "baby", points: 20 },
  ],
};
