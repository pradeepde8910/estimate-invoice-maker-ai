"""In-process login rate limiting.

Deliberately simple (no Redis dependency) given this app's single-process
deployment. Tracks failed login attempts per (client_ip, username) in a
sliding window and locks that pair out once a threshold is exceeded.

Caveat: state is per-process. Behind multiple gunicorn/uvicorn workers each
worker has its own counters, so the effective limit is
MAX_FAILED_ATTEMPTS * worker_count. That's still far better than the
previous unlimited brute force, but if you scale out workers, move this to
a shared store (Redis) to keep the limit exact.
"""
import time
import threading

WINDOW_SECONDS = 15 * 60
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60

_lock = threading.Lock()
_failures: dict[str, list[float]] = {}
_locked_until: dict[str, float] = {}


def _key(client_ip: str, username: str) -> str:
    return f"{client_ip}:{username.lower()}"


def check_login_rate_limit(client_ip: str, username: str) -> float | None:
    """Returns seconds remaining if this (ip, username) pair is locked out, else None."""
    key = _key(client_ip, username)
    now = time.time()
    with _lock:
        locked_until = _locked_until.get(key)
        if locked_until and locked_until > now:
            return locked_until - now
        if locked_until:
            del _locked_until[key]
        return None


def record_login_failure(client_ip: str, username: str) -> None:
    key = _key(client_ip, username)
    now = time.time()
    with _lock:
        attempts = [t for t in _failures.get(key, []) if now - t < WINDOW_SECONDS]
        attempts.append(now)
        _failures[key] = attempts
        if len(attempts) >= MAX_FAILED_ATTEMPTS:
            _locked_until[key] = now + LOCKOUT_SECONDS
            _failures[key] = []


def record_login_success(client_ip: str, username: str) -> None:
    key = _key(client_ip, username)
    with _lock:
        _failures.pop(key, None)
        _locked_until.pop(key, None)
