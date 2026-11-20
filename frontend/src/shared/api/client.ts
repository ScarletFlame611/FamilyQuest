import { getSession, latestSession, setSession } from "../session/session";
import type { Tokens } from "./types";

export type ErrorBody = { detail?: string; attempts_left?: number; missing?: number };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ErrorBody,
  ) {
    super(body.detail ?? `Ошибка ${status}`);
  }
}

export class NetworkError extends Error {
  constructor() {
    super("Нет связи с сервером");
  }
}

type Options = {
  body?: unknown;
  idempotencyKey?: string;
  // Для эндпоинтов, где 401 означает неверный PIN, а не истёкший токен
  keep401?: boolean;
  auth?: boolean;
};

// crypto.randomUUID доступен только на https и localhost, а телефон в тесте
// может открыть стенд по адресу в локальной сети
export function newIdempotencyKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

async function send(method: string, path: string, options: Options): Promise<Response> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
  const session = getSession();
  if (options.auth !== false && session) headers.Authorization = `Bearer ${session.accessToken}`;
  try {
    return await fetch(path, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new NetworkError();
  }
}

// «expired» — сервер отказал именно этому refresh-токену, и выходить надо;
// «offline» — сервер не ответил толком, и сессию терять нельзя
type RefreshResult = "ok" | "expired" | "offline";

let refreshing: Promise<RefreshResult> | null = null;

// Сколько ждать, пока соседняя вкладка, успевшая обменять тот же токен, сохранит новый
const OTHER_TAB_GRACE_MS = 500;

async function refreshTokens(): Promise<RefreshResult> {
  const session = latestSession();
  if (!session) return "expired";
  let response: Response;
  try {
    response = await send("POST", "/api/auth/refresh", {
      body: { refresh_token: session.refreshToken },
      auth: false,
    });
  } catch {
    return "offline";
  }
  // Пока шло обновление, сессию могли сменить: другая вкладка обменяла токен
  // или включили детский режим. Тогда повторяем запрос с тем, что есть сейчас
  const changed = () => latestSession()?.refreshToken !== session.refreshToken;
  if (changed()) return "ok";
  if (response.status === 401) {
    await new Promise((resolve) => setTimeout(resolve, OTHER_TAB_GRACE_MS));
    return changed() ? "ok" : "expired";
  }
  if (!response.ok) return "offline";
  const tokens = (await response.json()) as Tokens;
  setSession({ role: session.role, accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
  return "ok";
}

function refreshOnce(): Promise<RefreshResult> {
  refreshing ??= refreshTokens().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

export async function request<T>(method: string, path: string, options: Options = {}): Promise<T> {
  let response = await send(method, path, options);
  if (response.status === 401 && options.auth !== false && !options.keep401) {
    const failed = getSession();
    const refreshed = await refreshOnce();
    if (refreshed === "offline") throw new NetworkError();
    if (refreshed === "ok") response = await send(method, path, options);
    // Выходим, только если за это время сессию никто не заменил на рабочую
    if (response.status === 401 && getSession()?.refreshToken === failed?.refreshToken) {
      setSession(null);
    }
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ErrorBody;
    throw new ApiError(response.status, body);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// Файл (например, CSV) скачивается тем же путём, что и JSON, но отдаётся целиком
export async function requestFile(path: string): Promise<Blob> {
  const response = await send("GET", path, {});
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ErrorBody;
    throw new ApiError(response.status, body);
  }
  return response.blob();
}
