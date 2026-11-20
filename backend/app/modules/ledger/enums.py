from enum import StrEnum


class EntryKind(StrEnum):
    ACCRUAL = "accrual"
    RESERVE = "reserve"
    RELEASE = "release"
    SPEND = "spend"
    REVERSAL = "reversal"
    WRITE_OFF = "write_off"


# Какие записи меняют баланс, а какие резерв. Списание меняет оба:
# баллы уходят с баланса и одновременно перестают быть отложенными.
# Списание минуса взрослым поднимает баланс до нуля, но заработком не считается.
BALANCE_KINDS = (EntryKind.ACCRUAL, EntryKind.SPEND, EntryKind.REVERSAL, EntryKind.WRITE_OFF)
RESERVE_KINDS = (EntryKind.RESERVE, EntryKind.RELEASE, EntryKind.SPEND)
# Заработанные баллы: начисления и их отмены. Траты на награды и списание минуса
# сюда не входят, поэтому ни покупка, ни прощённый минус не меняют прогресс общей цели.
EARNING_KINDS = (EntryKind.ACCRUAL, EntryKind.REVERSAL)
