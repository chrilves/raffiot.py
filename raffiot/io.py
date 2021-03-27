"""
Data structure representing a computation.
"""

from __future__ import annotations

import time
from collections import abc
from typing import TypeVar, Generic, Callable, Any, List, Iterable

from typing_extensions import final

from raffiot._internal import IOTag
from raffiot.result import Result, Ok, Errors, Panic
from raffiot.utils import MatchError
from raffiot import result

__all__ = [
    "Fiber",
    "IO",
    "pure",
    "defer",
    "defer_io",
    "read",
    "error",
    "errors",
    "panic",
    "from_result",
    "zip",
    "sequence",
    "yield_",
    "async_",
    "defer_read",
    "defer_read_io",
    "traverse",
    "parallel",
    "wait",
    "zip_par",
    "sleep_until",
    "sleep",
    "rec",
    "safe",
]


R = TypeVar("R")
E = TypeVar("E")
A = TypeVar("A")
X = TypeVar("X")
R2 = TypeVar("R2")
E2 = TypeVar("E2")
A2 = TypeVar("A2")


@final
class Fiber(Generic[R, E, A]):
    pass


@final
class IO(Generic[R, E, A]):
    """
    Represent a computation that computes a value of type A,
    may fail with an errors (expected failure) of type E and have access
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

    def __init__(self, __tag, __fields):
        self.__tag = __tag
        self.__fields = __fields

    def map(self, f: Callable[[A], A2]) -> IO[R, E, A2]:
        """
        Transform the computed value with f if the computation is successful.
        Do nothing otherwise.
        """
        return IO(IOTag.MAP, (self, f))

    def flat_map(self, f: Callable[[A], IO[R, E, A2]]) -> IO[R, E, A2]:
        """
        Chain two computations.
        The result of the first one (self) can be used in the second (f).
        """
        return IO(IOTag.FLATMAP, (self, f))

    def then(self, *others: IO[R, E, A2]) -> IO[R, E, A2]:
        """
        Chain two computations.
        The result of the first one (self) is dropped.
        """
        if len(others) == 1 and isinstance(others[0], abc.Iterable):
            return IO(IOTag.SEQUENCE, list((self, *others[0])))
        return IO(IOTag.SEQUENCE, list((self, *others)))

    def zip(self: IO[R, E, A], *others: IO[R, E, X]) -> IO[R, E, Iterable[A]]:
        """
        Pack a list of IO (including self) into an IO computing the list
        of all values.

        If one IO fails, the whole computation fails.
        """
        if len(others) == 1 and isinstance(others[0], abc.Iterable):
            return IO(IOTag.ZIP, list((self, *others[0])))
        return IO(IOTag.ZIP, list((self, *others)))

    def zip_par(self: IO[R, E, A], *others: IO[R, E, X]) -> IO[R, E, Iterable[A]]:
        """
        Pack a list of IO (including self) into an IO computing the list
        of all values in parallel.

        If one IO fails, the whole computation fails.
        """
        return zip_par(self, *others)

    def parallel(self: IO[R, E, A], *others: IO[R, E, X]) -> IO[R, E, Iterable[Fiber]]:
        """
        Run all these IO (including self) in parallel.
        Return the list of fibers, in the same order.

        Each Fiber represent a parallel computation. Call

        >>> wait([fiber1, fiber2, ...])

        to wait until the computations of fiber1, fiber2, etc are done.
        :param l: the list of IO to run in parallel.
        :return: the same list where each IO has been replaced by its Fiber
        """
        if len(others) == 1 and isinstance(others[0], abc.Iterable):
            return IO(IOTag.PARALLEL, list((self, *others[0])))
        return IO(IOTag.PARALLEL, list((self, *others)))

    def flatten(self):
        """
        Concatenation function on IO
        """
        if self.__tag == 0:
            return self.__fields
        return IO(IOTag.FLATTEN, self)

    # Reader API

    def contra_map_read(self, f: Callable[[R2], R]) -> IO[R2, E, A]:
        """
        Transform the context with f.
        Note that f is not from R to R2 but from R2 to R!
        """
        return IO(IOTag.CONTRA_MAP_READ, (f, self))

    # Errors API

    def catch(self, handler: Callable[[List[E]], IO[R, E, A]]) -> IO[R, E, A]:
        """
        React to errors (the except part of a try-except).

        On errors, call the handler with the errors.
        """
        return IO(IOTag.CATCH, (self, handler))

    def map_error(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        """
        Transform the stored errors if the computation fails on an errors.
        Do nothing otherwise.
        """
        return IO(IOTag.MAP_ERROR, (self, f))

    # Panic

    def recover(
        self, handler: Callable[[List[Exception], List[E]], IO[R, E, A]]
    ) -> IO[R, E, A]:
        """
        React to panics (the except part of a try-except).

        On panic, call the handler with the exceptions.
        """
        return IO(IOTag.RECOVER, (self, handler))

    def map_panic(self, f: Callable[[Exception], Exception]) -> IO[R, E, A]:
        """
        Transform the exceptions stored if the computation fails on a panic.
        Do nothing otherwise.
        """
        return IO(IOTag.MAP_PANIC, (self, f))

    def run(self, context: R, pool_size: int = 1, nighttime=0.01) -> Result[E, A]:
        """
        Run the computation.

        Note that a IO is a data structure, no action is performed until you
        call run. You may view an IO value as a function declaration.
        Declaring a function does not execute its body. Only calling the
        function does. Likewise, declaring an IO does not execute its content,
        only running the IO does.

        Note that the return value is a  `Result[E,A]`.
        No exceptions will be raised by run (unless there is a bug), run will
        returns a panic instead!
        """
        from raffiot._runtime import SharedState

        return SharedState(pool_size, nighttime).run(self, context)

    def ap(self: IO[R, E, Callable[[X], A]], *arg: IO[R, E, X]) -> IO[R, E, A]:
        """
        Noting functions from [X1,...,XN] to A: `[X1, ..., Xn] -> A`.

        If self computes a function `f: [X1,...,XN] -> A`
        and arg computes a value `x1: X1`,...,`xn: Xn`
        then self.ap(arg) computes `f(x1,...,xn): A`.
        """
        return self.zip(*arg).map(lambda l: l[0](*l[1:]))

    def attempt(self) -> IO[R, E, Result[E, A]]:
        """
        Transform this computation that may fail into a computation
        that never fails but returns a Result[E,A].

        - If `self` successfully computes a, then `self.attempt()` successfully computes `Ok(a)`.
        - If `self` fails on errors e, then `self.attempt()` successfully computes `Errors(e)`.
        - If `self` fails on panic p, then `self.attempt()` successfully computes `Panic(p)`.

        Note that errors and panics stop the computation, unless a catch or
        recover reacts to such failures. But using map, flat_map, flatten and
        ap is sometimes easier than using catch and recover. attempt transforms
        a failed computation into a successful computation returning a failure,
        thus enabling you to use map, flat_map, ... to deal with errors.
        """
        return IO(IOTag.ATTEMPT, self)

    def finally_(self, after: Callable[[Result[E, A]], IO[R, E, Any]]) -> IO[R, E, A]:
        """
        After having computed self, but before returning its result,
        execute the io computation.

        This is extremely useful when you need to perform an action,
        unconditionally, at the end of a computation, without changing
        its result, like releasing a resource.
        """
        return self.attempt().flat_map(
            lambda r1: after(r1)
            .attempt()
            .flat_map(lambda r2: from_result(result.sequence(r2, r1)))
        )

    def on_failure(
        self, handler: Callable[[Result[E, Any]], IO[R, E, A]]
    ) -> IO[R, E, A]:
        """
        Combined form of catch and recover.
        React to any failure of the computation.
        Do nothing if the computation is successful.

        - The handler will be called on `Errors(e)` if the computation fails with errors e.
        - The handler will be called on `Panic(p)` if the computation fails with panic p.
        - The handler will never be called on `Ok(a)`.
        """

        def g(r: Result[E, A]) -> IO[R, E, A]:
            if isinstance(r, Ok):
                return IO(IOTag.PURE, r.success)
            return handler(r)

        return self.attempt().flat_map(g)

    def then_keep(self, *args: IO[R, E, A]) -> IO[R, E, A]:
        """
        Equivalent to `then(*args) but, on success, the computed value
        is self's one.

        Used to execute some IO after a successful computation without
        changing its value.
        :param args:
        :return:
        """
        return self.flat_map(lambda a: sequence(args).then(pure(a)))

    def __str__(self) -> str:
        if self.__tag == IOTag.PURE:
            return f"Pure({self.__fields})"
        if self.__tag == IOTag.MAP:
            return f"Map({self.__fields})"
        if self.__tag == IOTag.FLATMAP:
            return f"FlatMap({self.__fields})"
        if self.__tag == IOTag.FLATTEN:
            return f"Flatten({self.__fields})"
        if self.__tag == IOTag.SEQUENCE:
            return f"Sequence({self.__fields})"
        if self.__tag == IOTag.ZIP:
            return f"Zip({self.__fields})"
        if self.__tag == IOTag.DEFER:
            return f"Defer({self.__fields})"
        if self.__tag == IOTag.DEFER_IO:
            return f"DeferIO({self.__fields})"
        if self.__tag == IOTag.ATTEMPT:
            return f"Attempt({self.__fields})"
        if self.__tag == IOTag.READ:
            return f"Read({self.__fields})"
        if self.__tag == IOTag.CONTRA_MAP_READ:
            return f"ContraMapRead({self.__fields})"
        if self.__tag == IOTag.ERRORS:
            return f"Errors({self.__fields})"
        if self.__tag == IOTag.CATCH:
            return f"Catch({self.__fields})"
        if self.__tag == IOTag.MAP_ERROR:
            return f"MapError({self.__fields})"
        if self.__tag == IOTag.PANIC:
            return f"Panic({self.__fields})"
        if self.__tag == IOTag.RECOVER:
            return f"Recover({self.__fields})"
        if self.__tag == IOTag.MAP_PANIC:
            return f"MapPanic({self.__fields})"
        if self.__tag == IOTag.YIELD:
            return f"Yield({self.__fields})"
        if self.__tag == IOTag.ASYNC:
            return f"Async({self.__fields})"
        if self.__tag == IOTag.DEFER_READ:
            return f"DeferRead({self.__fields})"
        if self.__tag == IOTag.DEFER_READ_IO:
            return f"DeferReadIO({self.__fields})"
        if self.__tag == IOTag.PARALLEL:
            return f"Parallel({self.__fields})"
        if self.__tag == IOTag.WAIT:
            return f"Wait({self.__fields})"
        if self.__tag == IOTag.SLEEP_UNTIL:
            return f"SleepUntil({self.__fields})"
        if self.__tag == IOTag.REC:
            return f"Rec({self.__fields})"
        if self.__tag == IOTag.ACQUIRE:
            return f"Acquire({self.__fields})"
        if self.__tag == IOTag.RELEASE:
            return f"Release({self.__fields})"

    def __repr__(self):
        return str(self)


def pure(a: A) -> IO[R, E, A]:
    """
    An always successful computation returning a.
    """
    return IO(IOTag.PURE, a)


def defer(deferred: Callable[..., A], *args, **kwargs) -> IO[R, E, A]:
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
    return IO(IOTag.DEFER, (deferred, args, kwargs))


def defer_io(deferred: Callable[..., IO[R, E, A]], *args, **kwargs) -> IO[R, E, A]:
    """
    Make a function that returns an IO, an IO itself.

    This is extremely useful with recursive function that would normally blow
    the stack (raise a stack overflow exceptions). Deferring recursive calls
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
    return IO(IOTag.DEFER_IO, (deferred, args, kwargs))


read: IO[R, E, R] = IO(IOTag.READ, None)
"""
Read the context.

To execute a computation `IO[R,E,A]`, you need to call the run method with
some value r of type R: `io.run(r)`. the `read` action returns the value r
given to run.

Please note that the contra_map_read method can transform this value r.
"""


def error(err: E) -> IO[R, E, A]:
    """
    Computation that fails on the error err.
    """
    return IO(IOTag.ERRORS, [err])


def errors(*errs: E) -> IO[R, E, A]:
    """
    Computation that fails on the errors errs.
    """
    if (
        len(errs) == 1
        and isinstance(errs[0], abc.Iterable)
        and not isinstance(errs[0], str)
    ):
        return IO(IOTag.ERRORS, list(errs[0]))
    return IO(IOTag.ERRORS, list(errs))


def panic(*exceptions: Exception, errors: List[E] = None) -> IO[R, E, A]:
    """
    Computation that fails with the panic exceptions.
    """
    if len(exceptions) == 1 and isinstance(exceptions[0], abc.Iterable):
        return IO(IOTag.PANIC, (list(exceptions[0]), list(errors) if errors else []))
    return IO(IOTag.PANIC, (list(exceptions), list(errors) if errors else []))


def from_result(r: Result[E, A]) -> IO[R, E, A]:
    """
    Computation that:
    - success if r is an `Ok`
    - fails with errors e if r is `Errors(e)`
    - fails with panic p if r is `Panic(p)`
    """
    if isinstance(r, Ok):
        return pure(r.success)
    if isinstance(r, Errors):
        return errors(r.errors)
    if isinstance(r, Panic):
        return panic(r.exceptions, errors=r.errors)
    return panic(MatchError(f"{r} should be a Result"))


def zip(*l: Iterable[IO[R, E, A]]) -> IO[R, E, Iterable[A]]:
    """
    Transform a list of IO into an IO of list.
    :param l:
    :return:
    """
    if len(l) == 1 and isinstance(l[0], abc.Iterable):
        return IO(IOTag.ZIP, list(l[0]))
    return IO(IOTag.ZIP, list(l))


def sequence(*l: Iterable[IO[R, E, A]]) -> IO[R, E, Iterable[A]]:
    """
    Run these ios in sequence
    :param l:
    :return:
    """
    if len(l) == 1 and isinstance(l[0], abc.Iterable):
        return IO(IOTag.SEQUENCE, list(l[0]))
    return IO(IOTag.SEQUENCE, list(l))


yield_: IO[R, E, None] = IO(IOTag.YIELD, None)
"""
IO implement cooperative concurrency. It means an IO has to explicitly
make a break for other concurrent tasks to have a chance to progress.
This is what `yeild_()` does, it forces the IO to make a break, letting
other tasks be run on the thread pool until the IO start progressing again.
:return:
"""


def async_(
    f: Callable[[R, Callable[[Result[E, A]], None]], None], *args, **kwargs
) -> IO[R, E, A]:
    """
    Perform an Asynchronous call. `f` is a function of the form:

    >>> def f(context: E,
    >>>       callback: Callable[[Result[E,A]], None],
    >>>       *args,
    >>>       **kwargs) -> None:
    >>>     ...

    - `context` is the context of the IO, usually the one passed to `run`
       if not changed by `contra_map_read`.
    - `callback` **MUST ALWAYS BE CALLED EXACTLY ONCE**.
       Until `callback` is called, the IO will be suspended waiting for the
       asynchronous call to complete.
       When `callback` is called, the IO is resumed.
       The value passed to `callback` must be the result of the asynchonous call:

        - `Ok(value)` if the call was successful and returned `value`.
        - `Errors(errors)` if the call failed on errors `errors`.
        - `Panic(exceptions)` if the failed unexpectedly on exceptions `exceptions`.

    For example:

    >>> from raffiot.result import Ok
    >>> from raffiot.io import async_
    >>> def f(context, callback):
    >>>     print("In the asynchronous call, returning 2.")
    >>>     callback(Ok(2))
    >>>
    >>> io = async_(f)

    :param f:
    :return:
    """
    return IO(IOTag.ASYNC, (f, args, kwargs))


def defer_read(deferred: Callable[[], A], *args, **kwargs) -> IO[R, E, A]:
    """
    Like defer, but the function as first argument must be of the form:

    >>> def f(context:R, *args, **kwargs) -> Result[E,A]:

    :param deferred: the function to defer. Its first positional
                     arguments must be the context.
    :param args:
    :param kwargs:
    :return:
    """
    return IO(IOTag.DEFER_READ, (deferred, args, kwargs))


def defer_read_io(deferred: Callable[[], IO[R, E, A]], *args, **kwargs) -> IO[R, E, A]:
    """
    Like defer, but the function as first argument must be of the form:

    >>> def f(context:R, *args, **kwargs) -> IO[R,E,A]:

    :param deferred: the function to defer. Its first positional
                     arguments must be the context.
    :param args:
    :param kwargs:
    :return:
    """
    return IO(IOTag.DEFER_READ_IO, (deferred, args, kwargs))


def traverse(l: Iterable[A], f: Callable[[A], IO[R, E, A2]]) -> IO[R, E, Iterable[A2]]:
    """
    Apply the function `f` to every element of the iterable.
    The resulting IO computes the list of results.

    This function is essentially like map, but f returns IO[R,E,A2] instead of A2.

    :param l: the elements to apply to f
    :param f: the function for each element.
    :return:
    """
    return zip([defer_io(f, a) for a in l])


def parallel(*l: Iterable[IO[R, E, A]]) -> IO[E, E, Iterable[Fiber[R, E, A]]]:
    """
    Run all these IO in parallel.
    Return the list of fibers, in the same order.

    Each Fiber represent a parallel computation. Call

    >>> wait([fiber1, fiber2, ...])

    to wait until the computations of fiber1, fiber2, etc are done.
    :param l: the list of IO to run in parallel.
    :return: the same list where each IO has been replaced by its Fiber
    """
    if len(l) == 1 and isinstance(l[0], abc.Iterable):
        return IO(IOTag.PARALLEL, list(l[0]))
    return IO(IOTag.PARALLEL, list(l))


def wait(*l: Iterable[Fiber[Any, Any, Any]]) -> IO[R, E, List[Result[R, A]]]:
    """
    Wait until these Fibers finish. Return the list of Result
    in the same order.
    :param l:
    :return:
    """
    if len(l) == 1 and isinstance(l[0], abc.Iterable):
        return IO(IOTag.WAIT, list(l[0]))
    return IO(IOTag.WAIT, list(l))


def zip_par(*others: IO[R, E, X]) -> IO[R, E, List[X]]:
    """
    Run these IO in parallel, wait for them to finish, and merge the results.

    :param others:
    :return:
    """
    if len(others) == 1 and isinstance(others[0], abc.Iterable):
        args = others[0]
    else:
        args = others
    return (
        parallel(args).flat_map(wait).flat_map(lambda rs: from_result(result.zip(rs)))
    )


def sleep_until(epoch_in_seconds: float) -> IO[R, E, None]:
    """
    Pause the computation until the epoch is reached. The epoch
    is the number returned by `time.time`.

    Note that the computation may be awaken any time after the
    specified epoch.
    :param epoch_in_seconds:
    :return:
    """
    return IO(IOTag.SLEEP_UNTIL, epoch_in_seconds)


def sleep(seconds: float) -> IO[R, E, None]:
    """
    Pause the computation for this amount of seconds.

    Note that the computation may paused for longer.
    :param seconds: the minimum number of seconds to sleep (may be longer)
    :return:
    """
    return defer(time.time).flat_map(lambda t: sleep_until(t + seconds))


def rec(f: Callable[[IO[R, E, A]], IO[R, E, A]]) -> IO[R, E, A]:
    return IO(IOTag.REC, f)


def safe(f: Callable[..., IO[R, E, A]]) -> Callable[..., IO[R, E, A]]:
    """
    Ensures a function retuning an IO never raise any exceptions but returns a
    panic instead.
    """

    def wrapper(*args, **kwargs):
        return defer_io(lambda: f(*args, **kwargs))

    return wrapper
