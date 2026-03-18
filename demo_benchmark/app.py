from __future__ import annotations

import traceback

from flask import Flask, request
from werkzeug.exceptions import HTTPException

from .config import Settings
from .mongo_backend import MongoUnavailableError
from .routes.api import api_bp
from .routes.pages import pages_bp
from .routes.shared import build_config_payload, build_service, fetch_upstream_json, json_response, status_code


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValueError)
    @app.errorhandler(MongoUnavailableError)
    @app.errorhandler(RuntimeError)
    def handle_bad_request(exc: Exception):
        return json_response({"error": str(exc)}, 400)

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        if request.path.startswith("/api/"):
            message = exc.description
            if exc.code == 404:
                message = f"Unknown route: {request.method} {request.path}"
            return json_response({"error": message}, exc.code or 500)
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        return json_response(
            {
                "error": str(exc),
                "traceback": traceback.format_exc(limit=3),
            },
            500,
        )


def register_proxy_hook(app: Flask) -> None:
    @app.before_request
    def proxy_api_requests():
        settings: Settings = app.extensions["demo_settings"]
        if not settings.upstream_api_base_url:
            return None
        if not request.path.startswith("/api/") or request.path == "/api/config":
            return None
        status, payload = fetch_upstream_json(
            settings,
            request.path,
            request.method,
            query_string=request.query_string.decode("utf-8"),
            body=request.get_data(cache=True),
        )
        return json_response(payload, status_code(status))


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings()
    service = None if settings.upstream_api_base_url else build_service(settings)

    app = Flask(__name__, static_folder=str(settings.static_dir), static_url_path="/static")
    app.json.ensure_ascii = False
    app.extensions["demo_settings"] = settings
    app.extensions["demo_service"] = service

    register_proxy_hook(app)
    register_error_handlers(app)
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)
    return app


def main() -> None:
    settings = Settings()
    app = create_app(settings)
    print(f"Serving demo dashboard on http://{settings.app_host}:{settings.app_port}")
    app.run(host=settings.app_host, port=settings.app_port, debug=False)


__all__ = ["build_config_payload", "create_app", "fetch_upstream_json", "main"]


if __name__ == "__main__":
    main()
