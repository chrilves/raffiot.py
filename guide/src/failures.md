# Failures

All the computation we have seen until now were successful.
We will now see how `IO`'s failure management works.
But before, I need to present you the `Result[E,A]` type.

## The `Result[E,A]` type

`Result[E,A]` represent the result of a computation.
A computation can either be successful, returning a value of type `A`,
or failed with an expected error of type `E`, or failed with an
unexpected exception.
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

For the rest of this section, you will need these imports.

```python
>>> from raffiot import *
```

### `Ok(success:A)` : A Success


When a computation successfully return some value `a` of type `A`,
it actually returns the value `Ok(a)` of type `Result[E,A]`. The
value `a` can be obtained by `Ok(a).success`:

```python
>>> result : Result[Any,int] = Ok(5)
>>> result
Ok(success=5)
>>> result.success
5
```

### `Error(error:E)` : An Expected Failure

When a computation fail because of an error `e` of type `E`,
it actually return a value `Error(e)` of type `Result[E,Any]`.
The type `E` can be any type you want. Choose as type `E` a type
that fit your business domain errors the best.
The error `e` can be obtained by `Error(e).error`:

```python
>>> result : Result[int,Any] = Error(5)
>>> result
Error(error=5)
>>> result.error
5
```

### `Panic(exception:Exception)` : An Unexpected Failure

When a computation fail because of an unexpected failure,
it actually return a value `Panic(p)` of type `Result[Any,Any]`
where `p` is the exception encountered.
The exception type is always the Python exception type `Exception`.
The exception `p` can be obtained by `Panic(p).exception`:


```python
>>> result : Result[Any,Any] = Panic(Exception("BOOM!"))
>>> result
Panic(exception=Exception('BOOM!'))
>>> result.exception
Exception('BOOM!')
```

### `fold` : transforming a `Result[E,A]`

To transform a `Result[E,A]`, use the method `fold`. It takes
as argument three functions. The first one is called when the
result is an `Ok`. The second is called when it is an `Error`.
The third is called when it is a `Panic`. When called, each of
these function receive as argument the value/error/exception
(depending on the case) stored in the result:

```python
>>> Ok(5).fold(
...   lambda s: f"success: {s}",
...   lambda e: f"error: {e}",
...   lambda p: f"exeption: {p}"
... )
'success: 5'
>>> Error(7).fold(
...   lambda s: f"success: {s}",
...   lambda e: f"error: {e}",
...   lambda p: f"exeption: {p}"
... )
'error: 7'
>>> Panic(Exception("BOOM!")).fold(
...   lambda s: f"success: {s}",
...   lambda e: f"error: {e}",
...   lambda p: f"exeption: {p}"
... 
'exeption: BOOM!'
```

### `raise_on_panic` : reporting panics as exceptions

*Raffiot*'s functions and methods never raise exception
but instead return a `Panic`. When you need a failed
computation to raise the exception, call `raise_on_panic`
on the result:  

```python
>>> Ok(5).raise_on_panic()
Ok(success=5)
>>> Error(7).raise_on_panic()
Error(error=7)
>>> Panic(Exception("BOOM!")).raise_on_panic()
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/home/tof/dev/raffiot.py/raffiot/result.py", line 406, in raise_on_panic
    raise self.exception
Exception: BOOM!
```

`raise_on_panic` is **the only function/method raising exceptions**.
Never expect other functions to raise exception on failures, they
will return an `Error` or `Panic` instead:

```python
>>> main : IO[None,None,None] = io.panic(Exception("BOOM!"))
>>> main.run(None)
Panic(exception=Exception('BOOM!'))
>>> main.run(None).raise_on_panic()
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/home/tof/dev/raffiot.py/raffiot/result.py", line 406, in raise_on_panic
    raise self.exception
Exception: BOOM!
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
Error(error='Oops')

>>> main_int : IO[None,int,Any] = io.error(5)
>>> main_int.run(None)
Error(error=5)

>>> main_list : IO[None,List[int],Any] = io.error([1,2,3])
>>> main_list.run(None)
Error(error=[1, 2, 3])
```

### `catch` : reacting to expected failures to continue.

To react to errors, just call the method `catch`.
It is very similar to a `try-exept` block.
It takes as argument a function called the *error handler*.
When the computation fails because of an error `e`,
the error handler is called with `e` as argument.
The result is then the error handler's result.

```python
>>> def main(i: int) -> IO[None,str,int]:
...   return (
...   io.error(i)
...   .catch(lambda x:
...     io.pure(2*x)
...     if x % 2 == 0
...     else io.error("Oops"))
... )
>>> main(5).run(None)
Error(error='Oops')
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
Error(error=3)
```

If the computation is successful or if it fails on a panic,
then `map_error` has no effect.

## Panics: Unexpected Failures in IO

The type of panics is always the Python type of exception `Exception`.
Panics can be raise either manually, by calling `io.panic`, or
when `run` encounters an exception.
**The method `run` on `IO` never raises exceptions!**
Every exception `p` raised during the execution of `run` are caught and
transformed into panics `Panic(p)`.

### **ALL** exceptions are caught

All the functions and method that accept functions as arguments
run them inside a `try-except` block to catch every raised exception.
All exception caught this way are transformed into panics:

```python
>>> main : IO[None,None,float] = io.pure(0).map(lambda x: 1/x)
>>> main.run(None)
Panic(exception=ZeroDivisionError('division by zero'))
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
Panic(exception=Exception('BOOM!'))
```

### `recover` : **stopping** the computation safely after an unexpected failure.

Even in case of a panic, you have a chance to perform some emergency
actions to recover. For example, you may want to restart the computation
on panics. To react to panics, just call `recover`.
It is very similar to a `try-exept` block.
It takes as argument a function, called the *panic handler*.
If the computation fails because of a panic `p`, then the panic handler
is called with `p` as argument.
The result is then the the handler's result.

```python
>>> main : IO[None,None,Any] = (
...   io.panic(Exception("BOOM!"))
...   .recover(lambda p: io.pure("Recovered from " + str(p)))
... )
>>> main.run(None)
Ok(success='Recovered from BOOM!')
```

### `map_panic` : transforming an unexpected failure.

It is often useful to transform a panic. For example you may
want to add some useful information about the context: what
was the request that led to this error, what were the arguments
of the operation that failed, etc.

To transform an error, call `map_panic`. It behaves like `map`,
but on panics:

```python
>>> main : IO[None, None, None] = (
...   io.pure(0)
...   .map(lambda x: 1/x)
...   .map_panic(lambda exception: Exception("BOOM"))
... )
>>> main.run(None)
Panic(exception=Exception('BOOM'))
```

### More tools

Here are some very useful functions. They can all be expressed using the
functions and methods seen above but they deserve being seeing in details:

### `attempt` : failures as values.

The method `attemp` transform an `IO[R,E,A]` into
`IO[R,None,Result[E,A]]`. If the original computation is successful,
the transformed one returns an `Ok`. If the original computation fails
on an error `e`, the transformed one returns `Error(e)`. If the original
computation fails on a panic `p`, the transformed one returns `Panic(p)`:


```python
>>> io_ok : IO[None,None,Result[None,int]] = io.pure(5).attempt()
>>> io_ok.run(None)
Ok(success=Ok(success=5))
>>> io_error : IO[None,None,Result[int,None]] = io.error(7).attempt()
>>> io_error.run(None)
Ok(success=Error(error=7))
>>> io_panic : IO[None,None,Result[None,None]] = io.panic(Exception("BOOM!")).attempt()
>>> io_panic.run(None)
Ok(success=Panic(exception=Exception('BOOM!')))
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
>>> io_error : IO[None,int,None] = io.from_result(Error(5))
>>> io_error.run(None)
Error(error=5)
>>> io_panic : IO[None,None,None] = io.from_result(Panic(Exception("BOOM!")))
>>> io_panic.run(None)
Panic(exception=Exception('BOOM!'))
```

`from_result` is often useful after an `attempt` to restore the state
of the computation.

### `finally_` : doing something unconditionally.

The method `finally_` is the *finally* clause of a *try-except-finally*.
It executed an `IO` after the current one, discard its result and
restore the result of the current one:

```python
>>> pure(5).finally_(io.defer(print, "Hello")).run(None)
Hello
Ok(success=5)
>>> error(7).finally_(io.defer(print, "Hello")).run(None)
Hello
Error(error=7)
>>> panic(Exception("BOOM!")).finally_(io.defer(print, "Hello")).run(None)
Hello
Panic(exception=Exception('BOOM!'))
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
>>> pure(5).on_failure(lambda x: pure(12)).run(None)
Ok(success=5)
>>> error(7).on_failure(lambda x: pure(12)).run(None)
Ok(success=12)
>>> panic(Exception("BOOM!")).on_failure(lambda x: pure(12)).run(None)
Ok(success=12)
```