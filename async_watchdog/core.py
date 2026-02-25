import asyncio
import inspect
import math
import re
from asyncio import Event, create_task, CancelledError
from .logger import get_logger

_MIN_TIMEOUT = 0.001  # 1 ms — minimum sensible timeout
_MAX_TIMEOUT = 86400.0  # 24 h — maximum sensible timeout


def _sanitize_log_message(msg: str) -> str:
    """Remove control characters from log messages to prevent injection."""
    return re.sub(r"[\r\n\t\x00-\x1f\x7f]", " ", str(msg))


class Watchdog:
    def __init__(
        self,
        timeout: float,
        on_timeout: callable = None,
        logger=None,
    ):
        """
        Initialize the Watchdog.

        :param timeout: Seconds after which the watchdog triggers if no
            heartbeat is received. Must be a positive int or float
            (bool not accepted).
        :param on_timeout: Optional callback (sync or async) called when
            the timeout is reached. Must be callable if provided.

            .. warning::
                Synchronous callbacks must not perform blocking operations
                (e.g. ``time.sleep``, blocking I/O, heavy computation).
                Blocking inside a sync callback will freeze the entire
                asyncio event loop for the duration of the call.
                Use an async callback with ``await asyncio.sleep()`` or
                delegate blocking work to a thread via
                ``asyncio.get_event_loop().run_in_executor()``.

        :param logger: Optional logger instance. Defaults to the package
            logger.
        :raises TypeError: If ``timeout`` is not an int or float (bool
            excluded), or if ``on_timeout`` is not callable.
        :raises ValueError: If ``timeout`` is not in the range
            [0.001, 86400] seconds, or if it is not a finite number
            (``inf`` and ``nan`` are rejected).
        :note: ``start()`` is async and must be awaited.
            ``stop()`` is also async and must be awaited.
        """
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise TypeError(
                f"timeout must be a numeric value (int or float), "
                f"got {type(timeout).__name__!r}"
            )
        if not math.isfinite(timeout):
            raise ValueError(
                f"timeout must be a finite number, got {timeout!r}"
            )
        if timeout < _MIN_TIMEOUT:
            raise ValueError(
                f"timeout must be >= {_MIN_TIMEOUT} seconds, got {timeout!r}"
            )
        if timeout > _MAX_TIMEOUT:
            raise ValueError(
                f"timeout must be <= {_MAX_TIMEOUT} seconds, got {timeout!r}"
            )
        if on_timeout is not None and not callable(on_timeout):
            raise TypeError(
                f"on_timeout must be callable, "
                f"got {type(on_timeout).__name__!r}"
            )
        self._timeout = timeout
        self._on_timeout = on_timeout
        self._heartbeat = Event()
        self._task = None
        self._lock = asyncio.Lock()
        self._logger = logger if logger else get_logger(__name__)

    def beat(self):
        self._heartbeat.set()

    async def _run(self):
        try:
            await self._heartbeat.wait()  # Wait for the first heartbeat
            self._logger.info("Watchdog started, waiting for heartbeats...")
            while True:  # Main loop until cancelled
                try:
                    await asyncio.wait_for(
                        self._heartbeat.wait(), self._timeout
                    )
                    self._heartbeat.clear()
                except asyncio.TimeoutError:
                    if self._on_timeout is not None:
                        try:
                            await asyncio.wait_for(
                                maybe_awaitable(self._on_timeout()),
                                self._timeout,
                            )
                        except asyncio.TimeoutError:
                            self._logger.error(
                                f"Timeout callback exceeded time "
                                f"limit of {self._timeout} seconds "
                                f"and was cancelled."
                            )
                        except Exception as e:
                            safe_type = _sanitize_log_message(type(e).__name__)
                            self._logger.error(
                                f"Exception in timeout callback: "
                                f"{safe_type}. See DEBUG for details."
                            )
                            self._logger.debug(
                                f"Exception details: {safe_type}: "
                                f"{_sanitize_log_message(str(e))}",
                                exc_info=True,
                            )
                    else:
                        self._logger.warning(
                            f"Timeout of {self._timeout} seconds "
                            f"reached without heartbeat."
                        )
        except CancelledError:
            pass

    async def start(self):
        """
        Start the watchdog background task.

        This method is idempotent: calling it multiple times is safe.
        It is async to guarantee atomicity when called concurrently
        from multiple coroutines.

        .. warning::
            Do not call ``start()`` from synchronous code after the
            event loop is running. Schedule it with
            ``asyncio.ensure_future(wd.start())`` if needed.
        """
        async with self._lock:
            if self._task is None:
                self._task = create_task(self._run())

    async def stop(self):
        """
        Stop the watchdog and cancel the background task.

        Safe to call even if the watchdog was never started.
        """
        async with self._lock:
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except CancelledError:
                    pass
                self._task = None


async def maybe_awaitable(result):
    if inspect.isawaitable(result):
        return await result
    return result
