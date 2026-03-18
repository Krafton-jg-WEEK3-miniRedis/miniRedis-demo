from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value is not None else default


@dataclass(slots=True)
class Settings:
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = _env_int("APP_PORT", 8000)
    upstream_api_base_url: str = os.getenv("UPSTREAM_API_BASE_URL", "").rstrip("/")
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
    mongo_database: str = os.getenv("MONGO_DATABASE", os.getenv("MONGO_DB_NAME", "mini_redis_demo"))
    mongo_collection: str = os.getenv("MONGO_COLLECTION", "products")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key")
    mini_redis_host: str = os.getenv("MINI_REDIS_HOST", "127.0.0.1")
    mini_redis_port: int = _env_int("MINI_REDIS_PORT", 6379)
    mini_redis_timeout: float = _env_float("MINI_REDIS_TIMEOUT", 1.0)
    mini_redis_backend: str = os.getenv("MINI_REDIS_BACKEND", "tcp")
    demo_default_key: str = os.getenv("DEMO_DEFAULT_KEY", "customer:0001")
    benchmark_default_iterations: int = _env_int("BENCHMARK_DEFAULT_ITERATIONS", 25)
    metrics_history_limit: int = _env_int("METRICS_HISTORY_LIMIT", 50)
    cache_ttl_seconds: int = _env_int("CACHE_TTL_SECONDS", 300)

    @property
    def static_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "static"

    @property
    def artifacts_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "artifacts"
