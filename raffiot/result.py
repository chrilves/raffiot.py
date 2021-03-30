"""
Data structure to represent the result of computation.
"""

from __future__ import annotations

from collections import abc
from dataclasses import dataclass
from typing import TypeVar, Generic, Callable, Any, List, Iterable, Tuple

from typing_extensions import final

from raffiot.utils import (
    ComputationStatus,
    MatchError,
    MultipleExceptions,
    DomainErrors,
)

__all__ = [
    "safe",
    "Result",
    "Ok",
    "Errors",
    "Panic",
    "pure",
    "ok",
    "error",
    "errors",
    "panic",
    "traverse",
    "zip",
    "sequence",
    "returns_result",
]


E = TypeVar("E")
A = TypeVar("A")
E2 = TypeVar("E2")
A2 = TypeVar("A2")
X = TypeVar("X")


def safe(f: Callable[..., Result[E, A]]) -> Callable[..., Result[E, A]]:
    """
    Simple decorator to ensure all exceptions are caught and transformed into
    panics.

    A function that returns a Result[E,A] should never raise an exceptions but
    instead return a panic. This decorator make sure of it.

    :param f:
    :return:
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except Exception as exception:
            return Panic(exceptions=[exception], errors=[])

    return wrapper


class Result(Generic[E, A]):
    """
    The Result[E,A] data structure represents the result of a computation. It has
    3 possible cases:

    - *Ok(some_value: A)*
            The computation succeeded.
            The value some_value, of type A, is the result of the computation
    - *Errors(some_errors: List[E])*
            The computation failed with an expected errors.
            The errors some_errors, of type List[E], is the expected errors encountered.
    - *Panic(some_exceptions: List[Exception], errors: List[E])*
            The computation failed on an unexpected errors.
            The exceptions some_exceptions is the unexpected errors encountered.

    The distinction between errors (expected failures) and panics (unexpected
    failures) is essential.

    Errors are failures your program is prepared to deal with safely. An errors
    simply means some operation was not successful, but your program is still
    behaving nicely. Nothing terribly wrong happened. Generally errors belong to
    your business domain. You can take any type as E.

    Panics, on the contrary, are failures you never expected. Your computation
    can not progress further. All you can do when panics occur, is stopping your
    computation gracefully (like releasing resources before dying). The panic type
    is always Exception.

    As an example, if your program is an HTTP server. Errors are bad requests
    (errors code 400) while panics are internal server errors (errors code 500).
    Receiving bad request is part of the normal life of any HTTP server, it must
    know how to reply nicely. But internal server errors are bugs.
    """

    @final
    def unsafe_fold(
        self,
        on_success: Callable[[A], X],
        on_error: Callable[[List[E]], X],
        on_panic: Callable[[List[Exception], List[E]], X],
    ) -> X:
        """
        Transform this Result[E,A] into X.
        :param on_success: is called if this result is a `Ok`.
        :param on_error: is called if this result is a `Errors`.
        :param on_panic: is called if this result is a `Panic`.
        :return:
        """
        if isinstance(self, Ok):
            return on_success(self.success)
        if isinstance(self, Errors):
            return on_error(self.errors)
        if isinstance(self, Panic):
            return on_panic(self.exceptions, self.errors)
        raise on_panic([MatchError(f"{self} should be a Result")])

    @final
    @safe
    def fold(
        self,
        on_success: Callable[[A], X],
        on_error: Callable[[List[E]], X],
        on_panic: Callable[[List[Exception], List[E]], X],
    ) -> X:
        """
        Transform this Result[E,A] into X.
        :param on_success: is called if this result is a `Ok`.
        :param on_error: is called if this result is a `Errors`.
        :param on_panic: is called if this result is a `Panic`.
        :return:
        """
        return self.unsafe_fold(on_success, on_error, on_panic)

    @final
    def unsafe_fold_raise(
        self, on_success: Callable[[A], X], on_error: Callable[[List[E]], X]
    ) -> X:
        """
        Transform this `Result[E,A]` into `X` if this result is an `Ok` or `Errors`.
        But raise the stored exceptions is this is a panic.

        It is useful to raise an exceptions on panics.

        :param on_success: is called if this result is a `Ok`.
        :param on_error: is called if this result is a `Errors`.
        :return:
        """
        if isinstance(self, Ok):
            return on_success(self.success)
        if isinstance(self, Errors):
            return on_error(self.errors)
        if isinstance(self, Panic):
            raise MultipleExceptions.merge(*self.exceptions, errors=self.errors)
        raise MatchError(f"{self} should be a Result")

    @final
    @safe
    def fold_raise(
        self, on_success: Callable[[A], X], on_error: Callable[[List[E]], X]
    ) -> X:
        """
        Transform this `Result[E,A]` into `X` if this result is an `Ok` or `Errors`.
        But raise the stored exceptions is this is a panic.

        It is useful to raise an exceptions on panics.

        :param on_success: is called if this result is a `Ok`.
        :param on_error: is called if this result is a `Errors`.
        :return:
        """
        return self.unsafe_fold_raise(on_success, on_error)

    @final
    def unsafe_flat_map(self, f: Callable[[A], Result[E, A2]]) -> Result[E, A2]:
        """
        The usual monadic operation called
            - bind, >>=: in Haskell
            - flatMap: in Scala
            - andThem: in Elm
            ...

        Chain operations returning results.

        :param f: operation to perform it this result is an `Ok`.
        :return: the result combined result.
        """
        if isinstance(self, Ok):
            return f(self.success)
        return self

    @final
    @safe
    def flat_map(self, f: Callable[[A], Result[E, A2]]) -> Result[E, A2]:
        """
        The usual monadic operation called
            - bind, >>=: in Haskell
            - flatMap: in Scala
            - andThem: in Elm
            ...

        Chain operations returning results.

        :param f: operation to perform it this result is an `Ok`.
        :return: the result combined result.
        """
        return self.unsafe_flat_map(f)

    @final
    def unsafe_tri_map(
        self,
        f: Callable[[A], A2],
        g: Callable[[E], E2],
        h: Callable[[Exception], Exception],
    ) -> Result[E2, A2]:
        """
        Transform the value/errors/exceptions stored in this result.
        :param f: how to transform the value a if this result is `Ok(a)`
        :param g: how to transform the errors e if this result is `Errors(e)`
        :param h: how to transform the exceptions p if this result is `Panic(p)`
        :return: the "same" result with the stored value transformed.
        """
        return self.unsafe_fold(
            lambda x: Ok(f(x)),
            lambda x: Errors(list(map(g, x))),
            lambda x, y: Panic(exceptions=list(map(h, x)), errors=list(map(g, y))),
        )

    @final
    @safe
    def tri_map(
        self,
        f: Callable[[A], A2],
        g: Callable[[E], E2],
        h: Callable[[Exception], Exception],
    ) -> Result[E2, A2]:
        """
        Transform the value/errors/exceptions stored in this result.
        :param f: how to transform the value a if this result is `Ok(a)`
        :param g: how to transform the errors e if this result is `Errors(e)`
        :param h: how to transform the exceptions p if this result is `Panic(p)`
        :return: the "same" result with the stored value transformed.
        """
        return self.unsafe_tri_map(f, g, h)

    @final
    def is_ok(self) -> bool:
        """
        :return: True if this result is an `Ok`
        """
        return isinstance(self, Ok)

    @final
    def is_error(self) -> bool:
        """
        :return: True if this result is an `Errors`
        """
        return isinstance(self, Errors)

    @final
    def is_panic(self) -> bool:
        """
        :return: True if this result is an `Panic`
        """
        return isinstance(self, Panic)

    @final
    def unsafe_map(self, f: Callable[[A], A2]) -> Result[E, A2]:
        """
        Transform the value stored in `Ok`, it this result is an `Ok`.
        :param f: the transformation function.
        :return:
        """
        if isinstance(self, Ok):
            return Ok(f(self.success))
        return self

    @final
    @safe
    def map(self, f: Callable[[A], A2]) -> Result[E, A2]:
        """
        Transform the value stored in `Ok`, it this result is an `Ok`.
        :param f: the transformation function.
        :return:
        """
        return self.unsafe_map(f)

    @final
    def zip(self: Result[E, A], *arg: Result[E, X]) -> Result[E, List[A]]:
        """
        Transform a list of Result (including self) into a Result of list.

        Is Ok is all results are Ok.
        Is Errors some are Ok, but at least one is an errors but no panics.
        Is Panic is there is at least one panic.
        """
        return zip((self, *arg))

    @final
    def unsafe_ap(
        self: Result[E, Callable[[X], A]], *arg: Result[E, X]
    ) -> Result[E, A]:
        """
        Noting functions from X to A: `[X1, ..., Xn] -> A`.

        If this result represent a computation returning a function `f: [X1,...,XN] -> A`
        and arg represent a computation returning a value `x1: X1`,...,`xn: Xn`, then
        `self.ap(arg)` represents the computation returning `f(x1,...,xn): A`.
        """
        return zip((self, *arg)).unsafe_map(lambda l: l[0](*l[1:]))

    @final
    @safe
    def ap(self: Result[E, Callable[[X], A]], *arg: Result[E, X]) -> Result[E, A]:
        """
        Noting functions from [X1,...,XN] to A: `[X1, ..., Xn] -> A`.

        If this result represent a computation returning a function `f: [X1,...,XN] -> A`
        and arg represent computations returning values `x1: X1`,...,`xn: Xn` then
        `self.ap(arg)` represents the computation returning `f(x1,...,xn): A`.
        """
        return self.unsafe_ap(*arg)

    @final
    def flatten(self: Result[E, Result[E, A]]) -> Result[E, A]:
        """
        The concatenation function on results.
        """
        if isinstance(self, Ok):
            return self.success
        return self

    @final
    def unsafe_map_error(self, f: Callable[[E], E2]) -> Result[E2, A]:
        """
        Transform the errors stored if this result is an `Errors`.
        :param f: the transformation function
        :return:
        """
        if isinstance(self, Errors):
            return Errors(list(map(f, self.errors)))
        return self  # type: ignore

    @final
    @safe
    def map_error(self, f: Callable[[E], E2]) -> Result[E2, A]:
        """
        Transform the errors stored if this result is an `Errors`.
        :param f: the transformation function
        :return:
        """
        return self.unsafe_map_error(f)

    @final
    def unsafe_catch(self, handler: Callable[[List[E]], Result[E, A]]) -> Result[E, A]:
        """
        React to errors (the except part of a try-except).

        If this result is an `Errors(some_error)`, then replace it with `handler(some_error)`.
        Otherwise, do nothing.
        """
        if isinstance(self, Errors):
            return handler(self.errors)
        return self

    @final
    @safe
    def catch(self, handler: Callable[[E], Result[List[E], A]]) -> Result[E, A]:
        """
        React to errors (the except part of a try-except).

        If this result is an `Errors(some_error)`, then replace it with `handler(some_error)`.
        Otherwise, do nothing.
        """
        return self.unsafe_catch(handler)

    @final
    def unsafe_map_panic(self, f: Callable[[Exception], Exception]) -> Result[E, A]:
        """
        Transform the exceptions stored if this result is a `Panic(some_exception)`.
        """
        if isinstance(self, Panic):
            return Panic(list(map(f, self.exceptions)), self.errors)
        return self

    @final
    @safe
    def map_panic(self, f: Callable[[Exception], Exception]) -> Result[E, A]:
        """
        Transform the exceptions stored if this result is a `Panic(some_exception)`.
        """
        return self.unsafe_map_panic(f)

    @final
    def unsafe_recover(
        self, handler: Callable[[List[Exception], List[E]], Result[E, A]]
    ) -> Result[E, A]:
        """
        React to panics (the except part of a try-except).

        If this result is a `Panic(exceptions)`, replace it by `handler(exceptions)`.
        Otherwise do nothing.
        """
        if isinstance(self, Panic):
            return handler(self.exceptions, self.errors)
        return self

    @final
    @safe
    def recover(
        self, handler: Callable[[List[Exception], List[E]], Result[E, A]]
    ) -> Result[E, A]:
        """
        React to panics (the except part of a try-except).

        If this result is a `Panic(exceptions)`, replace it by `handler(exceptions)`.
        Otherwise do nothing.
        """
        return self.unsafe_recover(handler)

    @final
    def raise_on_panic(self) -> Result[E, A]:
        """
        If this result is an `Ok` or `Errors`, do nothing.
        If it is a `Panic(some_exception)`, raise the exceptions.

        Use with extreme care since it raise exceptions.
        """
        if isinstance(self, Panic):
            raise MultipleExceptions.merge(*self.exceptions, errors=self.errors)
        return self

    @final
    def unsafe_get(self) -> Result[E, A]:
        """
        If this result is an `Ok`, do nothing.
        If it is a `Panic(some_exception)`, raise the exceptions.

        Use with extreme care since it raise exceptions.
        """
        if isinstance(self, Ok):
            return self.success
        if isinstance(self, Errors):
            raise DomainErrors(self.errors)
        if isinstance(self, Panic):
            raise MultipleExceptions.merge(*self.exceptions, errors=self.errors)
        raise MatchError(f"{self} should be a result.")

    @final
    def to_computation_status(self) -> ComputationStatus:
        """
        Transform this Result into a Computation Status
        :return:
        """
        if self.is_ok():
            return ComputationStatus.SUCCEEDED
        return ComputationStatus.FAILED


@final
@dataclass
class Ok(Result[E, A]):
    """
    The result of a successful computation.
    """

    __slots__ = "success"

    success: A


@final
@dataclass
class Errors(Result[E, A]):
    """
    The result of a computation that failed on an excepted normal errors case.
    The program is still in a valid state and can progress safely.
    """

    __slots__ = "errors"

    errors: List[E]


@final
@dataclass
class Panic(Result[E, A]):
    """
    The result of a computation that failed unexpectedly.
    The program is not in a valid state and must terminate safely.
    """

    __slots__ = "exceptions", "errors"

    exceptions: List[Exception]

    errors: List[E]


def pure(a: A) -> Result[Any, A]:
    """
    Alias for `Ok(a)`.
    """
    return Ok(a)


def ok(a: A) -> Result[Any, A]:
    """
    Alias for `Ok(a)`.
    """
    return Ok(a)


def error(err: E) -> Result[E, Any]:
    """
    Alias for `Errors(err)`.
    """
    return Errors([err])


def errors(*errs: E) -> Result[E, Any]:
    """
    Alias for `Errors(errs)`.
    """
    if (
        len(errs) == 1
        and isinstance(errs[0], abc.Iterable)
        and not isinstance(errs[0], str)
    ):
        return Errors(list(errs[0]))
    return Errors(list(errs))


def panic(*exceptions: Exception, errors=None) -> Result[Any, Any]:
    """
    Alias for `Panic(exceptions)`.
    """
    if (
        len(exceptions) == 1
        and isinstance(exceptions[0], abc.Iterable)
        and not isinstance(exceptions[0], str)
    ):
        return Panic(
            exceptions=list(exceptions[0]), errors=list(errors) if errors else []
        )
    return Panic(exceptions=list(exceptions), errors=list(errors) if errors else [])


def zip(*l: Iterable[Result[E, A]]) -> Result[E, List[A]]:
    """
    Combine a list of `Result`.

    If everyone is `Ok(x)`, then return `Ok([...x...])`.
    If there are some errors but no panics, return `Errors(<the list of errors>)`.
    If there are some panics, return the Panic with all exceptions and errors
    encountered.

    :param l:
    :return:
    """
    if len(l) == 1 and isinstance(l[0], abc.Iterable):
        args = l[0]
    else:
        args = l

    values = []
    errs = []
    exceptions = []

    for arg in args:
        if isinstance(arg, Ok):
            values.append(arg.success)
        elif isinstance(arg, Errors):
            errs.extend(arg.errors)
        elif isinstance(arg, Panic):
            exceptions.extend(arg.exceptions)
            errs.extend(arg.errors)
        else:
            exceptions.append(MatchError(f"{arg} should be a Result"))

    if exceptions:
        return Panic(exceptions=exceptions, errors=errs)
    if errs:
        return Errors(errs)
    return Ok(values)


def sequence(*l: Iterable[Result[E, A]]) -> Result[List[E], A]:
    """
    Combine a list of `Result`.

    If everyone is `Ok(x)`, then return `Ok(<the value of the last result>)`.
    If there are some errs but no exceptions, return `Errors(<the list of errs>)`.
    If there are some exceptions, return the Panic with all exceptions and errs
    encountered.
    """
    if len(l) == 1 and isinstance(l[0], abc.Iterable):
        args = l[0]
    else:
        args = l

    value = None
    errs = []
    exceptions = []

    for arg in args:
        if isinstance(arg, Ok):
            value = arg.success
        elif isinstance(arg, Errors):
            errs.extend(arg.errors)
        elif isinstance(arg, Panic):
            exceptions.extend(arg.exceptions)
            errs.extend(arg.errors)
        else:
            exceptions.append(MatchError(f"{arg} should be a Result"))

    if exceptions:
        return Panic(exceptions=exceptions, errors=errs)
    if errs:
        return Errors(errs)
    return Ok(value)


def traverse(
    l: Iterable[A], f: Callable[[A], Result[E, A2]]
) -> Result[List[E], List[A2]]:
    """
    Apply the function `f` to every element of the iterable.
    The resulting Result is Ok if all results are Ok.

    This function is essentially like map, but f returns Result[E,A2] instead of A2.

    :param l: the elements to apply to f
    :param f: the function for each element.
    :return:
    """

    def g(i):
        try:
            return f(i)
        except Exception as exception:
            return Panic([exception], [])

    return zip([g(i) for i in l])


def returns_result(f: Callable[..., Result[E, A]]) -> Callable[..., Result[E, A]]:
    """
    Decorator that transform a function f returning A,
    into a function f returning `Result[E,A]`.

    All exceptions are transformed into panics.
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return Ok(f(*args, **kwargs))
        except Exception as exception:
            return panic(exception)

    return wrapper
