from enum import StrEnum


class EntryKind(StrEnum):
    ACCRUAL = "accrual"
    RESERVE = "reserve"
    RELEASE = "release"
    SPEND = "spend"
    REVERSAL = "reversal"


# Какие записи меняют баланс, а какие резерв. Списание меняет оба:
# баллы уходят с баланса и одновременно перестают быть отложенными.
BALANCE_KINDS = (EntryKind.ACCRUAL, EntryKind.SPEND, EntryKind.REVERSAL)
RESERVE_KINDS = (EntryKind.RESERVE, EntryKind.RELEASE, EntryKind.SPEND)
