# Asynchronous Computing

For now you know that an `IO` is very nice for stack safety,
dependency injection, failure management, and code-as-date manipulations.
There is another big feature `IO` has: simple asynchronous and
concurrent programming.

A call to some function is called synchronous when the thread making
the call actually waits for the call to return a value. This is annoying
because the thread could be used to perform useful computations instead
of just waiting.

On the contrary, a call is said asynchronous when the tread making the
call does not wait for the call to finish but run useful computations
in the mean time.

The notorious expression [callback Hell](http://callbackhell.com/) kindly
expresses how asynchronous programming can be error-prone, hard to write
and hard to read.

Asynchronous programming is all about callbacks, but fortunately,
programming models were created to hide much of its complexity under
a clean and simple interface. The famous [Promise](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise)
of JavaScript is such an interface. The [async/await](https://docs.python.org/3/library/asyncio-task.html)
syntax of many languages, including Python, is also such an interface.
So is *Raffiot*'s `IO`. But unlike the *async/await* syntax, synchronous
and asynchronous code can be transparently mixed with `IO`.

## `async_` : running something asynchronously

Calling a function `f` usually looks like this:

```python
>>> def f():
...   print("f is running")
...   return 3
>>> def main():
...   print("f not started yet")
...   result = f()
...   print(f"f finished and returned {result}")
>>> main()
f not started yet
f is running
f finished and returned 3
```

When the function `main` calls `f`, it waits for `f` to finish.
When `f` finishes, `main` resumes its computation with the result
of `f`.

Asynchronous functions, like
[apply_async](https://docs.python.org/fr/3/library/multiprocessing.html#multiprocessing.pool.Pool.apply_async)
do not work this way.
Calling an *asynchronous* function `fasync` usually looks like this.

```python
>>> import time
>>> from multiprocessing import Pool

>>> def f():
...  print("f is running")
...  return 3

>>> with Pool(4) as pool: 
...   def fasync(callback):
...     pool.apply_async(f, callback = callback)
... 
...   def main():
...     print("fasync not started yet")
...
...     def callback(result):
...       print(f"fasync finished and returned {result}")
...
...     fasync(callback)
...     print("fasync started")
... 
...   main()
...   time.sleep(0.5)
fasync not started yet
fasync started
f is running
fasync finished and returned 3
```

As you can seen, the function `main` does not wait that `f` finishes
but continues its execution printing `fasync started`.
The function `main` can not get the result of `f` so it defines
a function, called a **callback**, to process the result of when it
finishes.

With *Raffiot*'s `IO` you would write:


```python
>>> import time
>>> from multiprocessing import Pool
>>> from raffiot import io
>>> from raffiot.io import IO
>>> from raffiot.result import Result, Ok

>>> def f():
...   print("f is running")
...   return 3

>>> with Pool(4) as pool: 
...   f_io : IO[None,None,int] = io.async_(lambda r, exe, k:
...     exe.submit(lambda:
...       pool.apply_async(f, callback = lambda r: k(Ok(r))).wait()
...     )
...   )
... 
...   main : IO[None,None,None] = io.sequence(
...     io.defer(print, "fasync not started yet"),
...     f_io.flat_map(lambda result:
...       io.defer(print, f"fasync finished and returned {result}")
...     ),
...     io.defer(print, "fasync started")
...   )
... 
...   main.run(None)
fasync not started yet
f is running
fasync finished and returned 3
fasync started
```

Note that we call `.wait()` on the `AsyncResult` from `apply_async`.
But the call is still asynchronous because we start a
[Future](https://docs.python.org/3/library/concurrent.futures.html)
with `exe.submit`. The reason is *Raffiot* rely on Python's futures
for task scheduling and does not directly support `AsyncResult` yet.

**Very important**: when you use `async_`, you must always
**return a `Future`** and always **call the callback exactly once**
(no more, no less).

## `run` : the second argument.

An `IO` is executed on a pool of threads. Until now we only gave `io.run`
one argument: the context. But `io.run` accepts two argument! The second
one is the number of threads in the pool.

Note that every time an `IO` calls `time.sleep` it blocks its thread
and one thread is dedicated to the runtime system. So be sure to use
enough threads to keep your CPU busy.
Because of the infamous Python's
[Global Interpreter Lock](https://wiki.python.org/moin/GlobalInterpreterLock)
Python can not run thread in parallel.
So if your code only uses one 100% of a single core,
this is normal.
You know the story: Python is single-threaded.

To use *n* thread, just give *n* to `io.run`:

```python
>>> io.pure(5).run(None, 50)
Ok(success=5)
```

## `parallel` : running concurrent tasks

The function `io.parallel` runs a list of `IO`s in parallel.
Remember that because of Python's
[Global Interpreter Lock](https://wiki.python.org/moin/GlobalInterpreterLock)
only one thread executing Python's code can be running
at any time. But your code involves a lot of primitives
written in *C*/*C++*/etc, then you might get lucky and
use all of your cores.

`parallel` returns a list of values called **fibers**.
A *fiber* represents a tasks running in parallel/concurrently.
Every *fiber* in the returned list correspond to the
`IO` at the same location in the argument list.
For example in

```python
io.parallel(ios).flat_map(lambda fibers: ...)
```

for every index `i`, `fibers[i]` is the fiber representing
the computation of the *IO* `ios[i]` running in parallel/concurrently.

```python
>>> import time
>>> def task(i: int) -> IO[None,None,None] :
>>>   return io.defer(print, f"Task {i}: Begin").then(
...     io.defer(time.sleep, 1),
...     io.defer(print, f"Task {i}: End")
...   )
>>> main : IO[None,None,None] = (
...   io.parallel([task(i) for i in range(6)])
...   .then(io.defer(print,"Finished")))
>>> main.run(None)
Task 0: Begin
Task 1: Begin
Task 3: Begin
Task 4: Begin
Task 2: Begin
Finished
Task 5: Begin
Task 0: End
Task 1: End
Task 3: End
Task 4: End
Task 2: End
Task 5: End
Ok(success=None)
```

As you can see, `main` does not wait for the `IO`s running
in parallel/concurrently to continue its execution.

## `wait` : waiting for concurrent tasks to end

Sometimes you want to wait for a parallel/concurrent computation
to finish. Remember that parallel/concurrent computation are
represented by the *fibers* returned by `io.parallel`.

To wait for some fibers to finish, just call `io.wait` with
the list of fibers you want to wait on. The result of `wait`
is the list of all the fibers results (of type `Result[E,A]`).
For example, in

```python
io.wait(fibers).flat_map(lambda results: ...)
```

for any index `i`, `result[i]` of type `Result[E,A]` is the result
of the computation represented by the fiber `fibers[i]`.

```python
>>> main : IO[None,None,None] = (
...   io.parallel([task(i) for i in range(6)])
...   .flat_map(lambda fibers: io.wait(fibers))
...   .then(io.defer(print,"Finished")))
>>> main.run(None)
Task 0: Begin
Task 1: Begin
Task 3: Begin
Task 5: Begin
Task 4: Begin
Task 2: Begin
Task 0: End
Task 3: End
Task 1: End
Task 5: End
Task 4: End
Task 2: End
Finished
Ok(success=None)
```

## `yield_` : letting other task progress

Remember that an `IO` runs on a pool of thread.
There there is more `IO`s to run than the number of threads to run on,
there is a chance that some `IO` will not get executed.
An `IO` can explicitly release its thread for a moment to let other
tasks a chance to progress.

Call `io.yield_()` to release the current thread. The `IO` will make
a break and continue its execution later.

```python
>>> main : IO[None,None,None] = io.defer(print, "Hello").then(
...   io.yield_(),
...   io.defer(print, "World!") 
... )
>>> main.run(None)
Hello
World!
Ok(success=None)
```

## `sleep`: making a break

To pause an `IO` for some time, just call `io.sleep` with the number of seconds
you want the `IO` paused:

```python
>>> from time import time
>>> now : IO[None, None, None] = io.defer(time).flat_map(lambda t: io.defer(print, t))
>>> main : IO[None, None, None] = now.then(io.sleep(2), now)
>>> main.run(None)
1615136436.7838593
1615136438.785897
Ok(success=None)
```


Calling `io.sleep(0)` does nothing. The `IO` is guaranteed to be paused for at
least the time you requested, but it may sleep longer! Especially when threads
are busy.

## `sleep_until`: waking up in the future.

To pause an `IO` until some determined time in the future, call `io.sleep_until`
with the desired epoch:

```python
>>> from time import time
>>> now : IO[None, None, None] = io.defer(time).flat_map(lambda t: io.defer(print, t))
>>> time.time()
1615136688.9909387
>>> main : IO[None, None, None] = now.then(io.sleep_until(1615136788), now)
>>> main.run(None)
1615136713.6873975
1615136788.0037072
Ok(success=None)
```

Calling `io.sleep_until` with an epoch in the past does nothing.
The `IO` is guaranteed to be paused until the epoch you requested is reached but
it can sleep longer! Especially when threads are busy.

## `read_executor` : getting the executor

The function `io.read_executor` returns the executor on which the
current `IO` runs.

```python
>>> main : IO[None,None,None] = io.read_executor().map(lambda exe: exe.submit(print,"Hello World!"))
Hello World!
Ok(success=<Future at 0x7f7eaa3fb1f0 state=finished returned NoneType>)
```

## `contra_map_executor` : changing the executor

You may sometimes want to change the executor running the current `IO`.
For example you may want a long task to be executed on a different
thread pool:

```python
>>> from concurrent.futures import ThreadPoolExecutor
>>> with ThreadPoolExecutor() as executor2:
...   io.pure(18).contra_map_executor(lambda _: executor2).run(None)
Ok(success=18)
```