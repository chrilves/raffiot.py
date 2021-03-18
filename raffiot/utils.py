from collections import abc
from dataclasses import dataclass
from typing import Any


@dataclass
class MatchError(Exception):
    """
    Exception for pattern matching errors (used internally, should NEVER happen).
    """

    __slots__ = ["message"]

    message: None


def seq(*a: Any) -> Any:
    """
    The result is the result of the last argument.

    Accepts a single list or multiple arguments.
    :param a:
    :return:
    """
    if len(a) == 1 and isinstance(a[0], abc.Iterable):
        return a[0][-1]
    return a[-1]
