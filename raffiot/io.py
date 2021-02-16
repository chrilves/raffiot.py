"""
Data structure representing a computation.
"""

from __future__ import annotations
from typing import TypeVar, Generic, Callable, Any, List, Iterable
from collections import abc
from typing_extensions import final
from raffiot import result, _MatchError
from raffiot.result import Result, Ok, Error, Panic
from concurrent.futures import Executor, ThreadPoolExecutor, wait
from raffiot.__internal import *

R = TypeVar("R")
E = TypeVar("E")
A = TypeVar("A")
X = TypeVar("X")
R2 = TypeVar("R2")
E2 = TypeVar("E2")
A2 = TypeVar("A2")


@final
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
        return IO(IOTag.MAP, (self, f))

    @final
    def flat_map(self, f: Callable[[A], IO[R, E, A2]]) -> IO[R, E, A2]:
        """
        Chain two computations.
        The result of the first one (self) can be used in the second (f).
        """
        return IO(IOTag.FLATMAP, (self, f))

    @final
    def then(self, *others: IO[R, E, A2]) -> IO[R, E, A2]:
        """
        Chain two computations.
        The result of the first one (self) is dropped.
        """
        if len(others) == 1 and isinstance(others[0], abc.Iterable):
            return IO(IOTag.SEQUENCE, iter((self, *others[0])))
        return IO(IOTag.SEQUENCE, iter((self, *others)))

    @final
    def zip(self: IO[R, E, A], *others: IO[R, E, X]) -> IO[R, E, Iterable[A]]:
        """
        Pack a list of IO (including self) into an IO computing the list
        of all values.

        If one IO fails, the whole computation fails.
        """
        if len(others) == 1 and isinstance(others[0], abc.Iterable):
            return IO(IOTag.ZIP, iter((self, *others[0])))
        return IO(IOTag.ZIP, iter((self, *others)))

    @final
    def flatten(self):
        """
        Concatenation function on IO
        """
        if self.__tag == 0:
            return self.__fields
        return IO(IOTag.FLATTEN, self)

    # Reader API

    @final
    def contra_map_read(self, f: Callable[[R2], R]) -> IO[R2, E, A]:
        """
        Transform the context with f.
        Note that f is not from R to R2 but from R2 to R!
        """
        return IO(IOTag.CONTRA_MAP_READ, (f, self))

    # Error API

    @final
    def catch(self, handler: Callable[[E], IO[R, E, A]]) -> IO[R, E, A]:
        """
        React to errors (the except part of a try-except).

        On error, call the handler with the error.
        """
        return IO(IOTag.CATCH, (self, handler))

    @final
    def map_error(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        """
        Transform the stored error if the computation fails on an error.
        Do nothing otherwise.
        """
        return IO(IOTag.MAP_ERROR, (self, f))

    # Panic

    @final
    def recover(self, handler: Callable[[Exception], IO[R, E, A]]) -> IO[R, E, A]:
        """
        React to panics (the except part of a try-except).

        On panic, call the handler with the exception.
        """
        return IO(IOTag.RECOVER, (self, handler))

    @final
    def map_panic(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        """
        Transform the exception stored if the computation fails on a panic.
        Do nothing otherwise.
        """
        return IO(IOTag.MAP_PANIC, (self, f))

    @final
    def contra_map_executor(self, f: Callable[[Executor], Executor]) -> IO[R, E, A]:
        """
        Change the executor running this IO.
        :param f:
        :return:
        """
        return IO(IOTag.CONTRA_MAP_EXECUTOR, (f, self))

    @final
    def run(self, context: R, workers: int = 1) -> Result[E, A]:
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
        with ThreadPoolExecutor(max_workers=workers) as executor:
            fiber = Fiber(self, context, executor)
            fiber.schedule()
            while fiber.status != FiberStatus.FINISHED:
                fiber.future.result()
        return fiber.result

    @final
    def ap(self: IO[R, E, Callable[[X], A]], *arg: IO[R, E, X]) -> IO[R, E, A]:
        """
        Noting functions from [X1,...,XN] to A: `[X1, ..., Xn] -> A`.

        If self computes a function `f: [X1,...,XN] -> A`
        and arg computes a value `x1: X1`,...,`xn: Xn`
        then self.ap(arg) computes `f(x1,...,xn): A`.
        """
        return self.zip(*arg).map(lambda l: l[0](*l[1:]))

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
            lambda r: r.unsafe_fold(
                pure,
                lambda e: handler(Error(e)),
                lambda p: handler(Panic(p)),
            )
        )

    @final
    def __str__(self) -> str:
        if self.__tag == IOTag.PURE:
            return f"Pure({self.__fields})"
        if self.__tag == IOTag.MAP:
            return f"Map({self.__fields})"
        if self.__tag == IOTag.FLATMAP:
            return f"FlatMap({self.__fields})"
        if self.__tag == IOTag.SEQUENCE:
            return f"Sequence({self.__fields})"
        if self.__tag == IOTag.ZIP:
            return f"Zip({self.__fields})"
        if self.__tag == IOTag.FLATTEN:
            return f"Flatten({self.__fields})"
        if self.__tag == IOTag.DEFER:
            return f"Defer({self.__fields})"
        if self.__tag == IOTag.DEFER_IO:
            return f"DeferIO({self.__fields})"
        if self.__tag == IOTag.READ:
            return f"Read({self.__fields})"
        if self.__tag == IOTag.CONTRA_MAP_READ:
            return f"ContraMapRead({self.__fields})"
        if self.__tag == IOTag.ERROR:
            return f"Error({self.__fields})"
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
        if self.__tag == IOTag.EXECUTOR:
            return f"Executor({self.__fields})"
        if self.__tag == IOTag.CONTRA_MAP_EXECUTOR:
            return f"ContraMapExecutor({self.__fields})"

    @final
    def __repr__(self):
        return str(self)


def pure(a: A) -> IO[R, E, A]:
    """
    An always successful computation returning a.
    """
    return IO(IOTag.PURE, a)


def defer(deferred: Callable[[], A], *args, **kwargs) -> IO[R, E, A]:
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


def defer_io(deferred: Callable[[], IO[R, E, A]], *args, **kwargs) -> IO[R, E, A]:
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
    return IO(IOTag.DEFER_IO, (deferred, args, kwargs))


def read() -> IO[R, E, R]:
    """
    Read the context.

    To execute a computation `IO[R,E,A]`, you need to call the run method with
    some value r of type R: `io.run(r)`. the read() action returns the value r
    given to run.

    Please note that the contra_map_read method can transform this value r.
    """
    return IO(IOTag.READ, None)


def error(err: E) -> IO[R, E, A]:
    """
    Computation that fails on the error err.
    """
    return IO(IOTag.ERROR, err)


def panic(exception: Exception) -> IO[R, E, A]:
    """
    Computation that fails with the panic exception.
    """
    return IO(IOTag.PANIC, exception)


def from_result(r: Result[E, A]) -> IO[R, E, A]:
    """
    Computation that:
    - success if r is an `Ok`
    - fails with error e if r is `Error(e)`
    - fails with panic p if r is `Panic(p)`
    """
    if isinstance(r, Ok):
        return pure(r.success)
    if isinstance(r, Error):
        return error(r.error)
    if isinstance(r, Panic):
        return panic(r.exception)
    return panic(_MatchError(f"{r} should be a Result"))


def zip(*l: Iterable[IO[R, E, A]]) -> IO[R, E, Iterable[A]]:
    """
    Transform a list of IO into an IO of list.
    :param l:
    :return:
    """
    if len(l) == 1 and isinstance(l[0], abc.Iterable):
        return IO(IOTag.ZIP, iter(l[0]))
    return IO(IOTag.ZIP, iter(l))


def sequence(*l: Iterable[IO[R, E, A]]) -> IO[R, E, Iterable[A]]:
    """
    Run these ios in sequence
    :param l:
    :return:
    """
    if len(l) == 1 and isinstance(l[0], abc.Iterable):
        return IO(IOTag.SEQUENCE, iter(l[0]))
    return IO(IOTag.SEQUENCE, iter(l))


def yield_() -> IO[R, E, None]:
    """
    IO implement cooperative concurrency. It means an IO has to explicitly
    make a break for other concurrent tasks to have a chance to progress.
    This is what `yeild_()` does, it forces the IO to make a break, letting
    other tasks be run on the executor until the IO start progressing again.
    :return:
    """
    return IO(IOTag.YIELD, None)


def async_(
    f: Callable[[R, Executor, Callable[[Result[E, A]], None]], None]
) -> IO[R, E, A]:
    """
    Perform an Asynchronous call. `f` is a function of the form:

    >>> from concurrent.futures import Executor, Future
    >>> def f(context: E,
    >>>       executor: Executor,
    >>>       callback: Callable[[Result[E,A]], None]) -> Future:
    >>>     ...

    - `f` **MUST** return a `Future`.
    - `context` is the context of the IO, usually the one passed to `run`
       if not changed by `contra_map_read`.
    - `executor` is the `Executor` where the IO is run, usually the one
       passed to run if not changed by `contra_map_executor`.
    - `callback` **MUST ALWAYS BE CALLED EXACTLY ONCE**.
       Until `callback` is called, the IO will be suspended waiting for the
       asynchronous call to complete.
       When `callback` is called, the IO is resumed.
       The value passed to `callback` must be the result of the asynchonous call:

        - `Ok(value)` if the call was successful and returned `value`.
        - `Error(error)` if the call failed on error `error`.
        - `Panic(exception)` if the failed unexpectedly on exception `exception`.

    For example:

    >>> from raffiot.result import Ok
    >>> from raffiot.io import async_
    >>> def f(context, executor, callback):
    >>>     def h():
    >>>         print("In the asynchronous call, returning 2.")
    >>>         callback(Ok(2))
    >>>     return executor.submit(h)
    >>> io = async_(f)

    :param f:
    :return:
    """
    return IO(IOTag.ASYNC, f)


def read_executor() -> IO[R, E, Executor]:
    """
    Return the executor running this IO.
    :return:
    """
    return IO(IOTag.EXECUTOR, None)


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


def run_all(l: Iterable[IO[R, E, A]]) -> IO[R, E, None]:
    """
    Ensures that all the IO are executed (in the iterable order!)

    If at least one panics, it panics.
    If no IO panic but at least one raise an error, it raise one of the error
    (the first one in the iterable order).
    If there is neither panics not error, it succeed and return None.
    :param l: the iterable of all IOs to run.
    :return:
    """

    def f(results):
        level = 0
        ret = Ok(None)
        for r in results:
            if r.is_error() and level < 1:
                level = 1
                ret = r
            elif r.is_panic() and level < 2:
                return r
        return ret

    return pure(f).ap([x.attempt() for x in l])


def safe(f: Callable[..., IO[R, E, A]]) -> Callable[..., IO[R, E, A]]:
    """
    Ensures a function retuning an IO never raise any exception but returns a
    panic instead.
    """

    def wrapper(*args, **kwargs):
        return defer_io(lambda: f(*args, **kwargs))

    return wrapper
