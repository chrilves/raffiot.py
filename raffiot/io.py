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
    def __init__(self, tag, fields):
        self.tag = tag
        self.fields = fields

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


# IO PURE             0 VALUE
# IO AP               1 FUN       ARG
# IO FLATTEN          2 TOWER
# IO DEFER            3 DEFERED
# IO READ             4
# IO CONTRA_MAP_READ  5 FUN       MAIN
# IO RAISE            6 ERROR
# IO CATCH            7 MAIN      HANDLER
# IO MAP_ERROR        8 MAIN      FUN
# IO PANIC            9 EXCEPTION
# IO RECOVER         10 MAIN      HANDLER
# IO MAP_PANIC       11 MAIN      FUN


def pure(a: A) -> IO[R, E, A]:
    """
    An always successful computation returning a.
    """
    return IO(0, a)


def ap(fun: IO[R, E, Callable[[X], A]], arg: IO[R, E, X]) -> IO[R, E, A]:
    """
    Noting functions from X to A: X -> A

    If fun computes a function f: X -> A
    and arg computes a value x: X
    then fun.ap(arg) computes f(x): A
    """
    if fun.tag == 0 and arg.tag == 0:
        return IO(3, lambda: fun.fields(arg.fields))
    return IO(1, (fun, arg))


def map(main: IO[R, E, A], f: Callable[[A], A2]) -> IO[R, E, A2]:
    """
    Transform the computed value with f if the computation is successful.
    Do nothing otherwise.
    """
    return IO(1, (IO(0, f), main))


def flatten(tower: IO[R, E, IO[R, E, A]]) -> IO[R, E, A]:
    """
    Concatenation function on IO
    """
    if tower.tag == 0:
        return tower.fields
    return IO(2, tower)


def flat_map(main: IO[R, E, A], f: Callable[[A], IO[R, E, A2]]) -> IO[R, E, A2]:
    """
    Chain two computations.
    The result of the first one (main) can be used in the second (f).
    """
    if main.tag == 0:
        IO(2, IO(3, lambda: f(main.fields)))
    return IO(2, IO(1, (IO(0, f), main)))


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
    return IO(3, deferred)


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
    return IO(2, IO(3, deferred))


def read() -> IO[R, E, R]:
    """
    Read the context.

    To execute a computation IO[R,E,A], you need to call the run method with
    some value r of type R: io.run(r). the read() action returns the value r
    given to run.

    Please note that the contra_map_read method can transform this value r.
    """
    return IO(4, None)


def contra_map_read(fun: Callable[[R], R2], main: IO[R2, E, A]) -> IO[R, E2, A]:
    """
    Transform the context with f.
    Note that f is not from R to R2 but from R2 to R!
    """
    if main.tag in [0, 3, 6, 9]:
        return main
    return IO(5, (fun, main))


def error(err: E) -> IO[R, E, A]:
    """
    Computation that fails on the error err.
    """
    return IO(6, err)


def catch(main: IO[R, E, A], handler: Callable[[E], IO[R, E, A]]) -> IO[R, E, A]:
    """ "
    React to errors (the except part of a try-except).

    On error, call the handler with the error.
    """
    if main.tag in [0, 3, 4, 9]:
        return main
    return IO(7, (main, handler))


def map_error(main: IO[R, E2, A], fun: Callable[[E2], E]) -> IO[R, E2, A]:
    """
    Transform the stored error if the computation fails on an error.
    Do nothing otherwise.
    """
    if main.tag in [0, 3, 4, 9]:
        return main
    return IO(8, (main, fun))


def panic(exception: Exception) -> IO[R, E, A]:
    """
    Computation that fails with the panic exception.
    """
    return IO(9, exception)


def recover(
    main: IO[R, E, A], handler: Callable[[Exception], IO[R, E, A]]
) -> IO[R, E, A]:
    """
    React to panics (the except part of a try-except).

    On panic, call the handler with the exception.
    """
    if main.tag in [0, 4, 6]:
        return main
    return IO(10, (main, handler))


def map_panic(main: IO[R, E, A], fun: Callable[[Exception], Exception]) -> IO[R, E, A]:
    """
    Transform the exception stored if the computation fails on a panic.
    Do nothing otherwise.
    """
    if main.tag in [0, 4, 6]:
        return main
    return IO(11, (main, fun))


def from_result(r: Result[E, A]) -> IO[R, E, A]:
    """
    Computation that:
    - success if r is an Ok
    - fails with error e if r is Error(e)
    - fails with panic p if r is Panic(p)
    """
    return r.fold(pure, error, panic)


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
    cont = (0,)
    arg = None
    # CONT ID        0
    # CONT AP1       1 CONT CONTEXT IO
    # CONT AP2       2 CONT FUN
    # CONT FLATTEN   3 CONT CONTEXT
    # CONT CATCH     4 CONT CONTEXT HANDLER
    # CONT MAP_ERROR 5 CONT FUN
    # CONT RECOVER   6 CONT CONTEXT HANDLER
    # CONT MAP_PANIC 7 CONT FUN

    while True:
        # Eval IO
        while True:
            tag = io.tag
            if tag == 0:  # PURE
                arg = result.Ok(io.fields)
                break
            if tag == 1:  # AP
                cont = (1, cont, context, io.fields[1])
                io = io.fields[0]
                continue
            if tag == 2:  # FLATTEN
                cont = (3, cont, context)
                io = io.fields
                continue
            if tag == 3:  # DEREF
                try:
                    arg = result.Ok(io.fields())
                except Exception as exception:
                    arg = result.Panic(exception)
                break
            if tag == 4:  # READ
                arg = result.Ok(context)
                break
            if tag == 5:  # MAP READ
                try:
                    context = io.fields[0](context)
                    io = io.fields[1]
                    continue
                except Exception as exception:
                    arg = result.Panic(exception)
                    break
            if tag == 6:  # RAISE
                arg = result.Error(io.fields)
                break
            if tag == 7:  # CATCH
                cont = (4, cont, context, io.fields[1])
                io = io.fields[0]
                continue
            if tag == 8:  # MAP ERROR
                cont = (5, cont, io.fields[1])
                io = io.fields[0]
                continue
            if tag == 9:  # PANIC
                arg = result.Panic(io.fields)
                break
            if tag == 10:  # RECOVER
                cont = (6, cont, context, io.fields[1])
                io = io.fields[0]
                continue
            if tag == 11:  # MAP PANIC
                cont = (7, cont, io.fields[1])
                io = io.fields[0]
                continue
            arg = result.Panic(_MatchError(f"{io} should be an IO"))
            break

        # Eval Cont
        while True:
            tag = cont[0]
            if tag == 0:  # Cont ID
                return arg
            if tag == 1:  # Cont AP1
                context = cont[2]
                io = cont[3]
                cont = (2, cont[1], arg)
                break
            if tag == 2:  # Cont AP2
                try:
                    arg = cont[2].ap(arg)
                except Exception as exception:
                    arg = result.Panic(exception)
                cont = cont[1]
                continue
            if tag == 3:  # Cont Flatten
                if isinstance(arg, result.Ok):
                    context = cont[2]
                    io = arg.success
                    cont = cont[1]
                    break
                cont = cont[1]
                continue
            if tag == 4:  # Cont CATCH
                try:
                    if isinstance(arg, result.Error):
                        io = cont[3](arg.error)
                        context = cont[2]
                        cont = cont[1]
                        break
                except Exception as exception:
                    arg = result.Panic(exception)
                cont = cont[1]
                continue
            if tag == 5:  # Cont MAP ERROR
                try:
                    arg = arg.map_error(cont[2])
                except Exception as exception:
                    arg = result.Panic(exception)
                cont = cont[1]
                continue
            if tag == 6:  # Cont RECOVER
                try:
                    if isinstance(arg, result.Panic):
                        io = cont[3](arg.exception)
                        context = cont[2]
                        cont = cont[1]
                        break
                except Exception as exception:
                    arg = result.Panic(exception)
                cont = cont[1]
                continue
            if tag == 7:  # CONT MAP PANIC
                try:
                    arg = arg.map_panic(cont[2])
                except Exception as exception:
                    arg = result.Panic(exception)
                cont = cont[1]
                continue
            raise _MatchError(f"{cont} should be a Cont")


def safe(f: Callable[..., IO[R, E, A]]) -> Callable[..., IO[R, E, A]]:
    """
    Ensures a function retuning an IO never raise any exception but returns a
    panic instead.
    """

    def wrapper(*args, **kwargs):
        return pure(f).flat_map(lambda g: g(*args, **kwargs))

    return wrapper
