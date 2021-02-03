from __future__ import annotations
from typing import TypeVar, Generic, Callable, Any
from typing_extensions import final
from dataclasses import dataclass
from raffiot import result, MatchError
from raffiot.result import Result


R = TypeVar("R")
E = TypeVar("E")
A = TypeVar("A")
X = TypeVar("X")
R2 = TypeVar("R2")
E2 = TypeVar("E2")
A2 = TypeVar("A2")


class IO(Generic[R, E, A]):
    @final
    def map(self, f: Callable[[A], A2]) -> IO[Any, Any, A2]:
        return IOAp(IOPure(f), self)

    @final
    def flat_map(self, f: Callable[[A], IO[R, E, A2]]) -> IO[R, E, A2]:
        return IOFlatten(IOAp(IOPure(f), self))

    @final
    def then(self, io: IO[R, E, A2]) -> IO[R, E, A2]:
        return self.flat_map(lambda _: io)

    @final
    def ap(self, arg):
        return IOAp(self, arg)

    @final
    def flatten(self):
        return IOFlatten(self)

    # Error API

    @final
    def catch(self, handler: Callable[[E], IO[R, E, A]]) -> IO[R, E, A]:
        return IOCatch(self, handler)

    @final
    def map_error(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        return IOMapError(self, f)

    # Reader API

    @final
    def map_read(self, f: Callable[[R2], R]) -> IO[R2, E, A]:
        return IOMapRead(f, self)

    # Panic

    @final
    def map_panic(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        return IOMapPanic(self, f)

    @final
    def recover(self, handler: Callable[[Exception], IO[R, E, A]]) -> IO[R, E, A]:
        return IORecover(self, handler)

    @final
    def run(self, context: R) -> Result[E, A]:
        return run(context, self)

    @final
    def attempt(self) -> IO[R, E, Result[E, A]]:
        return (
            self.map(result.pure)
            .catch(lambda x: pure(result.error(x)))
            .recover(lambda x: pure(result.panic(x)))
        )

    @final
    def finally_(self, io: IO[R, Any, Any]) -> IO[R, E, A]:
        return self.attempt().flat_map(lambda r: io.attempt().then(from_result(r)))

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


@final
@dataclass
class IOPure(IO[R, E, A]):
    value: A


@final
@dataclass
class IODefer(IO[R, E, A]):
    deferred: Callable[[], A]


@final
@dataclass
class IOAp(IO[R, E, A], Generic[R, E, A, X]):
    fun: IO[R, E, Callable[[X], A]]
    arg: IO[R, E, X]


@final
@dataclass
class IOFlatten(IO[R, E, A]):
    tower: IO[R, E, IO[R, E, A]]


@final
@dataclass
class IORead(IO[R, E, R]):
    pass


@final
@dataclass
class IOMapRead(IO[R, E, A], Generic[R, E, A, R2]):
    fun: Callable[[R], R2]
    main: IO[R2, E, A]


@final
@dataclass
class IORaise(IO[R, E, A]):
    error: E


@final
@dataclass
class IOCatch(IO[R, E, A]):
    main: IO[R, E, A]
    handler: Callable[[E], IO[R, E, A]]


@final
@dataclass
class IOMapError(IO[R, E, A], Generic[R, E, A, E2]):
    main: IO[R, E2, A]
    fun: Callable[[E2], E]


@final
@dataclass
class IOPanic(IO[R, E, A]):
    exception: Exception


@final
@dataclass
class IORecover(IO[R, E, A]):
    main: IO[R, E, A]
    handler: Callable[[Exception], IO[R, E, A]]


@final
@dataclass
class IOMapPanic(IO[R, E, A], Generic[R, E, A, E2]):
    main: IO[R, E2, A]
    fun: Callable[[Exception], Exception]


def pure(a: A) -> IO[R, E, A]:
    return IOPure(a)


def defer(deferred: Callable[[], A]) -> IO[R, E, A]:
    return IODefer(deferred)


def deferIO(deferred: Callable[[], IO[R, E, A]]) -> IO[R, E, A]:
    return IOFlatten(IODefer(deferred))


def read() -> IO[R, E, R]:
    return IORead()


def error(err: E) -> IO[R, E, A]:
    return IORaise(err)


def panic(exception: Exception) -> IO[R, E, A]:
    return IOPanic(exception)


def from_result(r: Result[E, A]) -> IO[R, E, A]:
    return r.fold(pure, error, panic)


class _Cont:
    pass


@final
@dataclass
class _ContId(_Cont):
    pass


@final
@dataclass
class _ContAp1(_Cont):
    context: R
    io: IO[R, E, A]
    cont: _Cont


@final
@dataclass
class _ContAp2(_Cont):
    io: IO[R, E, A]
    cont: _Cont


@final
@dataclass
class _ContFlatten(_Cont):
    context: R
    cont: _Cont


@final
@dataclass
class _ContCatch(_Cont):
    context: R
    handler: Callable[[E], IO[R, E, A]]
    cont: _Cont


@final
@dataclass
class _ContMapError(_Cont):
    fun: Callable[[E], E2]
    cont: _Cont


@final
@dataclass
class _ContRecover(_Cont):
    context: R
    handler: Callable[[E], IO[R, E, A]]
    cont: _Cont


@final
@dataclass
class _ContMapPanic(_Cont):
    fun: Callable[[Exception], Exception]
    cont: _Cont


def run(main_context: R, main_io: IO[R, E, A]) -> Result[E, A]:
    context = main_context
    io = main_io
    cont = _ContId()
    arg = None
    first = True
    while True:
        if first:
            while True:
                if isinstance(io, IOPure):
                    arg = result.Ok(io.value)
                    first = False
                    break
                if isinstance(io, IOAp):
                    cont = _ContAp1(context, io.arg, cont)
                    io = io.fun
                    continue
                if isinstance(io, IOFlatten):
                    cont = _ContFlatten(context, cont)
                    io = io.tower
                    continue
                # Defer
                if isinstance(io, IODefer):
                    try:
                        arg = result.Ok(io.deferred())
                    except Exception as exception:
                        arg = result.Panic(exception)
                    first = False
                    break
                # Read
                if isinstance(io, IORead):
                    arg = result.Ok(context)
                    first = False
                    break
                if isinstance(io, IOMapRead):
                    try:
                        context = io.fun(context)
                        io = io.main
                        continue
                    except Exception as exception:
                        arg = result.Panic(exception)
                        first = False
                        break
                # Error
                if isinstance(io, IORaise):
                    arg = result.Error(io.error)
                    first = False
                    break
                if isinstance(io, IOCatch):
                    cont = _ContCatch(context, io.handler, cont)
                    io = io.main
                    continue
                if isinstance(io, IOMapError):
                    cont = _ContMapError(io.fun, cont)
                    io = io.main
                    continue
                # Panic
                if isinstance(io, IOPanic):
                    arg = result.Panic(io.exception)
                    first = False
                    break
                if isinstance(io, IORecover):
                    cont = _ContRecover(context, io.handler, cont)
                    io = io.main
                    continue
                if isinstance(io, IOMapPanic):
                    cont = _ContMapPanic(io.fun, cont)
                    io = io.main
                    continue
                return result.Panic(MatchError(f"{io} should be an IO"))
        else:
            while True:
                if isinstance(cont, _ContId):
                    return arg
                if isinstance(cont, _ContAp1):
                    context = cont.context
                    io = cont.io
                    cont = _ContAp2(arg, cont.cont)
                    first = True
                    break
                if isinstance(cont, _ContAp2):
                    try:
                        arg = cont.io.ap(arg)
                    except Exception as exception:
                        arg = result.Panic(exception)
                    cont = cont.cont
                    continue
                if isinstance(cont, _ContFlatten):
                    if isinstance(arg, result.Ok):
                        context = cont.context
                        io = arg.success
                        cont = cont.cont
                        first = True
                        break
                    cont = cont.cont
                    continue
                if isinstance(cont, _ContCatch):
                    try:
                        if isinstance(arg, result.Error):
                            io = cont.handler(arg.error)
                            context = cont.context
                            cont = cont.cont
                            first = True
                            break
                    except Exception as exception:
                        arg = result.Panic(exception)
                    cont = cont.cont
                    continue
                if isinstance(cont, _ContMapError):
                    try:
                        arg = arg.map_error(cont.fun)
                    except Exception as exception:
                        arg = result.Panic(exception)
                    cont = cont.cont
                    continue
                if isinstance(cont, _ContRecover):
                    try:
                        if isinstance(arg, result.Panic):
                            io = cont.handler(arg.exception)
                            context = cont.context
                            cont = cont.cont
                            first = True
                            break
                    except Exception as exception:
                        arg = result.Panic(exception)
                    cont = cont.cont
                    continue
                if isinstance(cont, _ContMapPanic):
                    try:
                        arg = arg.map_panic(cont.fun)
                    except Exception as exception:
                        arg = result.Panic(exception)
                    cont = cont.cont
                    continue

                raise MatchError(f"{cont} should be a _Cont")


def safe(f: Callable[..., IO[R, E, A]]) -> Callable[..., IO[R, E, A]]:
    def wrapper(*args, **kwargs):
        return IOPure(f).flat_map(lambda g: g(*args, **kwargs))

    return wrapper
