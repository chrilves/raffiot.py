"""
Data structure to represent the result of computation.
"""

from __future__ import annotations
from typing import TypeVar, Generic, Callable, Any, List, Iterable
from typing_extensions import final
from dataclasses import dataclass
from raffiot import _MatchError
from collections import abc

E = TypeVar("E")
A = TypeVar("A")
E2 = TypeVar("E2")
A2 = TypeVar("A2")
X = TypeVar("X")

__all__ = [
    "safe",
    "Result",
    "Ok",
    "Error",
    "Panic",
    "pure",
    "error",
    "panic",
    "traverse",
    "zip",
    "returns_result",
]


def safe(f: Callable[..., Result[E, A]]) -> Callable[..., Result[E, A]]:
    """
    Simple decorator to ensure all exception are caught and transformed into
    panics.

    A function that returns a Result[E,A] should never raise an exception but
    instead return a panic. This decorator make sure of it.

    :param f:
    :return:
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except Exception as exception:
            return Panic(exception)

    return wrapper


class Result(Generic[E, A]):
    """
    The Result[E,A] data structure represents the result of a computation. It has
    3 possible cases:

    - *Ok(some_value: A)*
            The computation succeeded.
            The value some_value, of type A, is the result of the computation
    - *Error(some_error: E)*
            The computation failed with an expected error.
            The error some_error, of type E, is the expected error encountered.
    - *Panic(some_exception: Exception)*
            The computation failed on an unexpected error.
            The exception some_exception is the unexpected error encountered.

    The distinction between errors (expected failures) and panics (unexpected
    failures) is essential.

    Errors are failures your program is prepared to deal with safely. An error
    simply means some operation was not successful, but your program is still
    behaving nicely. Nothing terribly wrong happened. Generally errors belong to
    your business domain. You can take any type as E.

    Panics, on the contrary, are failures you never expected. Your computation
    can not progress further. All you can do when panics occur, is stopping your
    computation gracefully (like releasing resources before dying). The panic type
    is always Exception.

    As an example, if your program is an HTTP server. Errors are bad requests
    (error code 400) while panics are internal server errors (error code 500).
    Receiving bad request is part of the normal life of any HTTP server, it must
    know how to reply nicely. But internal server errors are bugs.
    """

    @final
    def unsafe_fold(
        self,
        on_success: Callable[[A], X],
        on_error: Callable[[E], X],
        on_panic: Callable[[Exception], X],
    ) -> X:
        """
        Transform this Result[E,A] into X.
        :param on_success: is called if this result is a `Ok`.
        :param on_error: is called if this result is a `Error`.
        :param on_panic: is called if this result is a `Panic`.
        :return:
        """
        if isinstance(self, Ok):
            return on_success(self.success)
        if isinstance(self, Error):
            return on_error(self.error)
        if isinstance(self, Panic):
            return on_panic(self.exception)
        raise _MatchError(f"{self} should be a Result")

    @final
    @safe
    def fold(
        self,
        on_success: Callable[[A], X],
        on_error: Callable[[E], X],
        on_panic: Callable[[Exception], X],
    ) -> X:
        """
        Transform this Result[E,A] into X.
        :param on_success: is called if this result is a `Ok`.
        :param on_error: is called if this result is a `Error`.
        :param on_panic: is called if this result is a `Panic`.
        :return:
        """
        return self.unsafe_fold(on_success, on_error, on_panic)

    @final
    def unsafe_fold_raise(
        self, on_success: Callable[[A], X], on_error: Callable[[E], X]
    ) -> X:
        """
        Transform this `Result[E,A]` into `X` if this result is an `Ok` or `Error`.
        But raise the stored exception is this is a panic.

        It is useful to raise an exception on panics.

        :param on_success: is called if this result is a `Ok`.
        :param on_error: is called if this result is a `Error`.
        :return:
        """
        if isinstance(self, Ok):
            return on_success(self.success)
        if isinstance(self, Error):
            return on_error(self.error)
        if isinstance(self, Panic):
            raise self.exception
        raise _MatchError(f"{self} should be a Result")

    @final
    @safe
    def fold_raise(self, on_success: Callable[[A], X], on_error: Callable[[E], X]) -> X:
        """
        Transform this `Result[E,A]` into `X` if this result is an `Ok` or `Error`.
        But raise the stored exception is this is a panic.

        It is useful to raise an exception on panics.

        :param on_success: is called if this result is a `Ok`.
        :param on_error: is called if this result is a `Error`.
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
        Transform the value/error/exception stored in this result.
        :param f: how to transform the value a if this result is `Ok(a)`
        :param g: how to transform the error e if this result is `Error(e)`
        :param h: how to transform the exception p if this result is `Panic(p)`
        :return: the "same" result with the stored value transformed.
        """
        return self.unsafe_fold(
            lambda x: Ok(f(x)),
            lambda x: Error(g(x)),
            lambda x: Panic(h(x)),
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
        Transform the value/error/exception stored in this result.
        :param f: how to transform the value a if this result is `Ok(a)`
        :param g: how to transform the error e if this result is `Error(e)`
        :param h: how to transform the exception p if this result is `Panic(p)`
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
        :return: True if this result is an `Error`
        """
        return isinstance(self, Error)

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
    def zip(
        self: Result[E, Callable[[X], A]], *arg: Result[E, X]
    ) -> Result[E, List[A]]:
        """
        Transform a list of Result (including self) into a Result of list.

        Is Ok is all results are Ok.
        Is Error some are Ok, but at least one is an error but no panics.
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
        Transform the error stored if this result is an `Error`.
        :param f: the transformation function
        :return:
        """
        if isinstance(self, Error):
            return Error(f(self.error))
        return self  # type: ignore

    @final
    @safe
    def map_error(self, f: Callable[[E], E2]) -> Result[E2, A]:
        """
        Transform the error stored if this result is an `Error`.
        :param f: the transformation function
        :return:
        """
        return self.unsafe_map_error(f)

    @final
    def unsafe_catch(self, handler: Callable[[E], Result[E, A]]) -> Result[E, A]:
        """
        React to errors (the except part of a try-except).

        If this result is an `Error(some_error)`, then replace it with `handler(some_error)`.
        Otherwise, do nothing.
        """
        if isinstance(self, Error):
            return handler(self.error)
        return self

    @final
    @safe
    def catch(self, handler: Callable[[E], Result[E, A]]) -> Result[E, A]:
        """
        React to errors (the except part of a try-except).

        If this result is an `Error(some_error)`, then replace it with `handler(some_error)`.
        Otherwise, do nothing.
        """
        return self.unsafe_catch(handler)

    @final
    def unsafe_map_panic(self, f: Callable[[Exception], Exception]) -> Result[E, A]:
        """
        Transform the exception stored if this result is a `Panic(some_exception)`.
        """
        if isinstance(self, Panic):
            return Panic(f(self.exception))
        return self

    @final
    @safe
    def map_panic(self, f: Callable[[Exception], Exception]) -> Result[E, A]:
        """
        Transform the exception stored if this result is a `Panic(some_exception)`.
        """
        return self.unsafe_map_panic(f)

    @final
    def unsafe_recover(
        self, handler: Callable[[Exception], Result[E, A]]
    ) -> Result[E, A]:
        """
        React to panics (the except part of a try-except).

        If this result is a `Panic(exception)`, replace it by `handler(exception)`.
        Otherwise do nothing.
        """
        if isinstance(self, Panic):
            return handler(self.exception)
        return self

    @final
    @safe
    def recover(self, handler: Callable[[Exception], Result[E, A]]) -> Result[E, A]:
        """
        React to panics (the except part of a try-except).

        If this result is a `Panic(exception)`, replace it by `handler(exception)`.
        Otherwise do nothing.
        """
        return self.unsafe_recover(handler)

    @final
    def raise_on_panic(self) -> Result[E, A]:
        """
        If this result is an `Ok` or `Error`, do nothing.
        If it is a `Panic(some_exception)`, raise the exception.

        Use with extreme care since it raise exception.
        """
        if isinstance(self, Panic):
            raise self.exception
        return self


@final
@dataclass
class Ok(Result[E, A]):
    """
    The result of a successful computation.
    """

    success: A


@final
@dataclass
class Error(Result[E, A]):
    """
    The result of a computation that failed on an excepted normal error case.
    The program is still in a valid state and can progress safely.
    """

    error: E


@final
@dataclass
class Panic(Result[E, A]):
    """
    The result of a computation that failed unexpectedly.
    The program is not in a valid state and must terminate safely.
    """

    exception: Exception


def pure(a: A) -> Result[Any, A]:
    """
    Alias for `Ok(a)`.
    """
    return Ok(a)


def error(error: E) -> Result[E, Any]:
    """
    Alias for `Error(error)`.
    """
    return Error(error)


def panic(exception: Exception) -> Result[Any, Any]:
    """
    Alias for `Panic(exception)`.
    """
    return Panic(exception)


@safe
def traverse(l: Iterable[A], f: Callable[[A], Result[E, A2]]) -> Result[E, List[A2]]:
    """
    Apply the function `f` to every element of the iterable.
    The resulting Result is Ok if all results are Ok.

    This function is essentially like map, but f returns Result[E,A2] instead of A2.

    :param l: the elements to apply to f
    :param f: the function for each element.
    :return:
    """

    return zip([f(i) for i in l])


def zip(*l: Iterable[Result[E, A]]) -> Result[E, List[A]]:
    if len(l) == 1 and isinstance(l[0], abc.Iterable):
        args = l[0]
    else:
        args = l

    values = []
    error = None

    for arg in args:
        if arg.is_ok():
            values.append(arg.success)
        elif arg.is_error() and error is None:
            error = arg
        elif arg.is_panic():
            return arg

    if error is None:
        return Ok(values)
    else:
        return error


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
            return Panic(exception)

    return wrapper
