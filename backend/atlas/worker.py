"""Background worker. It is the only part that calls AI providers and writes to the atlas."""

import signal
import threading

from atlas.logging import get_logger
from atlas.pipeline import queue
from atlas.pipeline.handlers import HANDLERS
from atlas.pipeline.runner import work_once
from atlas.providers.registry import get_providers
from atlas.settings import get_settings

log = get_logger("atlas.worker")


def main() -> None:
    settings = get_settings()
    providers = get_providers()
    ensure_bucket = getattr(providers.blobs, "ensure_bucket", None)
    if ensure_bucket is not None and settings.environment == "development":
        ensure_bucket()

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    # Anything this worker held when it last stopped goes back on the queue.
    released = queue.release(settings.worker_name)
    log.info("worker.started", released=released, providers=settings.providers)
    while not stop.is_set():
        try:
            worked = work_once(HANDLERS, providers, settings)
        except Exception as error:
            log.error("worker.loop_error", error=error)
            worked = False
        if not worked:
            stop.wait(settings.worker_poll_seconds)
    log.info("worker.stopped")


if __name__ == "__main__":
    main()
