"""
This an INTERNAL module.
You should NEVER use anything from this module directly.
Use IO instead!
"""

from __future__ import annotations

from enum import Enum

from typing_extensions import final
from functools import total_ordering
import threading
from queue import Queue

__all__ = ["IOTag", "ContTag", "ResultTag", "Scheduled", "Lock", "Semaphore"]


@final
class IOTag(Enum):
    PURE = 0  # VALUE
    MAP = 1  # MAIN FUN
    FLATMAP = 2  # MAIN HANDLER
    FLATTEN = 3  # TOWER
    SEQUENCE = 4  # ARGS
    ZIP = 5  # ARGS
    DEFER = 6  # DEFERED
    DEFER_IO = 7  # DEFERED
    ATTEMPT = 8  # IO
    READ = 9  #
    CONTRA_MAP_READ = 10  # FUN MAIN
    ERROR = 11  # ERROR
    CATCH = 12  # MAIN HANDLER
    MAP_ERROR = 13  # MAIN      FUN
    PANIC = 14  # EXCEPTION
    RECOVER = 15  # MAIN HANDLER
    MAP_PANIC = 16  # MAIN FUN
    YIELD = 17  #
    ASYNC = 18  # DOUBLE_NEGATION
    EXECUTOR = 19  #
    CONTRA_MAP_EXECUTOR = 20  # MAIN FUN
    DEFER_READ = 21  # FUN ARGS KWARGS
    DEFER_READ_IO = 22  # FUN ARGS KWARGS
    PARALLEL = 23  # IOS
    WAIT = 24  # FIBERS
    SLEEP_UNTIL = 25  # EPOCH IN SECONDS
    REC = 26  # FUN
    LOCK = 27  # LOCK


@final
class ContTag(Enum):
    MAP = 0  # FUN
    FLATMAP = 1  # CONTEXT HANDLER
    FLATTEN = 2  # CONTEXT
    SEQUENCE = 3  # CONTEXT SIZE_IOS IOS
    ZIP = 4  # CONTEXT IOS NB_IOS NEXT_IO_INDEX
    ATTEMPT = 5  #
    CATCH = 6  # CONTEXT HANDLER
    MAP_ERROR = 7  # FUN
    RECOVER = 8  # CONTEXT HANDLER
    MAP_PANIC = 9  # FUN
    ID = 10  #


@final
class ResultTag(Enum):
    OK = 0
    ERROR = 1
    PANIC = 2


@total_ordering
class Scheduled:
    __slots__ = ["__schedule", "__fiber"]

    def __init__(self, schedule: float, fiber):
        self.__schedule = schedule
        self.__fiber = fiber

    def __eq__(self, other):
        if isinstance(other, Scheduled):
            return self.__schedule == other.__schedule and self.__fiber is other.__fiber
        return False

    def __lt__(self, other):
        if not isinstance(other, Scheduled):
            raise Exception(f"{other} should be a Schedule")
        if self.__schedule == other.__schedule:
            return hash(self.__fiber) < hash(other.__fiber)
        return self.__schedule < other.__schedule


@final
class Lock:

    __slots__ = ["lock", "fiber", "__nb_taken", "waiting"]

    def __init__(self):
        self.lock = threading.Lock()
        self.fiber = None
        self.__nb_taken = 0
        self.waiting = Queue()

    def acquire(self, fiber) -> bool:
        if self.fiber is None:
            self.__nb_taken = 1
            return True
        if self.fiber is fiber:
            self.fiber = fiber
            self.__nb_taken += 1
            return True
        return False

    def release(self):
        with self.lock:
            self.__nb_taken -= 1
            if self.__nb_taken == 0:
                if self.waiting.empty():
                    self.fiber = None
                    return
                self.fiber = self.waiting.get()
                self.__nb_taken = 1
                self.fiber._Fiber__monitor._Monitor__resume(self.fiber)

@final
class Semaphore:

    __slots__ = ["lock", "tokens", "waiting"]

    def __init__(self, tokens: int):
        self.lock = threading.Lock()
        self.tokens = tokens
        self.waiting = Queue()

    def acquire(self, fiber) -> bool:
        if self.tokens > 0:
            self.tokens -= 1
            return True
        return False

    def release(self):
        with self.lock:
            if self.waiting.empty():
                self.tokens += 1
                return
            fiber = self.waiting.get()
            fiber._Fiber__monitor._Monitor__resume(fiber)