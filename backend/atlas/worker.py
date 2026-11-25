"""Background worker entry point. The job loop arrives in M2-T2."""

import signal
import threading


def main() -> None:
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    stop.wait()


if __name__ == "__main__":
    main()
