# Failures

All the computation we have seen until now were successful.
We will now see how `IO`'s failure management works.
But before, I need to present you the `Result[E,A]` type.

## The `Result[E,A]` type

`Result[E,A]` represent the result of a computation.
A computation can either be successful, returning a value of type `A`,
or have failed on some expected errors of type `E`, or failed one some
unexpected exceptions.
`IO` and `Result` make a distinction between expected failures,
called *errors*, and unexpected failures, called *panics*.

For an operating system, an application crashing is an expected error.
A well designed operating system is expected to be prepared to such
errors. It has to deal with situations like this nicely and continue
running normally. Errors are part of the normal life of your program.
An error means that some operation failed but your program is still
healthy.

On the contrary, memory corruption inside the kernel is an unexpected
error. The system can not continue running normally. The failure may
have made the computation dangerous and/or the result wrong. The only
option is terminating the system as smoothly as possible.
Panics should never happen, but sometimes even the most improbable events
do occur. When panics happen, consider your computation lost. Terminate
it doing as little damage as possible.

*Raffiot* is designed to **report all encountered failures**. Failures are
never silently ignored but exposed via the `Result` type. This is why the
`Result` type works with lists of domain failures (*errors*) and unexpected
failures (*panics*). In addition, *Raffiot* saves the stack trace of every
exception encountered so that you always know where the exception was risen,
even with multiprocessing!

For the rest of this section, you will need these imports.

```python
>>> from raffiot import *
```

### `Ok(success:A)` : A Success

When a computation successfully return some value `a` of type `A`,
it actually returns the value `Ok(a)` of type `Result[E,A]`. The
value `a` can be obtained by `Ok(a).success`:

```python
>>> from typing import Any
>>> r : Result[Any,int] = Ok(5)
>>> r
Ok(success=5)
>>> r.success
5
```

### `Errors(errors:List[E])` : Some Expected Failures

When a computation fail because of an error `e` of type `E`,
it actually return a value `Errors(errors=[e])` of type `Result[E,Any]`.
The type `E` can be any type you want. Choose as type `E` a type
that fit your business domain errors the best.
The list of all errors encountered can be obtained by `Errors([e]).errors`:

```python
>>> r : Result[int,Any] = Errors([5])
>>> r
Errors(errors=[5])
>>> r.errors
5
```

Note that you must **ALWAYS** provide a **list** to `Errors! So, to avoid bugs,
please use the method `result.error(e: E) -> Result[E,Any]` when you want to
raise a single error or `result.errors(e1:E, e2:E, ...) -> Result[E,Any]` when
you want to raise several errors:

```python
>>> result.error(5)
Errors(errors=[5])
>>> result.errors(5, 2)
Errors(errors=[5, 2])
```

### Traced Exceptions: Never lose a stack trace!

*Raffiot* lift every exception encountered during a computation into a
`TracedException`. This is a very simple type:

```python
@dataclass
class TracedException(Exception):
    exception: Exception
    stack_trace: str
```

It packs an exception with its stack trace. To the best of our knowledge, Python
does not seem to store the stack trace with the exception but only keep the stack
trace of the last one encountered. This is a huge problem because in a parallel
or concurrent computation, many exception can be raised. If you use
multiprocessing, they can even be raises on a different process!

When you have an exception `exn`, there are two ways to build a `TracedException`:

- If you are in the `except` clause of the `try-except` block that caught the
  exception `exn`, you can call the static method
  `TracedException.in_except_clause(exn)` to capture the stack trace of the
  exception. **Note that it only works in the except clause!**
- If you are not in the `except` clause of the `try-except` block that caught the
  exception `exn`, you can call the static method
  `TracedException.with_stack_trace(exn)` to capture the current stack trace.

### `Panic(exceptions: List[TracedException], errors: List[E])` : Some Unexpected Failures

When a computation fail because of a exception `exn`,
it actually return a value
`Panic(exceptions=[TracedException(exception=exn, stack_trace="...")],errors=[])`
of type `Result[Any,Any]`.
Note that a `Panic` stores a list of traced exceptions and not a single one.
The original exception `exn` can be obtained by
`Panic([TracedException(exn)],[]).exceptions[0].exception` and its stack trace
by `Panic([TracedException(exn)],[]).exceptions[0].stack_trace`.


```python
>>> r : Result[Any,Any] = Panic(
...   exceptions=[TracedException.with_stack_trace(Exception("BOOM!"))],
...   errors=[]
... )
>>> r
Panic(
  exceptions=[TracedException(exception=Exception('BOOM!'), stack_trace='...')],
  errors=[]
)
>>> r.exceptions
[TracedException(exception=Exception('BOOM!'), stack_trace='...')]
>>> r.errors
[]
>>> r.exceptions[0].exception
Exception('BOOM!')
>>> print(r.exceptions[0].stack_trace)
  File "<stdin>", line 2, in <module>
  File "/raffiot.py/raffiot/utils.py", line 63, in with_stack_trace
    return TracedException(exception=exn, stack_trace="".join(format_stack()))
```

When an unexpected failures happen, there may have already been some expected
failures. This is why the `Panic` case have a list of errors slot. The list
of exceptions should never be empty (otherwise it shouldn't be a `Panic`).
Using the `Panic` constructor is error-prone as you **must always provide lists**
for the `exceptions`and `errors`field. Instead you can use the helper function
`result.panic`:


``` python
>>> result.panic(Exception("BOOM"))
Panic(exceptions=[TracedException(exception=Exception('BOOM'), stack_trace='...')], errors=[])
>>> result.panic(Exception("BOOM 1"), Exception("BOOM 2"))
Panic(exceptions=[
    TracedException(exception=Exception('BOOM 1'), stack_trace='...'),
    TracedException(exception=Exception('BOOM 2'), stack_trace='...')
  ],
  errors=[])
>>> result.panic(Exception("BOOM 1"), Exception("BOOM 2"), errors=[5,2])
Panic(exceptions=[
    TracedException(exception=Exception('BOOM 1'), stack_trace='...'),
    TracedException(exception=Exception('BOOM 2'), stack_trace='...')
  ],
  errors=[5, 2]
)
```

### `fold` : transforming a `Result[E,A]`

To transform a `Result[E,A]`, use the method `fold`. It takes
as argument three functions. The first one is called when the
result is an `Ok`. The second is called when it are some `Errors`.
The third is called on `Panic`. When called, each of
these function receive as argument the value/list of errors/list of traced
exceptions and errors (depending on the case) stored in the result:

```python
>>> Ok(5).fold(
...   lambda s: f"success: {s}",
...   lambda e: f"errors: {e}",
...   lambda p,e: f"traced exeptions: {p}, errors: {e}"
... )
'success: 5'
>>> result.errors(7,5).fold(
...   lambda s: f"success: {s}",
...   lambda e: f"errors: {e}",
...   lambda p,e: f"traced exeptions: {p}, errors: {e}"
... )
'error: [7,5]'
>>> result.panic(Exception("BOOM 1"), Exception("BOOM 2"), errors=[5,2]).fold(
...   lambda s: f"success: {s}",
...   lambda e: f"errors: {e}",
...   lambda p,e: f"traced exeptions: {p}, errors: {e}"
... )
'traced exeptions: [
    TracedException(exception=Exception(\'BOOM 1\'), stack_trace=\'...\'),
    TracedException(exception=Exception(\'BOOM 2\'), stack_trace=\'...\')
  ],
  errors: [5, 2]'
```

### `raise_on_panic` : reporting panics as exceptions

*Raffiot*'s functions and methods never raise exception
but instead return a `Panic`. When you need a failed
computation to raise the exception, call `raise_on_panic`
on the result:  

```python
>>> Ok(5).raise_on_panic()
Ok(success=5)
>>> result.error(7).raise_on_panic()
Errors(errors=[7])
>>> result.panic(Exception("BOOM!")).raise_on_panic()
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/dev/raffiot.py/raffiot/result.py", line 441, in raise_on_panic
    raise MultipleExceptions.merge(*self.exceptions, errors=self.errors)
raffiot.utils.TracedException: BOOM!
  File "<stdin>", line 1, in <module>
  File "/dev/raffiot.py/raffiot/result.py", line 559, in panic
    exceptions=TracedException.ensure_list_traced(exceptions),
  File "/dev/raffiot.py/raffiot/utils.py", line 76, in ensure_list_traced
    return [cls.ensure_traced(exn) for exn in exceptions]
  File "/dev/raffiot.py/raffiot/utils.py", line 76, in <listcomp>
    return [cls.ensure_traced(exn) for exn in exceptions]
  File "/dev/raffiot.py/raffiot/utils.py", line 70, in ensure_traced
    return cls.with_stack_trace(exception)
  File "/dev/raffiot.py/raffiot/utils.py", line 66, in with_stack_trace
    return TracedException(exception=exn, stack_trace="".join(format_stack()))
```

`raise_on_panic` and `unsafe_get` are
**the only functions/methods raising exceptions**.
Never expect other functions to raise exception on failures, they
will return an `Errors` or `Panic` instead:

```python
>>> main : IO[None,None,None] = io.panic(Exception("BOOM!"))
>>> main.run(None)
Panic(exceptions=[
  TracedException(exception=Exception('BOOM!'), stack_trace='...')
  ], errors=[])
>>> main.run(None).raise_on_panic()
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/raffiot.py/raffiot/result.py", line 441, in raise_on_panic
    raise MultipleExceptions.merge(*self.exceptions, errors=self.errors)
raffiot.utils.TracedException: BOOM!
  File "<stdin>", line 1, in <module>
  File "/raffiot.py/raffiot/io.py", line 467, in panic
    TracedException.ensure_list_traced(exceptions),
  File "raffiot.py/raffiot/utils.py", line 76, in ensure_list_traced
    return [cls.ensure_traced(exn) for exn in exceptions]
  File "raffiot.py/raffiot/utils.py", line 76, in <listcomp>
    return [cls.ensure_traced(exn) for exn in exceptions]
  File "raffiot.py/raffiot/utils.py", line 70, in ensure_traced
    return cls.with_stack_trace(exception)
  File "/raffiot.py/raffiot/utils.py", line 66, in with_stack_trace
    return TracedException(exception=exn, stack_trace="".join(format_stack()))
```

## Errors: Expected failures in IO

`IO` has built-in support errors. Remember that we call error the
expected failures. Errors can be of any type you want. You should
usually take as error type the one that fit your business domain
errors the best. **In the type `IO[R,E,A]`, `E` is the type of errors**.

### `error` : this failure was expected, we're still in safe zone!

To raise an error, simply call `io.error`:

```python
>>> from typing import Any, List

>>> main_str : IO[None,str,Any] = io.error("Oops")
>>> main_str.run(None)
Errors(errors=['Oops'])

>>> main_int : IO[None,int,Any] = io.error(5)
>>> main_int.run(None)
Errors(errors=[5])

>>> main_list : IO[None,List[int],Any] = io.error([1,2,3])
>>> main_list.run(None)
Error(error=[[1, 2, 3]])
```

### `errors` : raising several errors at once.

To raise several errors, simply call `io.errors`:

```python
>>> from typing import Any, List

>>> main_str : IO[None,str,Any] = io.errors("Oops1", "Oops2")
>>> main_str.run(None)
Errors(errors=['Oops1', 'Oops2'])

>>> main_int : IO[None,int,Any] = io.errors(5,7)
>>> main_int.run(None)
Errors(errors=[5, 7])
```

**But beware**: the iterable arguments will be treated as collections of errors
and not a single error. For example the error `[1,2,3]` will be treated by
`io.errors` as three errors `1`, `2` and `3`. So when you want to raise iterable
errors, use `io.error` instead:

```python
>>> main_list : IO[None,List[int],Any] = io.errors([1,2,3])
>>> main_list.run(None)
Errors(errors=[1, 2, 3])
```

### `catch` : reacting to expected failures to continue.

To react to errors, just call the method `catch`.
It is very similar to a `try-exept` block.
It takes as argument a function called the *error handler*.
When the computation fails because of some errors `le: List[E]`,
the error handler is called with `le` as argument.
The result is then the error handler's result.

```python
>>> def main(i: int) -> IO[None,str,int]:
...   return (
...   io.error(i)
...   .catch(lambda x:
...     io.pure(2*x[0])
...     if x[0] % 2 == 0
...     else io.error("Oops"))
... )
>>> main(5).run(None)
Errors(errors=['Oops'])
>>> main(6).run(None)
Ok(success=12)
```

If the computation is successful, or if it failed on a panic,
then `catch` has no effect.
Note that the error handler can itself raise errors and panics.

### `map_error` : transforming expected failures.

It is often useful to transform an error. For example you may
want to add some useful information about the context: what
was the request that led to this error, what were the arguments
of the operation that failed, etc.

To transform an error, call `map_error`. It behaves like `map`,
but on errors:

```python
>>> main : IO[None,int,Any] = io.error([1,2]).map_error(lambda l: l[0] + l[1])
>>> main.run(None)
Errors(errors=[3])
```

If the computation is successful or if it fails on a panic,
then `map_error` has no effect.

## Panics: Unexpected Failures in IO

The type of panics is always the Python type of exception `Exception`.
Panics can be raise either manually, by calling `io.panic`, or
when `run` encounters an exception.
**The method `run` on `IO` never raises exceptions!**
Every exception `p` raised during the execution of `run` are caught and
transformed into panics `result.panic(p)`.

### **ALL** exceptions are caught

All the functions and method that accept functions as arguments
run them inside a `try-except` block to catch every raised exception.
All exception caught this way are transformed into panics:

```python
>>> main : IO[None,None,float] = io.pure(0).map(lambda x: 1/x)
>>> main.run(None)
Panic(exceptions=[TracedException(
    exception=ZeroDivisionError('division by zero'),
    stack_trace='...')
  ], errors=[])
```

Remember that panics are unexpected failures and unexpected failures
should never happen. In an ideal world you should never give to
`map`, `flat_map`, `defer` and others functions that may raise exceptions.
In an ideal world, panics would never occur. But we do not live in an
ideal world, so `map`, `flat_map` and others covers your back by
catching any exception for your own safety.

### `panic` : something went terribly wrong, we're in **unsafe** zone.

It is sometimes useful to manually raise panics. For example when
you encounter a problematic situation you though were impossible
but still did happen. If your program is not designed to handle this
situation, you should raise a panic.

```python
>>> main : IO[None,None,Any] = io.panic(Exception("BOOM!"))
>>> main.run(None)
Panic(exceptions=[TracedException(
    exception=Exception('BOOM!'),
    stack_trace='...')
  ], errors=[])
```

The function `io.panic` accepts several exceptions as arguments and even
domain errors with the `errors` keyword argument.

### `recover` : **stopping** the computation safely after an unexpected failure.

Even in case of a panic, you have a chance to perform some emergency
actions to recover. For example, you may want to restart the computation
on panics. To react to panics, just call `recover`.
It is very similar to a `try-exept` block.
It takes as argument a function, called the *panic handler*.
If the computation fails because of a panic with exceptions
`lexn: List[TracedException]`,
and errors `lerr: List[E]`, then the panic handler is called with `lexn` as
first argument and `lerr`as its second argument.
The result is then the the handler's result.

```python
>>> main : IO[None,None,Any] = (
...   io.panic(Exception("BOOM!"))
...   .recover(lambda lexn, lerr: io.pure(
...     f"Recovered from traced exceptions: {lexn} and errors {lerr}")
...   )
... )
>>> main.run(None)
Ok(success='Recovered from traced exceptions:[TracedException('
  'exception=Exception(\'BOOM!\'), stack_trace=\'...')] and errors []')
```

### `map_panic` : transforming traced exceptions.

It is often useful to transform a panic. For example you may
want to add some useful information about the context: what
was the request that led to this error, what were the arguments
of the operation that failed, etc.

To transform all the exceptions of a `Panic`, call `map_panic`.
It behaves like `map`, but on exceptions contained in `Panic`:

```python
>>> main : IO[None, None, None] = (
...   io.pure(0)
...   .map(lambda x: 1/x)
...   .map_panic(lambda traced_exception:
...     TracedException(
...       exception=Exception("BOOM"),
...       stack_trace=traced_exception.stack_trace
...     )
...   )
... )
>>> main.run(None)
Panic(exceptions=[TracedException(exception=Exception('BOOM'),
 stack_trace='...')], errors=[])
```

### More tools

Here are some very useful functions. They can all be expressed using the
functions and methods seen above but they deserve being seeing in details:

### `attempt` : failures as values.

The method `attempt` transform an `IO[R,E,A]` into
`IO[R,None,Result[E,A]]`. If the original computation is successful,
the transformed one returns an `Ok(Ok(...))`. If the original computation fails
on some errors, the transformed one returns `Ok(Errors(...))`.
If the original computation fails on a panic, the transformed one returns `Ok(Panic(...))`:


```python
>>> io_ok : IO[None,None,Result[None,int]] = io.pure(5).attempt()
>>> io_ok.run(None)
Ok(success=Ok(success=5))
>>> io_error : IO[None,None,Result[int,None]] = io.error(7).attempt()
>>> io_error.run(None)
Ok(success=Errors(errors=[7]))
>>> io_panic : IO[None,None,Result[None,None]] = io.panic(Exception("BOOM!")).attempt()
>>> io_panic.run(None)
Ok(success=Panic(exceptions=[TracedException(exception=Exception('BOOM!'),
 stack_trace='...')], errors=[]))
```

It is hugely useful when you want to do different actions depending
on the result of a computation. Calling `attempt` and `flat_map` is
easier than combining `flat_map`, `catch` and `recover` correctly.

### `from_result` : from `Result[E,A]` to `IO[None,E,A]`

The function `io.from_result` does almost the opposite of `attempt`.
It transform a `Result[E,A]` into the corresponding `IO[None,E,A]`:

```python
>>> io_ok : IO[None,None,int] = io.from_result(Ok(5))
>>> io_ok.run(None)
>>> io_error : IO[None,int,None] = io.from_result(result.error(5))
>>> io_error.run(None)
Errors(errors=[5])
>>> io_panic : IO[None,None,None] = io.from_result(result.panic(
...   TracedException(Exception("BOOM!"),"")))
>>> io_panic.run(None)
Panic(exceptions=[TracedException(exception=Exception('BOOM!'),
  stack_trace='')], errors=[])
```

`from_result` is often useful after an `attempt` to restore the state
of the computation.

### `finally_` : doing something unconditionally.

The method `finally_` is the *finally* clause of a *try-except-finally*.
It executed a `IO` after the current one, discard its result and
restore the result of the current one. The `IO` executed after is actually
a function taking as argument a `Result[R,E]` from the preceding `IO`.
It enables to perform different actions depending on the result of the first
computation:


```python
>>> io.pure(5).finally_(lambda r: io.defer(print, f"Hello, result is {r}")).run(None)
Hello, result is Ok(success=5)
Ok(success=5)
>>> io.error(7).finally_(lambda r: io.defer(print, f"Hello, result is {r}")).run(None)
Hello, result is Errors(errors=[7])
Errors(errors=[7])
>>> io.panic(Exception("BOOM!")).finally_(lambda r: io.defer(print, f"Hello, result is {r}")).run(None)
Hello, result is Panic(exceptions=[TracedException(exception=Exception('BOOM!'),
  stack_trace='...')], errors=[])
Panic(exceptions=[TracedException(exception=Exception('BOOM!'),
  stack_trace='...')], errors=[])
```

### `on_failure` : reaction to both errors and panics.

Calling both methods `catch` and `recover` is sometimes annoying.
When you need to react to any failure, call `on_failure`. It
takes as argument a function called the *failure handler*.
When a computation fails, it calls the failure handler with the
failure passed as argument as a `Result[E,None]`.

This `Result[E,None]` is never `Ok` because `on_failure` call the handler
only on failures.

```python
>>> io.pure(5).on_failure(lambda x: io.pure(12)).run(None)
Ok(success=5)
>>> io.error(7).on_failure(lambda x: io.pure(12)).run(None)
Ok(success=12)
>>> io.panic(Exception("BOOM!")).on_failure(lambda x: io.pure(12)).run(None)
Ok(success=12)
```
