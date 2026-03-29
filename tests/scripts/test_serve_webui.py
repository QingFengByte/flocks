"""Tests for the lightweight WebUI static file server."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "serve_webui.py"
    spec = importlib.util.spec_from_file_location("serve_webui", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve_webui = load_module()


def test_resolve_request_path_returns_existing_asset(tmp_path):
    dist_dir = tmp_path / "dist"
    asset_file = dist_dir / "assets" / "app.js"
    asset_file.parent.mkdir(parents=True)
    asset_file.write_text("console.log('ok');", encoding="utf-8")
    (dist_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    resolved = serve_webui.resolve_request_path(dist_dir, "/assets/app.js")

    assert resolved == asset_file.resolve()


def test_resolve_request_path_falls_back_to_index_for_spa_route(tmp_path):
    dist_dir = tmp_path / "dist"
    index_file = dist_dir / "index.html"
    dist_dir.mkdir()
    index_file.write_text("<html></html>", encoding="utf-8")

    resolved = serve_webui.resolve_request_path(dist_dir, "/settings/profile")

    assert resolved == index_file.resolve()


def test_resolve_request_path_preserves_missing_asset_path(tmp_path):
    dist_dir = tmp_path / "dist"
    index_file = dist_dir / "index.html"
    dist_dir.mkdir()
    index_file.write_text("<html></html>", encoding="utf-8")

    resolved = serve_webui.resolve_request_path(dist_dir, "/assets/missing.js")

    assert resolved == (dist_dir / "assets" / "missing.js").resolve()
