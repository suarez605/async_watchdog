import asyncio
import inspect
from asyncio import Event, create_task, CancelledError
from .logger import get_logger


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
        :param logger: Optional logger instance. Defaults to the package
            logger.
        :raises TypeError: If ``timeout`` is not an int or float (bool
            excluded), or if ``on_timeout`` is not callable.
        :raises ValueError: If ``timeout`` is not greater than zero.
        """
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise TypeError(
                f"timeout must be a numeric value (int or float), "
                f"got {type(timeout).__name__!r}"
            )
        if timeout <= 0:
            raise ValueError(
                f"timeout must be greater than zero, got {timeout!r}"
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
                            self._logger.error(
                                f"Exception in timeout callback: "
                                f"{type(e).__name__}: {e}"
                            )
                    else:
                        self._logger.warning(
                            f"Timeout of {self._timeout} seconds "
                            f"reached without heartbeat."
                        )
        except CancelledError:
            pass

    def start(self):
        if self._task is None:
            self._task = create_task(self._run())

    async def stop(self):
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
