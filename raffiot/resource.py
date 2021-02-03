"""
Resource management module.
Ensure that create resources are always nicely released after use.
"""

from __future__ import annotations
from typing import TypeVar, Generic, Callable, Any, Tuple
from typing_extensions import final
from dataclasses import dataclass
from raffiot import result, io
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
    """
    Essentially an IO-powered data structure that produces resources of type A,
    can fail with errors of type E and read a context of type R.
    """

    create: IO[R, E, Tuple[A, IO[R, Any, Any]]]
    """
    IO to create one resource along with the IO for releasing it.
    
    On success, this IO must produce a Tuple[A, IO[R,Any,Any]:
        - The first value of the tuple, of type A, is the created resource.
        - The second value of the tuple, of type IO[R,Any,Any], is the IO that
            release the first value.
    
    For example:
        >>> Resource(io.defer(lambda: open("file")).map(lambda a: (a, io.defer(a.close))))
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
    def ap(
        self: Resource[R, E, Callable[[X], A2]], rs: Resource[R, E, X]
    ) -> Resource[R, E, A2]:
        """
        Noting functions from X to A: X -> A

        If self computes a function f: X -> A
        and arg computes a value x: X
        then self.ap(arg) computes f(x): A
        """
        return self.flat_map(lambda f: rs.map(f))

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
    def attempt(self) -> IO[R, Any, result.Result[E, A]]:
        """
        Transform this Resource that may fail into a Resource
        that never fails but creates a Result[E,A].

        - If self successfully computes a, then self.attempt() successfully computes Ok(a).
        - If self fails on error e, then self.attempt() successfully computes Error(e).
        - If self fails on panic p, then self.attempt() successfully computes Panic(p).

        Note that errors and panics stop the resource creation, unless a catch or
        recover reacts to such failures. But using map, flat_map, flatten and
        ap is sometimes easier than using catch and recover. attempt transforms
        a failed resource creation into a successful resource creation returning a failure,
        thus enabling you to use map, flat_map, ... to deal with errors.
        """
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

        - The handler will be called on Error(e) if the resource creation fails with error e.
        - The handler will be called on Panic(p) if the resource creation fails with panic p.
        - The handler will never be called on Ok(a).
        """
        return self.attempt().flat_map(
            lambda r: r.fold(
                pure,
                lambda e: handler(result.error(e)),
                lambda p: handler(result.panic(p)),
            )
        )


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

    The result of the Resource is the result of deferred().

    For more details, see io.defer
    """
    return liftIO(io.defer(deferred))


def defer_resource(deferred: Callable[[], Resource[R, E, A]]) -> Resource[R, E, A]:
    """
    Make a function that returns an Resource, a Resource itself.

    This is extremely useful with recursive function that would normally blow
    the stack (raise a stack overflow exception). Deferring recursive calls
    eliminates stack overflow.

    For more information see io.defer_io
    """
    return Resource(io.defer(deferred).flat_map(lambda rs: rs.create))


def read() -> Resource[R, E, R]:
    """
    Read the context.

    To execute a computation IO[R,E,A], you need to call the run method with
    some value r of type R: io.run(r). the read() action returns the value r
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


def from_result(r: result.Result[E, A]) -> Resource[R, E, A]:
    """
    Resource creation that:
    - success if r is an Ok
    - fails with error e if r is Error(e)
    - fails with panic p if r is Panic(p)
    """
    return r.fold(pure, error, panic)


def from_io_resource(mio: IO[R, E, Resource[R, E, A]]) -> Resource[R, E, A]:
    """
    Construct a Resource from an IO[R,E,Resource[R,E,A]]
    """
    return Resource(mio.flat_map(lambda rs: rs.create))


def from_open_close_io(
    open: IO[R, E, A], close: Callable[[A], IO[R, Any, Any]]
) -> Resource[R, E, A]:
    """
    Construct a Resource from an IO to open a resource and one to close it.
    """
    return Resource(open.map(lambda a: (a, close(a))))


def from_open_close(
    open: Callable[[], A], close: Callable[[A], None]
) -> Resource[R, E, A]:
    """
    Construct a Resource from a function to open a resource and one to close it.
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
