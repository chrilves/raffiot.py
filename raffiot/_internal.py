"""
This an INTERNAL module.
You should NEVER use anything from this module directly.
Use IO instead!
"""

from __future__ import annotations

from enum import Enum

from typing_extensions import final

__all__ = ["IOTag", "ContTag", "ResultTag", "FiberState"]


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
    ERRORS = 11  # ERRORS
    CATCH = 12  # MAIN HANDLER
    MAP_ERROR = 13  # MAIN      FUN
    PANIC = 14  # EXCEPTION
    RECOVER = 15  # MAIN HANDLER
    MAP_PANIC = 16  # MAIN FUN
    YIELD = 17  #
    ASYNC = 18  # DOUBLE_NEGATION
    DEFER_READ = 19  # FUN ARGS KWARGS
    DEFER_READ_IO = 20  # FUN ARGS KWARGS
    PARALLEL = 21  # IOS
    WAIT = 22  # FIBERS
    SLEEP_UNTIL = 23  # EPOCH IN SECONDS
    REC = 24  # FUN
    ACQUIRE = 25  # LOCK
    RELEASE = 26  # LOCK


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
    START = 11  # START IO


@final
class ResultTag(Enum):
    OK = 0
    ERROR = 1
    PANIC = 2


@final
class FiberState(Enum):
    ACTIVE = 0
    WAITING_ASYNC = 1
    WAITING_FIBERS = 2
    FINISHED = 3
