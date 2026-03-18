from __future__ import annotations

from flask import Flask, jsonify, request, send_from_directory

from .config import Settings
from .metrics import MetricsCollector
from .mini_redis import MiniRedisStubClient, MiniRedisTCPClient
from .mongo_backend import MongoRepository, MongoUnavailableError
from .service import DemoService


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


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings()
    service = None if settings.upstream_api_base_url else build_service(settings)
    static_dir = settings.static_dir

    app = Flask(__name__, static_folder=None)

    @app.get("/")
    @app.get("/index.html")
    def index():
        return send_from_directory(static_dir, "index.html")

    @app.get("/static/<path:filename>")
    def static_files(filename: str):
        return send_from_directory(static_dir, filename)

    @app.get("/api/config")
    def api_config():
        return jsonify(build_config_payload(settings))

    @app.get("/api/lookup")
    def api_lookup():
        key = request.args.get("key", settings.demo_default_key)
        mode = request.args.get("mode", "mongo")
        return jsonify(service.lookup(key, mode))

    @app.post("/api/market/search")
    def api_market_search():
        body = request.get_json(force=True, silent=True) or {}
        return jsonify(
            service.marketplace_search(
                source=body.get("source", "mongo"),
                query=body.get("query", ""),
                location=body.get("location", "all"),
                category=body.get("category", "all"),
                limit=int(body.get("limit", 12)),
            )
        )

    @app.post("/api/market/listing")
    def api_market_listing():
        body = request.get_json(force=True, silent=True) or {}
        return jsonify(
            service.marketplace_listing(
                listing_id=int(body["listing_id"]),
                source=body.get("source", "mongo"),
            )
        )

    @app.post("/api/market/compare")
    def api_market_compare():
        body = request.get_json(force=True, silent=True) or {}
        return jsonify(
            service.compare_marketplace_search(
                query=body.get("query", ""),
                location=body.get("location", "all"),
                category=body.get("category", "all"),
                limit=int(body.get("limit", 12)),
                iterations=int(body.get("iterations", settings.benchmark_default_iterations)),
            )
        )

    @app.post("/api/redis/command")
    def api_redis_command():
        body = request.get_json(force=True, silent=True) or {}
        return jsonify(
            service.execute_redis_command(
                command=body["command"],
                key=body["key"],
                value=body.get("value"),
                ttl_seconds=int(body["ttl_seconds"]) if body.get("ttl_seconds") not in (None, "") else None,
            )
        )

    @app.post("/api/benchmark")
    def api_benchmark():
        body = request.get_json(force=True, silent=True) or {}
        key = body.get("key", settings.demo_default_key)
        iterations = int(body.get("iterations", settings.benchmark_default_iterations))
        return jsonify(service.run_benchmark(key, iterations))

    @app.get("/api/lookup/compare")
    def api_lookup_compare():
        key = request.args.get("key", settings.demo_default_key)
        return jsonify(service.lookup_compare(key))

    @app.post("/api/ttl/set")
    def api_ttl_set():
        body = request.get_json(force=True, silent=True) or {}
        return jsonify(
            service.ttl_set(
                key=body["key"],
                ttl_seconds=int(body.get("ttl_seconds", 15)),
            )
        )

    @app.get("/api/ttl/status")
    def api_ttl_status():
        key = request.args.get("key", "")
        if not key:
            return jsonify({"error": "key is required"}), 400
        return jsonify(service.ttl_status(key))

    @app.post("/api/qa/run")
    def api_qa_run():
        return jsonify(service.run_qa())

    @app.post("/api/cache/warm")
    def api_cache_warm():
        body = request.get_json(force=True, silent=True) or {}
        raw_limit = body.get("limit")
        limit = int(raw_limit) if raw_limit not in (None, "", 0, "0") else None
        doc_type = body.get("doc_type", "listing")
        if isinstance(doc_type, str) and doc_type.strip().lower() == "all":
            doc_type = None
        return jsonify(service.warm_cache(doc_type, limit))

    @app.get("/api/metrics/current")
    def api_metrics_current():
        return jsonify(service.metrics.snapshot())

    @app.get("/api/metrics/history")
    def api_metrics_history():
        return jsonify({"history": service.metrics.history_payload()})

    @app.errorhandler(Exception)
    def handle_error(exc: Exception):
        import traceback
        if isinstance(exc, (ValueError, MongoUnavailableError)):
            return jsonify({"error": str(exc)}), 400
        return jsonify({"error": str(exc), "traceback": traceback.format_exc(limit=3)}), 500

    return app


def main() -> None:
    settings = Settings()
    app = create_app(settings)
    app.run(host=settings.app_host, port=settings.app_port)


if __name__ == "__main__":
    main()
