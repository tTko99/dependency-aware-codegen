"""Cancellable process boundary for blocking providers/tools, NOT a security sandbox."""
from __future__ import annotations

import multiprocessing
import os
import signal
import subprocess
import time


def _worker(connection, function, args):
    if os.name == "posix":
        os.setsid()
    try:
        connection.send((True, function(*args)))
    except BaseException as exc:  # noqa: BLE001 - worker exception transport
        connection.send((False, f"{type(exc).__name__}: {exc}"))
    finally:
        connection.close()


def bounded(function, args, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("global deadline expired")
    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(writer, function, args), daemon=False)
    process.start()
    writer.close()
    try:
        if not reader.poll(max(0, deadline - time.monotonic())):
            raise TimeoutError("global deadline expired")
        success, value = reader.recv()
        if time.monotonic() >= deadline:
            raise TimeoutError("global deadline expired")
        if not success:
            raise RuntimeError(value)
        return value
    finally:
        if process.is_alive():
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                )
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.kill()
        process.join()
        reader.close()
