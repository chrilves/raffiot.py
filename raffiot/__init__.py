from dataclasses import dataclass

from typing_extensions import final

__all__ = [
    "MatchError",
]


@final
@dataclass
class MatchError(Exception):
    """
    Exception for pattern matching errors (used internally, should NEVER happen).
    """

    message: str


@final
@dataclass
class RuntimeFailure(Exception):
    """
    A failure of the Runtime system.
    """

    message: str
