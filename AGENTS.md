# AGENTS.md — async_watchdog

A fast, simple async watchdog for monitoring heartbeats in asyncio applications.
This file is intended for agentic coding tools operating in this repository.

---

## Project Overview

- **Language:** Pure Python 3.11 (requires `>=3.10`)
- **Package manager:** `pipenv` (see `Pipfile` / `Pipfile.lock`)
- **Build system:** `setuptools` via `pyproject.toml` (PEP 517/518/621)
- **No external runtime dependencies** (`dependencies = []` in `pyproject.toml`)
- **Core concept:** `Watchdog` monitors heartbeats via `asyncio.Event`; triggers a
  callback (or logs a warning) when no heartbeat arrives within a timeout window.

---

## Environment Setup

```bash
pipenv install --dev   # install all deps into a virtualenv
pipenv shell           # activate (optional)
pipenv run <command>   # run without activating
```

The package is installed in editable mode (`pip install -e .`) automatically
(see `Pipfile`).

---

## Build / Lint / Test Commands

```bash
# Tests
pipenv run pytest tests/tests.py          # run all tests
pipenv run pytest tests/tests.py -v       # verbose
pipenv run pytest tests/tests.py::test_async_timeout_callback  # single test

# Lint & format (run both before every commit)
pipenv run ruff format async_watchdog/ tests/
pipenv run ruff check --fix async_watchdog/ tests/

# Check only (no changes)
pipenv run ruff format --check async_watchdog/ tests/
pipenv run ruff check async_watchdog/ tests/

# Legacy linter (secondary, ruff takes precedence)
pipenv run flake8 async_watchdog/ tests/

# Build & publish
pipenv run python -c "import shutil; shutil.rmtree('dist', ignore_errors=True)"
pipenv run python -m build          # generates dist/*.whl and dist/*.tar.gz
pipenv run twine check dist/*       # validate before uploading
pipenv run twine upload dist/*      # requires PyPI token

# Manual uvloop smoke test
pipenv run python tests/tests.py
```

> **Note:** No `pytest.ini` / `setup.cfg` — pass all pytest options on the
> command line. Build config lives in `pyproject.toml`.

---

## Project Structure

```
async_watchdog/
├── async_watchdog/        # Main package
│   ├── __init__.py        # Public API: exports Watchdog
│   ├── core.py            # Watchdog class + maybe_awaitable helper
│   └── logger.py          # WatchdogFormatter + get_logger factory
├── tests/
│   └── tests.py           # All tests (pytest + pytest-asyncio)
├── pyproject.toml         # Package metadata and build config (PEP 517/621)
├── ruff.toml              # Ruff formatter/linter config (79-char limit)
├── Pipfile                # Dependency declarations (version-pinned ranges)
├── Pipfile.lock           # Locked dependency versions (tracked in VCS)
├── skills-lock.json       # Installed agent skills
└── AGENTS.md              # This file
```

---

## Code Style Guidelines

### General
- Follow **PEP 8**. Max line length: **79 characters**.
- **Ruff** is the formatter and linter (`ruff.toml` at repo root). Always run
  `pipenv run ruff format` + `pipenv run ruff check --fix` before committing.
- Flake8 is kept as a secondary linter for compatibility; ruff takes precedence.
- Use **f-strings** for all string interpolation.
- Never use `print` in library code; use the logger.

### Imports
- Standard library first, then local package imports — separated by a blank line.
- Use explicit `from`-style imports; avoid wildcard imports.

```python
import asyncio
import inspect
from asyncio import Event, create_task, CancelledError

from .logger import get_logger
```

### Naming Conventions

| Construct             | Convention           | Example                         |
|-----------------------|----------------------|---------------------------------|
| Classes               | `PascalCase`         | `Watchdog`, `WatchdogFormatter` |
| Functions / methods   | `snake_case`         | `get_logger`, `maybe_awaitable` |
| Private attrs/methods | `_single_underscore` | `_timeout`, `_run`, `_heartbeat`|
| Test functions        | `test_<description>` | `test_async_timeout_callback`   |
| Constants             | `UPPER_SNAKE_CASE`   | `_MIN_TIMEOUT`, `_MAX_TIMEOUT`  |

### Type Annotations
- Annotate parameters where practical: `timeout: float`, `beat_interval: float`.
- Use bare `callable` (not `typing.Callable`) for callback parameters.
- Return type annotations are optional but welcome.
- Use `X | None` (Python 3.10+ union syntax) for nullable parameters.

### Docstrings
- Use reStructuredText `:param name:` style on all public methods:

```python
def __init__(self, timeout: float, on_timeout: callable = None, logger=None):
    """
    Initialize the Watchdog.
    :param timeout: Seconds after which the watchdog triggers if no heartbeat.
    :param on_timeout: Optional callback (sync or async) called on timeout.
    :param logger: Optional logger; defaults to the package logger.
    """
```

---

## Async Patterns

> **Skill available:** `async-python-patterns` — load it for detailed asyncio
> guidance, concurrency patterns, semaphores, queues, and performance best practices.

- The library is **asyncio-native**. Never use `time.sleep`; always `asyncio.sleep`.
- `Watchdog._run` follows a **wait-for-first-heartbeat** pattern before entering the
  timeout loop — slow-start processes are not penalised.
- Use `maybe_awaitable` (`core.py`) when invoking user callbacks that may be sync or
  async:

```python
await maybe_awaitable(self._on_timeout())
```

- Both `start()` and `stop()` are **async** and must be awaited.
- `start()` is idempotent and concurrency-safe — protected by an `asyncio.Lock`.
- Always catch `asyncio.CancelledError` at the outermost level of long-running
  coroutines; handle with `pass` or cleanup logic, then let it propagate if needed.
- Use `asyncio.Event` for signaling, `asyncio.wait_for()` for timeouts, and
  `create_task()` for background tasks.

---

## Error Handling

- Catch `CancelledError` at the top of `_run()` — do **not** swallow it mid-loop.
- In `stop()`, wrap `await self._task` with `except CancelledError: pass` —
  cancellation is expected, not an error.
- Catch `asyncio.TimeoutError` inside the watchdog loop to trigger the callback or
  fall back to a log warning. Never let `TimeoutError` propagate to the caller.
- Never raise bare exceptions; always use specific exception types.

---

## Logging

- Obtain a logger via `get_logger(__name__)` from `async_watchdog.logger`.
- `WatchdogFormatter` automatically prepends `[Watchdog]` to every message.
- `Watchdog.__init__` accepts an optional `logger` argument for injection in tests.
- Default log level: `INFO`. Use `WARNING` for timeout events without a callback.
- `logger.propagate = False` is set — messages do **not** bubble to the root logger.
- Callback exception type is logged at `ERROR`; full details at `DEBUG` only.

---

## Security Constraints

These invariants must be preserved in all future changes:

- **`timeout` validation** — must be a finite float in `[0.001, 86400]` seconds.
  `float('inf')`, `float('nan')`, zero, and negatives are rejected at construction.
- **Log injection** — all exception messages written to logs must be passed through
  `_sanitize_log_message()` (strips `\r`, `\n`, and other control characters).
- **Concurrency** — `start()` and `stop()` are guarded by `asyncio.Lock`; do not
  remove this guard or make either method synchronous.
- **Blocking callbacks** — sync `on_timeout` callbacks must not perform blocking I/O
  or `time.sleep`; document this constraint in any new callback-accepting API.
- **Supply chain** — `Pipfile.lock` is tracked in VCS. Do not add it to `.gitignore`.
  Dev dependencies use version ranges (e.g. `>=9.0,<10.0`), not wildcards (`*`).

---

## Testing Guidelines

> **Skill available:** `python-testing-patterns` — load it for comprehensive pytest
> patterns, fixtures, mocking strategies, parameterization, and CI/CD integration.

### Framework
- **pytest** + **pytest-asyncio** (`@pytest.mark.asyncio` on every async test).
- No `asyncio_mode = "auto"` — decorate every async test explicitly.

### Test Structure
- All tests live in `tests/tests.py`. Add new tests there or in new files under
  `tests/` as the suite grows.
- Use helper coroutines (e.g. `simulate_healthy_process`) to encapsulate scenario
  logic and keep test bodies readable.
- Use `try/finally` to guarantee `await wd.stop()` is called even on assertion
  failures:

```python
wd = Watchdog(timeout=0.1, on_timeout=on_timeout)
await wd.start()   # start() is async — always await it
try:
    await simulate_healthy_process(wd, beat_interval=0.02, num_beats=5)
    await asyncio.sleep(timeout * 0.5)
finally:
    await wd.stop()

on_timeout.assert_not_called()
```

### Mocking Callbacks
- **Sync callbacks:** `unittest.mock.MagicMock`
- **Async callbacks:** list-append pattern (more reliable than `AsyncMock` in
  time-sensitive tests):

```python
callback_calls = []

async def on_timeout():
    callback_calls.append(1)

wd = Watchdog(timeout=0.1, on_timeout=on_timeout)
```

### Timing
- Use multipliers (`timeout * 2`, `timeout * 0.5`) instead of magic numbers.
- Keep timeout values small (0.05–0.1 s) to keep the suite fast.
- Add safety margins after operations: `await asyncio.sleep(timeout * 0.5)`.

---

## Available Agent Skills

| Skill                      | When to Use                                                  |
|----------------------------|--------------------------------------------------------------|
| `async-python-patterns`    | asyncio patterns, concurrency, semaphores, queues, perf tips |
| `python-testing-patterns`  | pytest fixtures, mocking, parameterization, TDD, CI/CD       |

Load a skill by invoking it through the agent skill system before implementing
features that fall within its domain.

---

## Agent Workflow for New Features

1. **explorer** — understand existing code, patterns, and constraints
2. **proposer** — generate 2–3 implementation approaches with trade-offs
3. *(lead engineer decides the approach, consulting user if unclear)*
4. **designer** — produce detailed technical design (classes, interfaces, data flow)
5. **task-planner** — decompose design into atomic, ordered, unambiguous tasks
6. **implementer** × N — implement one task at a time (invoke once per task)
7. **test-writer** — write tests for the new code (load `python-testing-patterns`)
8. **test-runner** — execute tests; if failures occur, return to **implementer**
9. **security-researcher** — security review of all new code before closing
10. **reviewer** — final technical review before closing the feature

> Never implement code directly in the orchestrator. Always delegate to **implementer**.
> Pass full context (prior decisions, constraints, expected output) to every subagent.
