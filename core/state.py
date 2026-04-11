from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field

from .config import NexusPaths


LIGHT_SYMBOLS = {
    "idle": "○",
    "planning": "◌",
    "thinking": "●",
    "acting": "●",
    "error": "●",
}

LIGHT_COLORS = {
    "idle": "white",
    "planning": "cyan",
    "thinking": "yellow",
    "acting": "green",
    "error": "red",
}


@dataclass(slots=True)
class ActivitySnapshot:
    state: str = "idle"
    pulse_on: bool = False
    api_latency_ms: int = 0
    current_model: str = "-"
    last_error: str = ""
    autonomous_mode: bool = False
    detail: str = ""
    current_goal: str = ""
    current_step: int = 0
    total_steps: int = 0
    cancellable: bool = False


@dataclass
class ActivityMonitor:
    snapshot: ActivitySnapshot = field(default_factory=ActivitySnapshot)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                if self.snapshot.state == "acting":
                    self.snapshot.pulse_on = not self.snapshot.pulse_on
                elif self.snapshot.state == "thinking":
                    self.snapshot.pulse_on = True
                elif self.snapshot.state == "planning":
                    self.snapshot.pulse_on = not self.snapshot.pulse_on
                elif self.snapshot.state == "error":
                    self.snapshot.pulse_on = True
                else:
                    self.snapshot.pulse_on = False
                self._write_activity_file()
            time.sleep(0.35)

    def set_state(self, state: str, error: str = "", detail: str = "") -> None:
        with self._lock:
            self.snapshot.state = state
            if error:
                self.snapshot.last_error = error
            if detail:
                self.snapshot.detail = detail
            elif state == "idle":
                self.snapshot.detail = ""
            self._write_activity_file()

    def set_latency(self, latency_ms: int) -> None:
        with self._lock:
            self.snapshot.api_latency_ms = latency_ms
            self._write_activity_file()

    def set_model(self, model_name: str) -> None:
        with self._lock:
            self.snapshot.current_model = model_name
            self._write_activity_file()

    def set_autonomous_mode(self, enabled: bool) -> None:
        with self._lock:
            self.snapshot.autonomous_mode = enabled
            self._write_activity_file()

    def set_detail(self, detail: str) -> None:
        with self._lock:
            self.snapshot.detail = detail
            self._write_activity_file()

    def set_goal(self, goal: str) -> None:
        with self._lock:
            self.snapshot.current_goal = goal
            self._write_activity_file()

    def set_step_progress(self, current_step: int, total_steps: int, detail: str = "") -> None:
        with self._lock:
            self.snapshot.current_step = max(0, int(current_step))
            self.snapshot.total_steps = max(0, int(total_steps))
            if detail:
                self.snapshot.detail = detail
            self._write_activity_file()

    def set_cancellable(self, enabled: bool) -> None:
        with self._lock:
            self.snapshot.cancellable = enabled
            self._write_activity_file()

    def read(self) -> ActivitySnapshot:
        with self._lock:
            return ActivitySnapshot(**asdict(self.snapshot))

    def _write_activity_file(self) -> None:
        NexusPaths.ensure()
        NexusPaths.activity_path.write_text(json.dumps(asdict(self.snapshot), indent=2), encoding="utf-8")
