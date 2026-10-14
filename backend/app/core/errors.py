class DomainError(Exception):
    def __init__(self, message: str, extra: dict[str, int] | None = None) -> None:
        super().__init__(message)
        self.message = message
        # Дополнительные поля ответа, например число оставшихся попыток PIN
        self.extra = extra or {}


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class ForbiddenError(DomainError):
    pass


class InvalidInputError(DomainError):
    pass


class UnauthorizedError(DomainError):
    pass


class TooManyAttemptsError(DomainError):
    pass
