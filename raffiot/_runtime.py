"""
This an INTERNAL module.
You should NEVER use anything from this module directly.
Use Runtime instead!
"""

from __future__ import annotations

import heapq
import threading
import time
import uuid
from collections import deque
from enum import Enum
from functools import total_ordering
from queue import Queue
from random import randint
from threading import Thread
from typing import Any, List, TypeVar, Generic, Callable

from typing_extensions import final

from raffiot._internal import ContTag, FiberState, IOTag, ResultTag
from raffiot.io import IO
from raffiot.result import Result, Ok, Errors, Panic
from raffiot.utils import MatchError

__all__ = [
    "SharedState",
    "Lock",
    "Semaphore",
]

R = TypeVar("R", contravariant=True)
E = TypeVar("E", covariant=True)
A = TypeVar("A", covariant=True)


@final
class RunnerState(Enum):
    ACTIVE = 0
    IDLE = 1


@total_ordering
class Scheduled:
    schedule: float
    fiber: Any

    __slots__ = "schedule", "fiber"

    def __init__(self, schedule: float, fiber: Fiber[R, E, A]):
        self.schedule = schedule
        self.fiber = fiber

    def __eq__(self, other):
        return self.schedule == other.schedule and self.fiber is other.fiber

    def __lt__(self, other):
        if self.schedule == other.schedule:
            return self.fiber.uuid < other.fiber.uuid
        return self.schedule < other.schedule


@final
class SharedState:

    __slots__ = (
        "scheduled_lock",
        "scheduled",
        "pool",
        "pool_size",
        "nighttime",
    )

    def __init__(self, pool_size: int, nighttime: float) -> None:
        self.scheduled_lock = threading.Lock()
        self.scheduled: List[Scheduled] = []
        self.pool_size = max(pool_size, 1)
        self.pool: List[Runner] = [Runner(self, i) for i in range(self.pool_size)]
        self.nighttime = nighttime

    def run(self, io: IO[R, E, A], context: R) -> Result[E, A]:
        fiber = Fiber(io, context)
        self.pool[0].queue.appendleft(fiber)
        for i in range(self.pool_size - 1):
            self.pool[i + 1].start()
        self.pool[0].run()
        for i in range(self.pool_size - 1):
            self.pool[i + 1].join()
        return fiber.result

    def sleeping_time(self) -> float:
        for runner in self.pool:
            if (
                runner.state == RunnerState.ACTIVE
                or (runner.count_remote + runner.count_local > 0)
                or runner.queue
            ):
                return self.nighttime
        with self.scheduled_lock:
            for runner in self.pool:
                runner.state_lock.acquire()

            index = 0
            while index < self.pool_size:
                runner = self.pool[index]
                if (
                    runner.state == RunnerState.ACTIVE
                    or (runner.count_remote + runner.count_local > 0)
                    or runner.queue
                ):
                    while index >= 0:
                        self.pool[index].state_lock.release()
                        index -= 1
                    return self.nighttime
                index += 1

            if self.scheduled:
                t = max(0, self.scheduled[0].schedule - time.time())
            else:
                t = None
            for runner in self.pool:
                runner.state_lock.release()
            return t


@final
class Fiber(Generic[R, E, A]):
    __slots__ = (
        "_context",
        "_cont",
        "_arg_tag",
        "_arg_value",
        "result",
        "_state_lock",
        "_state",
        "_timestamp",
        "_callbacks",
        "_nb_waiting",
        "_paused",
        "_runner",
        "uuid",
    )

    def __init__(self, io: IO[R, E, A], context: R) -> None:
        self._context = context
        self._cont = [ContTag.ID, io, ContTag.START]
        self._arg_tag = None
        self._arg_value = None

        self.result = None

        self._state_lock = threading.Lock()
        self._state = FiberState.ACTIVE
        self._timestamp = 0.0
        self._callbacks = []
        self._nb_waiting = 0
        self._paused = False
        self._runner: Runner = None

        self.uuid = uuid.uuid4()


def resume_fiber(fiber: Fiber[Any, Any, Any]) -> None:
    fiber._state = FiberState.ACTIVE
    if fiber._paused:
        runner = fiber._runner
        runner.queue.append(fiber)
        with runner.count_lock:
            runner.count_remote -= 1
    else:
        fiber._runner.count_local -= 1


def run_callback(
    fiber: Fiber[Any, Any, Any], index: int, res: Result[Any, Any]
) -> None:
    with fiber._state_lock:
        fiber._arg_value[index] = res
        fiber._nb_waiting -= 1
        if fiber._nb_waiting == 0 and fiber._state == FiberState.WAITING_FIBERS:
            fiber._arg_tag = ResultTag.OK
            resume_fiber(fiber)


def add_callback(
    par_fiber: Fiber[Any, Any, Any],
    waiting_fiber: Fiber[Any, Any, Any],
    index: int,
) -> None:
    finished = False
    with par_fiber._state_lock:
        if par_fiber._state == FiberState.FINISHED:
            finished = True
        else:
            par_fiber._callbacks.append((waiting_fiber, index))
    if finished:
        run_callback(waiting_fiber, index, par_fiber.result)


def finish_fiber(fiber: Fiber[Any, Any, Any]):
    with fiber._state_lock:
        fiber._state = FiberState.FINISHED
        for waiting_fiber, index in fiber._callbacks:
            run_callback(waiting_fiber, index, fiber.result)
        fiber._callbacks = None
        fiber._context = None
        fiber._cont = None
        fiber._arg_tag = None
        fiber._arg_value = None
        fiber._runner = None


@final
class Runner(Thread):

    __slots__ = (
        "queue",
        "shared_state",
        "state_lock",
        "state",
        "count_lock",
        "count_local",
        "count_remote",
    )

    def __init__(self, shared_state: SharedState, index: int) -> None:
        super().__init__()
        self.queue: deque[Fiber[Any, Any, Any]] = deque()
        self.shared_state = shared_state
        self.state_lock = threading.Lock()
        self.state = RunnerState.ACTIVE
        self.count_lock = threading.Lock()
        self.count_local = 0
        self.count_remote = 0

    def run(self):
        queue = self.queue
        pool = self.shared_state.pool
        pool_size = len(pool)

        while True:
            self.activate_scheduled()
            try:
                fiber = queue.popleft()
            except IndexError:
                fiber = None
                if pool_size > 1:
                    starting_point = randint(0, pool_size - 1)
                    tried_runners = 0
                    while tried_runners < pool_size:
                        runner = pool[(starting_point + tried_runners) % pool_size]
                        tried_runners += 1
                        if runner is not self:
                            try:
                                fiber = runner.queue.pop()
                                break
                            except IndexError:
                                pass

                if fiber is None:
                    with self.count_lock:
                        self.count_local += self.count_remote
                        self.count_remote = 0
                    self.state = RunnerState.IDLE
                    sleeping_time = self.shared_state.sleeping_time()
                    if sleeping_time is None:
                        return
                    time.sleep(sleeping_time)
                    with self.state_lock:
                        self.state = RunnerState.ACTIVE
                    continue
            if self.step(fiber):
                queue.append(fiber)

    def activate_scheduled(self) -> None:
        if self.shared_state.scheduled_lock.acquire(blocking=False):
            try:
                now = time.time()
                while (
                    self.shared_state.scheduled
                    and self.shared_state.scheduled[0].schedule <= now
                ):
                    self.queue.appendleft(
                        heapq.heappop(self.shared_state.scheduled).fiber
                    )
            finally:
                self.shared_state.scheduled_lock.release()

    def step(self, fiber: Fiber[R, E, A]) -> bool:
        cont = fiber._cont
        context = fiber._context
        arg_tag = fiber._arg_tag
        arg_value = fiber._arg_value

        fiber._cont = None
        fiber._context = None
        fiber._arg_value = None

        try:
            while True:
                # Eval Cont
                while True:
                    tag = cont.pop()
                    if tag == ContTag.MAP:
                        fun = cont.pop()
                        try:
                            if arg_tag == ResultTag.OK:
                                arg_value = fun(arg_value)
                        except Exception as exception:
                            if arg_tag == ResultTag.OK:
                                arg_value = ([exception], [])
                            elif arg_tag == ResultTag.ERROR:
                                arg_value = ([exception], arg_value)
                            else:
                                arg_value[0].append(exception)
                            arg_tag = ResultTag.PANIC
                        continue
                    if tag == ContTag.FLATMAP:
                        context = cont.pop()
                        f = cont.pop()
                        try:
                            if arg_tag == ResultTag.OK:
                                io = f(arg_value)
                                break
                        except Exception as exception:
                            if arg_tag == ResultTag.OK:
                                arg_value = ([exception], [])
                            elif arg_tag == ResultTag.ERROR:
                                arg_value = ([exception], arg_value)
                            else:
                                arg_value[0].append(exception)
                            arg_tag = ResultTag.PANIC
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
                                if arg_tag == ResultTag.OK:
                                    arg_value = ([exception], [])
                                elif arg_tag == ResultTag.ERROR:
                                    arg_value = ([exception], arg_value)
                                else:
                                    arg_value[0].append(exception)
                                arg_tag = ResultTag.PANIC
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
                            arg_value = Errors(arg_value)
                            continue
                        if arg_tag == ResultTag.PANIC:
                            arg_tag = ResultTag.OK
                            arg_value = Panic(arg_value[0], arg_value[1])
                            continue
                        arg_tag = ResultTag.OK
                        arg_value = Panic(MatchError(f"Wrong result tag {arg_tag}"))
                        continue
                    if tag == ContTag.CATCH:
                        context = cont.pop()
                        handler = cont.pop()
                        try:
                            if arg_tag == ResultTag.ERROR:
                                io = handler(arg_value)
                                break
                        except Exception as exception:
                            if arg_tag == ResultTag.OK:
                                arg_value = ([exception], [])
                            elif arg_tag == ResultTag.ERROR:
                                arg_value = ([exception], arg_value)
                            else:
                                arg_value[0].append(exception)
                            arg_tag = ResultTag.PANIC
                        continue
                    if tag == ContTag.MAP_ERROR:
                        fun = cont.pop()
                        try:
                            if arg_tag == ResultTag.ERROR:
                                arg_value = list(map(fun, arg_value))
                            if arg_tag == ResultTag.PANIC:
                                arg_value[1] = list(map(fun, arg_value[1]))
                        except Exception as exception:
                            if arg_tag == ResultTag.OK:
                                arg_value = ([exception], [])
                            elif arg_tag == ResultTag.ERROR:
                                arg_value = ([exception], arg_value)
                            else:
                                arg_value[0].append(exception)
                            arg_tag = ResultTag.PANIC
                        continue
                    if tag == ContTag.RECOVER:
                        context = cont.pop()
                        handler = cont.pop()
                        try:
                            if arg_tag == ResultTag.PANIC:
                                io = handler(arg_value[0], arg_value[1])
                                break
                        except Exception as exception:
                            if arg_tag == ResultTag.OK:
                                arg_value = ([exception], [])
                            elif arg_tag == ResultTag.ERROR:
                                arg_value = ([exception], arg_value)
                            else:
                                arg_value[0].append(exception)
                            arg_tag = ResultTag.PANIC
                        continue
                    if tag == ContTag.MAP_PANIC:
                        fun = cont.pop()
                        try:
                            if arg_tag == ResultTag.PANIC:
                                arg_value = (list(map(fun, arg_value[0])), arg_value[1])
                        except Exception as exception:
                            if arg_tag == ResultTag.OK:
                                arg_value = ([exception], [])
                            elif arg_tag == ResultTag.ERROR:
                                arg_value = ([exception], arg_value)
                            else:
                                arg_value[0].append(exception)
                            arg_tag = ResultTag.PANIC
                        continue
                    if tag == ContTag.ID:
                        if arg_tag == ResultTag.OK:
                            fiber.result = Ok(arg_value)
                        elif arg_tag == ResultTag.ERROR:
                            fiber.result = Errors(arg_value)
                        elif arg_tag == ResultTag.PANIC:
                            fiber.result = Panic(arg_value[0], arg_value[1])
                        else:
                            fiber.result = Panic(
                                [MatchError(f"Wrong result tag {arg_tag}")], []
                            )
                        finish_fiber(fiber)
                        return False
                    if tag == ContTag.START:
                        io = cont.pop()
                        break
                    if arg_tag == ResultTag.OK:
                        arg_value = ([MatchError(f"Invalid cont {cont + [tag]}")], [])
                    elif arg_tag == ResultTag.ERROR:
                        arg_value = (
                            [MatchError(f"Invalid cont {cont + [tag]}")],
                            arg_value,
                        )
                    else:
                        arg_value[0].append(MatchError(f"Invalid cont {cont + [tag]}"))
                    arg_tag = ResultTag.PANIC

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
                            arg_value = ([exception], [])
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
                            arg_value = ([exception], [])
                        break
                    if tag == IOTag.DEFER_IO:
                        try:
                            io = io._IO__fields[0](
                                *io._IO__fields[1], **io._IO__fields[2]
                            )
                            continue
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = ([exception], [])
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
                            arg_value = ([exception], [])
                            break
                    if tag == IOTag.ERRORS:
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
                        self.activate_scheduled()
                        if self.queue:
                            fiber._arg_tag = ResultTag.OK
                            fiber._arg_value = None
                            fiber._context = context
                            fiber._cont = cont
                            return True
                        else:
                            arg_tag = ResultTag.OK
                            arg_value = None
                            break
                    if tag == IOTag.ASYNC:
                        timestamp = time.time()

                        fiber._context = context
                        fiber._cont = cont
                        fiber._state = FiberState.WAITING_ASYNC
                        fiber._timestamp = timestamp
                        fiber._paused = False
                        fiber._runner = self
                        self.count_local += 1

                        def make_callback(ts):
                            def callback(r):
                                with fiber._state_lock:
                                    if (
                                        fiber._state == FiberState.WAITING_ASYNC
                                        and fiber._timestamp == ts
                                    ):
                                        if isinstance(r, Ok):
                                            fiber._arg_tag = ResultTag.OK
                                            fiber._arg_value = r.success
                                        elif isinstance(r, Errors):
                                            fiber._arg_tag = ResultTag.ERROR
                                            fiber._arg_value = r.errors
                                        elif isinstance(r, Panic):
                                            fiber._arg_tag = ResultTag.PANIC
                                            fiber._arg_value = (r.exceptions, r.errors)
                                        else:
                                            fiber._arg_tag = ResultTag.PANIC
                                            fiber._arg_value = (
                                                MatchError(
                                                    "{res} should be a Result in defer_read"
                                                ),
                                                [],
                                            )
                                        resume_fiber(fiber)

                            return callback

                        try:
                            io._IO__fields[0](
                                context,
                                make_callback(timestamp),
                                *io._IO__fields[1],
                                **io._IO__fields[2],
                            )
                        except Exception as exception:
                            with fiber._state_lock:
                                if (
                                    fiber._state == FiberState.WAITING_ASYNC
                                    and fiber._timestamp == timestamp
                                ):
                                    fiber._state = FiberState.ACTIVE
                                    self.count_local -= 1
                                    arg_tag = ResultTag.PANIC
                                    arg_value = ([exception], [])
                                    break
                        with fiber._state_lock:
                            if fiber._state == FiberState.ACTIVE:
                                break
                            else:
                                fiber._paused = True
                                return False
                    if tag == IOTag.DEFER_READ:
                        try:
                            res = io._IO__fields[0](
                                *(context, *io._IO__fields[1]), **io._IO__fields[2]
                            )
                            if isinstance(res, Ok):
                                arg_tag = ResultTag.OK
                                arg_value = res.success
                                break
                            if isinstance(res, Errors):
                                arg_tag = ResultTag.ERROR
                                arg_value = res.errors
                                break
                            if isinstance(res, Panic):
                                arg_tag = ResultTag.PANIC
                                arg_value = (res.exceptions, res.errors)
                                break
                            arg_tag = ResultTag.PANIC
                            arg_value = (
                                [MatchError("{res} should be a Result in defer_read")],
                                [],
                            )
                            break
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = ([exception], [])
                        break
                    if tag == IOTag.DEFER_READ_IO:
                        try:
                            io = io._IO__fields[0](
                                *(context, *io._IO__fields[1]), **io._IO__fields[2]
                            )
                            continue
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = ([exception], [])
                            break
                    if tag == IOTag.PARALLEL:
                        arg_value = []
                        for fio in io._IO__fields:
                            par_fiber = Fiber(fio, context)
                            arg_value.append(par_fiber)
                            self.queue.appendleft(par_fiber)
                        arg_tag = ResultTag.OK
                        break
                    if tag == IOTag.WAIT:
                        fibers: List[Fiber[Any, Any, Any]] = io._IO__fields

                        if fibers:
                            fiber._arg_value = [None for _ in fibers]
                            fiber._nb_waiting = len(fibers)
                            fiber._state = FiberState.WAITING_FIBERS
                            fiber._paused = False
                            fiber._runner = self
                            self.count_local += 1

                            for index, par_fiber in enumerate(fibers):
                                add_callback(par_fiber, fiber, index)

                            with fiber._state_lock:
                                if fiber._state == FiberState.ACTIVE:
                                    break
                                else:
                                    fiber._paused = True
                                    fiber._context = context
                                    fiber._cont = cont
                                    return False
                        arg_tag = ResultTag.OK
                        arg_value = []
                        break
                    if tag == IOTag.SLEEP_UNTIL:
                        when = io._IO__fields
                        if when > time.time():
                            fiber._context = context
                            fiber._cont = cont
                            fiber._arg_tag = ResultTag.OK
                            fiber._arg_value = None
                            with self.shared_state.scheduled_lock:
                                heapq.heappush(
                                    self.shared_state.scheduled, Scheduled(when, fiber)
                                )
                            return False
                        arg_tag = ResultTag.OK
                        arg_value = None
                        break
                    if tag == IOTag.REC:
                        try:
                            io = io._IO__fields(io)
                            continue
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = ([exception], [])
                            break
                    if tag == IOTag.ACQUIRE:
                        lock = io._IO__fields
                        try:
                            if lock.acquire(fiber):
                                arg_tag = ResultTag.OK
                                arg_value = None
                                break
                            else:
                                lock.wait(fiber)
                                fiber._context = context
                                fiber._cont = cont
                                fiber._arg_tag = ResultTag.OK
                                fiber._arg_value = None
                                return False
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = ([exception], [])
                            break
                    if tag == IOTag.RELEASE:
                        lock = io._IO__fields
                        try:
                            lock.release(self.queue.appendleft)
                            arg_tag = ResultTag.OK
                            arg_value = None
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = ([exception], [])
                        break
                    arg_tag = ResultTag.PANIC
                    arg_value = ([MatchError(f"{io} should be an IO")], [])
                    break

        except Exception as exception:
            fiber.result = Panic([exception], [])
            finish_fiber(fiber)
            return False


@final
class Lock:

    __slots__ = "_lock", "_fiber", "_nb_taken", "_waiting"

    def __init__(self):
        self._lock = threading.Lock()
        self._fiber = None
        self._nb_taken = 0
        self._waiting = Queue()

    def acquire(self, fiber) -> bool:
        with self._lock:
            if self._fiber is None:
                self._nb_taken = 1
                self._fiber = fiber
                return True
            if self._fiber is fiber:
                self._fiber = fiber
                self._nb_taken += 1
                return True
            return False

    def wait(self, fiber: Fiber[Any, Any, Any]) -> None:
        self._waiting.put(fiber)

    def release(self, resume: Callable[[Fiber], None]) -> None:
        with self._lock:
            self._nb_taken -= 1
            if self._nb_taken == 0:
                if self._waiting.empty():
                    self._fiber = None
                    return
                self._fiber = self._waiting.get()
                self._nb_taken = 1
                resume(self._fiber)


@final
class Semaphore:

    __slots__ = "_lock", "_tokens", "_waiting"

    def __init__(self, tokens: int):
        self._lock = threading.Lock()
        self._tokens = tokens
        self._waiting = Queue()

    def acquire(self, fiber: Fiber[Any, Any, Any]) -> bool:
        with self._lock:
            if self._tokens > 0:
                self._tokens -= 1
                return True
            return False

    def wait(self, fiber: Fiber[Any, Any, Any]) -> None:
        self._waiting.put(fiber)

    def release(self, resume: Callable[[Fiber[Any, Any, Any]], None]) -> None:
        with self._lock:
            if self._waiting.empty():
                self._tokens += 1
                return
            resume(self._waiting.get())
