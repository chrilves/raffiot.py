"""
Resource management module.
Ensure that create resources are always nicely released after use.
"""

from __future__ import annotations
from typing import TypeVar, Generic, Callable, Any, Tuple, List, Iterable
from collections import abc
from typing_extensions import final
from dataclasses import dataclass
from raffiot import result, io, _MatchError
from raffiot.io import IO
from raffiot.result import Result, Ok, Error, Panic
from concurrent.futures import Executor

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
    """
    Essentially an IO-powered data structure that produces resources of type A,
    can fail with errors of type E and read a context of type R.
    """

    create: IO[R, E, Tuple[A, IO[R, Any, Any]]]
    """
    IO to create one resource along with the IO for releasing it.
    
    On success, this IO must produce a `Tuple[A, IO[R,Any,Any]`:
        - The first value of the tuple, of type `A`, is the created resource.
        - The second value of the tuple, of type `IO[R,Any,Any]`, is the IO that
            release the first value.
    
    For example:
        
        >>> Resource(io.defer(lambda: open("file")).map(
        >>>     lambda a: (a, io.defer(a.close))))
    """

    @final
    def use(self, fun: Callable[[A], IO[R, E, X]]) -> IO[R, E, X]:
        """
        Create a resource a:A and use it in fun.

        Once created, the resource a:A is guaranteed to be released (by running
        its releasing IO). The return value if the result of fun(a).

        This is the only way to use a resource.
        """

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
        """
        Transform the created resource with f if the creation is successful.
        Do nothing otherwise.
        """

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
        """
        Chain two Resource.
        The resource created by the first one (self) can be used to create the second (f).
        """

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
    def then(self, rs: Resource[R, E, A2]) -> Resource[R, E, A2]:
        """
        Chain two Resource.
        The resource created by the first one (self) is dropped.
        """
        return self.flat_map(lambda _: rs)

    @final
    def zip(self: Resource[R, E, A], *rs: Resource[R, E, A]) -> Resource[R, E, List[A]]:
        """
        Pack a list of resources (including self) into a Resource creating the
        list of all resources.

        If one resource creation fails, the whole creation fails (opened resources
        are released then).
        """
        return zip((self, *rs))

    @final
    def ap(
        self: Resource[R, E, Callable[[X], A]], *arg: Resource[R, E, X]
    ) -> Resource[R, E, A]:
        """
        Noting functions from [X1,...,XN] to A: `[X1, ..., Xn] -> A`.

        If self computes a function `f: [X1,...,XN] -> A`
        and arg computes a value `x1: X1`,...,`xn: Xn`
        then self.ap(arg) computes `f(x1,...,xn): A`.
        """
        return self.zip(*arg).map(lambda l: l[0](*l[1:]))

    @final
    def flatten(self: Resource[R, E, Resource[R, E, A]]) -> Resource[R, E, A]:
        """
        Concatenation function on Resource
        """
        return self.flat_map(lambda x: x)

    # Reader API

    @final
    def contra_map_read(self, f: Callable[[R2], R]) -> Resource[R2, E, A]:
        """
        Transform the context with f.
        Note that f is not from R to R2 but from R2 to R!
        """
        return Resource(
            self.create.contra_map_read(f).map(
                lambda x: (x[0], x[1].contra_map_read(f))
            )
        )

    # Error API

    @final
    def catch(self, handler: Callable[[E], Resource[R, E, A]]) -> Resource[R, E, A]:
        """
        React to errors (the except part of a try-except).

        On error, call the handler with the error.
        """
        return Resource(self.create.catch(lambda e: handler(e).create))

    @final
    def map_error(self, f: Callable[[E], E2]) -> Resource[R, E2, A]:
        """
        Transform the stored error if the resource creation fails on an error.
        Do nothing otherwise.
        """
        return Resource(self.create.map_error(f))

    # Panic

    @final
    def recover(
        self, handler: Callable[[Exception], Resource[R, E, A]]
    ) -> Resource[R, E, A]:
        """
        React to panics (the except part of a try-except).

        On panic, call the handler with the exception.
        """
        return Resource(self.create.recover(lambda p: handler(p).create))

    @final
    def map_panic(self, f: Callable[[E], E2]) -> Resource[R, E2, A]:
        """
        Transform the exception stored if the computation fails on a panic.
        Do nothing otherwise.
        """
        return Resource(
            self.create.map_panic(f).map(lambda x: (x[0], x[1].map_panic(f)))
        )

    @final
    def attempt(self) -> IO[R, Any, Result[E, A]]:
        """
        Transform this Resource that may fail into a Resource
        that never fails but creates a Result[E,A].

        - If self successfully computes a, then `self.attempt()` successfully computes `Ok(a)`.
        - If self fails on error e, then `self.attempt()` successfully computes `Error(e)`.
        - If self fails on panic p, then `self.attempt()` successfully computes `Panic(p)`.

        Note that errors and panics stop the resource creation, unless a catch or
        recover reacts to such failures. But using map, flat_map, flatten and
        ap is sometimes easier than using catch and recover. attempt transforms
        a failed resource creation into a successful resource creation returning a failure,
        thus enabling you to use map, flat_map, ... to deal with errors.
        """
        return Resource(
            self.create.attempt().map(
                lambda x: x.fold(
                    lambda v: (Ok(v[0]), v[1]),
                    lambda e: (Error(e), io.pure(None)),
                    lambda p: (Panic(p), io.pure(None)),
                )
            )
        )

    @final
    def finally_(self, rs: Resource[R, Any, Any]) -> Resource[R, E, A]:
        """
        After having computed self, but before returning its result,
        execute the rs Resource creation.

        This is extremely useful when you need to perform an action,
        unconditionally, at the end of a resource creation, without changing
        its result, like executing a lifted IO.
        """
        return self.attempt().flat_map(lambda r: rs.attempt().then(from_result(r)))

    @final
    def on_failure(
        self, handler: Callable[[Result[E, Any]], IO[R, E, A]]
    ) -> IO[R, E, A]:
        """
        Combined form of catch and recover.
        React to any failure of the resource creation.
        Do nothing if the resource creation is successful.

        - The handler will be called on `Error(e)` if the resource creation fails with error e.
        - The handler will be called on `Panic(p)` if the resource creation fails with panic p.
        - The handler will never be called on `Ok(a)`.
        """
        return self.attempt().flat_map(
            lambda r: r.fold(
                pure,
                lambda e: handler(result.error(e)),
                lambda p: handler(result.panic(p)),
            )
        )

    @final
    def contra_map_executor(
        self, f: Callable[[Executor], Executor]
    ) -> Resource[R, E, A]:
        """
        Change the executor running this IO.
        :param f:
        :return:
        """
        return Resource(self.create.contra_map_executor(f))


def liftIO(mio: IO[R, E, A]) -> Resource[R, E, A]:
    """
    Transform an IO into a Resource whose created resource if the result of the IO.
    The releasing IO does nothing.
    """
    return Resource(mio.map(lambda a: (a, io.pure(None))))


def pure(a: A) -> Resource[R, E, A]:
    """
    A Resource that always returns the same constant.
    """
    return Resource(io.pure((a, io.pure(None))))


def defer(deferred: Callable[[], A]) -> Resource[R, E, A]:
    """
    Defer a computation.

    The result of the Resource is the result of `deferred()`.

    For more details, see `io.defer`
    """
    return liftIO(io.defer(deferred))


def defer_resource(deferred: Callable[[], Resource[R, E, A]]) -> Resource[R, E, A]:
    """
    Make a function that returns an `Resource`, a `Resource` itself.

    This is extremely useful with recursive function that would normally blow
    the stack (raise a stack overflow exception). Deferring recursive calls
    eliminates stack overflow.

    For more information see `io.defer_io`
    """
    return Resource(io.defer(deferred).flat_map(lambda rs: rs.create))


def read() -> Resource[R, E, R]:
    """
    Read the context.

    To execute a computation `IO[R,E,A]`, you need to call the run method with
    some value r of type R: `io.run(r)`. the `read()` action returns the value r
    given to run.

    Please note that the contra_map_read method can transform this value r.
    """
    return liftIO(io.read())


def error(err: E) -> Resource[R, E, A]:
    """
    Resource creation that always fails on the error err.
    """
    return Resource(io.error(err))


def panic(exception: Exception) -> Resource[R, E, A]:
    """
    Resource creation that always fails with the panic exception.
    """
    return Resource(io.panic(exception))


def from_result(r: Result[E, A]) -> Resource[R, E, A]:
    """
    Resource creation that:
    - success if r is an `Ok`
    - fails with error e if r is `Error(e)`
    - fails with panic p if r is `Panic(p)`
    """
    return r.fold(pure, error, panic)


def from_io_resource(mio: IO[R, E, Resource[R, E, A]]) -> Resource[R, E, A]:
    """
    Construct a `Resource` from an `IO[R,E,Resource[R,E,A]]`
    """
    return Resource(mio.flat_map(lambda rs: rs.create))


def from_open_close_io(
    open: IO[R, E, A], close: Callable[[A], IO[R, Any, Any]]
) -> Resource[R, E, A]:
    """
    Construct a `Resource` from an IO to open a resource and one to close it.
    """
    return Resource(open.map(lambda a: (a, close(a))))


def from_open_close(
    open: Callable[[], A], close: Callable[[A], None]
) -> Resource[R, E, A]:
    """
    Construct a `Resource` from a function to open a resource and one to close it.
    """
    return Resource(io.defer(open).map(lambda a: (a, io.pure(a).map(close))))


def from_with(expr: Callable[[], Any]) -> Resource[R, E, A]:
    """
    Create a Resource from "with" python expression:

    >> with expr as x:
    >>     body

    is equivalent to

    >> from_with(lambda: expr)
    """

    def manager_handler():
        manager = expr()
        enter = type(manager).__enter__
        exit = type(manager).__exit__
        (enter(manager), io.defer(lambda: exit(manager, None, None, None)))

    return Resource(io.defer(manager_handler))


def zip(*rs: Resource[R, E, A]) -> Resource[R, E, List[A]]:
    """
    Transform a list of Resource into a Resource creating a list
    of all resources.

    If once resource creation fails, the whole creation fails.
    The resources opened are then released.
    :param rs: the list of resources to pack.
    :return:
    """
    if len(rs) == 1 and isinstance(rs[0], abc.Iterable):
        args = rs[0]
    else:
        args = rs

    def process(l: Result[E, A]):
        close = []
        args = []
        level = 0
        error = None

        for arg in l:
            if arg.is_ok():
                args.append(arg.success[0])
                close.append(arg.success[1])
            elif arg.is_error() and level < 1:
                error = arg
                level = 1
            elif arg.is_panic() and level < 2:
                error = arg
                level = 2
            else:
                level = 2
                error = Panic(_MatchError(f"{arg} should be a Result "))

        if level == 0:
            return io.pure((args, io.run_all(close)))
        else:
            return io.run_all(close).attempt().then(io.from_result(error))

    return Resource(io.zip([x.create.attempt() for x in args]).flat_map(process))


def traverse(
    l: Iterable[A], f: Callable[[A], Resource[R, E, A2]]
) -> Resource[R, E, Iterable[A2]]:
    """
    Apply the function `f` to every element of the iterable.
    The resulting Resource creates the list of all the resources.

    This function is essentially like map, but f returns Resource[R,E,A2] instead of A2.

    :param l: the elements to apply to f
    :param f: the function for each element.
    :return:
    """

    def append(l3: List[A2]) -> Callable[[A2], List[A2]]:
        def do_it(a2: A2) -> List[A2]:
            l3.append(a2)
            return l3

        return do_it

    r = pure([])

    def dumb(r, a):
        return r.flat_map(lambda l2: f(a).map(append(l2)))

    for a in l:
        r = dumb(r, a)
    return r


def yield_() -> Resource[R, E, None]:
    """
    Resource implement cooperative concurrency. It means a Resource has to
    explicitly make a break for other concurrent tasks to have a chance to
    progress.
    This is what `yeild_()` does, it forces the Resource to make a break,
    letting other tasks be run on the executor until the IO start progressing
    again.
    :return:
    """
    return liftIO(io.yield_())


def async_(
    f: Callable[[R, Executor, Callable[[Result[E, A]], None]], None]
) -> Resource[E, R, A]:
    """
    Perform an Asynchronous call. `f` is a function of the form:

    >>> from concurrent.futures import Executor, Future
    >>> def f(context: E,
    >>>       executor: Executor,
    >>>       callback: Callable[[Result[E,A]], None]) -> Future:
    >>>     ...

    - `f` **MUST** return a `Future`.
    - `context` is the context of the Resource, usually the one passed to `run`
       if not changed by `contra_map_read`.
    - `executor` is the `Executor` where the Resource is run, usually the one
       passed to run if not changed by `contra_map_executor`.
    - `callback` **MUST ALWAYS BE CALLED EXACTLY ONCE**.
       Until `callback` is called, the Resource will be suspended waiting for the
       asynchronous call to complete.
       When `callback` is called, the Resource is resumed.
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
    >>> resource = async_(f)
    """
    return liftIO(io.async_(f))


def read_executor() -> Resource[R, E, Executor]:
    """
    Return the executor running this IO.
    :return:
    """
    return liftIO(io.read_executor())
