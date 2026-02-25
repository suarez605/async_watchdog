# async-watchdog

[![PyPI version](https://badge.fury.io/py/async-watchdog.svg)](https://badge.fury.io/py/async-watchdog)
[![Python](https://img.shields.io/pypi/pyversions/async-watchdog.svg)](https://pypi.org/project/async-watchdog/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A fast, simple asyncio watchdog for monitoring heartbeats in async Python
applications. If a monitored process stops reporting activity within the
configured timeout, `async-watchdog` fires a callback or logs a warning —
keeping your system observable without adding runtime dependencies.

---

## Installation

```bash
pip install async-watchdog
```

---

## Quick Start

```python
import asyncio
from async_watchdog import Watchdog

async def main():
    wd = Watchdog(timeout=5.0)
    await wd.start()

    # Signal that the process is alive
    wd.beat()

    # ... do work, call wd.beat() periodically ...

    await wd.stop()

asyncio.run(main())
```

The watchdog waits for the **first** `beat()` before starting the timeout
clock, so slow-starting processes are not penalised.

---

## Usage

### Async callback on timeout

The recommended pattern for I/O-bound reactions (sending alerts, closing
connections, restarting tasks):

```python
import asyncio
from async_watchdog import Watchdog

async def on_timeout():
    print("No heartbeat received — restarting worker...")
    # await send_alert(...)  # safe: async I/O is fine here

async def worker(wd: Watchdog):
    for _ in range(5):
        await asyncio.sleep(1)
        wd.beat()
    # Worker stops sending beats — timeout will fire after this

async def main():
    wd = Watchdog(timeout=3.0, on_timeout=on_timeout)
    await wd.start()
    try:
        await worker(wd)
        await asyncio.sleep(5)  # Wait for timeout to trigger
    finally:
        await wd.stop()

asyncio.run(main())
```

### Sync callback on timeout

Synchronous callbacks work too. Use them for lightweight, non-blocking
reactions such as setting a flag or incrementing a counter:

```python
import asyncio
from async_watchdog import Watchdog

timeout_count = 0

def on_timeout():
    global timeout_count
    timeout_count += 1
    print(f"Timeout #{timeout_count} detected")

async def main():
    wd = Watchdog(timeout=2.0, on_timeout=on_timeout)
    await wd.start()
    try:
        wd.beat()           # First beat starts the clock
        await asyncio.sleep(6)  # No more beats — callback fires ~every 2 s
    finally:
        await wd.stop()

asyncio.run(main())
```

> **Warning:** Sync callbacks must not perform blocking operations
> (see [Security](#security)).

### No callback — logging only

Omit `on_timeout` to get a `WARNING` log entry on every missed heartbeat
window. Useful during development or when you only need observability:

```python
import asyncio
from async_watchdog import Watchdog

async def main():
    wd = Watchdog(timeout=5.0)  # No on_timeout
    await wd.start()
    try:
        wd.beat()
        await asyncio.sleep(12)  # Watchdog logs warnings at t=5, t=10
    finally:
        await wd.stop()

asyncio.run(main())
```

Output:
```
[Watchdog] WARNING  Timeout of 5.0 seconds reached without heartbeat.
[Watchdog] WARNING  Timeout of 5.0 seconds reached without heartbeat.
```

### Integration in a real worker loop

A typical pattern for a long-running background worker that must report
liveness to the watchdog on every iteration:

```python
import asyncio
from async_watchdog import Watchdog

async def on_worker_timeout():
    print("Worker is unresponsive — triggering recovery")
    # await notify_ops_team(...)

async def process_item(item):
    await asyncio.sleep(0.1)  # Simulate work
    return item * 2

async def worker(wd: Watchdog, queue: asyncio.Queue):
    while True:
        item = await queue.get()
        await process_item(item)
        wd.beat()           # Report liveness after each successful iteration
        queue.task_done()

async def main():
    queue = asyncio.Queue()
    wd = Watchdog(timeout=10.0, on_timeout=on_worker_timeout)

    await wd.start()
    worker_task = asyncio.create_task(worker(wd, queue))

    try:
        for i in range(20):
            await queue.put(i)
            await asyncio.sleep(0.5)

        await queue.join()
    finally:
        worker_task.cancel()
        await wd.stop()

asyncio.run(main())
```

---

## API Reference

### `Watchdog(timeout, on_timeout=None, logger=None)`

Creates a new watchdog instance.

| Parameter    | Type              | Required | Description |
|--------------|-------------------|----------|-------------|
| `timeout`    | `float`           | Yes      | Seconds to wait for a heartbeat before triggering. Must be in `[0.001, 86400]`. `inf`, `nan`, zero, and negatives are rejected. |
| `on_timeout` | `callable \| None` | No       | Callback invoked on each missed heartbeat window. Accepts both sync and async callables. If `None`, a `WARNING` is logged instead. |
| `logger`     | `logging.Logger \| None` | No | Custom logger instance. Defaults to the package logger with `[Watchdog]` prefix. |

**Raises:**

- `TypeError` — if `timeout` is not a numeric `int` or `float` (booleans
  excluded), or if `on_timeout` is not callable.
- `ValueError` — if `timeout` is outside `[0.001, 86400]` or is not finite.

---

### Methods

#### `await wd.start()`

Starts the watchdog background task. The watchdog blocks until the first
`beat()` is received before beginning timeout monitoring.

- **Idempotent:** safe to call multiple times; only one background task is
  ever created.
- **Concurrency-safe:** protected by an `asyncio.Lock`.

#### `wd.beat()`

Signals that the monitored process is alive. Resets the timeout window.
Synchronous — call it from anywhere in your async code without `await`.

#### `await wd.stop()`

Cancels the background task and cleans up. Safe to call even if `start()`
was never called. After `stop()`, the watchdog can be restarted with
`start()`.

---

### Callback behaviour

| Scenario | Behaviour |
|---|---|
| Async callback | Awaited directly; non-blocking for the event loop |
| Sync callback | Called inline; must not block (see [Security](#security)) |
| Callback raises an exception | Exception type logged at `ERROR`; watchdog continues running |
| Callback exceeds `timeout` | Cancelled and logged at `ERROR`; watchdog continues running |
| No callback provided | `WARNING` logged on every missed heartbeat window |

---

## Security

### Blocking sync callbacks

Synchronous `on_timeout` callbacks run directly on the asyncio event loop.
**Any blocking operation inside a sync callback will freeze the entire event
loop** for the duration of the call, preventing all other coroutines from
making progress.

**Do not use in sync callbacks:**
- `time.sleep()`
- Blocking file or network I/O
- CPU-intensive computation

**Safe alternatives:**

```python
# Option 1: Use an async callback for I/O
async def on_timeout():
    await asyncio.sleep(1)          # Non-blocking
    await send_alert_via_http()     # Non-blocking

# Option 2: Offload blocking work to a thread pool
import asyncio

def blocking_work():
    time.sleep(1)  # Runs in a thread, not the event loop

async def on_timeout():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, blocking_work)
```

### Log injection

All exception messages written to logs are sanitised (control characters
stripped) to prevent log injection attacks.

---

## Requirements

- **Python:** `>= 3.10`
- **Runtime dependencies:** none
- **Optional:** [`uvloop`](https://github.com/MagicStack/uvloop) for higher
  throughput (drop-in replacement for the default asyncio event loop)

---

## License

[MIT](https://opensource.org/licenses/MIT) — Álvaro Suárez Lozano
