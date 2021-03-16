"""
Local Variables to work around Python annoying limitations about lambdas.

Python forbids local variables and
"""

from __future__ import annotations

from typing_extensions import final
from dataclasses import dataclass
from typing import Generic, TypeVar, Callable, List, Any
from raffiot import io, resource
from raffiot.io import IO
from raffiot.resource import Resource
from collections import abc
from abc import ABC


__all__ = [
    "Val",
    "Var",
    "sequence",
]


A = TypeVar("A")
B = TypeVar("B")


@dataclass
class Val(Generic[A]):
    value: A

    @final
    def get(self) -> A:
        return self.value

    @final
    def get_io(self) -> IO[None, None, A]:
        return io.defer(self.get)

    @final
    def get_rs(self) -> Resource[None, None, A]:
        return resource.defer(self.get)

    @classmethod
    def pure(cls, a: A) -> Val[A]:
        return Val(a)

    def map(self, f: Callable[[A], B]) -> Val[B]:
        return Val(f(self.value))

    def flat_map(self, f: Callable[[A], Val[B]]) -> Val[B]:
        return f(self.value)

    @classmethod
    def zip(cls, *vals: Any) -> Val[List[A]]:
        if len(vals) == 1 and isinstance(vals[0], abc.Iterable):
            return Val([x.value for x in vals[0]])
        return Val([x.value for x in vals])

    def zip_with(self, *vals: Any) -> Val[List[A]]:
        return Val.zip(self, *vals)

    def ap(self, *arg: Val[A]) -> Val[B]:
        if len(arg) == 1 and isinstance(arg[0], abc.Iterable):
            l = [x.value for x in arg[0]]
        else:
            l = [x.value for x in arg]
        return Val(self.value(*l))


@final
@dataclass
class Var(Val[A]):
    value: A

    def set(self, v: A) -> A:
        old = self.value
        self.value = v
        return old

    def set_io(self, v: A) -> IO[None, None, None]:
        return io.defer(self.set, v)

    def set_rs(self, v: A) -> Resource[None, None, None]:
        return resource.defer(self.set, v)

    @classmethod
    def pure(cls, a: A) -> Var[A]:
        return Var(a)

    def map(self, f: Callable[[A], B]) -> Var[B]:
        return Var(f(self.value))

    def flat_map(self, f: Callable[[A], Var[B]]) -> Var[B]:
        return f(self.value)

    @classmethod
    def zip(cls, *vars: Any) -> Val[List[A]]:
        if len(vars) == 1 and isinstance(vars[0], abc.Iterable):
            return Var([x.value for x in vars[0]])
        return Var([x.value for x in vars])

    def zip_with(self, *vars: Any) -> Val[List[A]]:
        return Var.zip(self, *vars)

    def ap(self, *arg: Any) -> Val[B]:
        if len(arg) == 1 and isinstance(arg[0], abc.Iterable):
            l = [x.value for x in arg[0]]
        else:
            l = [x.value for x in arg]
        return Var(self.value(*l))


def sequence(*a: Any) -> Any:
    if len(a) == 1 and isinstance(a[0], abc.Iterable):
        return a[0][-1]
    return a[-1]
