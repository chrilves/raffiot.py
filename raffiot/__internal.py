"""
This an INTERNAL module.
You should NEVER use anything from this module directly.
Use IO instead!
"""

from __future__ import annotations
from typing_extensions import final
from raffiot import result, _MatchError
from raffiot.result import Ok, Error, Panic
from concurrent.futures import Executor
from enum import Enum


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
    READ = 8  #
    CONTRA_MAP_READ = 9  # FUN MAIN
    ERROR = 10  # ERROR
    CATCH = 11  # MAIN HANDLER
    MAP_ERROR = 12  # MAIN      FUN
    PANIC = 13  # EXCEPTION
    RECOVER = 14  # MAIN HANDLER
    MAP_PANIC = 15  # MAIN FUN
    YIELD = 16  #
    ASYNC = 17  # DOUBLE_NEGATION
    EXECUTOR = 18  #
    CONTRA_MAP_EXECUTOR = 19  # MAIN FUN


@final
class ContTag(Enum):
    ID = 0  #
    MAP = 1  # FUN
    FLATMAP = 2  # CONTEXT HANDLER
    FLATTEN = 3  # CONTEXT
    SEQUENCE = 4  # CONTEXT IOS
    ZIP = 5  # CONTEXT IOS NB_IOS NEXT_IO_INDEX
    CATCH = 6  # CONTEXT HANDLER
    MAP_ERROR = 7  # FUN
    RECOVER = 8  # CONTEXT HANDLER
    MAP_PANIC = 9  # FUN


@final
class ResultTag(Enum):
    OK = 0
    ERROR = 1
    PANIC = 2


@final
class FiberStatus(Enum):
    RUNNING = 0
    SUSPENDED = 1
    FINISHED = 2


@final
class Fiber:
    __slots__ = ["io", "context", "cont", "executor", "status", "future", "result"]

    @final
    def __init__(self, io, context, executor: Executor):
        self.io = io
        self.context = context
        self.cont = [ContTag.ID]
        self.executor = executor
        self.status = FiberStatus.RUNNING
        self.future = None
        self.result = None

    @final
    def schedule(self):
        self.future = self.executor.submit(self.step)

    @final
    def step(self):
        context = self.context
        io = self.io
        cont = self.cont

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
                        ios = io._IO__fields
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

                        self.io = IO(IOTag.PURE, None)
                        self.context = context
                        self.cont = cont
                        self.schedule()
                        return
                    if tag == IOTag.ASYNC:
                        from raffiot.io import from_result

                        def callback(r):
                            self.status = FiberStatus.RUNNING
                            self.io = from_result(r)
                            self.schedule()

                        self.status = FiberStatus.SUSPENDED
                        self.context = context
                        self.cont = cont
                        try:
                            self.future = io._IO__fields(
                                context, self.executor, callback
                            )
                            return
                        except Exception as exception:
                            self.status = FiberStatus.RUNNING
                            arg_tag = ResultTag.PANIC
                            arg_value = exception
                            break
                    if tag == IOTag.EXECUTOR:
                        arg_tag = ResultTag.OK
                        arg_value = self.executor
                        break
                    if tag == IOTag.CONTRA_MAP_EXECUTOR:
                        try:
                            new_executor = io._IO__fields[0](self.executor)
                            if not isinstance(new_executor, Executor):
                                raise Exception(f"{new_executor} is not an Executor!")
                            self.executor = new_executor
                            io = io._IO__fields[1]
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
                    if tag == ContTag.ID:
                        self.status = FiberStatus.FINISHED
                        if arg_tag == ResultTag.OK:
                            self.result = Ok(arg_value)
                            return
                        if arg_tag == ResultTag.ERROR:
                            self.result = Error(arg_value)
                            return
                        if arg_tag == ResultTag.PANIC:
                            self.result = Panic(arg_value)
                            return
                        self.result = Panic(_MatchError(f"Wrong result tag {arg_tag}"))
                        return
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
                    arg_tag = ResultTag.PANIC
                    arg_value = Panic(_MatchError(f"Invalid cont {cont + [tag]}"))
        except Exception as exception:
            self.status = FiberStatus.FINISHED
            self.result = Panic(exception)
