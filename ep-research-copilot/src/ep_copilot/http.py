"""Small HTTP helper: timeouts, retries with exponential backoff, polite rate limiting."""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "ep-research-copilot/0.1 (open-source research surveillance; public APIs)"


class FetchError(RuntimeError):
    """A source could not be retrieved after retries."""


class RateLimiter:
    def __init__(self, per_second: float):
        self.interval = 1.0 / per_second
        self._last = 0.0

    def wait(self) -> None:
        delay = self._last + self.interval - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()


RETRY_STATUS = {429, 500, 502, 503, 504}


def get(url: str, params: dict | None = None, *, limiter: RateLimiter | None = None,
        timeout: float = 30.0, retries: int = 4, backoff: float = 1.0,
        opener=urllib.request.urlopen, sleep=time.sleep) -> bytes:
    """GET with retries. Raises FetchError with the URL and last error after the final attempt."""
    full = url + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    last: Exception | None = None
    for attempt in range(retries + 1):
        if limiter:
            limiter.wait()
        try:
            req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
            with opener(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in RETRY_STATUS:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last = exc
        if attempt < retries:
            sleep(backoff * (2 ** attempt))
    host = urllib.parse.urlsplit(url)
    raise FetchError(f"Could not reach {host.scheme}://{host.netloc}{host.path} after {retries + 1} attempts ({last}). "
                     "Check the internet connection, or try the demo with --offline.")
