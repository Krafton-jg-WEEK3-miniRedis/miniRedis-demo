from __future__ import annotations

import json
import traceback
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server

from .config import Settings
from .metrics import MetricsCollector
from .mini_redis import MiniRedisStubClient, MiniRedisTCPClient
from .mongo_backend import MongoRepository, MongoUnavailableError
from .service import DemoService


def read_request_body(environ) -> bytes:
    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError:
        length = 0
    return environ["wsgi.input"].read(length) if length else b""


def load_json_body(environ) -> dict:
    raw_body = read_request_body(environ) or b"{}"
    if not raw_body:
        return {}
    return json.loads(raw_body.decode("utf-8"))


def json_response(start_response, status: str, payload: dict) -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    start_response(status, [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
    return [body]


def static_response(start_response, path: Path) -> list[bytes]:
    content = path.read_bytes()
    suffix = path.suffix
    content_type = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
    }.get(suffix, "application/octet-stream")
    start_response("200 OK", [("Content-Type", content_type), ("Content-Length", str(len(content)))])
    return [content]


def build_config_payload(settings: Settings, payload: dict | None = None) -> dict:
    config = dict(payload or {})
    config.setdefault("default_key", settings.demo_default_key)
    config.setdefault("default_iterations", settings.benchmark_default_iterations)
    config.setdefault("redis_backend", settings.mini_redis_backend)
    config.setdefault("mongo_database", settings.mongo_database)
    config.setdefault("mongo_collection", settings.mongo_collection)
    config.setdefault("locations", ["all", "성남시 분당구", "서울 강남구", "서울 마포구", "수원시 영통구", "용인시 수지구"])
    config.setdefault("categories", ["all", "digital", "game", "furniture", "outdoor", "home", "fashion"])
    config["api_target"] = settings.upstream_api_base_url or "local"
    config["api_mode"] = "proxy" if settings.upstream_api_base_url else "local"
    return config


def fetch_upstream_json(settings: Settings, path: str, method: str, query_string: str = "", body: bytes = b"") -> tuple[str, dict]:
    url = f"{settings.upstream_api_base_url}{path}"
    if query_string:
        url = f"{url}?{query_string}"
    headers = {"Accept": "application/json"}
    if body:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body or None, headers=headers, method=method)
    try:
        with urlopen(request, timeout=5) as response:
            payload = response.read()
            status = f"{response.status} {HTTPStatus(response.status).phrase}"
    except HTTPError as exc:
        payload = exc.read()
        status = f"{exc.code} {HTTPStatus(exc.code).phrase}"
    except URLError as exc:
        raise RuntimeError(f"Failed to reach upstream API: {exc.reason}") from exc

    if not payload:
        return status, {}
    return status, json.loads(payload.decode("utf-8"))


def build_service(settings: Settings) -> DemoService:
    metrics = MetricsCollector(history_limit=settings.metrics_history_limit)
    mongo_repo = MongoRepository(settings.mongo_uri, settings.mongo_database, settings.mongo_collection)
    if settings.mini_redis_backend == "stub":
        redis_client = MiniRedisStubClient(metrics=metrics)
    else:
        redis_client = MiniRedisTCPClient(
            settings.mini_redis_host,
            settings.mini_redis_port,
            settings.mini_redis_timeout,
            metrics=metrics,
        )
    return DemoService(mongo_repo=mongo_repo, redis_client=redis_client, metrics=metrics, artifacts_dir=settings.artifacts_dir, cache_ttl_seconds=settings.cache_ttl_seconds)


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    service = None if settings.upstream_api_base_url else build_service(settings)
    static_dir = settings.static_dir

    def app(environ, start_response):
        method = environ["REQUEST_METHOD"].upper()
        path = environ.get("PATH_INFO", "/")
        try:
            if method == "GET" and path in ("/", "/index.html"):
                return static_response(start_response, static_dir / "index.html")
            if method == "GET" and path.startswith("/static/"):
                return static_response(start_response, static_dir / path.removeprefix("/static/"))
            if path.startswith("/api/") and settings.upstream_api_base_url:
                body = read_request_body(environ) if method in {"POST", "PUT", "PATCH"} else b""
                status, payload = fetch_upstream_json(
                    settings,
                    path,
                    method,
                    query_string=environ.get("QUERY_STRING", ""),
                    body=body,
                )
                if path == "/api/config":
                    payload = build_config_payload(settings, payload)
                return json_response(start_response, status, payload)
            if method == "GET" and path == "/api/lookup":
                query = parse_qs(environ.get("QUERY_STRING", ""))
                key = query.get("key", [settings.demo_default_key])[0]
                mode = query.get("mode", ["mongo"])[0]
                return json_response(start_response, "200 OK", service.lookup(key, mode))
            if method == "POST" and path == "/api/market/search":
                body = load_json_body(environ)
                return json_response(
                    start_response,
                    "200 OK",
                    service.marketplace_search(
                        source=body.get("source", "mongo"),
                        query=body.get("query", ""),
                        location=body.get("location", "all"),
                        category=body.get("category", "all"),
                        limit=int(body.get("limit", 12)),
                    ),
                )
            if method == "POST" and path == "/api/market/listing":
                body = load_json_body(environ)
                return json_response(
                    start_response,
                    "200 OK",
                    service.marketplace_listing(
                        listing_id=int(body["listing_id"]),
                        source=body.get("source", "mongo"),
                    ),
                )
            if method == "POST" and path == "/api/market/compare":
                body = load_json_body(environ)
                return json_response(
                    start_response,
                    "200 OK",
                    service.compare_marketplace_search(
                        query=body.get("query", ""),
                        location=body.get("location", "all"),
                        category=body.get("category", "all"),
                        limit=int(body.get("limit", 12)),
                        iterations=int(body.get("iterations", settings.benchmark_default_iterations)),
                    ),
                )
            if method == "POST" and path == "/api/redis/command":
                body = load_json_body(environ)
                return json_response(
                    start_response,
                    "200 OK",
                    service.execute_redis_command(
                        command=body["command"],
                        key=body["key"],
                        value=body.get("value"),
                        ttl_seconds=int(body["ttl_seconds"]) if body.get("ttl_seconds") not in (None, "") else None,
                    ),
                )
            if method == "POST" and path == "/api/benchmark":
                body = load_json_body(environ)
                key = body.get("key", settings.demo_default_key)
                iterations = int(body.get("iterations", settings.benchmark_default_iterations))
                return json_response(start_response, "200 OK", service.run_benchmark(key, iterations))
            if method == "GET" and path == "/api/lookup/compare":
                query = parse_qs(environ.get("QUERY_STRING", ""))
                key = query.get("key", [settings.demo_default_key])[0]
                return json_response(start_response, "200 OK", service.lookup_compare(key))
            if method == "POST" and path == "/api/ttl/set":
                body = load_json_body(environ)
                return json_response(
                    start_response,
                    "200 OK",
                    service.ttl_set(
                        key=body["key"],
                        ttl_seconds=int(body.get("ttl_seconds", 15)),
                    ),
                )
            if method == "GET" and path == "/api/ttl/status":
                query = parse_qs(environ.get("QUERY_STRING", ""))
                key = query.get("key", [""])[0]
                if not key:
                    return json_response(start_response, "400 Bad Request", {"error": "key is required"})
                return json_response(start_response, "200 OK", service.ttl_status(key))
            if method == "POST" and path == "/api/qa/run":
                return json_response(start_response, "200 OK", service.run_qa())
            if method == "GET" and path == "/api/metrics/current":
                return json_response(start_response, "200 OK", service.metrics.snapshot())
            if method == "GET" and path == "/api/metrics/history":
                return json_response(start_response, "200 OK", {"history": service.metrics.history_payload()})
            if method == "GET" and path == "/api/config":
                return json_response(start_response, "200 OK", build_config_payload(settings))
            return json_response(start_response, "404 Not Found", {"error": f"Unknown route: {method} {path}"})
        except (ValueError, MongoUnavailableError, RuntimeError) as exc:
            return json_response(start_response, "400 Bad Request", {"error": str(exc)})
        except Exception as exc:  # pragma: no cover - runtime protection
            return json_response(
                start_response,
                "500 Internal Server Error",
                {"error": str(exc), "traceback": traceback.format_exc(limit=3)},
            )

    return app


def main() -> None:
    settings = Settings()
    app = create_app(settings)
    with make_server(settings.app_host, settings.app_port, app) as server:
        print(f"Serving demo dashboard on http://{settings.app_host}:{settings.app_port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
