from __future__ import annotations

from flask import Blueprint, current_app


pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
@pages_bp.get("/index.html")
def index():
    return current_app.send_static_file("index.html")
