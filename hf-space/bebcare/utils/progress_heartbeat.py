"""Background progress bumps during long-running generation steps."""
from __future__ import annotations

import asyncio
from typing import Callable, Optional


class ProgressHeartbeat:
    """Advance a fractional progress callback on a timer while work runs."""

    def __init__(
        self,
        report: Callable[[str, float], None],
        stage: str,
        start: float,
        end: float,
        *,
        interval_sec: float = 4.0,
        step: float = 0.04,
    ) -> None:
        self._report = report
        self._stage = stage
        self._current = start
        self._end = end
        self._interval = interval_sec
        self._step = step
        self._task: Optional[asyncio.Task] = None

    def tick(self, fraction: Optional[float] = None, *, stage: Optional[str] = None) -> None:
        if stage is not None:
            self._stage = stage
        if fraction is not None:
            self._current = min(max(fraction, 0.0), self._end)
        self._report(self._stage, self._current)

    async def __aenter__(self) -> ProgressHeartbeat:
        self.tick(self._current)

        async def _loop() -> None:
            ceiling = self._end - self._step
            while self._current < ceiling:
                await asyncio.sleep(self._interval)
                self._current = min(self._current + self._step, ceiling)
                self._report(self._stage, self._current)

        self._task = asyncio.create_task(_loop())
        return self

    async def __aexit__(self, *_) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._report(self._stage, self._end)
