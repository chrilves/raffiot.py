"""
Local Variables to work around Python annoying limitations about lambdas.

Python forbids local variables and
"""

from __future__ import annotations

from collections import abc
from dataclasses import dataclass
from typing import Generic, TypeVar, Callable, List, Any, Tuple

from typing_extensions import final

from raffiot import io, resource
from raffiot.io import IO
from raffiot.resource import Resource

__all__ = [
    "UpdateResult",
    "Var",
]


A = TypeVar("A")
B = TypeVar("B")


@final
@dataclass
class UpdateResult(Generic[A, B]):
    """
    The result of the `update` methods of `Var`.
    """

    __slots__ = "old_value", "new_value", "returned"

    """
    The result of an Update
    """

    old_value: A
    """
    The value before the Update
    """

    new_value: A
    """
    The value after the update
    """

    returned: B
    """
    The result produced by the update
    """


@final
class Var(Generic[A]):
    """
    A mutable variable.
    **All** concurrent access are protected using a Reentrant Lock.

    **IMPORTANT:** /!\\ **NEVER CREATE VARIABLES BY THE CONSTRUCTOT !!!!** /!\\

    Use `Var.create instead.`
    """

    __slots__ = "_lock", "_value"

    def __init__(self, lock: Resource[Any, None, None], value: A):
        self._lock = lock
        self._value = value

    def lock(self) -> Resource[Any, None, None]:
        """
        The Reentrant Lock that guarantees exclusive access to this variable.
        """
        return self._lock

    @classmethod
    def create(cls, a: A) -> IO[Any, None, Var[A]]:
        """
        Create a new variable whose value is `a`.

        :param a:
        :return:
        """
        return resource.reentrant_lock.map(lambda lock: Var(lock, a))

    @classmethod
    def create_rs(cls, a: A) -> Resource[Any, None, Var[A]]:
        """
        Create a new variable whose value is `a`.

        :param a:
        :return:
        """
        return resource.lift_io(resource.reentrant_lock.map(lambda lock: Var(lock, a)))

    #############
    #   GETTER  #
    #############

    def get(self) -> IO[None, None, A]:
        """
        Get the current value of this variable.
        :return:
        """
        return self._lock.with_(io.defer(lambda: self._value))

    def get_rs(self) -> Resource[None, None, A]:
        """
        Get the current value of this variable.
        :return:
        """
        return self._lock.then(resource.defer(lambda: self._value))

    #############
    #   SETTER  #
    #############

    def set(self, v: A) -> IO[None, None, None]:
        """
        Assign a new value to this variable.

        :param v:
        :return:
        """

        def h(w) -> None:
            self._value = w

        return self._lock.with_(io.defer(h, v))

    def set_rs(self, v: A) -> Resource[None, None, None]:
        """
        Assign a new value to this variable.

        :param v:
        :return:
        """

        def h(w) -> None:
            self._value = w

        return self._lock.then(resource.defer(h, v))

    #####################
    #   GETTER + SETTER #
    #####################

    def get_and_set(self, v: A) -> IO[Any, None, A]:
        """
        Assign a new value to this variable. The previous value is returned.

        :param v:
        :return:
        """

        def h():
            old_value = self._value
            self._value = v
            return old_value

        return self._lock.with_(io.defer(h))

    def get_and_set_rs(self, v: A) -> Resource[None, None, None]:
        """
        Assign a new value to this variable. The previous value is returned.

        :param v:
        :return:
        """

        def h():
            old_value = self._value
            self._value = v
            return old_value

        return self._lock.then(resource.defer(h))

    ###############
    #    UPDATE   #
    ###############

    def update(self, f: Callable[[A], Tuple[A, B]]) -> IO[UpdateResult[A, B]]:
        """
        Update the value contained in this variable.

        :param f:
        :return:
        """

        def h() -> UpdateResult[A, B]:
            old_value = self._value
            new_value, ret = f(self._value)
            self._value = new_value
            return UpdateResult(old_value, new_value, ret)

        return self._lock.with_(io.defer(h))

    def update_io(
        self, f: Callable[[A], IO[Any, None, Tuple[A, B]]]
    ) -> IO[Any, None, UpdateResult[A, B]]:
        """
        Update the value contained in this variable.

        :param f:
        :return:
        """

        def h() -> IO[Any, None, UpdateResult[A, B]]:
            old_value = self._value

            def g(x: Tuple[A, B]) -> UpdateResult[A, B]:
                self._value = x[0]
                return UpdateResult(old_value, self._value, x[1])

            return f(old_value).map(g)

        return self._lock.with_(io.defer_io(h))

    def update_rs(
        self, f: Callable[[A], Resource[Any, None, Tuple[A, B]]]
    ) -> Resource[Any, None, UpdateResult[A, B]]:
        """
        Update the value contained in this variable.

        :param f:
        :return:
        """

        def h() -> Resource[Any, None, UpdateResult[A, B]]:
            old_value = self._value

            def g(x: Tuple[A, B]) -> UpdateResult[A, B]:
                self._value = x[0]
                return UpdateResult(old_value, self._value, x[1])

            return f(old_value).map(g)

        return self._lock.then(resource.defer_resource(h))

    ######################
    #  Creating New Vars #
    ######################

    def traverse(self, f: Callable[[A], IO[Any, None, B]]) -> IO[Any, None, Var[B]]:
        """
        Create a new variable by transforming the current value of this variable.

        :param f:
        :return:
        """

        def h():
            return f(self._value).flat_map(Var.create)

        return self._lock.with_(io.defer_io(h))

    @classmethod
    def zip(cls, *vars: Var[A]) -> IO[Any, None, List[A]]:
        """ "
        Group these variables current values into a list.
        """

        if len(vars) == 1 and isinstance(vars[0], abc.Iterable):
            args = vars[0]
        else:
            args = vars
        return resource.zip([x._lock for x in args]).with_(
            io.defer(lambda: [x._value for x in args])
        )

    def zip_with(self, *vars: Var[A]) -> IO[Any, None, List[A]]:
        """
        Group this variable current value with `vars` variable current values.

        :param vals: other variables to combine with self.
        :return:
        """
        return Var.zip(self, *vars)

    def ap(self, *arg: Var[A]) -> IO[Any, None, B]:
        """
        Apply the function contained in this variable to `args` variables.

        :param arg:
        :return:
        """
        return self.zip_with(*arg).map(lambda l: l[0](*l[1:]))
