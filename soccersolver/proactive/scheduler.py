"""
SoccerSolver - Proactive Background Scheduler
Runs autonomous background scouting runs on schedule or intervals.
"""

import threading
import time
from typing import Optional, Callable
from soccersolver.proactive.triggers import ProactiveEventEngine


class ProactiveScheduler:
    def __init__(self, engine: Optional[ProactiveEventEngine] = None, interval_seconds: int = 3600):
        self.engine = engine or ProactiveEventEngine()
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_run_time: Optional[float] = None
        self.runs_completed: int = 0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def trigger_now(self):
        """Forces an immediate proactive scan cycle."""
        self._execute_cycle()

    def _run_loop(self):
        while not self._stop_event.is_set():
            self._execute_cycle()
            self._stop_event.wait(self.interval_seconds)

    def _execute_cycle(self):
        self.last_run_time = time.time()
        self.runs_completed += 1
        # Scan for contract expiry opportunities
        self.engine.scan_contract_expiry_opportunities(limit=2)
