from __future__ import annotations

import json
from typing import Any

from .benchmark import summarize, timed_call, write_artifact
from .metrics import MetricsCollector
from .mongo_backend import MongoRepository
from .qa import run_qa_suite


class DemoService:
    def __init__(self, mongo_repo: MongoRepository, redis_client, metrics: MetricsCollector, artifacts_dir) -> None:
        self.mongo_repo = mongo_repo
        self.redis_client = redis_client
        self.metrics = metrics
        self.artifacts_dir = artifacts_dir

    def lookup(self, key: str, mode: str) -> dict[str, Any]:
        if mode == "mongo":
            document, latency_ms = timed_call(self.mongo_repo.get_document, key)
            success = document is not None
            self.metrics.record_event("lookup.mongo", latency_ms, success=success)
            return {
                "mode": mode,
                "key": key,
                "found": success,
                "latency_ms": round(latency_ms, 3),
                "source": "mongo",
                "payload": document,
            }

        if mode != "cache":
            raise ValueError(f"Unsupported lookup mode: {mode}")

        cached, cache_latency = timed_call(self.redis_client.get, key)
        if cached is not None:
            self.metrics.record_cache_hit()
            self.metrics.record_event("lookup.cache.hit", cache_latency, success=True)
            return {
                "mode": mode,
                "key": key,
                "found": True,
                "latency_ms": round(cache_latency, 3),
                "source": "mini-redis-hit",
                "payload": json.loads(cached),
            }

        self.metrics.record_cache_miss()
        document, mongo_latency = timed_call(self.mongo_repo.get_document, key)
        if document is None:
            total = cache_latency + mongo_latency
            self.metrics.record_event("lookup.cache.miss", total, success=False)
            return {
                "mode": mode,
                "key": key,
                "found": False,
                "latency_ms": round(total, 3),
                "source": "mongo-miss",
                "payload": None,
            }

        self.redis_client.set(key, json.dumps(document, ensure_ascii=False))
        total_latency = cache_latency + mongo_latency
        self.metrics.record_event("lookup.cache.miss", total_latency, success=True)
        return {
            "mode": mode,
            "key": key,
            "found": True,
            "latency_ms": round(total_latency, 3),
            "source": "mini-redis-miss-filled",
            "payload": document,
        }

    def marketplace_search(
        self,
        source: str,
        query: str = "",
        location: str = "all",
        category: str = "all",
        limit: int = 12,
    ) -> dict[str, Any]:
        cache_key = self._search_cache_key(query, location, category, limit)
        if source == "mongo":
            items, latency_ms = timed_call(self.mongo_repo.search_listings, query, location, category, limit)
            self.metrics.record_event("market.search.mongo", latency_ms, success=True)
            return {
                "source": "mongo",
                "items": items,
                "trace": self._trace_payload(
                    request_type="search",
                    key=cache_key,
                    source="mongo-direct",
                    cache_status="bypass",
                    latency_ms=latency_ms,
                    result_count=len(items),
                ),
            }

        if source != "cache":
            raise ValueError(f"Unsupported marketplace source: {source}")

        cached, cache_latency = timed_call(self.redis_client.get, cache_key)
        if cached is not None:
            items = json.loads(cached)
            self.metrics.record_cache_hit()
            self.metrics.record_event("market.search.cache.hit", cache_latency, success=True)
            return {
                "source": "cache",
                "items": items,
                "trace": self._trace_payload(
                    request_type="search",
                    key=cache_key,
                    source="mini-redis",
                    cache_status="hit",
                    latency_ms=cache_latency,
                    result_count=len(items),
                ),
            }

        self.metrics.record_cache_miss()
        items, mongo_latency = timed_call(self.mongo_repo.search_listings, query, location, category, limit)
        self.redis_client.set(cache_key, json.dumps(items, ensure_ascii=False))
        total_latency = cache_latency + mongo_latency
        self.metrics.record_event("market.search.cache.miss", total_latency, success=True)
        return {
            "source": "cache",
            "items": items,
            "trace": self._trace_payload(
                request_type="search",
                key=cache_key,
                source="mongo-then-mini-redis",
                cache_status="miss-fill",
                latency_ms=total_latency,
                result_count=len(items),
            ),
        }

    def marketplace_listing(self, listing_id: int, source: str) -> dict[str, Any]:
        cache_key = f"market:listing:{listing_id}"
        if source == "mongo":
            listing, latency_ms = timed_call(self.mongo_repo.get_listing_by_id, listing_id)
            self.metrics.record_event("market.listing.mongo", latency_ms, success=listing is not None)
            return {
                "source": "mongo",
                "listing": listing,
                "trace": self._trace_payload(
                    request_type="listing",
                    key=cache_key,
                    source="mongo-direct",
                    cache_status="bypass",
                    latency_ms=latency_ms,
                    result_count=1 if listing else 0,
                ),
            }

        if source != "cache":
            raise ValueError(f"Unsupported marketplace source: {source}")

        cached, cache_latency = timed_call(self.redis_client.get, cache_key)
        if cached is not None:
            listing = json.loads(cached)
            self.metrics.record_cache_hit()
            self.metrics.record_event("market.listing.cache.hit", cache_latency, success=True)
            return {
                "source": "cache",
                "listing": listing,
                "trace": self._trace_payload(
                    request_type="listing",
                    key=cache_key,
                    source="mini-redis",
                    cache_status="hit",
                    latency_ms=cache_latency,
                    result_count=1,
                ),
            }

        self.metrics.record_cache_miss()
        listing, mongo_latency = timed_call(self.mongo_repo.get_listing_by_id, listing_id)
        total_latency = cache_latency + mongo_latency
        if listing is not None:
            self.redis_client.set(cache_key, json.dumps(listing, ensure_ascii=False))
        self.metrics.record_event("market.listing.cache.miss", total_latency, success=listing is not None)
        return {
            "source": "cache",
            "listing": listing,
            "trace": self._trace_payload(
                request_type="listing",
                key=cache_key,
                source="mongo-then-mini-redis",
                cache_status="miss-fill" if listing else "miss-empty",
                latency_ms=total_latency,
                result_count=1 if listing else 0,
            ),
        }

    def compare_marketplace_search(
        self,
        query: str = "",
        location: str = "all",
        category: str = "all",
        limit: int = 12,
        iterations: int = 7,
    ) -> dict[str, Any]:
        cache_key = self._search_cache_key(query, location, category, limit)
        direct_samples: list[float] = []
        cache_samples: list[float] = []

        for _ in range(iterations):
            _, latency_ms = timed_call(self.mongo_repo.search_listings, query, location, category, limit)
            direct_samples.append(latency_ms)

        self.redis_client.delete(cache_key)
        _, warmup_latency_ms = timed_call(self.marketplace_search, "cache", query, location, category, limit)
        for _ in range(iterations):
            _, latency_ms = timed_call(self.marketplace_search, "cache", query, location, category, limit)
            cache_samples.append(latency_ms)

        direct = summarize(direct_samples)
        cache = summarize(cache_samples)
        payload = {
            "key": cache_key,
            "iterations": iterations,
            "warmup_miss_ms": round(warmup_latency_ms, 3),
            "direct": direct,
            "cache": cache,
            "speedup": round(direct["avg_ms"] / cache["avg_ms"], 3) if cache["avg_ms"] else None,
        }
        payload["artifact_path"] = str(write_artifact(self.artifacts_dir, payload))
        return payload

    def execute_redis_command(
        self,
        command: str,
        key: str,
        value: str | None = None,
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        started_result, latency_ms = None, 0.0
        command_upper = command.upper()
        if command_upper == "GET":
            started_result, latency_ms = timed_call(self.redis_client.get, key)
        elif command_upper == "SET":
            if value is None:
                raise ValueError("SET requires a value.")
            started_result, latency_ms = timed_call(self.redis_client.set, key, value)
        elif command_upper == "DEL":
            started_result, latency_ms = timed_call(self.redis_client.delete, key)
        elif command_upper == "EXPIRE":
            if ttl_seconds is None:
                raise ValueError("EXPIRE requires ttl_seconds.")
            started_result, latency_ms = timed_call(self.redis_client.expire, key, ttl_seconds)
        else:
            raise ValueError(f"Unsupported command: {command}")
        self.metrics.record_event(f"redis.playground.{command_lower(command_upper)}", latency_ms, success=True)
        return {
            "command": command_upper,
            "key": key,
            "value": value,
            "ttl_seconds": ttl_seconds,
            "response": started_result,
            "latency_ms": round(latency_ms, 3),
        }

    def run_benchmark(self, key: str, iterations: int) -> dict[str, Any]:
        direct_samples: list[float] = []
        cache_samples: list[float] = []

        for _ in range(iterations):
            _, latency_ms = timed_call(self.mongo_repo.get_document, key)
            direct_samples.append(latency_ms)
            self.metrics.record_event("benchmark.mongo", latency_ms, success=True)

        self.redis_client.delete(key)
        _, warmup_latency_ms = timed_call(self.lookup, key, "cache")
        for _ in range(iterations):
            _, latency_ms = timed_call(self.lookup, key, "cache")
            cache_samples.append(latency_ms)

        direct_summary = summarize(direct_samples)
        cache_summary = summarize(cache_samples)
        payload = {
            "key": key,
            "iterations": iterations,
            "warmup_miss_ms": round(warmup_latency_ms, 3),
            "direct": direct_summary,
            "cache": cache_summary,
            "cache_hits": self.metrics.cache_hits,
            "cache_misses": self.metrics.cache_misses,
            "speedup": round(
                direct_summary["avg_ms"] / cache_summary["avg_ms"], 3
            )
            if cache_summary["avg_ms"] > 0
            else None,
        }
        artifact_path = write_artifact(self.artifacts_dir, payload)
        payload["artifact_path"] = str(artifact_path)
        return payload

    def run_qa(self) -> dict[str, Any]:
        results = run_qa_suite(self.redis_client)
        pass_count = sum(1 for result in results if result["status"] == "pass")
        fail_count = len(results) - pass_count
        for result in results:
            self.metrics.record_event(
                f"qa.{result['scenario']}",
                result["latency_ms"],
                success=result["status"] == "pass",
            )
        return {
            "results": results,
            "summary": {
                "total": len(results),
                "passed": pass_count,
                "failed": fail_count,
            },
        }

    def _search_cache_key(self, query: str, location: str, category: str, limit: int) -> str:
        query_token = query.strip().lower() or "all"
        location_token = location.strip().lower() or "all"
        category_token = category.strip().lower() or "all"
        return f"market:search:{query_token}:{location_token}:{category_token}:{limit}"

    def _trace_payload(
        self,
        request_type: str,
        key: str,
        source: str,
        cache_status: str,
        latency_ms: float,
        result_count: int,
    ) -> dict[str, Any]:
        return {
            "request_type": request_type,
            "key": key,
            "source": source,
            "cache_status": cache_status,
            "latency_ms": round(latency_ms, 3),
            "result_count": result_count,
        }


def command_lower(value: str) -> str:
    return value.strip().lower()
