"""
This an INTERNAL module.
You should NEVER use anything from this module directly.
Use IO instead!
"""

from __future__ import annotations
from typing_extensions import final
from raffiot import result, _MatchError
from raffiot.result import Ok, Error, Panic
from concurrent.futures import Executor, wait
from enum import Enum
from queue import Queue
import threading


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
    REC = 25  # FUN


class ContTag(Enum):
    MAP = 0  # FUN
    FLATMAP = 1  # CONTEXT HANDLER
    FLATTEN = 2  # CONTEXT
    SEQUENCE = 3  # CONTEXT IOS
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


@final
class Monitor:
    """
    Used to know if there is still some futures running.
    Every future created when running fibers must be registered
    in the monitor.
    The monitor waits until there is no more future running.
    """

    __slots__ = ["__executor", "__lock", "__queue"]

    def __init__(self, executor: Executor):
        self.__executor = executor
        self.__lock = threading.Lock()
        self.__queue = []

    def register_future(self, future):
        with self.__lock:
            self.__queue.append(future)

    def wait_for_completion(self):
        ok = True
        while ok:
            with self.__lock:
                futures = self.__queue
                self.__queue = []
            wait(futures)
            with self.__lock:
                ok = not (not self.__queue)


@final
class Fiber:
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

    def __init__(self, io, context, executor: Executor, monitor: Monitor):
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

    def __schedule(self):
        self.__monitor.register_future(self.__executor.submit(self.__step))

    def __finish(self):
        with self.__finish_lock:
            self.finished = True
            while not self.__callbacks.empty():
                fiber, index = self.__callbacks.get()
                fiber.__run_callback(index, self.result)

    def __add_callback(self, fiber, index):
        with self.__finish_lock:
            if self.finished:
                fiber.__run_callback(index, self.result)
            else:
                self.__callbacks.put((fiber, index))

    def __run_callback(self, index, res):
        with self.__waiting_lock:
            self.__waiting[index] = res
            self.__nb_waiting -= 1
            if self.__nb_waiting == 0:
                from raffiot.io import IO

                self.__io = IO(IOTag.PURE, self.__waiting)
                self.__waiting = None
                self.__schedule()

    @classmethod
    def run(cls, io, context, executor):
        monitor = Monitor(executor)
        fiber = Fiber(io, context, executor, monitor)
        fiber.__schedule()
        monitor.wait_for_completion()
        return fiber.result

    @classmethod
    def run_async(cls, io, context, executor):
        return executor.submit(cls.run, io, context, executor)

    def __step(self):
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
                        ios = iter(io._IO__fields)
                        try:
                            io = next(ios)
                        except StopIteration:
                            arg_tag = ResultTag.OK
                            arg_value = None
                            break
                        except Exception as exception:
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                        cont.append(ios)
                        cont.append(context)
                        cont.append(ContTag.SEQUENCE)
                        continue
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
                        from raffiot.io import IO

                        self.__io = IO(IOTag.PURE, None)
                        self.__context = context
                        self.__cont = cont
                        self.__schedule()
                        return
                    if tag == IOTag.ASYNC:
                        from raffiot.io import from_result

                        def callback(r):
                            self.__io = from_result(r)
                            self.__schedule()

                        self.__context = context
                        self.__cont = cont
                        try:
                            self.__monitor.register_future(
                                io._IO__fields[0](
                                    context,
                                    self.__executor,
                                    callback,
                                    *io._IO__fields[1],
                                    **io._IO__fields[2],
                                )
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
                            fiber.__schedule()
                        arg_tag = ResultTag.OK
                        break
                    if tag == IOTag.WAIT:
                        fibers = io._IO__fields
                        if not fibers:
                            arg_tag = ResultTag.OK
                            arg_value = []
                            break
                        self.__waiting = [None for _ in fibers]
                        self.__nb_waiting = len(fibers)
                        for index, fib in enumerate(fibers):
                            fib.__add_callback(self, index)
                        return
                    if tag == IOTag.REC:
                        try:
                            io = io._IO__fields(io)
                            continue
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
                            try:
                                io = next(cont[-2])
                            except StopIteration:
                                cont.pop()  # CONTEXT
                                cont.pop()  # IOS
                                continue
                            except Exception as exception:
                                cont.pop()  # CONTEXT
                                cont.pop()  # IOS
                                arg_tag = ResultTag.PANIC
                                arg_value = exception
                                continue
                            context = cont[-1]
                            cont.append(ContTag.SEQUENCE)
                            break
                        # CLEANING CONT
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
                        self.__finish()
                        return
                    arg_tag = ResultTag.PANIC
                    arg_value = Panic(_MatchError(f"Invalid cont {cont + [tag]}"))
        except Exception as exception:
            self.finished = True
            self.result = Panic(exception)
