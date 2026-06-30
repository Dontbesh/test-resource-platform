import socket
import time


class TcpConnectivityChecker:
    def check(self, host: str, port: int, timeout_seconds: float) -> tuple[bool, int, str | None]:
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout_seconds):
                latency_ms = int((time.perf_counter() - started) * 1000)
                return True, latency_ms, None
        except OSError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return False, latency_ms, str(exc)
