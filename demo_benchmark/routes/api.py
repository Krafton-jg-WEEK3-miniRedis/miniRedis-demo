from __future__ import annotations

from flask import Blueprint, request

from .shared import (
    build_config_payload,
    fetch_upstream_json,
    get_service,
    get_settings,
    json_response,
    status_code,
)


api_bp = Blueprint("api", __name__, url_prefix="/api")


def payload_body() -> dict:
    return request.get_json(silent=True) or {}


@api_bp.get("/lookup")
def lookup():
    settings = get_settings()
    key = request.args.get("key", settings.demo_default_key)
    mode = request.args.get("mode", "mongo")
    return json_response(get_service().lookup(key, mode))


@api_bp.post("/market/search")
def market_search():
    body = payload_body()
    return json_response(
        get_service().marketplace_search(
            source=body.get("source", "mongo"),
            query=body.get("query", ""),
            location=body.get("location", "all"),
            category=body.get("category", "all"),
            limit=int(body.get("limit", 12)),
        )
    )


@api_bp.post("/market/listing")
def market_listing():
    body = payload_body()
    return json_response(
        get_service().marketplace_listing(
            listing_id=int(body["listing_id"]),
            source=body.get("source", "mongo"),
        )
    )


@api_bp.post("/market/compare")
def market_compare():
    body = payload_body()
    settings = get_settings()
    return json_response(
        get_service().compare_marketplace_search(
            query=body.get("query", ""),
            location=body.get("location", "all"),
            category=body.get("category", "all"),
            limit=int(body.get("limit", 12)),
            iterations=int(body.get("iterations", settings.benchmark_default_iterations)),
        )
    )


@api_bp.post("/redis/command")
def redis_command():
    body = payload_body()
    ttl_seconds = body.get("ttl_seconds")
    return json_response(
        get_service().execute_redis_command(
            command=body["command"],
            key=body["key"],
            value=body.get("value"),
            ttl_seconds=int(ttl_seconds) if ttl_seconds not in (None, "") else None,
        )
    )


@api_bp.post("/benchmark")
def benchmark():
    body = payload_body()
    settings = get_settings()
    key = body.get("key", settings.demo_default_key)
    iterations = int(body.get("iterations", settings.benchmark_default_iterations))
    return json_response(get_service().run_benchmark(key, iterations))


@api_bp.get("/lookup/compare")
def lookup_compare():
    settings = get_settings()
    key = request.args.get("key", settings.demo_default_key)
    return json_response(get_service().lookup_compare(key))


@api_bp.post("/ttl/set")
def ttl_set():
    body = payload_body()
    return json_response(
        get_service().ttl_set(
            key=body["key"],
            ttl_seconds=int(body.get("ttl_seconds", 15)),
        )
    )


@api_bp.get("/ttl/status")
def ttl_status():
    key = request.args.get("key", "")
    if not key:
        return json_response({"error": "key is required"}, 400)
    return json_response(get_service().ttl_status(key))


@api_bp.post("/qa/run")
def qa_run():
    return json_response(get_service().run_qa())


@api_bp.post("/cache/warm")
def cache_warm():
    body = payload_body()
    raw_limit = body.get("limit")
    limit = int(raw_limit) if raw_limit not in (None, "", 0, "0") else None
    doc_type = body.get("doc_type", "listing")
    if isinstance(doc_type, str) and doc_type.strip().lower() == "all":
        doc_type = None
    return json_response(get_service().warm_cache(doc_type, limit))


@api_bp.get("/metrics/current")
def metrics_current():
    return json_response(get_service().metrics.snapshot())


@api_bp.get("/metrics/history")
def metrics_history():
    return json_response({"history": get_service().metrics.history_payload()})


@api_bp.get("/config")
def config():
    settings = get_settings()
    payload: dict | None = None
    if settings.upstream_api_base_url:
        status, upstream_payload = fetch_upstream_json(settings, request.path, request.method)
        if status_code(status) >= 400:
            return json_response(upstream_payload, status_code(status))
        payload = upstream_payload
    return json_response(build_config_payload(settings, payload))


@api_bp.route("/<path:_subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def unknown_api_route(_subpath: str):
    return json_response({"error": f"Unknown route: {request.method} {request.path}"}, 404)
