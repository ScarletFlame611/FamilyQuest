import { NetworkError, newIdempotencyKey } from "../api/client";

// Ключ создаётся на первую попытку и живёт до ответа сервера. После обрыва связи
// повтор уходит с тем же ключом: если первый запрос всё же дошёл, сервер вернёт
// его результат, а не выполнит действие второй раз
export class KeyedAction {
  private key: string | null = null;

  async run<T>(send: (key: string) => Promise<T>): Promise<T> {
    this.key ??= newIdempotencyKey();
    try {
      const result = await send(this.key);
      this.key = null;
      return result;
    } catch (error) {
      if (!(error instanceof NetworkError)) this.key = null;
      throw error;
    }
  }
}
