from __future__ import annotations

import json
from http import HTTPStatus
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app, jsonify

from ..config import Settings
from ..metrics import MetricsCollector
from ..mini_redis import MiniRedisStubClient, MiniRedisTCPClient
from ..mongo_backend import MongoRepository
from ..service import DemoService


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


def fetch_upstream_json(
    settings: Settings,
    path: str,
    method: str,
    query_string: str = "",
    body: bytes = b"",
) -> tuple[str, dict]:
    url = f"{settings.upstream_api_base_url}{path}"
    if query_string:
        url = f"{url}?{query_string}"
    headers = {"Accept": "application/json"}
    if body:
        headers["Content-Type"] = "application/json"
    upstream_request = Request(url, data=body or None, headers=headers, method=method)
    try:
        with urlopen(upstream_request, timeout=5) as response:
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
    service = DemoService(
        mongo_repo=mongo_repo,
        redis_client=redis_client,
        metrics=metrics,
        artifacts_dir=settings.artifacts_dir,
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )
    if settings.warm_cache_on_startup:
        limit = settings.warm_cache_limit if settings.warm_cache_limit > 0 else None
        service.warm_cache(settings.warm_cache_doc_type, limit)
    return service


def get_settings() -> Settings:
    return current_app.extensions["demo_settings"]


def get_service() -> DemoService:
    service = current_app.extensions.get("demo_service")
    if service is None:
        raise RuntimeError("Demo service is not available in upstream proxy mode.")
    return service


def status_code(status: str) -> int:
    return int(status.split(" ", 1)[0])


def json_response(payload: dict, code: int = 200):
    response = jsonify(payload)
    response.status_code = code
    return response
