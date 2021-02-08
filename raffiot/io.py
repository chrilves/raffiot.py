"""
Data structure representing a computation.
"""

from __future__ import annotations
from typing import TypeVar, Generic, Callable, Any
from typing_extensions import final
from raffiot import result, _MatchError
from raffiot.result import Result, Ok, Error, Panic

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

    /!\\ **VERY IMPORTANT** /!\\

    1. **DO NEVER SUB-CLASS IO**: it would break the API.
    2. **DO NEVER INSTANTIATE an IO DIRECTLY**: use **only** the functions
       ands methods in this module.
    3. The IO is **LAZY**:
        no code is run until you invoke the run method.
    4. The IO never raises exceptions (unless there is a bug):
        it returns panics instead.
    5. The IO is stack-safe, but you need to make sure your own code is too!
        use defer and defer_io to avoid stack-overflow.

    Have a look to the documentation and examples to learn how to use it.
    """

    __slots__ = "__tag", "__fields"

    @final
    def __init__(self, __tag, __fields):
        self.__tag = __tag
        self.__fields = __fields

    @final
    def map(self, f: Callable[[A], A2]) -> IO[R, E, A2]:
        """
        Transform the computed value with f if the computation is successful.
        Do nothing otherwise.
        """
        return IO(1, (self, f))

    @final
    def flat_map(self, f: Callable[[A], IO[R, E, A2]]) -> IO[R, E, A2]:
        """
        Chain two computations.
        The result of the first one (self) can be used in the second (f).
        """
        return IO(2, (self, f))

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
        Noting functions from X to A: `X -> A`

        If self computes a function `f: X -> A`
        and arg computes a value `x: X`
        then self.ap(arg) computes `f(x): A`
        """
        return IO(3, (self, arg))

    @final
    def flatten(self):
        """
        Concatenation function on IO
        """
        if self.__tag == 0:
            return self.__fields
        return IO(4, self)

    # Reader API

    @final
    def contra_map_read(self, f: Callable[[R2], R]) -> IO[R2, E, A]:
        """
        Transform the context with f.
        Note that f is not from R to R2 but from R2 to R!
        """
        return IO(8, (f, self))

    # Error API

    @final
    def catch(self, handler: Callable[[E], IO[R, E, A]]) -> IO[R, E, A]:
        """
        React to errors (the except part of a try-except).

        On error, call the handler with the error.
        """
        return IO(10, (self, handler))

    @final
    def map_error(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        """
        Transform the stored error if the computation fails on an error.
        Do nothing otherwise.
        """
        return IO(11, (self, f))

    # Panic

    @final
    def recover(self, handler: Callable[[Exception], IO[R, E, A]]) -> IO[R, E, A]:
        """
        React to panics (the except part of a try-except).

        On panic, call the handler with the exception.
        """
        return IO(13, (self, handler))

    @final
    def map_panic(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        """
        Transform the exception stored if the computation fails on a panic.
        Do nothing otherwise.
        """
        return IO(14, (self, f))

    @final
    def run(self, context: R) -> Result[E, A]:
        """
        Run the computation.

        Note that a IO is a data structure, no action is performed until you
        call run. You may view an IO value as a function declaration.
        Declaring a function does not execute its body. Only calling the
        function does. Likewise, declaring an IO does not execute its content,
        only running the IO does.

        Note that the return value is a  `Result[E,A]`.
        No exception will be raised by run (unless there is a bug), run will
        returns a panic instead!
        """
        ctxt = context
        io = self
        cont = [0]
        arg_tag = None
        arg_value = None
        # CONT ID        0
        # CONT MAP       1 CONT FUN
        # CONT FLATMAP1  2 CONT CONTEXT HANDLER
        # CONT AP1       3 CONT CONTEXT IO
        # CONT AP2       4 CONT FUN
        # CONT FLATTEN   5 CONT CONTEXT
        # CONT CATCH     6 CONT CONTEXT HANDLER
        # CONT MAP_ERROR 7 CONT FUN
        # CONT RECOVER   8 CONT CONTEXT HANDLER
        # CONT MAP_PANIC 9 CONT FUN

        while True:
            # Eval IO
            while True:
                tag = io.__tag
                if tag == 0:  # PURE
                    arg_tag = 0
                    arg_value = io.__fields
                    break
                if tag == 1:  # MAP
                    cont.append(io.__fields[1])
                    cont.append(1)
                    io = io.__fields[0]
                    continue
                if tag == 2:  # FLATMAP
                    cont.append(io.__fields[1])
                    cont.append(ctxt)
                    cont.append(2)
                    io = io.__fields[0]
                    continue
                if tag == 3:  # AP
                    cont.append(io.__fields[1])
                    cont.append(ctxt)
                    cont.append(3)
                    io = io.__fields[0]
                    continue
                if tag == 4:  # FLATTEN
                    cont.append(ctxt)
                    cont.append(5)
                    io = io.__fields
                    continue
                if tag == 5:  # DEREF
                    try:
                        arg_tag = 0
                        arg_value = io.__fields()
                    except Exception as exception:
                        arg_tag = 2
                        arg_value = exception
                    break
                if tag == 6:  # DEREF_IO
                    try:
                        io = io.__fields()
                        continue
                    except Exception as exception:
                        arg_tag = 2
                        arg_value = exception
                        break
                if tag == 7:  # READ
                    arg_tag = 0
                    arg_value = ctxt
                    break
                if tag == 8:  # MAP READ
                    try:
                        ctxt = io.__fields[0](ctxt)
                        io = io.__fields[1]
                        continue
                    except Exception as exception:
                        arg_tag = 2
                        arg_value = exception
                        break
                if tag == 9:  # RAISE
                    arg_tag = 1
                    arg_value = io.__fields
                    break
                if tag == 10:  # CATCH
                    cont.append(io.__fields[1])
                    cont.append(ctxt)
                    cont.append(6)
                    io = io.__fields[0]
                    continue
                if tag == 11:  # MAP ERROR
                    cont.append(io.__fields[1])
                    cont.append(7)
                    io = io.__fields[0]
                    continue
                if tag == 12:  # PANIC
                    arg_tag = 2
                    arg_value = io.__fields
                    break
                if tag == 13:  # RECOVER
                    cont.append(io.__fields[1])
                    cont.append(ctxt)
                    cont.append(8)
                    io = io.__fields[0]
                    continue
                if tag == 14:  # MAP PANIC
                    cont.append(io.__fields[1])
                    cont.append(9)
                    io = io.__fields[0]
                    continue
                arg_tag = 2
                arg_value = _MatchError(f"{io} should be an IO")
                break

            # Eval Cont
            while True:
                tag = cont.pop()
                if tag == 0:  # Cont ID
                    if arg_tag == 0:
                        return Ok(arg_value)
                    if arg_tag == 1:
                        return Error(arg_value)
                    if arg_tag == 2:
                        return Panic(arg_value)
                    raise _MatchError(f"Wrong result tag {arg_tag}")
                if tag == 1:  # Cont MAP
                    fun = cont.pop()
                    try:
                        if arg_tag == 0:
                            arg_value = fun(arg_value)
                    except Exception as exception:
                        arg_tag = 2
                        arg_value = exception
                    continue
                if tag == 2:  # Cont FLATMAP
                    ctxt = cont.pop()
                    f = cont.pop()
                    try:
                        if arg_tag == 0:
                            io = f(arg_value)
                            break
                    except Exception as exception:
                        arg_tag = 2
                        arg_value = exception
                    continue
                if tag == 3:  # Cont AP1
                    ctxt = cont.pop()
                    io = cont.pop()
                    cont.append(arg_value)
                    cont.append(arg_tag)
                    cont.append(4)
                    break
                if tag == 4:  # Cont AP2
                    fun_tag = cont.pop()
                    fun_value = cont.pop()
                    try:
                        if fun_tag == 0 and arg_tag == 0:
                            arg_value = fun_value(arg_value)
                    except Exception as exception:
                        arg_tag = 2
                        arg_value = exception
                    continue
                if tag == 5:  # Cont Flatten
                    ctxt = cont.pop()
                    if arg_tag == 0:
                        io = arg_value
                        break
                    continue
                if tag == 6:  # Cont CATCH
                    ctxt = cont.pop()
                    handler = cont.pop()
                    try:
                        if arg_tag == 1:
                            io = handler(arg_value)
                            break
                    except Exception as exception:
                        arg_tag = 2
                        arg_value = exception
                    continue
                if tag == 7:  # Cont MAP ERROR
                    fun = cont.pop()
                    try:
                        if arg_tag == 1:
                            arg_value = fun(arg_value)
                    except Exception as exception:
                        arg_tag = 2
                        arg_value = exception
                    continue
                if tag == 8:  # Cont RECOVER
                    ctxt = cont.pop()
                    handler = cont.pop()
                    try:
                        if arg_tag == 2:
                            io = handler(arg_value)
                            break
                    except Exception as exception:
                        arg_tag = 2
                        arg_value = exception
                    continue
                if tag == 9:  # CONT MAP PANIC
                    fun = cont.pop()
                    try:
                        if arg_tag == 2:
                            arg_value = fun(arg_value)
                    except Exception as exception:
                        arg_tag = 2
                        arg_value = exception
                    continue
                raise _MatchError(f"{cont} should be a Cont")

    @final
    def attempt(self) -> IO[R, E, Result[E, A]]:
        """
        Transform this computation that may fail into a computation
        that never fails but returns a Result[E,A].

        - If `self` successfully computes a, then `self.attempt()` successfully computes `Ok(a)`.
        - If `self` fails on error e, then `self.attempt()` successfully computes `Error(e)`.
        - If `self` fails on panic p, then `self.attempt()` successfully computes `Panic(p)`.

        Note that errors and panics stop the computation, unless a catch or
        recover reacts to such failures. But using map, flat_map, flatten and
        ap is sometimes easier than using catch and recover. attempt transforms
        a failed computation into a successful computation returning a failure,
        thus enabling you to use map, flat_map, ... to deal with errors.
        """
        return (
            self.map(Ok)
            .catch(lambda x: pure(Error(x)))
            .recover(lambda x: pure(Panic(x)))
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

        - The handler will be called on `Error(e)` if the computation fails with error e.
        - The handler will be called on `Panic(p)` if the computation fails with panic p.
        - The handler will never be called on `Ok(a)`.
        """
        return self.attempt().flat_map(
            lambda r: r.fold(
                pure,
                lambda e: handler(Error(e)),
                lambda p: handler(Panic(p)),
            )
        )


# IO PURE             0 VALUE
# IO MAP              1 MAIN      FUN
# IO FLATMAP          2 MAIN      HANDLER
# IO AP               3 FUN       ARG
# IO FLATTEN          4 TOWER
# IO DEFER            5 DEFERED
# IO DEFER_IO         6 DEFERED
# IO READ             7
# IO CONTRA_MAP_READ  8 FUN       MAIN
# IO RAISE            9 ERROR
# IO CATCH           10 MAIN      HANDLER
# IO MAP_ERROR       11 MAIN      FUN
# IO PANIC           12 EXCEPTION
# IO RECOVER         13 MAIN      HANDLER
# IO MAP_PANIC       14 MAIN      FUN


def pure(a: A) -> IO[R, E, A]:
    """
    An always successful computation returning a.
    """
    return IO(0, a)


def defer(deferred: Callable[[], A]) -> IO[R, E, A]:
    """
    Defer a computation.

    The result of the computation is the result of deferred() but
    this call is deferred until the IO is run.

    /!\\ **VERY IMPORTANT** /!\\

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
    return IO(5, deferred)


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
    return IO(6, deferred)


def read() -> IO[R, E, R]:
    """
    Read the context.

    To execute a computation `IO[R,E,A]`, you need to call the run method with
    some value r of type R: `io.run(r)`. the read() action returns the value r
    given to run.

    Please note that the contra_map_read method can transform this value r.
    """
    return IO(7, None)


def error(err: E) -> IO[R, E, A]:
    """
    Computation that fails on the error err.
    """
    return IO(9, err)


def panic(exception: Exception) -> IO[R, E, A]:
    """
    Computation that fails with the panic exception.
    """
    return IO(12, exception)


def from_result(r: Result[E, A]) -> IO[R, E, A]:
    """
    Computation that:
    - success if r is an `Ok`
    - fails with error e if r is `Error(e)`
    - fails with panic p if r is `Panic(p)`
    """
    return r.fold(pure, error, panic)


def safe(f: Callable[..., IO[R, E, A]]) -> Callable[..., IO[R, E, A]]:
    """
    Ensures a function retuning an IO never raise any exception but returns a
    panic instead.
    """

    def wrapper(*args, **kwargs):
        return defer_io(lambda: g(*args, **kwargs))

    return wrapper
