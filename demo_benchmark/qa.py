from __future__ import annotations

import time
from typing import Any, Callable

from .mini_redis import RedisCommandError, RedisProtocolError


def run_demo_qa_suite(service: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def record(name: str, fn: Callable) -> None:
        started = time.perf_counter()
        try:
            status, expected, actual, reason = fn()
            results.append(_scenario_result(name, started, status, expected, actual, reason))
        except Exception as exc:
            results.append(_scenario_result(name, started, "fail", "-", None, str(exc)))

    # 1. MongoDB 연결 확인
    def check_mongo():
        doc = service.mongo_repo.get_document("listing:1001")
        if doc is not None:
            return "pass", "document found", doc.get("listing_id"), None
        return "fail", "document found", None, "listing:1001 not found in MongoDB — run mini-redis-seed"

    # 2. 캐시 MISS → MongoDB 조회 → Redis 저장
    def check_cache_miss():
        service.redis_client.delete("listing:1001")
        result = service.lookup("listing:1001", "cache")
        if result["source"] == "mini-redis-miss-filled":
            return "pass", "mini-redis-miss-filled", result["source"], None
        return "fail", "mini-redis-miss-filled", result["source"], "캐시 MISS 후 MongoDB 조회 및 Redis 저장 실패"

    # 3. 캐시 HIT 확인
    def check_cache_hit():
        result = service.lookup("listing:1001", "cache")
        if result["source"] == "mini-redis-hit":
            return "pass", "mini-redis-hit", result["source"], None
        return "fail", "mini-redis-hit", result["source"], "캐시 HIT 실패 — Redis에 데이터가 없음"

    # 4. 검색 캐시 MISS → HIT
    def check_search_cache():
        service.redis_client.delete("market:search:아이폰:all:digital:12")
        first = service.marketplace_search("cache", query="아이폰", location="all", category="digital", limit=12)
        second = service.marketplace_search("cache", query="아이폰", location="all", category="digital", limit=12)
        first_status = first["trace"]["cache_status"]
        second_status = second["trace"]["cache_status"]
        if first_status == "miss-fill" and second_status == "hit":
            return "pass", "miss-fill → hit", f"{first_status} → {second_status}", None
        return "fail", "miss-fill → hit", f"{first_status} → {second_status}", "검색 캐시 MISS→HIT 흐름 실패"

    # 5. TTL 설정 후 키 존재 확인
    def check_ttl_set():
        result = service.ttl_set("listing:1001", ttl_seconds=10)
        cached = service.redis_client.get("listing:1001")
        if result["redis_set"] and cached is not None:
            return "pass", "key exists with TTL", "exists", None
        return "fail", "key exists with TTL", "not found", "TTL 설정 후 Redis에서 키를 찾을 수 없음"

    # 6. TTL 만료 후 Redis nil, MongoDB 유지
    def check_ttl_expire():
        service.redis_client.set("qa:ttl:test", "expiring")
        service.redis_client.expire("qa:ttl:test", 1)
        time.sleep(1.2)
        cached = service.redis_client.get("qa:ttl:test")
        if cached is None:
            return "pass", None, cached, None
        return "fail", None, cached, "TTL 만료 후에도 Redis에서 값이 반환됨"

    # 7. MongoDB vs Redis 응답속도 비교
    def check_speed_comparison():
        result = service.lookup_compare("listing:1001")
        mongo_ms = result["mongo"]["latency_ms"]
        redis_ms = result["redis"]["latency_ms"]
        if result["redis"]["found"] and redis_ms <= mongo_ms:
            return "pass", "redis ≤ mongo", f"redis={redis_ms}ms, mongo={mongo_ms}ms", None
        if not result["redis"]["found"]:
            return "fail", "redis found", "not found", "Redis에 캐시가 없음 — 먼저 캐시 워밍 필요"
        return "fail", "redis ≤ mongo", f"redis={redis_ms}ms, mongo={mongo_ms}ms", "Redis가 MongoDB보다 느림"

    record("MongoDB 연결 확인", check_mongo)
    record("캐시 MISS → Redis 저장", check_cache_miss)
    record("캐시 HIT 확인", check_cache_hit)
    record("검색 캐시 MISS → HIT", check_search_cache)
    record("TTL 설정 후 키 존재", check_ttl_set)
    record("TTL 만료 후 Redis nil", check_ttl_expire)
    record("MongoDB vs Redis 속도", check_speed_comparison)

    return results


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
