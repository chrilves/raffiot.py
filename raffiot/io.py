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
    def map(self, f: Callable[[A], A2]) -> IO[R, E, A2]:
        return map(self, f)

    @final
    def flat_map(self, f: Callable[[A], IO[R, E, A2]]) -> IO[R, E, A2]:
        return flat_map(self, f)

    @final
    def then(self, io: IO[R, E, A2]) -> IO[R, E, A2]:
        return self.flat_map(lambda _: io)

    @final
    def ap(self, arg):
        return ap(self, arg)

    @final
    def flatten(self):
        return flatten(self)

    # Error API

    @final
    def catch(self, handler: Callable[[E], IO[R, E, A]]) -> IO[R, E, A]:
        return catch(self, handler)

    @final
    def map_error(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        return map_error(self, f)

    # Reader API

    @final
    def map_read(self, f: Callable[[R2], R]) -> IO[R2, E, A]:
        return map_read(f, self)

    # Panic

    @final
    def map_panic(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        return map_panic(self, f)

    @final
    def recover(self, handler: Callable[[Exception], IO[R, E, A]]) -> IO[R, E, A]:
        return recover(self, handler)

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
class __IOPure(IO[R, E, A]):
    value: A


@final
@dataclass
class __IOAp(IO[R, E, A], Generic[R, E, A, X]):
    fun: IO[R, E, Callable[[X], A]]
    arg: IO[R, E, X]


@final
@dataclass
class __IOFlatten(IO[R, E, A]):
    tower: IO[R, E, IO[R, E, A]]


@final
@dataclass
class __IODefer(IO[R, E, A]):
    deferred: Callable[[], A]


@final
@dataclass
class __IORead(IO[R, E, R]):
    pass


@final
@dataclass
class __IOMapRead(IO[R, E, A], Generic[R, E, A, R2]):
    fun: Callable[[R], R2]
    main: IO[R2, E, A]


@final
@dataclass
class __IORaise(IO[R, E, A]):
    error: E


@final
@dataclass
class __IOCatch(IO[R, E, A]):
    main: IO[R, E, A]
    handler: Callable[[E], IO[R, E, A]]


@final
@dataclass
class __IOMapError(IO[R, E, A], Generic[R, E, A, E2]):
    main: IO[R, E2, A]
    fun: Callable[[E2], E]


@final
@dataclass
class __IOPanic(IO[R, E, A]):
    exception: Exception


@final
@dataclass
class __IORecover(IO[R, E, A]):
    main: IO[R, E, A]
    handler: Callable[[Exception], IO[R, E, A]]


@final
@dataclass
class __IOMapPanic(IO[R, E, A]):
    main: IO[R, E, A]
    fun: Callable[[Exception], Exception]


def pure(a: A) -> IO[R, E, A]:
    return __IOPure(a)


def map(main: IO[R, E, A], f: Callable[[A], A2]) -> IO[R, E, A2]:
    return __IOAp(__IOPure(f), main)


def flat_map(main: IO[R, E, A], f: Callable[[A], IO[R, E, A2]]) -> IO[R, E, A2]:
    return __IOFlatten(__IOAp(__IOPure(f), main))


def ap(fun: IO[R, E, Callable[[X], A]], arg: IO[R, E, X]) -> IO[R, E, A]:
    return __IOAp(fun, arg)


def flatten(tower: IO[R, E, IO[R, E, A]]) -> IO[R, E, A]:
    return __IOFlatten(tower)


def defer(deferred: Callable[[], A]) -> IO[R, E, A]:
    return __IODefer(deferred)


def deferIO(deferred: Callable[[], IO[R, E, A]]) -> IO[R, E, A]:
    return __IOFlatten(__IODefer(deferred))


def read() -> IO[R, E, R]:
    return __IORead()


def map_read(fun: Callable[[R], R2], main: IO[R2, E, A]) -> IO[R, E2, A]:
    return __IOMapRead(fun, main)


def error(err: E) -> IO[R, E, A]:
    return __IORaise(err)


def catch(main: IO[R, E, A], handler: Callable[[E], IO[R, E, A]]) -> IO[R, E, A]:
    return __IOCatch(main, handler)


def map_error(main: IO[R, E2, A], fun: Callable[[E2], E]) -> IO[R, E2, A]:
    return __IOMapError(main, fun)


def panic(exception: Exception) -> IO[R, E, A]:
    return __IOPanic(exception)


def recover(
    main: IO[R, E, A], handler: Callable[[Exception], IO[R, E, A]]
) -> IO[R, E, A]:
    return __IORecover(main, handler)


def map_panic(main: IO[R, E, A], fun: Callable[[Exception], Exception]) -> IO[R, E, A]:
    return __IOMapPanic(main, fun)


def from_result(r: Result[E, A]) -> IO[R, E, A]:
    return r.fold(pure, error, panic)


class __Cont:
    pass


@final
@dataclass
class __ContId(__Cont):
    pass


@final
@dataclass
class __ContAp1(__Cont):
    context: R
    io: IO[R, E, A]
    cont: __Cont


@final
@dataclass
class __ContAp2(__Cont):
    io: IO[R, E, A]
    cont: __Cont


@final
@dataclass
class __ContFlatten(__Cont):
    context: R
    cont: __Cont


@final
@dataclass
class __ContCatch(__Cont):
    context: R
    handler: Callable[[E], IO[R, E, A]]
    cont: __Cont


@final
@dataclass
class __ContMapError(__Cont):
    fun: Callable[[E], E2]
    cont: __Cont


@final
@dataclass
class __ContRecover(__Cont):
    context: R
    handler: Callable[[E], IO[R, E, A]]
    cont: __Cont


@final
@dataclass
class __ContMapPanic(__Cont):
    fun: Callable[[Exception], Exception]
    cont: __Cont


def run(main_context: R, main_io: IO[R, E, A]) -> Result[E, A]:
    context = main_context
    io = main_io
    cont = __ContId()
    arg = None
    first = True
    while True:
        if first:
            while True:
                if isinstance(io, __IOPure):
                    arg = result.Ok(io.value)
                    first = False
                    break
                if isinstance(io, __IOAp):
                    cont = __ContAp1(context, io.arg, cont)
                    io = io.fun
                    continue
                if isinstance(io, __IOFlatten):
                    cont = __ContFlatten(context, cont)
                    io = io.tower
                    continue
                # Defer
                if isinstance(io, __IODefer):
                    try:
                        arg = result.Ok(io.deferred())
                    except Exception as exception:
                        arg = result.Panic(exception)
                    first = False
                    break
                # Read
                if isinstance(io, __IORead):
                    arg = result.Ok(context)
                    first = False
                    break
                if isinstance(io, __IOMapRead):
                    try:
                        context = io.fun(context)
                        io = io.main
                        continue
                    except Exception as exception:
                        arg = result.Panic(exception)
                        first = False
                        break
                # Error
                if isinstance(io, __IORaise):
                    arg = result.Error(io.error)
                    first = False
                    break
                if isinstance(io, __IOCatch):
                    cont = __ContCatch(context, io.handler, cont)
                    io = io.main
                    continue
                if isinstance(io, __IOMapError):
                    cont = __ContMapError(io.fun, cont)
                    io = io.main
                    continue
                # Panic
                if isinstance(io, __IOPanic):
                    arg = result.Panic(io.exception)
                    first = False
                    break
                if isinstance(io, __IORecover):
                    cont = __ContRecover(context, io.handler, cont)
                    io = io.main
                    continue
                if isinstance(io, __IOMapPanic):
                    cont = __ContMapPanic(io.fun, cont)
                    io = io.main
                    continue
                return result.Panic(MatchError(f"{io} should be an IO"))
        else:
            while True:
                if isinstance(cont, __ContId):
                    return arg
                if isinstance(cont, __ContAp1):
                    context = cont.context
                    io = cont.io
                    cont = __ContAp2(arg, cont.cont)
                    first = True
                    break
                if isinstance(cont, __ContAp2):
                    try:
                        arg = cont.io.ap(arg)
                    except Exception as exception:
                        arg = result.Panic(exception)
                    cont = cont.cont
                    continue
                if isinstance(cont, __ContFlatten):
                    if isinstance(arg, result.Ok):
                        context = cont.context
                        io = arg.success
                        cont = cont.cont
                        first = True
                        break
                    cont = cont.cont
                    continue
                if isinstance(cont, __ContCatch):
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
                if isinstance(cont, __ContMapError):
                    try:
                        arg = arg.map_error(cont.fun)
                    except Exception as exception:
                        arg = result.Panic(exception)
                    cont = cont.cont
                    continue
                if isinstance(cont, __ContRecover):
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
                if isinstance(cont, __ContMapPanic):
                    try:
                        arg = arg.map_panic(cont.fun)
                    except Exception as exception:
                        arg = result.Panic(exception)
                    cont = cont.cont
                    continue

                raise MatchError(f"{cont} should be a _Cont")


def safe(f: Callable[..., IO[R, E, A]]) -> Callable[..., IO[R, E, A]]:
    def wrapper(*args, **kwargs):
        return __IOPure(f).flat_map(lambda g: g(*args, **kwargs))

    return wrapper
