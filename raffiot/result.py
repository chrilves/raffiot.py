from __future__ import annotations
from typing import TypeVar, Generic, Callable, Any, cast
from typing_extensions import final
from dataclasses import dataclass

E = TypeVar("E")
A = TypeVar("A")
E2 = TypeVar("E2")
A2 = TypeVar("A2")
X = TypeVar("X")


def safe(f: Callable[..., Result[E, A]]) -> Callable[..., Result[E, A]]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except Exception as exception:
            return Panic(exception)

    return wrapper


class Result(Generic[E, A]):
    @final
    def fold(
        self,
        on_success: Callable[[A], X],
        on_error: Callable[[E], X],
        on_panic: Callable[[Exception], X],
    ) -> X:
        if isinstance(self, Ok):
            return on_success(self.success)
        if isinstance(self, Error):
            return on_error(self.error)
        if isinstance(self, Panic):
            return on_panic(self.exception)
        raise MatchError(f"{self} should be a Result")

    @final
    def fold_raise(self, on_success: Callable[[A], X], on_error: Callable[[E], X]) -> X:
        if isinstance(self, Ok):
            return on_success(self.success)
        if isinstance(self, Error):
            return on_error(self.error)
        if isinstance(self, Panic):
            raise self.exception
        raise MatchError(f"{self} should be a Result")

    @final
    def flat_map(self, f: Callable[[A], Result[E, A2]]) -> Result[E, A2]:
        if isinstance(self, Ok):
            return safe(f)(self.success)
        return self

    @final
    def tri_map(
        self,
        f: Callable[[A], A2],
        g: Callable[[E], E2],
        h: Callable[[Exception], Exception],
    ) -> Result[E2, A2]:
        return self.fold(
            safe(lambda x: Ok(f(x))),
            safe(lambda x: Error(g(x))),
            safe(lambda x: Panic(h(x))),
        )

    @final
    def is_ok(self) -> bool:
        return isinstance(self, Ok)

    @final
    def is_error(self) -> bool:
        return isinstance(self, Error)

    @final
    def is_panic(self) -> bool:
        return isinstance(self, Panic)

    @final
    def map(self, f: Callable[[A], A2]) -> Result[E, A2]:
        return self.flat_map(lambda x: Ok(f(x)))

    @final
    def ap(self: Result[E, Callable[[X], A]], arg: Result[E, X]) -> Result[E, A]:
        return self.flat_map(lambda f: arg.map(f))

    @final
    def flatten(self: Result[E, Result[E, A]]) -> Result[E, A]:
        return self.flat_map(lambda x: x)

    @final
    @safe
    def map_error(self, f: Callable[[E], E2]) -> Result[E2, A]:
        if isinstance(self, Error):
            return Error(f(self.error))
        return self  # type: ignore

    @final
    def catch(self, handler: Callable[[E], Result[E, A]]) -> Result[E, A]:
        if isinstance(self, Error):
            return safe(handler)(self.error)
        return self

    @final
    @safe
    def map_panic(self, f: Callable[[Exception], Exception]) -> Result[E, A]:
        if isinstance(self, Panic):
            return Panic(f(self.exception))
        return self

    @final
    def recover(self, handler: Callable[[Exception], Result[E, A]]) -> Result[E, A]:
        if isinstance(self, Panic):
            return safe(handler)(self.exception)
        return self

    @final
    def fail_on_panic(self) -> Result[E, A]:
        if isinstance(self, Panic):
            raise self.exception
        return self


@final
@dataclass
class Ok(Result[E, A]):
    success: A


@final
@dataclass
class Error(Result[E, A]):
    error: E


@final
@dataclass
class Panic(Result[E, A]):
    exception: Exception


def pure(a: A) -> Result[Any, A]:
    return Ok(a)


def error(error: E) -> Result[E, Any]:
    return Error(error)


def panic(exception: Exception) -> Result[Any, Any]:
    return Panic(exception)


def returns_result(f: Callable[..., Result[E, A]]) -> Callable[..., Result[E, A]]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return Ok(f(*args, **kwargs))
        except Exception as exception:
            return Panic(exception)

    return wrapper
