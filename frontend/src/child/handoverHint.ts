// Подсказку нужно показать один раз, сразу после включения режима, а не после
// каждой перезагрузки, поэтому флаг живёт только в памяти
let pending = false;

export function showHandoverHint() {
  pending = true;
}

export function isHandoverHintPending(): boolean {
  return pending;
}

export function clearHandoverHint() {
  pending = false;
}
