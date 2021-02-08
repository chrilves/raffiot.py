from dataclasses import dataclass


@dataclass
class _MatchError(Exception):
    """
    Exception for pattern matching errors (used internally, should NEVER happen).
    """

    message: str
