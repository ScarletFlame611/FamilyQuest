import { getSession, setSession } from "../session/session";
import { request, requestFile } from "./client";
import type {
  Balance,
  ChildEventType,
  ChildSession,
  Entry,
  Family,
  Goal,
  Me,
  Purchase,
  RewardOffer,
  SessionEvents,
  Task,
  TaskCreate,
  Tokens,
} from "./types";

function adultSession(tokens: Tokens) {
  setSession({ role: "adult", accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
}

export const api = {
  async login(email: string, password: string) {
    adultSession(
      await request<Tokens>("POST", "/api/auth/login", {
        body: { email, password },
        auth: false,
        keep401: true,
      }),
    );
  },

  async logout() {
    const session = getSession();
    setSession(null);
    if (session) {
      await request<void>("POST", "/api/auth/logout", {
        body: { refresh_token: session.refreshToken },
        auth: false,
      }).catch(() => undefined);
    }
  },

  me: () => request<Me>("GET", "/api/me"),
  family: () => request<Family>("GET", "/api/family"),
  setPin: (currentPassword: string, pin: string) =>
    request<void>("PUT", "/api/family/pin", { body: { current_password: currentPassword, pin } }),

  async startChildMode(childId: string) {
    const adult = getSession();
    const tokens = await request<Tokens>("POST", "/api/child-mode/start", {
      body: { child_id: childId, adult_refresh_token: adult?.refreshToken },
    });
    setSession({ role: "child", accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
  },

  async exitChildMode(pin: string) {
    adultSession(await request<Tokens>("POST", "/api/child-mode/exit", { body: { pin }, keep401: true }));
  },

  async exitChildModeWithPassword(password: string) {
    adultSession(
      await request<Tokens>("POST", "/api/child-mode/exit-with-password", {
        body: { password },
        keep401: true,
      }),
    );
  },

  myTasks: () => request<Task[]>("GET", "/api/tasks/my"),
  board: () => request<Task[]>("GET", "/api/tasks/board"),
  pendingTasks: () => request<Task[]>("GET", "/api/tasks/pending"),
  task: (id: string) => request<Task>("GET", `/api/tasks/${id}`),
  createTask: (key: string, body: TaskCreate) =>
    request<Task>("POST", "/api/tasks", { body, idempotencyKey: key }),
  take: (key: string, id: string) =>
    request<Task>("POST", `/api/tasks/${id}/take`, { idempotencyKey: key }),
  mark: (key: string, id: string) =>
    request<Task>("POST", `/api/tasks/${id}/mark`, { idempotencyKey: key }),
  confirm: (key: string, id: string) =>
    request<Task>("POST", `/api/tasks/${id}/confirm`, { idempotencyKey: key }),

  balance: () => request<Balance>("GET", "/api/balance"),
  ledger: () => request<Entry[]>("GET", "/api/ledger"),

  rewards: () => request<RewardOffer[]>("GET", "/api/rewards"),
  buy: (key: string, id: string) =>
    request<Purchase>("POST", `/api/rewards/${id}/buy`, { idempotencyKey: key }),
  pendingPurchases: () => request<Purchase[]>("GET", "/api/purchases/pending"),
  give: (key: string, id: string) =>
    request<Purchase>("POST", `/api/purchases/${id}/give`, { idempotencyKey: key }),
  cancelPurchase: (key: string, id: string, reason: string) =>
    request<Purchase>("POST", `/api/purchases/${id}/cancel`, {
      body: { reason },
      idempotencyKey: key,
    }),

  goal: () => request<Goal>("GET", "/api/goal"),

  sendChildEvents: (events: { type: ChildEventType; detail: string | null; ago_ms: number }[]) =>
    request<void>("POST", "/api/child-mode/events", { body: { events } }),
  childSessions: () => request<ChildSession[]>("GET", "/api/child-mode/sessions"),
  sessionEvents: (id: string) =>
    request<SessionEvents>("GET", `/api/child-mode/sessions/${id}/events`),
  sessionEventsCsv: (id: string) => requestFile(`/api/child-mode/sessions/${id}/events.csv`),
};
