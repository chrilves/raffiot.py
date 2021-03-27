# Combining a list of IOs

Remember that an `IO` is the description of some computation, like
a source code. As such, it can be manipulated like any value, and
so stored in lists. This section covers the operations you have
on lists of `IO`s.

## `zip` : from a list of IO to an IO of list

The `zip` function and method transform a list of `IO` into
an `IO` returning a list. Each value of the resulting list is
the value returned by the `IO` at the same location in the
input list.

The whole computation fails on the first failure encountered.

```python
>>> from typing import List
>>> main : IO[None,None,List] = io.zip(io.pure(8), io.pure("Hello"))
>>> main.run(None)
Ok(success=[8, 'Hello'])
>>> main : IO[None,str,List] = io.zip(io.pure(8), io.error("Oups"))
>>> main.run(None)
Errors(errors=['Oups'])
```

## `sequence` : running IOs in sequence

The function `io.sequence` is like the method `then`:
it executes a list of `IO` sequentially, returning the
value of the last `IO` and failing on the first failure
encountered:

```python
>>> main : IO[None,None,int] = io.sequence(
...   io.defer(print, "Hello"),
...   io.defer(print, "World"),
...   io.pure(12)  
... )
>>> main.run(None)
Hello
World
Ok(success=12)
```

## `traverse` : almost like `map`

The function `io.traverse` is very much like the function `map` on lists.
Like the `map` on lists it applies a function to every element of a list.
But unlike the `map` on lists the function it applies to every element
returns an `IO`.

`io.traverse` is useful when you need to execute a function returning
an `IO` to every element of a list. It returns an `IO` computing the
list of values returned by each call.

Like `zip` and `sequence`, it fails on the first failure encountered.

```python
>>> from typing import List
>>> def add_context(i: int) -> IO[int,None,int]:
...   return io.read.flat_map(lambda c:
...     io.defer(print, f"context = {c}, argument = {i}")
...     .then(io.pure(c + i))
...   )
>>> main : IO[int,None,List[int]] = io.traverse(range(10), add_context)
>>> main.run(10)
context = 10, argument = 0
context = 10, argument = 1
context = 10, argument = 2
context = 10, argument = 3
context = 10, argument = 4
context = 10, argument = 5
context = 10, argument = 6
context = 10, argument = 7
context = 10, argument = 8
context = 10, argument = 9
Ok(success=[10, 11, 12, 13, 14, 15, 16, 17, 18, 19])
```