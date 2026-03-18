from __future__ import annotations

import resource
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MetricEvent:
    name: str
    latency_ms: float
    success: bool
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    def __init__(self, history_limit: int = 50) -> None:
        self.history_limit = history_limit
        self.events: deque[MetricEvent] = deque(maxlen=history_limit * 10)
        self.history: deque[dict[str, Any]] = deque(maxlen=history_limit)
        self.cache_hits = 0
        self.cache_misses = 0
        self.error_count = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.active_connections = 0
        self.command_timestamps: deque[float] = deque()
        self._last_cpu_total = self._cpu_total()
        self._last_cpu_time = time.time()

    def record_event(self, name: str, latency_ms: float, success: bool = True) -> None:
        if not success:
            self.error_count += 1
        now = time.time()
        self.events.append(MetricEvent(name=name, latency_ms=latency_ms, success=success, timestamp=now))
        self.command_timestamps.append(now)
        self._trim_commands(now)

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        self.cache_misses += 1

    def record_network(self, sent: int, received: int) -> None:
        self.bytes_sent += max(sent, 0)
        self.bytes_received += max(received, 0)

    def connection_opened(self) -> None:
        self.active_connections += 1

    def connection_closed(self) -> None:
        self.active_connections = max(0, self.active_connections - 1)

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        self._trim_commands(now)
        latencies = [event.latency_ms for event in self.events if event.success]
        snapshot = {
            "timestamp": now,
            "request_count": len(self.events),
            "error_count": self.error_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_ratio": round(self.cache_hits / max(self.cache_hits + self.cache_misses, 1), 4),
            "requests_per_sec": round(len(self.command_timestamps), 2),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
            "rss_used_memory_kb": self._memory_kb(),
            "active_connections": self.active_connections,
            "cpu_percent": round(self._cpu_percent(now), 2),
            "network_tx_bytes": self.bytes_sent,
            "network_rx_bytes": self.bytes_received,
        }
        self.history.append(snapshot)
        return snapshot

    def history_payload(self) -> list[dict[str, Any]]:
        return list(self.history)

    def _trim_commands(self, now: float) -> None:
        while self.command_timestamps and now - self.command_timestamps[0] > 1.0:
            self.command_timestamps.popleft()

    def _memory_kb(self) -> int:
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

    def _cpu_total(self) -> float:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return usage.ru_utime + usage.ru_stime

    def _cpu_percent(self, now: float) -> float:
        elapsed = max(now - self._last_cpu_time, 1e-6)
        current_cpu_total = self._cpu_total()
        delta = current_cpu_total - self._last_cpu_total
        self._last_cpu_total = current_cpu_total
        self._last_cpu_time = now
        return (delta / elapsed) * 100.0
