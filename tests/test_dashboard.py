from __future__ import annotations

import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from demo_benchmark.benchmark import summarize
from demo_benchmark.app import build_config_payload, create_app
from demo_benchmark.config import Settings
from demo_benchmark.metrics import MetricsCollector
from demo_benchmark.mini_redis import MiniRedisStubClient
from demo_benchmark.service import DemoService


class FakeMongoRepository:
    def __init__(self, documents):
        self.documents = documents

    def get_document(self, key: str):
        return self.documents.get(key)

    def search_listings(self, query: str = "", location: str = "", category: str = "", limit: int = 12):
        results = [doc for doc in self.documents.values() if doc.get("doc_type") == "listing"]
        if query:
            query_lower = query.lower()
            results = [doc for doc in results if query_lower in doc["title"].lower() or query_lower in doc["description"].lower()]
        if location and location != "all":
            results = [doc for doc in results if doc["location"] == location]
        if category and category != "all":
            results = [doc for doc in results if doc["category"] == category]
        return results[:limit]

    def get_listing_by_id(self, listing_id: int):
        for document in self.documents.values():
            if document.get("listing_id") == listing_id:
                return document
        return None


class DemoServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metrics = MetricsCollector(history_limit=10)
        self.redis = MiniRedisStubClient(metrics=self.metrics)
        self.mongo = FakeMongoRepository(
            {
                "customer:0001": {
                    "key": "customer:0001",
                    "name": "Demo Customer 1",
                    "tier": "silver",
                },
                "listing:1001": {
                    "key": "listing:1001",
                    "doc_type": "listing",
                    "listing_id": 1001,
                    "title": "아이폰 14 프로 256GB",
                    "description": "상태 좋은 아이폰 중고 매물입니다.",
                    "location": "성남시 분당구",
                    "category": "digital",
                    "price": 900000,
                    "likes": 40,
                    "views": 300,
                    "score": 420,
                    "status": "판매중",
                    "seller": {
                        "seller_id": 501,
                        "nickname": "동네판매자501",
                        "response_rate": "96%",
                    },
                },
            }
        )
        self.tempdir = tempfile.TemporaryDirectory()
        self.service = DemoService(
            mongo_repo=self.mongo,
            redis_client=self.redis,
            metrics=self.metrics,
            artifacts_dir=Path(self.tempdir.name),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_cache_lookup_warms_and_then_hits(self) -> None:
        first = self.service.lookup("customer:0001", "cache")
        second = self.service.lookup("customer:0001", "cache")

        self.assertEqual(first["source"], "mini-redis-miss-filled")
        self.assertEqual(second["source"], "mini-redis-hit")
        self.assertEqual(self.metrics.cache_misses, 1)
        self.assertEqual(self.metrics.cache_hits, 1)

    def test_benchmark_writes_artifact(self) -> None:
        result = self.service.run_benchmark("customer:0001", 3)

        artifact = Path(result["artifact_path"])
        self.assertTrue(artifact.exists())
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        self.assertEqual(payload["key"], "customer:0001")
        self.assertEqual(payload["iterations"], 3)
        self.assertIn("avg_ms", payload["direct"])
        self.assertIn("avg_ms", payload["cache"])

    def test_qa_suite_runs_against_stub(self) -> None:
        result = self.service.run_qa()

        self.assertGreaterEqual(result["summary"]["total"], 10)
        self.assertEqual(result["summary"]["failed"], 0)
        malformed = next(item for item in result["results"] if item["scenario"] == "Malformed RESP")
        self.assertEqual(malformed["status"], "pass")

    def test_marketplace_search_cache_warms_and_hits(self) -> None:
        first = self.service.marketplace_search("cache", query="아이폰", location="성남시 분당구", category="digital")
        second = self.service.marketplace_search("cache", query="아이폰", location="성남시 분당구", category="digital")

        self.assertEqual(first["trace"]["cache_status"], "miss-fill")
        self.assertEqual(second["trace"]["cache_status"], "hit")
        self.assertEqual(second["items"][0]["listing_id"], 1001)

    def test_marketplace_listing_returns_trace(self) -> None:
        result = self.service.marketplace_listing(1001, "mongo")

        self.assertEqual(result["listing"]["listing_id"], 1001)
        self.assertEqual(result["trace"]["request_type"], "listing")

    def test_redis_playground_set_and_get(self) -> None:
        self.service.execute_redis_command("SET", "market:test:key", value="hello")
        result = self.service.execute_redis_command("GET", "market:test:key")

        self.assertEqual(result["response"], "hello")


class BenchmarkTests(unittest.TestCase):
    def test_summarize_calculates_expected_fields(self) -> None:
        summary = summarize([1.0, 2.0, 4.0, 8.0])

        self.assertEqual(summary["avg_ms"], 3.75)
        self.assertEqual(summary["min_ms"], 1.0)
        self.assertEqual(summary["max_ms"], 8.0)
        self.assertGreater(summary["requests_per_sec"], 0)


class AppConfigTests(unittest.TestCase):
    def test_build_config_payload_marks_proxy_target(self) -> None:
        settings = Settings(upstream_api_base_url="http://211.188.52.76:8088")

        payload = build_config_payload(settings, {"default_key": "shared:key"})

        self.assertEqual(payload["default_key"], "shared:key")
        self.assertEqual(payload["api_target"], "http://211.188.52.76:8088")
        self.assertEqual(payload["api_mode"], "proxy")

    def test_config_route_merges_upstream_payload(self) -> None:
        app = create_app(Settings(upstream_api_base_url="http://211.188.52.76:8088"))
        captured: dict[str, object] = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = headers

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/config",
            "QUERY_STRING": "",
            "CONTENT_LENGTH": "0",
            "wsgi.input": BytesIO(b""),
        }

        with patch(
            "demo_benchmark.app.fetch_upstream_json",
            return_value=("200 OK", {"default_key": "remote:key", "redis_backend": "tcp"}),
        ):
            body = b"".join(app(environ, start_response))

        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(captured["status"], "200 OK")
        self.assertEqual(payload["default_key"], "remote:key")
        self.assertEqual(payload["redis_backend"], "tcp")
        self.assertEqual(payload["api_target"], "http://211.188.52.76:8088")
        self.assertEqual(payload["api_mode"], "proxy")


if __name__ == "__main__":
    unittest.main()
