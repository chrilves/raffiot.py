# First Steps with IO

*Raffiot* is available as a
[*pip* package](https://pypi.org/project/raffiot/)
(and soon *conda*). For now just type this in a
terminal:

```shell
$ pip install -U raffiot
```

This guide will teach you how to use *Raffiot* by exploring most of its features via the Python interactive shell (also known as Python's REPL):

```shell
$ python
Python 3.9.1 (default, Dec 13 2020, 11:55:53) 
[GCC 10.2.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>>
```

Start by importing the `io` module and `IO` type:

```python
>>> from raffiot import io
>>> from raffiot.io import IO
```

## Hello World!

Let's start by the classic *"Hello World!"*:

```python
>>> main : IO[None,None,None] = io.defer(print, "Hello World!")
```

As you can see, nothing is printed yet! The `defer` function delays the
execution of `print("Hello World!")` until the the value `main` is run.

**Very important**: a value of type `IO`, like `main`, is the description
of some computation, very much like the text of a Python script.
Nothing is executed until the (value of type) `IO` is actually run, very
much like the code of Python script is only executed when this script is
run.

Inspecting the value `main`, gives you:

```python
>>> main
Defer((<built-in function print>, ('Hello World!',), {}))
```

Running an `IO` is very simple! Just call its `run` method like:

```python
>>> main.run(None)
Hello World!
Ok(success=None)
>>> main.run(None)
Hello World!
Ok(success=None)
```

As you can see, every call to `run` printed `Hello World!` and returned
the value `Ok(None)`. `Ok` means the computation was successful, `None`
is the return value of computation.

## `defer` : doing something **later**

The first argument of `defer` is the function you want to call later.
The following arguments are the function's normal arguments.
For example, to call `datetime.now()` later, just create the `IO`:

```python
>>> from datetime import *
>>> now : IO[None,None,datetime] = io.defer(datetime.now)
```

Every time you run it, it will call `datetime.now()` and give you
its result:

```python
>>> now.run(None)
Ok(success=datetime.datetime(2021, 2, 19, 18, 38, 42, 572766))
>>> now.run(None)
Ok(success=datetime.datetime(2021, 2, 19, 18, 38, 47, 896153))
```

**In the type `IO[R,E,A]`, `A` is the type of values returned when the computation is successful**.
`now` being of type `IO[None,None,datetime]`, it returns values
of type `datetime`.

Likewise, you can define the `print_io` function that prints its arguments
later:

```python
>>> def print_io(*args, **kwargs) -> IO[None, None, None]:
...     return io.defer(print, *args, **kwargs)
```

Note that calling `print_io("Hello")` will not print anything but return
an `IO`. To actually print `Hello` you need to run the `IO`:

```python
>>> print_io("Hello", "World", "!")
Defer((<built-in function print>, ('Hello', 'World', '!'), {}))
>>> print_io("Hello", "World", "!").run(None)
Hello World !
Ok(success=None)
```

This ability to represent any computation as a value is one of the main
strength of an `IO`. It means you can work with computation like any
other value: composing them, storing them in variables, in lists, etc.

## `then` : doing something sequentially.

You will often need to execute some `IO` sequentially.
The method `then` compose some values of type `IO`, running
them one by one. The return value is the one of the last `IO`:

```python
>>> main : IO[None,None,datetime] = print_io("First line").then(
...   print_io("Second line"),
...   print_io("Third line"),
...   now
... )
>>> main.run(None)
First line
Second line
Third line
Ok(success=datetime.datetime(2021, 2, 20, 15, 52, 11, 205845))
```

You may sometimes prefer the analogous function `io.sequence`
that behaves like the method `then`.

## `map` : transforming results.

You can transform the return value of an `IO` using the `map` method.
It is very similar to the `map` function on lists, but works on `IO`.
Just provide `map` some function. It will use this function to transform
the `IO` return value:


```python
>>> date_str : IO[None,None,str] = now.map(lambda d: d.isoformat())
>>> date_str
Map((Defer((<built-in method now of type object at 0x7ff733070bc0>,
 (), {})), <function <lambda> at 0x7ff7338d9280>))
>>> date_str.run(None)
Ok(success='2021-02-19T23:54:46.297503')
```

## `flat_map` : chaining IOs.

`map` transform the return value of an `IO`. So transforming the
return value of `date_str` with `print_io` will give you an  `IO`
whose return value is also an `IO`. When you will run it, instead
if executing the inner `IO`, it will return it to you:

```python
>>> main : IO[None,None,IO[None,None,None]] = date_str.map(lambda x: print_io(x))
>>> main.run(None)
Ok(success=Defer((<built-in function print>, ('2021-02-20T15:54:38.444494',), {})))
```

When you want to use the result of some `IO` into some other `IO`,
use `flat_map`:

```python
>>> main: IO[None,None,None] = date_str.flat_map(lambda x: print_io(x))
>>> main.run(None)
2021-02-20T15:55:13.940717
Ok(success=None)
```

Here the return value of `date_str` is given to `print_io` via `x` and
both `IO` are executed, returning the result of `print_io(x)`.

## `flatten` : concatenating an IO of IO.

Instead of having used `flat_map`, you could have used `map` and then
`flatten` to reduce the `IO of IO` into a single layer of `IO`:

```python
>>> main : IO[None,None,None]= date_str.map(lambda x: print_io(x)).flatten()
>>> main.run(None)
2021-02-20T15:58:44.244715
Ok(success=None)
```

Most of the time, you will use `flat_map` because it is simpler to use.
But now you know where its name comes from: flatten of map.

## `pure` : just a value.

`pure` is very simple: the result of the computation is the very same
argument of `pure`:

```python
>>> main : IO[None,None,int] = io.pure(5)
>>> main
Pure(5)
>>> main.run(None)
Ok(success=5)
```

It is very useful when some functions/method expect some `IO`
but you want to provide a constant.

## `defer_io` : computing an IO later.

`defer_io` is very much like `defer` but for functions returning `IO`:

```python
>>> main : IO[None,None,IO[None,None,None]] = io.defer(print_io, "Hello", "World", "!")
>>> main.run(None)
Ok(success=Defer((<built-in function print>, ('Hello', 'World', '!'), {})))
>>> main : IO[None,None,None] = io.defer_io(print_io, "Hello", "World", "!")
>>> main.run(None)
Hello World !
Ok(success=None)
```

Like `flat_map` is `faltten` of `map`, `defer_io` is `flatten` of `defer`.
It is useful to defer the call of function returning `IO`.


## Use Case: Stack-Safety

Let's see one of the main feature of `IO`: it is stack safe!
When you run the following function in Python, even if the
argument `times` is small, the computation will fail miserably
because it blew the stack:

```python
>>> def print_date(times: int) -> None:
...   if times > 0:
...     d = datetime.now()
...     print(d.isoformat())
...     print_date(times - 1)
>>> print_date(1000)
<LOTS OF DATES>
2021-02-20T16:20:37.188880
2021-02-20T16:20:37.188883
2021-02-20T16:20:37.188886
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "<stdin>", line 5, in print_date
  File "<stdin>", line 5, in print_date
  File "<stdin>", line 5, in print_date
  [Previous line repeated 992 more times]
  File "<stdin>", line 4, in print_date
RecursionError: maximum recursion depth exceeded while calling a Python object
2021-02-20T16:20:37.188889
```

On the contrary, the equivalent function using `IO` will never
blew the stack, even for very high values of `times`:

```python
>>> def print_date_io(times: int) -> IO[None, None, None]:
...   if times > 0:
...     return (
...       now
...       .flat_map(lambda d: print_io(d.isoformat()))
...       .flat_map(lambda _: print_date_io(times - 1))
...     )
...   else
...     return io.pure(None)
>>> print_date(1000000)
<LOTS OF DATES>
2021-02-20T16:23:22.968454
2021-02-20T16:23:22.968464
Ok(success=None)
```

With `IO`, you can use recursion without fear! Just remember to
wrap your computation in an `IO` (using `defer`, `defer_io`, `map`,
`flat_map`and others) to benefit from `IO`'s safety.