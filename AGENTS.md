# AGENTS.md — async_watchdog

A fast, simple async watchdog for monitoring heartbeats in asyncio applications.
This file is intended for agentic coding tools operating in this repository.

---

## Project Overview

- **Language:** Pure Python 3.11 (requires `>=3.10`)
- **Package manager:** `pipenv` (see `Pipfile` / `Pipfile.lock`)
- **Build system:** `setuptools` via `setup.py` (no `pyproject.toml`)
- **No external runtime dependencies** (`install_requires=[]` in `setup.py`)
- **Core concept:** `Watchdog` monitors heartbeats via `asyncio.Event`; triggers a
  callback (or logs a warning) when no heartbeat arrives within a timeout window.

---

## Environment Setup

```bash
# Install all dependencies (runtime + dev) into a pipenv virtualenv
pipenv install --dev

# Activate the virtualenv
pipenv shell

# Or run commands directly without activating
pipenv run <command>
```

The package is installed in editable mode (`pip install -e .`) inside the pipenv
virtualenv automatically (see `Pipfile`).

---

## Build / Lint / Test Commands

```bash
# Run all tests
pipenv run pytest tests/

# Run a single test by name  ← most common during development
pipenv run pytest tests/tests.py::test_async_timeout_callback

# Run a single test file
pipenv run pytest tests/tests.py

# Verbose output
pipenv run pytest tests/ -v

# Print stdout inline (no capture)
pipenv run pytest tests/ -s

# Format code with ruff (always run before committing)
pipenv run ruff format async_watchdog/ tests/

# Check formatting without applying changes
pipenv run ruff format --check async_watchdog/ tests/

# Lint with ruff (mirrors flake8 E/W/F rules, 79-char limit)
pipenv run ruff check async_watchdog/ tests/

# Lint and auto-fix fixable issues
pipenv run ruff check --fix async_watchdog/ tests/

# Run linting with flake8 (legacy, kept for compatibility)
pipenv run flake8 async_watchdog/ tests/

# Build distribution packages
pipenv run python setup.py sdist bdist_wheel

# Upload to PyPI (requires credentials)
pipenv run twine upload dist/*

# Manual test execution with uvloop (for performance validation)
pipenv run python tests/tests.py
```

> **Note:** There is no `pytest.ini`, `setup.cfg`, or `pyproject.toml` configuring
> pytest. All options must be passed on the command line.

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
├── setup.py               # Package metadata and build config
├── ruff.toml              # Ruff formatter/linter config (79-char limit)
├── Pipfile                # Dependency declarations
├── Pipfile.lock           # Locked dependency versions
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

| Construct            | Convention              | Example                        |
|----------------------|-------------------------|--------------------------------|
| Classes              | `PascalCase`            | `Watchdog`, `WatchdogFormatter`|
| Functions / methods  | `snake_case`            | `get_logger`, `maybe_awaitable`|
| Private attrs/methods| `_single_underscore`    | `_timeout`, `_run`, `_heartbeat`|
| Test functions       | `test_<description>`    | `test_async_timeout_callback`  |
| Constants            | `UPPER_SNAKE_CASE`      | *(none yet — follow convention)*|

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

- `stop()` is `async` and must be awaited. It cancels the internal task cleanly.
- Always catch `asyncio.CancelledError` at the outermost level of long-running
  coroutines; handle with `pass` or cleanup logic, then let it propagate if needed.
- Use `asyncio.Event` for signaling, `asyncio.wait_for()` for timeouts, and
  `create_task()` for background tasks.
- `start()` is idempotent — multiple calls are safe (guards with `if self._task is None`).

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
wd.start()
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

The following skills are installed and can be loaded by agentic tools operating in
this repository (see `skills-lock.json`):

| Skill                      | When to Use                                                  |
|----------------------------|--------------------------------------------------------------|
| `async-python-patterns`    | asyncio patterns, concurrency, semaphores, queues, perf tips |
| `python-testing-patterns`  | pytest fixtures, mocking, parameterization, TDD, CI/CD       |

Load a skill by invoking it through the agent skill system before implementing
features that fall within its domain.

---

## Agent Workflow for New Features

When implementing a new feature in this repository, follow this standard flow:

1. **explorer** — understand existing code, patterns, and constraints
2. **proposer** — generate 2–3 implementation approaches with trade-offs
3. *(lead engineer decides the approach, consulting user if unclear)*
4. **designer** — produce detailed technical design (classes, interfaces, data flow)
5. **task-planner** — decompose design into atomic, ordered, unambiguous tasks
6. **implementer** × N — implement one task at a time (invoke once per task)
7. **test-writer** — write tests for the new code (load `python-testing-patterns`)
8. **test-runner** — execute tests; if failures occur, return to **implementer**
9. **reviewer** — final technical review before closing the feature

> Never implement code directly in the orchestrator. Always delegate to **implementer**.
> Pass full context (prior decisions, constraints, expected output) to every subagent.
