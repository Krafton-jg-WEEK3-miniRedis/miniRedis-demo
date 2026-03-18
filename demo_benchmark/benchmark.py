from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any


def timed_call(func, *args, **kwargs) -> tuple[Any, float]:
    started = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return result, elapsed_ms


def summarize(samples: list[float]) -> dict[str, float]:
    if not samples:
        return {"avg_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "p95_ms": 0.0, "requests_per_sec": 0.0}
    sorted_samples = sorted(samples)
    p95_index = min(len(sorted_samples) - 1, max(0, round((len(sorted_samples) - 1) * 0.95)))
    avg_ms = statistics.mean(sorted_samples)
    return {
        "avg_ms": round(avg_ms, 3),
        "min_ms": round(sorted_samples[0], 3),
        "max_ms": round(sorted_samples[-1], 3),
        "p95_ms": round(sorted_samples[p95_index], 3),
        "requests_per_sec": round(1000 / avg_ms, 3) if avg_ms > 0 else 0.0,
    }


def write_artifact(directory: Path, payload: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = directory / f"benchmark-{timestamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
