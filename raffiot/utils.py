from __future__ import annotations

from collections import abc
from dataclasses import dataclass
from enum import IntEnum
from traceback import format_exc, format_stack
from typing import Any, List, Generic, TypeVar, Iterable

from typing_extensions import final

__all__ = [
    "TracedException",
    "MatchError",
    "MultipleExceptions",
    "ComputationStatus",
    "seq",
    "DomainErrors",
]

E = TypeVar("E", covariant=True)


@final
@dataclass
class TracedException:
    __slots__ = ("exception", "stack_trace")

    exception: Exception
    """
    The exception that was raised.
    """

    stack_trace: str
    """
    Its stack trace.
    """

    def __str__(self):
        return f"{self.exception}\n{self.stack_trace}"

    @classmethod
    def in_except_clause(cls, exn: Exception) -> TracedException:
        """
        Collect the stack trace of the exception.

        BEWARE: this method should only be used in the except clause
        of a try-except block and called with the caught exception!

        :param exn:
        :return:
        """
        if isinstance(exn, TracedException):
            return exn
        return TracedException(exception=exn, stack_trace=format_exc())

    @classmethod
    def with_stack_trace(cls, exn: Exception) -> TracedException:
        """
        Collect the stack trace at the current position.

        :param exn:
        :return:
        """
        if isinstance(exn, TracedException):
            return exn
        return TracedException(exception=exn, stack_trace="".join(format_stack()))

    @classmethod
    def ensure_traced(cls, exception: Exception) -> TracedException:
        return cls.with_stack_trace(exception)

    @classmethod
    def ensure_list_traced(
        cls, exceptions: Iterable[Exception]
    ) -> List[TracedException]:
        return [cls.ensure_traced(exn) for exn in exceptions]


@dataclass
class MatchError(Exception):
    """
    Exception for pattern matching errors (used internally, should NEVER happen).
    """

    message: str


@final
@dataclass
class MultipleExceptions(Exception, Generic[E]):
    """
    Represents
    """

    exceptions: List[TracedException]
    """
    The list exceptions encountered
    """

    errors: List[E]
    """
    The list of errors encountered
    """

    @classmethod
    def merge(cls, *exceptions: TracedException, errors: List[E] = None) -> Exception:
        """
        Merge some exceptions, retuning the exceptions if there is only one
        or a  `MultipleExceptions` otherwise.

        :param exceptions:
        :param errors:
        :return:
        """
        stack = [exn for exn in exceptions]
        base_exceptions = []
        errs = [x for x in errors] if errors else []

        while stack:
            item = stack.pop()
            if isinstance(item, MultipleExceptions):
                stack.extend(item.exceptions)
                errs.extend(item.errors)
                continue
            if isinstance(item, abc.Iterable) and not isinstance(item, str):
                stack.extend(item)
                continue
            base_exceptions.append(TracedException.ensure_traced(item))

        base_exceptions.reverse()
        return MultipleExceptions(base_exceptions, errs)

    def __str__(self):
        msg = ""
        for traced in self.exceptions:
            msg += f"\nException: {traced.exception}\n{traced.stack_trace}"
        for err in self.errors:
            msg += f"\nError: {err}"
        return msg


@final
@dataclass
class DomainErrors(Exception, Generic[E]):
    """
    Errors from the business domain
    """

    errors: List[E]


@final
class ComputationStatus(IntEnum):
    FAILED = 0
    SUCCEEDED = 1


def seq(*a: Any) -> Any:
    """
    The result is the result of the last argument.

    Accepts a single list or multiple arguments.
    :param a:
    :return:
    """
    if len(a) == 1 and isinstance(a[0], abc.Iterable):
        return a[0][-1]  # type: ignore
    return a[-1]
