"""
Local Variables to work around Python annoying limitations about lambdas.

Python forbids local variables and
"""
from __future__ import annotations

from collections import abc
from dataclasses import dataclass
from typing import Generic, TypeVar, Callable, List, Any

from typing_extensions import final

from raffiot import io, resource
from raffiot.io import IO
from raffiot.resource import Resource

__all__ = [
    "Val",
]


A = TypeVar("A")
B = TypeVar("B")


@final
@dataclass
class Val(Generic[A]):
    """
    Immutable Value.

    Used to create local "variables" in lambdas.
    """

    __slots__ = "value"

    value: A

    def get(self) -> A:
        """
        Get this Val value.
        :return:
        """
        return self.value

    def get_io(self) -> IO[None, None, A]:
        """
        Get this Val value.
        :return:
        """
        return io.defer(self.get)

    def get_rs(self) -> Resource[None, None, A]:
        """
        Get this Val value.
        :return:
        """
        return resource.defer(self.get)

    @classmethod
    def pure(cls, a: A) -> Val[A]:
        """
        Create a new Val with value `a`

        :param a: the value of this val.
        :return:
        """
        return Val(a)

    def map(self, f: Callable[[A], B]) -> Val[B]:
        """
        Create a new Val from this one by applying this **pure** function.

        :param f:
        :return:
        """
        return Val(f(self.value))

    def traverse(self, f: Callable[[A], IO[B]]) -> IO[Val[B]]:
        """
        Create a new Val from this one by applying this `IO` function.

        :param f:
        :return:
        """

        return io.defer_io(f, self.value).map(Val)

    def flat_map(self, f: Callable[[A], Val[B]]) -> Val[B]:
        """
        Create a new Val from this one.

        :param f:
        :return:
        """
        return f(self.value)

    def flatten(self) -> Val[B]:  # A = Val[B]
        """ "
        Flatten this `Val[Val[A]]` into a `Val[A]`
        """

        return Val(self.value.value)

    @classmethod
    def zip(cls, *vals: Any) -> Val[List[A]]:
        """ "
        Group these list of Val into a Val of List
        """

        if len(vals) == 1 and isinstance(vals[0], abc.Iterable):
            return Val([x.value for x in vals[0]])
        return Val([x.value for x in vals])

    def zip_with(self, *vals: Any) -> Val[List[A]]:
        """
        Group this Val with other Val into a list of Val.

        :param vals: other Val to combine with self.
        :return:
        """

        return Val.zip(self, *vals)

    def ap(self, *arg: Val[A]) -> Val[B]:
        """
        Apply the function contained in this Val to `args` Vals.

        :param arg:
        :return:
        """

        if len(arg) == 1 and isinstance(arg[0], abc.Iterable):
            l = [x.value for x in arg[0]]
        else:
            l = [x.value for x in arg]
        return Val(self.value(*l))
