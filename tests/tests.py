import asyncio
import logging
import pytest
import uvloop
from async_watchdog.core import Watchdog
from unittest.mock import MagicMock
import time


async def simulate_healthy_process(
    watchdog: Watchdog, beat_interval: float, num_beats: int
):
    """Simula un proceso que envía heartbeats regulares"""
    try:
        for i in range(num_beats):
            await asyncio.sleep(beat_interval)
            watchdog.beat()
            print(f"Heartbeat {i + 1}/{num_beats} sent")
    except asyncio.CancelledError:
        print("Healthy process simulation cancelled")
        raise


async def simulate_failing_process(
    watchdog: Watchdog, beat_interval: float, fail_after: int
):
    """Simula un proceso que falla después de ciertos heartbeats"""
    try:
        for i in range(fail_after):
            await asyncio.sleep(beat_interval)
            watchdog.beat()
            print(f"Heartbeat {i + 1} sent")

        # Simular fallo - dejar de enviar heartbeats
        print(
            f"Process failed after {fail_after} heartbeats, "
            f"no more heartbeats will be sent"
        )
        await asyncio.sleep(10)  # Dormir para simular hang
    except asyncio.CancelledError:
        print("Failing process simulation cancelled")
        raise


async def simulate_slow_start_process(
    watchdog: Watchdog,
    initial_delay: float,
    beat_interval: float,
    num_beats: int,
):
    """Simula un proceso que tarda en enviar el primer heartbeat"""
    try:
        # Delay inicial antes del primer heartbeat
        await asyncio.sleep(initial_delay)

        for i in range(num_beats):
            watchdog.beat()
            print(f"Heartbeat {i + 1}/{num_beats} sent")
            if i < num_beats - 1:  # No dormir después del último
                await asyncio.sleep(beat_interval)
    except asyncio.CancelledError:
        print("Slow start process simulation cancelled")
        raise


@pytest.mark.asyncio
async def test_healthy_process_no_timeout():
    """Test: Proceso saludable no debe disparar timeout"""
    timeout = 0.1  # 100ms
    beat_interval = 0.02  # 20ms
    num_beats = 10

    on_timeout = MagicMock()

    wd = Watchdog(timeout=timeout, on_timeout=on_timeout)

    try:
        await wd.start()

        # Ejecutar proceso saludable
        await simulate_healthy_process(wd, beat_interval, num_beats)

        # Dar margen de seguridad
        await asyncio.sleep(timeout * 0.5)

    finally:
        await wd.stop()

    # Verificar que no hubo timeout
    on_timeout.assert_not_called()


@pytest.mark.asyncio
async def test_failing_process_triggers_timeout():
    """Test: Proceso que falla debe disparar timeout"""
    timeout = 0.1  # 100ms
    beat_interval = 0.02  # 20ms
    fail_after = 3

    on_timeout = MagicMock()

    wd = Watchdog(timeout=timeout, on_timeout=on_timeout)

    try:
        await wd.start()

        # Crear tarea que falla
        failing_task = asyncio.create_task(
            simulate_failing_process(wd, beat_interval, fail_after)
        )

        # Esperar suficiente tiempo para que se detecte el timeout
        await asyncio.sleep(timeout * 3)

        # Cancelar el proceso colgado
        failing_task.cancel()
        try:
            await failing_task
        except asyncio.CancelledError:
            pass

    finally:
        await wd.stop()

    # Verificar que se detectó al menos un timeout
    assert on_timeout.call_count >= 1


@pytest.mark.asyncio
async def test_watchdog_waits_for_first_heartbeat():
    """Test: Watchdog debe esperar el primer heartbeat antes de monitoreo"""
    timeout = 0.05  # 50ms
    initial_delay = 0.02  # 20ms delay antes del primer heartbeat
    beat_interval = 0.01  # 10ms entre beats

    on_timeout = MagicMock()

    wd = Watchdog(timeout=timeout, on_timeout=on_timeout)

    try:
        await wd.start()

        # Proceso que tarda un poco en empezar pero luego es regular
        await simulate_slow_start_process(wd, initial_delay, beat_interval, 5)

        # Margen de seguridad
        await asyncio.sleep(timeout * 0.5)

    finally:
        await wd.stop()

    # No debe haber timeout porque el primer delay está dentro de lo esperado
    on_timeout.assert_not_called()


@pytest.mark.asyncio
async def test_watchdog_stops_cleanly():
    """Test: Watchdog debe detenerse limpiamente sin disparar timeout"""
    timeout = 0.1

    on_timeout = MagicMock()

    wd = Watchdog(timeout=timeout, on_timeout=on_timeout)

    try:
        await wd.start()

        # Enviar primer heartbeat para que empiece el monitoreo
        wd.beat()
        await asyncio.sleep(0.01)  # Dar tiempo para que procese

        # Detener watchdog
        await wd.stop()

        # Esperar más tiempo del timeout para verificar que no se llama
        await asyncio.sleep(timeout * 2)

    except Exception:
        # Cleanup en caso de error
        await wd.stop()
        raise

    on_timeout.assert_not_called()


@pytest.mark.asyncio
async def test_async_timeout_callback():
    """Test: Callback asíncrono de timeout funciona correctamente"""
    timeout = 0.05

    callback_calls = []

    async def async_timeout_handler():
        callback_calls.append(time.time())
        await asyncio.sleep(0.001)  # Simular trabajo asíncrono

    wd = Watchdog(timeout=timeout, on_timeout=async_timeout_handler)

    try:
        await wd.start()

        # Enviar primer heartbeat y luego parar
        wd.beat()
        await asyncio.sleep(0.01)

        # Esperar timeout
        await asyncio.sleep(timeout * 2)

    finally:
        await wd.stop()

    # Verificar que el callback asíncrono se ejecutó
    assert len(callback_calls) >= 1


@pytest.mark.asyncio
async def test_sync_timeout_callback():
    """Test: Callback síncrono de timeout funciona correctamente"""
    timeout = 0.05

    callback_calls = []

    def sync_timeout_handler():
        callback_calls.append(time.time())

    wd = Watchdog(timeout=timeout, on_timeout=sync_timeout_handler)

    try:
        await wd.start()

        # Enviar primer heartbeat y luego parar
        wd.beat()
        await asyncio.sleep(0.01)

        # Esperar timeout
        await asyncio.sleep(timeout * 2)

    finally:
        await wd.stop()

    # Verificar que el callback síncrono se ejecutó
    assert len(callback_calls) >= 1


@pytest.mark.asyncio
async def test_multiple_start_calls_safe():
    """Test: Múltiples llamadas a start() son seguras"""
    timeout = 0.1

    on_timeout = MagicMock()

    wd = Watchdog(timeout=timeout, on_timeout=on_timeout)

    try:
        # Múltiples start() no deben crear múltiples tareas
        await wd.start()
        first_task = wd._task

        await wd.start()  # Segunda llamada
        await wd.start()  # Tercera llamada

        # Debe ser la misma tarea
        assert wd._task is first_task

        # Enviar heartbeat y verificar funcionamiento normal
        wd.beat()
        await asyncio.sleep(0.01)

    finally:
        await wd.stop()

    on_timeout.assert_not_called()


@pytest.mark.asyncio
async def test_stop_before_start():
    """Test: stop() antes de start() debe ser seguro"""
    timeout = 0.1

    wd = Watchdog(timeout=timeout)

    # stop() sin start() previo debe ser seguro
    await wd.stop()

    # Después debería poder start() normalmente
    await wd.start()
    wd.beat()
    await asyncio.sleep(0.01)

    await wd.stop()


@pytest.mark.asyncio
async def test_concurrent_beats():
    """Test: Múltiples beats concurrentes deben funcionar correctamente"""
    timeout = 0.1

    on_timeout = MagicMock()

    wd = Watchdog(timeout=timeout, on_timeout=on_timeout)

    async def beat_sender(beat_id: int, num_beats: int):
        for i in range(num_beats):
            await asyncio.sleep(0.01)
            wd.beat()
            print(f"Beat {i + 1} from sender {beat_id}")

    try:
        await wd.start()

        # Múltiples "procesos" enviando beats concurrentemente
        tasks = [
            asyncio.create_task(beat_sender(1, 5)),
            asyncio.create_task(beat_sender(2, 5)),
            asyncio.create_task(beat_sender(3, 5)),
        ]

        await asyncio.gather(*tasks)

        # Margen de seguridad
        await asyncio.sleep(timeout * 0.5)

    finally:
        await wd.stop()

    on_timeout.assert_not_called()


@pytest.mark.asyncio
async def test_sync_callback_exception_does_not_kill_watchdog():
    """Test: Excepción en callback síncrono no mata el watchdog"""
    timeout = 0.05

    callback_calls = []

    def failing_sync_callback():
        callback_calls.append(1)
        raise RuntimeError("Callback failed")

    wd = Watchdog(timeout=timeout, on_timeout=failing_sync_callback)

    try:
        await wd.start()

        # Enviar primer heartbeat
        wd.beat()
        await asyncio.sleep(0.01)

        # Esperar a que se dispare el timeout al menos 2 veces
        await asyncio.sleep(timeout * 3)

    finally:
        await wd.stop()

    # Verificar que el callback se llamó al menos 2 veces
    # (si el watchdog muriera en el primer fallo, solo habría 1 llamada)
    assert len(callback_calls) >= 2


@pytest.mark.asyncio
async def test_async_callback_exception_does_not_kill_watchdog():
    """Test: Excepción en callback asíncrono no mata el watchdog"""
    timeout = 0.05

    callback_calls = []

    async def failing_async_callback():
        callback_calls.append(1)
        raise ValueError("Async callback failed")

    wd = Watchdog(timeout=timeout, on_timeout=failing_async_callback)

    try:
        await wd.start()

        # Enviar primer heartbeat
        wd.beat()
        await asyncio.sleep(0.01)

        # Esperar a que se dispare el timeout al menos 2 veces
        await asyncio.sleep(timeout * 3)

    finally:
        await wd.stop()

    # Verificar que el callback se llamó al menos 2 veces
    assert len(callback_calls) >= 2


@pytest.mark.asyncio
async def test_callback_exception_is_logged():
    """Test: Excepción en callback se loguea correctamente"""
    timeout = 0.05

    def failing_callback():
        raise RuntimeError("boom")

    # Inyectar mock logger
    mock_logger = MagicMock(spec=logging.Logger)

    wd = Watchdog(
        timeout=timeout, on_timeout=failing_callback, logger=mock_logger
    )

    try:
        await wd.start()

        # Enviar primer heartbeat
        wd.beat()
        await asyncio.sleep(0.01)

        # Esperar a que se dispare el timeout
        await asyncio.sleep(timeout * 2)

    finally:
        await wd.stop()

    # Verificar que se llamó a logger.error al menos una vez
    assert mock_logger.error.call_count >= 1

    # Verificar que el mensaje contiene "RuntimeError"
    error_call_args = mock_logger.error.call_args_list[0]
    error_message = error_call_args[0][0]
    assert "RuntimeError" in error_message


# ============================================================================
# FEATURE #2: Tests de validación de parámetros
# ============================================================================


def test_timeout_negative_raises_value_error():
    """Test: timeout negativo debe lanzar ValueError"""
    with pytest.raises(ValueError, match="timeout must be >="):
        Watchdog(timeout=-1.0)


def test_timeout_zero_raises_value_error():
    """Test: timeout cero debe lanzar ValueError"""
    with pytest.raises(ValueError, match="timeout must be >="):
        Watchdog(timeout=0)


@pytest.mark.parametrize("invalid_timeout", ["foo", None, True])
def test_timeout_invalid_type_raises_type_error(invalid_timeout):
    """Test: timeout con tipo inválido debe lanzar TypeError"""
    with pytest.raises(TypeError, match="numeric value"):
        Watchdog(timeout=invalid_timeout)


@pytest.mark.parametrize("invalid_callback", ["not_callable", 42])
def test_on_timeout_not_callable_raises_type_error(invalid_callback):
    """Test: on_timeout no callable debe lanzar TypeError"""
    with pytest.raises(TypeError, match="callable"):
        Watchdog(timeout=0.1, on_timeout=invalid_callback)


# ============================================================================
# FEATURE #3: Tests de timeout en callback async
# ============================================================================


@pytest.mark.asyncio
async def test_hanging_async_callback_is_interrupted():
    """Test: Callback async que cuelga no bloquea el watchdog"""
    timeout = 0.05

    async def hanging_callback():
        """Callback que nunca retorna"""
        await asyncio.sleep(9999)

    wd = Watchdog(timeout=timeout, on_timeout=hanging_callback)

    try:
        await wd.start()

        # Enviar primer heartbeat
        wd.beat()
        await asyncio.sleep(0.01)

        # Esperar varios ciclos de timeout
        await asyncio.sleep(timeout * 4)

        # Verificar que el watchdog sigue vivo
        assert wd._task is not None
        assert not wd._task.done()

    finally:
        await wd.stop()


@pytest.mark.asyncio
async def test_hanging_async_callback_timeout_is_logged():
    """Test: Callback async que cuelga se loguea como error"""
    timeout = 0.05

    async def hanging_callback():
        """Callback que nunca retorna"""
        await asyncio.sleep(9999)

    # Inyectar mock logger
    mock_logger = MagicMock(spec=logging.Logger)

    wd = Watchdog(
        timeout=timeout, on_timeout=hanging_callback, logger=mock_logger
    )

    try:
        await wd.start()

        # Enviar primer heartbeat
        wd.beat()
        await asyncio.sleep(0.01)

        # Esperar a que se dispare el timeout
        await asyncio.sleep(timeout * 3)

    finally:
        await wd.stop()

    # Verificar que se llamó a logger.error al menos una vez
    assert mock_logger.error.call_count >= 1

    # Verificar que el mensaje contiene "exceeded" o "cancelled"
    error_call_args = mock_logger.error.call_args_list[0]
    error_message = error_call_args[0][0]
    assert "exceeded" in error_message or "cancelled" in error_message


# Función utilitaria para ejecutar tests con uvloop
def run_test_with_uvloop(test_func):
    """Ejecutar un test específico con uvloop"""

    async def wrapper():
        await test_func()

    uvloop.run(wrapper())


# Tests que se pueden ejecutar manualmente con uvloop
if __name__ == "__main__":
    print("🚀 Ejecutando tests con uvloop...")

    tests = [
        ("Healthy Process", test_healthy_process_no_timeout),
        ("Failing Process", test_failing_process_triggers_timeout),
        ("First Heartbeat Wait", test_watchdog_waits_for_first_heartbeat),
        ("Clean Stop", test_watchdog_stops_cleanly),
        ("Async Callback", test_async_timeout_callback),
        ("Sync Callback", test_sync_timeout_callback),
        ("Multiple Starts", test_multiple_start_calls_safe),
        ("Stop Before Start", test_stop_before_start),
        ("Concurrent Beats", test_concurrent_beats),
        (
            "Sync Callback Exception",
            test_sync_callback_exception_does_not_kill_watchdog,
        ),
        (
            "Async Callback Exception",
            test_async_callback_exception_does_not_kill_watchdog,
        ),
        ("Callback Exception Logged", test_callback_exception_is_logged),
        ("Timeout Negative", test_timeout_negative_raises_value_error),
        ("Timeout Zero", test_timeout_zero_raises_value_error),
        ("Timeout Invalid Type", test_timeout_invalid_type_raises_type_error),
        (
            "OnTimeout Not Callable",
            test_on_timeout_not_callable_raises_type_error,
        ),
        (
            "Hanging Callback Interrupted",
            test_hanging_async_callback_is_interrupted,
        ),
        (
            "Hanging Callback Logged",
            test_hanging_async_callback_timeout_is_logged,
        ),
    ]

    for test_name, test_func in tests:
        print(f"\n🧪 {test_name}...")
        try:
            run_test_with_uvloop(test_func)
            print(f"✅ {test_name}: PASSED")
        except Exception as e:
            print(f"❌ {test_name}: FAILED - {e}")

    print("\n🏁 Tests completados!")
