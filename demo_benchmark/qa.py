from __future__ import annotations

import time
from typing import Any, Callable

from .mini_redis import RedisCommandError, RedisProtocolError


def _scenario_result(
    name: str,
    started_at: float,
    status: str,
    expected: Any,
    actual: Any,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "scenario": name,
        "status": status,
        "expected": expected,
        "actual": actual,
        "latency_ms": round((time.perf_counter() - started_at) * 1000, 3),
        "failure_reason": failure_reason,
    }


def _run_case(name: str, func: Callable[[], Any], expected: Any, predicate: Callable[[Any], bool]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        actual = func()
        if predicate(actual):
            return _scenario_result(name, started, "pass", expected, actual)
        return _scenario_result(name, started, "fail", expected, actual, "Unexpected response")
    except Exception as exc:  # pragma: no cover - exercised in integration flows
        return _scenario_result(name, started, "fail", expected, None, str(exc))


def run_qa_suite(redis_client) -> list[dict[str, Any]]:
    results = [
        _run_case("PING", redis_client.ping, "PONG", lambda value: value in ("PONG", "OK")),
        _run_case(
            "SET then GET",
            lambda: (redis_client.set("qa:key", "first"), redis_client.get("qa:key"))[-1],
            "first",
            lambda value: value == "first",
        ),
        _run_case(
            "Overwrite existing key",
            lambda: (redis_client.set("qa:key", "second"), redis_client.get("qa:key"))[-1],
            "second",
            lambda value: value == "second",
        ),
        _run_case("Missing key lookup", lambda: redis_client.get("qa:missing"), None, lambda value: value is None),
        _run_case(
            "DEL multiple keys",
            lambda: (
                redis_client.set("qa:del:1", "1"),
                redis_client.set("qa:del:2", "2"),
                redis_client.delete("qa:del:1", "qa:del:2", "qa:del:3"),
            )[-1],
            2,
            lambda value: value == 2,
        ),
    ]

    started = time.perf_counter()
    try:
        redis_client.set("qa:ttl", "expiring")
        expire_response = redis_client.expire("qa:ttl", 1)
        time.sleep(1.05)
        actual = redis_client.get("qa:ttl")
        status = "pass" if expire_response in (1, "1", "OK") and actual is None else "fail"
        reason = None if status == "pass" else "EXPIRE did not remove the key lazily"
        results.append(_scenario_result("EXPIRE lazy expiration", started, status, None, actual, reason))
    except Exception as exc:
        results.append(_scenario_result("EXPIRE lazy expiration", started, "fail", None, None, str(exc)))

    results.extend(
        [
            _run_case("QUIT", redis_client.quit, "OK", lambda value: value in ("OK", "PONG", "BYE")),
            _run_case("EXIT", redis_client.exit, "OK", lambda value: value in ("OK", "PONG", "BYE")),
        ]
    )

    started = time.perf_counter()
    try:
        redis_client.execute("UNKNOWN")
        results.append(_scenario_result("Unknown command", started, "fail", "error", None, "Unknown command succeeded"))
    except RedisCommandError as exc:
        results.append(_scenario_result("Unknown command", started, "pass", "error", str(exc)))
    except Exception as exc:
        results.append(_scenario_result("Unknown command", started, "fail", "error", None, str(exc)))

    started = time.perf_counter()
    try:
        redis_client.execute("GET")
        results.append(_scenario_result("Wrong arity", started, "fail", "error", None, "Wrong arity succeeded"))
    except RedisCommandError as exc:
        results.append(_scenario_result("Wrong arity", started, "pass", "error", str(exc)))
    except Exception as exc:
        results.append(_scenario_result("Wrong arity", started, "fail", "error", None, str(exc)))

    started = time.perf_counter()
    try:
        redis_client.send_raw(b"not-a-valid-resp\r\n")
        results.append(_scenario_result("Malformed RESP", started, "fail", "protocol error", None, "Malformed RESP succeeded"))
    except (RedisProtocolError, RedisCommandError) as exc:
        results.append(_scenario_result("Malformed RESP", started, "pass", "protocol error", str(exc)))
    except Exception as exc:
        results.append(_scenario_result("Malformed RESP", started, "fail", "protocol error", None, str(exc)))

    return results
