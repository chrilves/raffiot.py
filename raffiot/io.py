"""
Data structure representing a computation.
"""

from __future__ import annotations
from typing import TypeVar, Generic, Callable, Any
from typing_extensions import final
from dataclasses import dataclass
from raffiot import result, _MatchError
from raffiot.result import Result

R = TypeVar("R")
E = TypeVar("E")
A = TypeVar("A")
X = TypeVar("X")
R2 = TypeVar("R2")
E2 = TypeVar("E2")
A2 = TypeVar("A2")


class IO(Generic[R, E, A]):
    """
    Represent a computation that computes a value of type A,
    may fail with an error (expected failure) of type E and have access
    anytime to a read-only context of type R.

    /!\\ VERY IMPORTANT /!\\
        1. The IO is LAZY:
            no code is run until you invoke the run method.
        2. The IO never raises exceptions (unless there is a bug):
            it returns panics instead.
        3. The IO is stack-safe, but you need to make sure your own code is too!
            use defer and defer_io to avoid stack-overflow.

    Have a look to the documentation and examples to learn how to use it.
    """

    @final
    def map(self, f: Callable[[A], A2]) -> IO[R, E, A2]:
        """
        Transform the computed value with f if the computation is successful.
        Do nothing otherwise.
        """
        return map(self, f)

    @final
    def flat_map(self, f: Callable[[A], IO[R, E, A2]]) -> IO[R, E, A2]:
        """
        Chain two computations.
        The result of the first one (self) can be used in the second (f).
        """
        return flat_map(self, f)

    @final
    def then(self, io: IO[R, E, A2]) -> IO[R, E, A2]:
        """
        Chain two computations.
        The result of the first one (self) is dropped.
        """
        return self.flat_map(lambda _: io)

    @final
    def ap(self: IO[R, E, Callable[[X], A]], arg: IO[R, E, X]) -> IO[R, E, A]:
        """
        Noting functions from X to A: X -> A

        If self computes a function f: X -> A
        and arg computes a value x: X
        then self.ap(arg) computes f(x): A
        """
        return ap(self, arg)

    @final
    def flatten(self):
        """
        Concatenation function on IO
        """
        return flatten(self)

    # Reader API

    @final
    def contra_map_read(self, f: Callable[[R2], R]) -> IO[R2, E, A]:
        """
        Transform the context with f.
        Note that f is not from R to R2 but from R2 to R!
        """
        return contra_map_read(f, self)

    # Error API

    @final
    def catch(self, handler: Callable[[E], IO[R, E, A]]) -> IO[R, E, A]:
        """
        React to errors (the except part of a try-except).

        On error, call the handler with the error.
        """
        return catch(self, handler)

    @final
    def map_error(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        """
        Transform the stored error if the computation fails on an error.
        Do nothing otherwise.
        """
        return map_error(self, f)

    # Panic

    @final
    def recover(self, handler: Callable[[Exception], IO[R, E, A]]) -> IO[R, E, A]:
        """
        React to panics (the except part of a try-except).

        On panic, call the handler with the exception.
        """
        return recover(self, handler)

    @final
    def map_panic(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        """
        Transform the exception stored if the computation fails on a panic.
        Do nothing otherwise.
        """
        return map_panic(self, f)

    @final
    def run(self, context: R) -> Result[E, A]:
        """
        Run the computation.

        Note that a IO is a data structure, no action is performed until you
        call run. You may view an IO value as a function declaration.
        Declaring a function does not execute its body. Only calling the
        function does. Likewise, declaring an IO does not execute its content,
        only running the IO does.

        Note that the return value is a Result[E,A].
        No exception will be raised by run (unless there is a bug), run will
        returns a panic instead!
        """
        return run(context, self)

    @final
    def attempt(self) -> IO[R, E, Result[E, A]]:
        """
        Transform this computation that may fail into a computation
        that never fails but returns a Result[E,A].

        - If self successfully computes a, then self.attempt() successfully computes Ok(a).
        - If self fails on error e, then self.attempt() successfully computes Error(e).
        - If self fails on panic p, then self.attempt() successfully computes Panic(p).

        Note that errors and panics stop the computation, unless a catch or
        recover reacts to such failures. But using map, flat_map, flatten and
        ap is sometimes easier than using catch and recover. attempt transforms
        a failed computation into a successful computation returning a failure,
        thus enabling you to use map, flat_map, ... to deal with errors.
        """
        return (
            self.map(result.pure)
            .catch(lambda x: pure(result.error(x)))
            .recover(lambda x: pure(result.panic(x)))
        )

    @final
    def finally_(self, io: IO[R, Any, Any]) -> IO[R, E, A]:
        """
        After having computed self, but before returning its result,
        execute the io computation.

        This is extremely useful when you need to perform an action,
        unconditionally, at the end of a computation, without changing
        its result, like releasing a resource.
        """
        return self.attempt().flat_map(lambda r: io.attempt().then(from_result(r)))

    @final
    def on_failure(
        self, handler: Callable[[Result[E, Any]], IO[R, E, A]]
    ) -> IO[R, E, A]:
        """
        Combined form of catch and recover.
        React to any failure of the computation.
        Do nothing if the computation is successful.

        - The handler will be called on Error(e) if the computation fails with error e.
        - The handler will be called on Panic(p) if the computation fails with panic p.
        - The handler will never be called on Ok(a).
        """
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
class __IOContraMapRead(IO[R, E, A], Generic[R, E, A, R2]):
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
    """
    An always successful computation returning a.
    """
    return __IOPure(a)


def map(main: IO[R, E, A], f: Callable[[A], A2]) -> IO[R, E, A2]:
    """
    Transform the computed value with f if the computation is successful.
    Do nothing otherwise.
    """
    return __IOAp(__IOPure(f), main)


def flat_map(main: IO[R, E, A], f: Callable[[A], IO[R, E, A2]]) -> IO[R, E, A2]:
    """
    Chain two computations.
    The result of the first one (main) can be used in the second (f).
    """
    return __IOFlatten(__IOAp(__IOPure(f), main))


def ap(fun: IO[R, E, Callable[[X], A]], arg: IO[R, E, X]) -> IO[R, E, A]:
    """
    Noting functions from X to A: X -> A

    If fun computes a function f: X -> A
    and arg computes a value x: X
    then fun.ap(arg) computes f(x): A
    """
    return __IOAp(fun, arg)


def flatten(tower: IO[R, E, IO[R, E, A]]) -> IO[R, E, A]:
    """
    Concatenation function on IO
    """
    return __IOFlatten(tower)


def defer(deferred: Callable[[], A]) -> IO[R, E, A]:
    """
    Defer a computation.

    The result of the computation is the result of deferred() but
    this call is deferred until the IO is run.

    /!\\ VERY IMPORTANT /!\\
    This is the only valid way to execute side effects.
    All side effect should we wrapped by:
        defer(lambda: <your side effecting code>)

    For example, the following code is buggy:
        >>> hello: IO[None, None, None] = pure(print("Hello World!"))
        "Hello World!" is printed
        >>> hello.run(None)
        Nothing printed
    The correct version is:
        >>> hello: IO[None, None, None] = defer(lambda: print("Hello World!"))
        Nothing is printed
        >>> hello.run(None)
        "Hello World!" is printed
        >>> hello.run(None)
        "Hello World!" is printed again
    """
    return __IODefer(deferred)


def defer_io(deferred: Callable[[], IO[R, E, A]]) -> IO[R, E, A]:
    """
    Make a function that returns an IO, an IO itself.

    This is extremely useful with recursive function that would normally blow
    the stack (raise a stack overflow exception). Deferring recursive calls
    eliminates stack overflow.

    For example, the following code blow the stack:
        >>> def f() -> IO[None,None,None]:
        >>>    return f()
        >>> f().run(None)
        RecursionError: maximum recursion depth exceeded
    But, this one runs forever:
        >> def f() -> IO[None,None,None]:
        >>    return defer_io(lambda: f())
        >> f().run(None)
    """
    return __IOFlatten(__IODefer(deferred))


def read() -> IO[R, E, R]:
    """
    Read the context.

    To execute a computation IO[R,E,A], you need to call the run method with
    some value r of type R: io.run(r). the read() action returns the value r
    given to run.

    Please note that the contra_map_read method can transform this value r.
    """
    return __IORead()


def contra_map_read(fun: Callable[[R], R2], main: IO[R2, E, A]) -> IO[R, E2, A]:
    """
    Transform the context with f.
    Note that f is not from R to R2 but from R2 to R!
    """
    return __IOContraMapRead(fun, main)


def error(err: E) -> IO[R, E, A]:
    """
    Computation that fails on the error err.
    """
    return __IORaise(err)


def catch(main: IO[R, E, A], handler: Callable[[E], IO[R, E, A]]) -> IO[R, E, A]:
    """ "
    React to errors (the except part of a try-except).

    On error, call the handler with the error.
    """
    return __IOCatch(main, handler)


def map_error(main: IO[R, E2, A], fun: Callable[[E2], E]) -> IO[R, E2, A]:
    """
    Transform the stored error if the computation fails on an error.
    Do nothing otherwise.
    """
    return __IOMapError(main, fun)


def panic(exception: Exception) -> IO[R, E, A]:
    """
    Computation that fails with the panic exception.
    """
    return __IOPanic(exception)


def recover(
    main: IO[R, E, A], handler: Callable[[Exception], IO[R, E, A]]
) -> IO[R, E, A]:
    """
    React to panics (the except part of a try-except).

    On panic, call the handler with the exception.
    """
    return __IORecover(main, handler)


def map_panic(main: IO[R, E, A], fun: Callable[[Exception], Exception]) -> IO[R, E, A]:
    """
    Transform the exception stored if the computation fails on a panic.
    Do nothing otherwise.
    """
    return __IOMapPanic(main, fun)


def from_result(r: Result[E, A]) -> IO[R, E, A]:
    """
    Computation that:
    - success if r is an Ok
    - fails with error e if r is Error(e)
    - fails with panic p if r is Panic(p)
    """
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
    """
    Run the IO main_io with main_context as the context (the value that read()
    returns).

    It never raise any exception (unless there is a bug) so do not
    treat the absence of exception as a success. Instead process the
    returned Result[E,A].
    """
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
                if isinstance(io, __IOContraMapRead):
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
                return result.Panic(_MatchError(f"{io} should be an IO"))
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

                raise _MatchError(f"{cont} should be a _Cont")


def safe(f: Callable[..., IO[R, E, A]]) -> Callable[..., IO[R, E, A]]:
    """
    Ensures a function retuning an IO never raise any exception but returns a
    panic instead.
    """

    def wrapper(*args, **kwargs):
        return __IOPure(f).flat_map(lambda g: g(*args, **kwargs))

    return wrapper
