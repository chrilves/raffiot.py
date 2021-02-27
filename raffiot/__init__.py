from dataclasses import dataclass

__all__ = [
    "_MatchError",
]


@dataclass
class _MatchError(Exception):
    """
    Exception for pattern matching errors (used internally, should NEVER happen).
    """

    message: str
