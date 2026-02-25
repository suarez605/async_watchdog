# ROADMAP — async_watchdog

Pending features ordered by priority. Criteria: production readiness and PyPI
publication. Items within each tier are ordered by implementation dependency.

---

## 🔴 Critical — Blocking for publication

These are the first things a developer checks before deciding to install a
library.

| # | Feature | Why it is blocking |
|---|---|---|
| 1 | **Context manager** (`async with Watchdog(...) as wd`) | Without it, forgetting `await wd.stop()` produces task leaks. Standard pattern for async resources in Python. Any experienced dev will expect it. |
| 2 | **State query methods** (`is_running()`, `is_healthy()`) | Today there is no way to know if the watchdog is active without accessing `_task` (private). Unacceptable in a public API. |
| 3 | **README with real usage examples** | PyPI displays the README as the landing page. Without usage examples, nobody installs. |
| 4 | **`__version__`** in the package | De facto standard in any Python library. Required for `pip show async-watchdog` and for users to report bugs with a version number. |

---

## 🟠 High — Required before first stable release

| # | Feature | Why it matters |
|---|---|---|
| 5 | **Watchdog name** (`name` param in `__init__`) | With multiple watchdogs in one app, logs cannot distinguish which one failed. Critical for production debugging. |
| 6 | **Last heartbeat tracking** (`last_heartbeat_at`, `time_since_last_heartbeat()`) | Basic information that any monitoring system needs to expose. |
| 7 | **`restart()` method** | Incomplete lifecycle without it. Today you must destroy and recreate the object. |
| 8 | **Lifecycle logs** (start, stop, first heartbeat received) | Today only timeouts are logged. Hard to operate in production without knowing when the watchdog started or stopped. |

---

## 🟡 Medium — For a mature release (v1.0)

| # | Feature | Why it matters |
|---|---|---|
| 9 | **Pause and resume** (`pause()` / `resume()`) | Useful during maintenance windows. Avoids false alarms. |
| 10 | **Severity escalation** (different action after N consecutive timeouts) | Standard pattern in process supervisors. Enables gradual recovery. |
| 11 | **Consecutive timeout counter** exposed in the callback | The callback today receives zero context. Knowing how many consecutive failures have occurred is essential for making decisions. |
| 12 | **Exportable metrics** (uptime, total timeouts, average heartbeat latency) | Prometheus / DataDog integration. Required for adoption in enterprise environments. |

---

## 🔵 Low — Future

| # | Feature | Notes |
|---|---|---|
| 13 | **Event history** | Useful for debugging intermittent failures in production. |
| 14 | **Heartbeat with payload** (`wd.beat({"cpu": 45, "status": "ok"})`) | More granular health monitoring. |
| 15 | **Structured logging** (JSON output) | Integration with modern observability stacks. |
| 16 | **Memory leak tests** | Important for long-running applications. |

---

## ✅ Completed

| Feature | Description |
|---|---|
| **#1 Callback exception handling** | Exceptions in `on_timeout` are caught, logged as `ERROR`, and the watchdog loop continues. |
| **#2 Parameter validation** | `__init__` raises `TypeError` / `ValueError` for invalid `timeout` or `on_timeout` values. |
| **#3 Async callback timeout** | Hanging async callbacks are interrupted after `self._timeout` seconds via `asyncio.wait_for`. |
