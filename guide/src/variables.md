# Variables

`IO` is heavily expression based but *Python* does not allow to define local
variables in expressions. *Raffiot* provides two types to work around this
limitation: `Val` and `Var`. A `Val` is an immutable variable while a `Var` is
a mutable variable.

## Immutable Variables

Immutable variables can be created very easily by using the class `Val`:

```python
>>> from raffiot import *
>>> Val(5)
Val(value=5)
```

`Val` has most of the usual operations like `map`, `flat_map`, `zip`, etc.
Please have a look the the [API](./api/index.html) for a complete list of
methods.

For example, Python's forbids this syntax:

```python
>>> lambda x:
>>>   y = x + 5
>>>   print(f"y={y}")
```

because it only allows lambdas to contain one single expression.
To simulate this behaviour, you can use:

```python
>>> lambda x: Val(x+5).map(lambda y: print(f"y={y}"))
```

We totally agree that the first syntax is far superior, but until Python allows
lambda to declare local variables, this is probably the best we can get.


## Mutable Variables

*Raffiot*'s mutable variable are not only mutable variables. They are designed
to play nicely with concurrency. **Every access to the a `Var` is exclusive**,
which means only one fiber is allowed to read or modify the variable at any
time.

### `Var.create`, `Var.create_rs`: the only ways to create a mutable variable

Because a `Var` is not just a value, it can only be created either by the *IO*
`Var.create(a:A)` of type `IO[Any,None,Var[A]]` or the *Resource*
`Var.create(a:A)` of type `Resource[Any,None,Var[A]]`:

```python
>>> from typing import Any
>>> main: IO[Any,None,None] = (
...   Var.create(5).flat_map(lambda var1: var1.set(7).then(var1.get()))
... )
>>> main.run(None)
Ok(success=7)
>>> main_rs: Resource[Any,None,None] = (
...   Var.create_rs(5).flat_map(lambda var1: var1.set_rs(7).then(var1.get_rs()))
... )
>>> main_rs.use(io.pure).run(None)
Ok(success=7)
```

As you can see, you can use the methods `get`/`set` to get/set the current value
as an `IO` or `get_rs`/`set_rs` to get/set the current value as a `Resource`.

Alternatively, you can use the method `get_and_set` and `get_and_set_rs` to
assign a new value to the variable and get the previous value at the same time.

### `update`: modifying the current value

When you need to update the current value of a variable `var:Var[A]`, use the
`update` method.
It takes as input a function `f: Callable[[A], Tuple[A,B]]`. This function will
receive the current value of the variable and must return a pair
`(new_value, returned)`. The `new_value` will become the new value of the
variable. The value `returned` serves to output some value if you want to.

```python
>>> main: IO[Any,None,None] = (
...   Var.create(5).flat_map(lambda v: v.update(lambda x: (x+1, 2*x)))
... )
>>> main.run(None)
Ok(success=UpdateResult(old_value=5, new_value=6, returned=10))
```

The functions `update_io` and `update_rs` are respectively for *IO* and
*Resource* functions.

### `traverse`: creating a new variable from another one.

The `traverse` methods create a new variable using an existing one:

```python
>>> main: IO[Any,None,None] = (
...   Var.create(5)
...      .flat_map(lambda var1: var1.traverse(lambda x: io.defer(print, x)
...                                                       .then(io.pure(x+1))
...                                          )
...                                  .flat_map(lambda var2: var2.get())
...       )
... )
5
Ok(success=6)
```

### `zip`: Getting the values of a group of variables

The `zip` class method regroup the values a list of variable. All concurrent
access to the variables are forbidden during the zip to ensure consistent
reading of the variables values:*

```python
>>> main: IO[Any,None,None] = (
...   io.zip(Var.create(0), Var.create(1))
...     .flat_map(lambda vars:
...       Var.zip(vars[0], vars[1])
...     )
... )
>>> main.run(None)
Ok(success=[0, 1])
```

Note: the `zip_with` instance method is equivalent.

### `ap`: Combining the values of a group of variables

The `zip` class method regroup the values a list of variable. All concurrent
access to the variables are forbidden during the zip to ensure consistent
reading of the variables values:*

```python
>>> main: IO[Any,None,None] = (
...   Var.create(lambda x, y: x + y)
...      .flat_map(lambda var_fun:
...         io.zip(Var.create(2), Var.create(3))
...           .flat_map(lambda vars:
...             var_fun.ap(vars[0], vars[1])
...           )
...     )
... )
>>> main.run(None)
Ok(success=5)
```