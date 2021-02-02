from __future__ import annotations
from typing import TypeVar, Generic, Callable, Any, Tuple
from typing_extensions import final
from dataclasses import dataclass
from raffiot import result, io, MatchError
from raffiot.io import IO

R = TypeVar("R")
E = TypeVar("E")
A = TypeVar("A")
X = TypeVar("X")
R2 = TypeVar("R2")
E2 = TypeVar("E2")
A2 = TypeVar("A2")


@final
@dataclass
class Resource(Generic[R, E, A]):
    create: IO[R, E, Tuple[A, IO[R, E, None]]]

    @final
    def use(self, fun: Callable[[A], IO[R, E, X]]) -> IO[R, E, X]:
        def safe_use(x: Tuple[A, IO[R, E, None]]) -> IO[R, E, X]:
            a, close = x
            try:
                return (
                    fun(a)
                    .attempt()
                    .flat_map(lambda r: close.attempt().then(io.from_result(r)))
                )
            except Exception as exception:
                return close.attempt().then(io.panic(exception))

        return self.create.flat_map(safe_use)

    @final
    def map(self, f: Callable[[A], A2]) -> Resource[R, E, A2]:
        def safe_map(
            x: Tuple[A, IO[R, E, None]]
        ) -> IO[R, E, Tuple[A2, IO[R, E, None]]]:
            a, close = x
            try:
                return io.pure((f(a), close))
            except Exception as exception:
                return close.attempt().then(io.panic(exception))

        return Resource(self.create.flat_map(safe_map))

    @final
    def flat_map(self, f: Callable[[A], Resource[R, E, A2]]) -> Resource[R, E, A2]:
        def safe_flat_map_a(
            xa: Tuple[A, IO[R, E, None]]
        ) -> IO[R, E, Tuple[A2, IO[R, E, None]]]:
            a, close_a = xa
            try:

                def safe_flat_map_a2(
                    xa2: Tuple[A2, IO[R, Any, None]]
                ) -> IO[R, E, Tuple[A2, IO[R, Any, None]]]:
                    a2, close_a2 = xa2
                    return io.pure((a2, close_a.attempt().then(close_a2)))

                return (
                    f(a)
                    .create.attempt()
                    .flat_map(
                        lambda r: r.fold(
                            safe_flat_map_a2,
                            lambda e: close_a.attempt().then(io.error(e)),
                            lambda p: close_a.attempt().then(io.panic(p)),
                        )
                    )
                )
            except Exception as exception:
                return close_a.attempt().then(io.panic(exception))

        return Resource(self.create.flat_map(safe_flat_map_a))

    @final
    def ap(
        self: Resource[R, E, Callable[[X], A2]], rs: Resource[R, E, X]
    ) -> Resource[R, E, A2]:
        return self.flat_map(lambda f: rs.map(f))

    @final
    def flatten(self: Resource[R, E, Resource[R, E, A]]) -> Resource[R, E, A]:
        return self.flat_map(lambda x: x)

    # Error API

    @final
    def catch(self, handler: Callable[[E], Resource[R, E, A]]) -> Resource[R, E, A]:
        return Resource(self.create.catch(lambda e: handler(e).create))

    @final
    def map_error(self, f: Callable[[E], E2]) -> Resource[R, E2, A]:
        return Resource(
            self.create.map_error(f).map(lambda x: (x[0], x[1].map_error(f)))
        )

    # Reader API

    @final
    def map_read(self, f: Callable[[R2], R]) -> Resource[R2, E, A]:
        return Resource(self.create.map_read(f).map(lambda x: (x[0], x[1].map_read(f))))

    # Panic

    @final
    def map_panic(self, f: Callable[[E], E2]) -> Resource[R, E2, A]:
        return Resource(
            self.create.map_panic(f).map(lambda x: (x[0], x[1].map_panic(f)))
        )

    @final
    def recover(
        self, handler: Callable[[Exception], Resource[R, E, A]]
    ) -> Resource[R, E, A]:
        return Resource(self.create.recover(lambda p: handler(p).create))

    @final
    def attempt(self) -> IO[R, Any, result.Result[E, A]]:
        return Resource(
            self.create.attempt().map(
                lambda x: x.fold(
                    lambda v: (result.Ok(v[0]), v[1]),
                    lambda e: (result.Error(e), io.pure(None)),
                    lambda p: (result.Panic(p), io.pure(None)),
                )
            )
        )

    @final
    def finally_(self, rs: Resource[R, Any, Any]) -> Resource[R, E, A]:
        return self.attempt().flat_map(lambda r: rs.attempt().then(from_result(r)))

    @final
    def on_failure(
        self, handler: Callable[[Result[E, Any]], IO[R, E, A]]
    ) -> IO[R, E, A]:
        return self.attempt().flat_map(
            lambda r: r.fold(
                pure,
                lambda e: handler(result.error(e)),
                lambda p: handler(result.panic(p)),
            )
        )


def liftIO(mio: IO[R, E, A]) -> Resource[R, E, A]:
    return Resource(mio.map(lambda a: (a, io.pure(None))))


def pure(a: A) -> Resource[R, E, A]:
    return Resource(io.pure((a, io.pure(None))))


def defer(deferred: Callable[[], A]) -> Resource[R, E, A]:
    return liftIO(io.defer(deferred))


def defer_resource(deferred: Callable[[], Resource[R, E, A]]) -> Resource[R, E, A]:
    return Resource(io.defer(deferred).flat_map(lambda rs: rs.create))


def read() -> Resource[R, E, R]:
    return liftIO(io.read())


def error(err: E) -> Resource[R, E, A]:
    return Resource(io.IORaise(err))


def panic(exception: Exception) -> Resource[R, E, A]:
    return Resource(io.IOPanic(exception))


def from_result(r: result.Result[E, A]) -> Resource[R, E, A]:
    return r.fold(pure, error, panic)


def from_openIO(
    open: IO[R, E, A], close: Callable[[A], IO[R, Any, Any]]
) -> Resource[R, E, A]:
    return Resource(open.map(lambda a: (a, close(a))))


def from_open(open: Callable[[], A], close: Callable[[A], None]) -> Resource[R, E, A]:
    return Resource(io.defer(open).map(lambda a: (a, io.pure(a).map(close))))


def from_io_rs(mio: IO[R, E, Resource[R, E, A]]) -> Resource[R, E, A]:
    return Resource(mio.flat_map(lambda rs: rs.create))
