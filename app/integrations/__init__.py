"""External service integrations — Module 2/3 adapters.

Every integration supports two modes:

* **Live mode** — an API key is configured; the real endpoint is called with
  retry/backoff, and failures are caught, logged, and reported in the morning
  brief (never silently swallowed).
* **Simulation mode** — no key; the call is faked, logged as `simulated`, and
  returns a deterministic placeholder so the studio can be demoed and developed
  offline without spending money or publishing anything.

Nothing is published or transacted until the human hits Approve.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from ..activity import log


class IntegrationBase(ABC):
    name: str = "integration"

    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key
        self.configured = bool(api_key and api_key.strip())

    @property
    def mode(self) -> str:
        return "live" if self.configured else "simulated"

    def _log(self, action: str, status: str, detail: str = "", module: str | None = None) -> None:
        mod = module or self.name
        log(mod, action, status, detail)

    def call_with_retry(
        self,
        action: str,
        func,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        module: str | None = None,
    ) -> Any:
        """Call `func` with exponential backoff; log and re-raise on total failure."""
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                result = func()
                if attempt > 1:
                    self._log(action, "ok", f"succeeded on attempt {attempt}", module=module)
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self._log(
                    action,
                    "warn",
                    f"attempt {attempt}/{max_attempts} failed: {exc}",
                    module=module,
                )
                if attempt < max_attempts:
                    time.sleep(base_delay * (2 ** (attempt - 1)))
        self._log(action, "error", f"all attempts failed: {last_error}", module=module)
        raise last_error  # type: ignore[no-any-return]

    @abstractmethod
    def health(self) -> dict[str, Any]:
        ...
