"""
Data structure representing a computation.
"""

from __future__ import annotations

import concurrent.futures as fut
import heapq
import threading
import time
from collections import abc
from concurrent.futures import Executor, ThreadPoolExecutor, Future
from queue import Queue
from typing import TypeVar, Generic, Callable, Any, List, Iterable

from typing_extensions import final

from raffiot import _MatchError
from raffiot.__internal import IOTag, ResultTag, ContTag, Scheduled
from raffiot.result import Result, Ok, Error, Panic

R = TypeVar("R")
E = TypeVar("E")
A = TypeVar("A")
X = TypeVar("X")
R2 = TypeVar("R2")
E2 = TypeVar("E2")
A2 = TypeVar("A2")

__all__ = [
    "IO",
    "pure",
    "defer",
    "defer_io",
    "read",
    "error",
    "panic",
    "from_result",
    "zip",
    "sequence",
    "yield_",
    "async_",
    "read_executor",
    "defer_read",
    "defer_read_io",
    "traverse",
    "parallel",
    "wait",
    "sleep_until",
    "sleep",
    "rec",
    "safe",
    "Monitor",
    "Fiber",
]


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

    # Error API

    def catch(self, handler: Callable[[E], IO[R, E, A]]) -> IO[R, E, A]:
        """
        React to errors (the except part of a try-except).

        On error, call the handler with the error.
        """
        return IO(IOTag.CATCH, (self, handler))

    def map_error(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        """
        Transform the stored error if the computation fails on an error.
        Do nothing otherwise.
        """
        return IO(IOTag.MAP_ERROR, (self, f))

    # Panic

    def recover(self, handler: Callable[[Exception], IO[R, E, A]]) -> IO[R, E, A]:
        """
        React to panics (the except part of a try-except).

        On panic, call the handler with the exception.
        """
        return IO(IOTag.RECOVER, (self, handler))

    def map_panic(self, f: Callable[[E], E2]) -> IO[R, E2, A]:
        """
        Transform the exception stored if the computation fails on a panic.
        Do nothing otherwise.
        """
        return IO(IOTag.MAP_PANIC, (self, f))

    def contra_map_executor(self, f: Callable[[Executor], Executor]) -> IO[R, E, A]:
        """
        Change the executor running this IO.
        :param f:
        :return:
        """
        return IO(IOTag.CONTRA_MAP_EXECUTOR, (f, self))

    def run(self, context: R, workers: int = None) -> Result[E, A]:
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
            return Fiber.run(self, context, executor)

    def run_async(self, context: R, executor: Executor) -> Future[Result[E, A]]:
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
        return Fiber.run_async(self, context, executor)

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
        - If `self` fails on error e, then `self.attempt()` successfully computes `Error(e)`.
        - If `self` fails on panic p, then `self.attempt()` successfully computes `Panic(p)`.

        Note that errors and panics stop the computation, unless a catch or
        recover reacts to such failures. But using map, flat_map, flatten and
        ap is sometimes easier than using catch and recover. attempt transforms
        a failed computation into a successful computation returning a failure,
        thus enabling you to use map, flat_map, ... to deal with errors.
        """
        return IO(IOTag.ATTEMPT, self)

    def finally_(self, io: IO[R, Any, Any]) -> IO[R, E, A]:
        """
        After having computed self, but before returning its result,
        execute the io computation.

        This is extremely useful when you need to perform an action,
        unconditionally, at the end of a computation, without changing
        its result, like releasing a resource.
        """
        return self.attempt().flat_map(lambda r: io.attempt().then(from_result(r)))

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
        if self.__tag == IOTag.LOCK:
            return f"Lock({self.__fields})"

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
    f: Callable[[R, Executor, Callable[[Result[E, A]], None]], None], *args, **kwargs
) -> IO[R, E, A]:
    """
    Perform an Asynchronous call. `f` is a function of the form:

    >>> from concurrent.futures import Executor, Future
    >>> def f(context: E,
    >>>       executor: Executor,
    >>>       callback: Callable[[Result[E,A]], None],
    >>>       *args,
    >>>       **kwargs) -> Future:
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
    return IO(IOTag.ASYNC, (f, args, kwargs))


def read_executor() -> IO[R, E, Executor]:
    """
    Return the executor running this IO.
    :return:
    """
    return IO(IOTag.EXECUTOR, None)


def defer_read(deferred: Callable[[], A], *args, **kwargs) -> IO[R, E, A]:
    """
    Like defer, but the function as first argument must be of the form:

    >>> def f(context:R, executor:Executor, *args, **kwargs) -> Result[E,A]:

    :param deferred: the function to defer. Its first and second positional
                     arguments must be the context and the executor
    :param args:
    :param kwargs:
    :return:
    """
    return IO(IOTag.DEFER_READ, (deferred, args, kwargs))


def defer_read_io(deferred: Callable[[], IO[R, E, A]], *args, **kwargs) -> IO[R, E, A]:
    """
    Like defer, but the function as first argument must be of the form:

    >>> def f(context:R, executor:Executor, *args, **kwargs) -> IO[R,E,A]:

    :param deferred: the function to defer. Its first and second positional
                     arguments must be the context and the executor
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


def wait(*l: Iterable[Fiber]) -> IO[R, E, List[Result[R, A]]]:
    """
    Wait until these Fibers finish. Return the list of Result
    in the same order.
    :param l:
    :return:
    """
    if len(l) == 1 and isinstance(l[0], abc.Iterable):
        return IO(IOTag.WAIT, list(l[0]))
    return IO(IOTag.WAIT, list(l))


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
    Ensures a function retuning an IO never raise any exception but returns a
    panic instead.
    """

    def wrapper(*args, **kwargs):
        return defer_io(lambda: f(*args, **kwargs))

    return wrapper


@final
class Monitor:
    """
    Used to know if there is still some futures running.
    Every future created when running fibers must be registered
    in the monitor.
    The monitor waits until there is no more future running.
    """

    __slots__ = [
        "__executor",
        "__queue_lock",
        "__queue",
        "__scheduled_lock",
        "__scheduled",
    ]

    def __init__(self, executor: Executor) -> None:
        self.__executor = executor
        self.__queue_lock = threading.Lock()
        self.__queue = []
        self.__scheduled_lock = threading.Lock()
        self.__scheduled = []

    def __async(self, fn, *args, **kwargs):
        future = fn(*args, **kwargs)
        if not isinstance(future, Future):
            raise Exception(f"Async call returned {future} which is not a Future.")
        with self.__queue_lock:
            self.__queue.append(future)

    def __wakeup(self, out):
        with self.__scheduled_lock:
            now = time.time()
            while self.__scheduled and self.__scheduled[0]._Scheduled__schedule <= now:
                fiber = heapq.heappop(self.__scheduled)._Scheduled__fiber
                out.append(fiber._Fiber__executor.submit(fiber._Fiber__step))

    def __resume(self, fiber) -> None:
        with self.__queue_lock:
            self.__queue.append(fiber._Fiber__executor.submit(fiber._Fiber__step))
            self.__wakeup(self.__queue)

    def __sleep(self, fiber, when: float) -> None:
        with self.__scheduled_lock:
            heapq.heappush(self.__scheduled, Scheduled(when, fiber))
            now = time.time()
            while self.__scheduled and self.__scheduled[0]._Scheduled__schedule <= now:
                fiber = heapq.heappop(self.__scheduled)._Scheduled__fiber
                with self.__queue_lock:
                    self.__queue.append(
                        fiber._Fiber__executor.submit(fiber._Fiber__step)
                    )

    def __wait_for_completion(self) -> None:
        ok = True
        while ok:
            with self.__queue_lock:
                futures = self.__queue
                self.__queue = []
            self.__wakeup(futures)
            fut.wait(futures)
            with self.__queue_lock:
                if self.__queue:
                    sleep_time = 0
                else:
                    with self.__scheduled_lock:
                        if self.__scheduled:
                            sleep_time = max(
                                0,
                                self.__scheduled[0]._Scheduled__schedule - time.time(),
                            )
                        else:
                            sleep_time = 0
                            ok = False
            time.sleep(sleep_time)


@final
class Fiber(Generic[R, E, A]):
    __slots__ = [
        "__io",
        "__context",
        "__cont",
        "__executor",
        "__monitor",
        "result",
        "__finish_lock",
        "finished",
        "__callbacks",
        "__waiting_lock",
        "__waiting",
        "__nb_waiting",
    ]

    def __init__(
        self, io: IO[R, E, A], context: R, executor: Executor, monitor: Monitor
    ) -> None:
        self.__io = io
        self.__context = context
        self.__cont = [ContTag.ID]
        self.__executor = executor
        self.__monitor = monitor
        self.result = None

        self.__finish_lock = threading.Lock()
        self.finished = False
        self.__callbacks = Queue()

        self.__waiting_lock = threading.Lock()
        self.__waiting = []
        self.__nb_waiting = 0

    def __add_callback(self, fiber: Fiber[Any, Any, Any], index: int) -> None:
        finished = False
        with self.__finish_lock:
            if self.finished:
                finished = True
            else:
                self.__callbacks.put((fiber, index))
        if finished:
            fiber.__run_callback(index, self.result)

    def __run_callback(self, index: int, res: Result[Any, Any]) -> None:
        resume = False
        with self.__waiting_lock:
            self.__waiting[index] = res
            self.__nb_waiting -= 1
            if self.__nb_waiting == 0:
                resume = True
        if resume:
            self.__io = IO(IOTag.PURE, self.__waiting)
            self.__waiting = None
            self.__monitor._Monitor__resume(self)

    @classmethod
    def run(cls, io: IO[R, E, A], context: R, executor: Executor) -> Result[E, A]:
        monitor = Monitor(executor)
        fiber = Fiber(io, context, executor, monitor)
        monitor._Monitor__resume(fiber)
        monitor._Monitor__wait_for_completion()
        return fiber.result

    @classmethod
    def run_async(
        cls, io: IO[R, E, A], context: R, executor: Executor
    ) -> Future[Result[E, A]]:
        return executor.submit(cls.run, io, context, executor)

    def __step(self) -> None:
        context = self.__context
        io = self.__io
        cont = self.__cont

        try:
            while True:
                # Eval IO
                while True:
                    tag = io._IO__tag
                    if tag == IOTag.PURE:
                        arg_tag = ResultTag.OK
                        arg_value = io._IO__fields
                        break
                    if tag == IOTag.MAP:
                        cont.append(io._IO__fields[1])
                        cont.append(ContTag.MAP)
                        io = io._IO__fields[0]
                        continue
                    if tag == IOTag.FLATMAP:
                        cont.append(io._IO__fields[1])
                        cont.append(context)
                        cont.append(ContTag.FLATMAP)
                        io = io._IO__fields[0]
                        continue
                    if tag == IOTag.SEQUENCE:
                        ios = io._IO__fields
                        size = len(ios)
                        if size > 1:
                            it = iter(ios)
                            io = next(it)
                            cont.append(it)
                            cont.append(size - 1)
                            cont.append(context)
                            cont.append(ContTag.SEQUENCE)
                            continue
                        if size == 1:
                            io = ios[0]
                            continue
                        arg_tag = ResultTag.OK
                        arg_value = None
                        break
                    if tag == IOTag.ZIP:
                        ios = iter(io._IO__fields)
                        try:
                            io = next(ios)
                        except StopIteration:
                            arg_tag = ResultTag.OK
                            arg_value = []
                            break
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                            break
                        cont.append([])
                        cont.append(ios)
                        cont.append(context)
                        cont.append(ContTag.ZIP)
                        continue
                    if tag == IOTag.FLATTEN:
                        cont.append(context)
                        cont.append(ContTag.FLATTEN)
                        io = io._IO__fields
                        continue
                    if tag == IOTag.DEFER:
                        try:
                            arg_tag = ResultTag.OK
                            arg_value = io._IO__fields[0](
                                *io._IO__fields[1], **io._IO__fields[2]
                            )
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                        break
                    if tag == IOTag.DEFER_IO:
                        try:
                            io = io._IO__fields[0](
                                *io._IO__fields[1], **io._IO__fields[2]
                            )
                            continue
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                            break
                    if tag == IOTag.ATTEMPT:
                        io = io._IO__fields
                        cont.append(ContTag.ATTEMPT)
                        continue
                    if tag == IOTag.READ:
                        arg_tag = ResultTag.OK
                        arg_value = context
                        break
                    if tag == IOTag.CONTRA_MAP_READ:
                        try:
                            context = io._IO__fields[0](context)
                            io = io._IO__fields[1]
                            continue
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                            break
                    if tag == IOTag.ERROR:
                        arg_tag = ResultTag.ERROR
                        arg_value = io._IO__fields
                        break
                    if tag == IOTag.CATCH:
                        cont.append(io._IO__fields[1])
                        cont.append(context)
                        cont.append(ContTag.CATCH)
                        io = io._IO__fields[0]
                        continue
                    if tag == IOTag.MAP_ERROR:
                        cont.append(io._IO__fields[1])
                        cont.append(ContTag.MAP_ERROR)
                        io = io._IO__fields[0]
                        continue
                    if tag == IOTag.PANIC:
                        arg_tag = ResultTag.PANIC
                        arg_value = io._IO__fields
                        break
                    if tag == IOTag.RECOVER:
                        cont.append(io._IO__fields[1])
                        cont.append(context)
                        cont.append(ContTag.RECOVER)
                        io = io._IO__fields[0]
                        continue
                    if tag == IOTag.MAP_PANIC:
                        cont.append(io._IO__fields[1])
                        cont.append(ContTag.MAP_PANIC)
                        io = io._IO__fields[0]
                        continue
                    if tag == IOTag.YIELD:
                        self.__io = IO(IOTag.PURE, None)
                        self.__context = context
                        self.__cont = cont
                        self.__monitor._Monitor__resume(self)
                        return
                    if tag == IOTag.ASYNC:

                        def callback(r):
                            self.__io = from_result(r)
                            self.__monitor._Monitor__resume(self)

                        self.__context = context
                        self.__cont = cont
                        try:
                            self.__monitor._Monitor__async(
                                io._IO__fields[0],
                                context,
                                self.__executor,
                                callback,
                                *io._IO__fields[1],
                                **io._IO__fields[2],
                            )
                            return
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                            break
                    if tag == IOTag.EXECUTOR:
                        arg_tag = ResultTag.OK
                        arg_value = self.__executor
                        break
                    if tag == IOTag.CONTRA_MAP_EXECUTOR:
                        try:
                            new_executor = io._IO__fields[0](self.__executor)
                            if not isinstance(new_executor, Executor):
                                raise Exception(f"{new_executor} is not an Executor!")
                            self.__executor = new_executor
                            io = io._IO__fields[1]
                            continue
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                            break
                    if tag == IOTag.DEFER_READ:
                        try:
                            res = io._IO__fields[0](
                                *(context, self.__executor, *io._IO__fields[1]),
                                **io._IO__fields[2],
                            )
                            if isinstance(res, Ok):
                                arg_tag = ResultTag.OK
                                arg_value = res.success
                                break
                            if isinstance(res, Error):
                                arg_tag = ResultTag.ERROR
                                arg_value = res.error
                                break
                            if isinstance(res, Panic):
                                arg_tag = ResultTag.PANIC
                                arg_value = res.exception
                                break
                            arg_tag = ResultTag.PANIC
                            arg_value = Panic(
                                _MatchError("{res} should be a Result in defer_read")
                            )
                            break
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                        break
                    if tag == IOTag.DEFER_READ_IO:
                        try:
                            io = io._IO__fields[0](
                                *(context, self.__executor, *io._IO__fields[1]),
                                **io._IO__fields[2],
                            )
                            continue
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                            break
                    if tag == IOTag.PARALLEL:
                        arg_value = []
                        for fio in io._IO__fields:
                            fiber = Fiber(fio, context, self.__executor, self.__monitor)
                            arg_value.append(fiber)
                            fiber.__monitor._Monitor__resume(fiber)
                        arg_tag = ResultTag.OK
                        break
                    if tag == IOTag.WAIT:
                        fibers = io._IO__fields
                        self.__waiting = [None for _ in fibers]
                        self.__nb_waiting = len(fibers)
                        self.__context = context
                        self.__cont = cont
                        all_finished = True
                        for index, fib in enumerate(fibers):
                            with fib.__finish_lock:
                                if fib.finished:
                                    with self.__waiting_lock:
                                        self.__waiting[index] = fib.result
                                        self.__nb_waiting -= 1
                                        if self.__nb_waiting == 0:
                                            all_finished = True
                                else:
                                    all_finished = False
                                    fib.__callbacks.put((self, index))
                        if all_finished:
                            arg_tag = ResultTag.OK
                            arg_value = self.__waiting
                            break
                        return
                    if tag == IOTag.SLEEP_UNTIL:
                        when = io._IO__fields
                        if when > time.time():
                            self.__io = IO(IOTag.PURE, None)
                            self.__context = context
                            self.__cont = cont
                            self.__monitor._Monitor__sleep(self, when)
                            return
                        arg_tag = ResultTag.OK
                        arg_value = None
                        break
                    if tag == IOTag.REC:
                        try:
                            io = io._IO__fields(io)
                            continue
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                            break
                    if tag == IOTag.LOCK:
                        lock = io._IO__fields
                        try:
                            with lock.lock:
                                if lock.acquire(self):
                                    arg_tag = ResultTag.OK
                                    arg_value = None
                                    break
                                else:
                                    self.__io = IO(IOTag.PURE, None)
                                    self.__context = context
                                    self.__cont = cont
                                    lock.waiting.put(self)
                                    return
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                            break
                    arg_tag = ResultTag.PANIC
                    arg_value = _MatchError(f"{io} should be an IO")
                    break

                # Eval Cont
                while True:
                    tag = cont.pop()
                    if tag == ContTag.MAP:
                        fun = cont.pop()
                        try:
                            if arg_tag == ResultTag.OK:
                                arg_value = fun(arg_value)
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                        continue
                    if tag == ContTag.FLATMAP:
                        context = cont.pop()
                        f = cont.pop()
                        try:
                            if arg_tag == ResultTag.OK:
                                io = f(arg_value)
                                break
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                        continue
                    if tag == ContTag.SEQUENCE:
                        if arg_tag == ResultTag.OK:
                            size = cont[-2]
                            if size > 1:
                                io = next(cont[-3])
                                cont[-2] -= 1
                                context = cont[-1]
                                cont.append(ContTag.SEQUENCE)
                                break
                            context = cont.pop()
                            cont.pop()
                            io = next(cont.pop())
                            break
                        # CLEANING CONT
                        cont.pop()  # SIZE
                        cont.pop()  # CONTEXT
                        cont.pop()  # IOS
                        continue
                    if tag == ContTag.ZIP:
                        if arg_tag == ResultTag.OK:
                            cont[-3].append(arg_value)  # RESULT LIST
                            try:
                                io = next(cont[-2])  # IOS
                            except StopIteration:
                                cont.pop()  # CONTEXT
                                cont.pop()  # IOS
                                arg_tag = ResultTag.OK
                                arg_value = cont.pop()
                                continue
                            except Exception as exception:
                                cont.pop()  # CONTEXT
                                cont.pop()  # IOS
                                cont.pop()  # RESULT LIST
                                arg_tag = ResultTag.PANIC
                                arg_value = exception
                                continue
                            context = cont[-1]
                            cont.append(ContTag.ZIP)
                            break
                        # CLEANING CONT
                        cont.pop()  # CONTEXT
                        cont.pop()  # IOS
                        cont.pop()  # RESULT LIST
                        continue
                    if tag == ContTag.FLATTEN:
                        context = cont.pop()
                        if arg_tag == ResultTag.OK:
                            io = arg_value
                            break
                        continue
                    if tag == ContTag.ATTEMPT:
                        if arg_tag == ResultTag.OK:
                            arg_value = Ok(arg_value)
                            continue
                        if arg_tag == ResultTag.ERROR:
                            arg_tag = ResultTag.OK
                            arg_value = Error(arg_value)
                            continue
                        if arg_tag == ResultTag.PANIC:
                            arg_tag = ResultTag.OK
                            arg_value = Panic(arg_value)
                            continue
                        arg_tag = ResultTag.OK
                        arg_value = Panic(_MatchError(f"Wrong result tag {arg_tag}"))
                        continue
                    if tag == ContTag.CATCH:
                        context = cont.pop()
                        handler = cont.pop()
                        try:
                            if arg_tag == ResultTag.ERROR:
                                io = handler(arg_value)
                                break
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                        continue
                    if tag == ContTag.MAP_ERROR:
                        fun = cont.pop()
                        try:
                            if arg_tag == ResultTag.ERROR:
                                arg_value = fun(arg_value)
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                        continue
                    if tag == ContTag.RECOVER:
                        context = cont.pop()
                        handler = cont.pop()
                        try:
                            if arg_tag == ResultTag.PANIC:
                                io = handler(arg_value)
                                break
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                        continue
                    if tag == ContTag.MAP_PANIC:
                        fun = cont.pop()
                        try:
                            if arg_tag == ResultTag.PANIC:
                                arg_value = fun(arg_value)
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                        continue
                    if tag == ContTag.ID:
                        if arg_tag == ResultTag.OK:
                            self.result = Ok(arg_value)
                        elif arg_tag == ResultTag.ERROR:
                            self.result = Error(arg_value)
                        elif arg_tag == ResultTag.PANIC:
                            self.result = Panic(arg_value)
                        else:
                            self.result = Panic(
                                _MatchError(f"Wrong result tag {arg_tag}")
                            )
                        with self.__finish_lock:
                            self.finished = True
                        while not self.__callbacks.empty():
                            fiber, index = self.__callbacks.get()
                            fiber.__run_callback(index, self.result)
                        return
                    arg_tag = ResultTag.PANIC
                    arg_value = Panic(_MatchError(f"Invalid cont {cont + [tag]}"))
        except Exception as exception:
            self.finished = True
            self.result = Panic(exception)
