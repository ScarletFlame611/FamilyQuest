import { getSession, setSession } from "../session/session";
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

let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const session = getSession();
  if (!session) return false;
  const response = await send("POST", "/api/auth/refresh", {
    body: { refresh_token: session.refreshToken },
    auth: false,
  });
  if (!response.ok) return false;
  const tokens = (await response.json()) as Tokens;
  // Пока шло обновление, сессию могли сменить (например, включили детский режим)
  if (getSession()?.refreshToken !== session.refreshToken) return true;
  setSession({ role: session.role, accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
  return true;
}

function refreshOnce(): Promise<boolean> {
  refreshing ??= refreshTokens().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

export async function request<T>(method: string, path: string, options: Options = {}): Promise<T> {
  let response = await send(method, path, options);
  if (response.status === 401 && options.auth !== false && !options.keep401) {
    if (await refreshOnce()) {
      response = await send(method, path, options);
    }
    if (response.status === 401) {
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
