from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from beer_run import main, models, paths
from beer_run.migrations import runner


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"


def _clean_runtime_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for variable in (
        "BOOZERUN_DATABASE_PATH",
        "BOOZERUN_DATA_ROOT",
        "BOOZERUN_ENV_PATH",
        "BOOZERUN_QUARANTINE_ROOT",
        "BOOZERUN_UPLOAD_ROOT",
        "SQLALCHEMY_DATABASE_URL",
    ):
        environment.pop(variable, None)
    return environment


def test_package_initialization_is_inert_from_another_working_directory(tmp_path):
    script = (
        "import sys; "
        f"sys.path.insert(0, {str(SOURCE_ROOT)!r}); "
        "import beer_run; "
        "assert 'beer_run.main' not in sys.modules; "
        "assert 'beer_run.auth' not in sys.modules; "
        "assert 'beer_run.legal' not in sys.modules"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=_clean_runtime_environment(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_default_runtime_paths_are_repository_anchored_from_any_directory(tmp_path):
    script = (
        "import json, sys; "
        f"sys.path.insert(0, {str(SOURCE_ROOT)!r}); "
        "from beer_run import paths; "
        "print(json.dumps({"
        "'repository': str(paths.REPOSITORY_ROOT), "
        "'frontend_app': str(paths.FRONTEND_APP_ROOT), "
        "'frontend_pages': str(paths.FRONTEND_PAGE_ROOT), "
        "'frontend_static': str(paths.FRONTEND_STATIC_ROOT), "
        "'database': str(paths.DEFAULT_DATABASE_PATH), "
        "'environment': str(paths.ENV_FILE_PATH), "
        "'data': str(paths.DATA_ROOT), "
        "'uploads': str(paths.UPLOAD_ROOT), "
        "'quarantine': str(paths.ACCOUNT_DELETION_QUARANTINE_ROOT)"
        "}))"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=_clean_runtime_environment(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout)
    assert resolved == {
        "repository": str(REPOSITORY_ROOT),
        "frontend_app": str(SOURCE_ROOT / "frontend" / "app"),
        "frontend_pages": str(SOURCE_ROOT / "frontend" / "pages"),
        "frontend_static": str(SOURCE_ROOT / "frontend" / "static"),
        "database": str(REPOSITORY_ROOT / "boozerun.db"),
        "environment": str(REPOSITORY_ROOT / ".env"),
        "data": str(REPOSITORY_ROOT / "data"),
        "uploads": str(REPOSITORY_ROOT / "static" / "uploads"),
        "quarantine": str(REPOSITORY_ROOT / ".account-deletion-quarantine"),
    }


def test_backend_uses_one_package_module_identity():
    assert main.models is models
    assert runner.initial_schema.__name__ == (
        "beer_run.migrations.versions.001_initial_schema"
    )
    assert "models" not in sys.modules
    assert "migrations.runner" not in sys.modules


def test_canonical_app_has_complete_route_table():
    routes = {route.path for route in main.app.routes}
    assert {
        "/",
        "/token",
        "/api/me",
        "/api/beer-runs",
        "/api/config",
        "/terms",
        "/privacy",
        "/wrapped",
    }.issubset(routes)
    assert "/assets" in routes
    assert "/static/uploads" in routes
    assert "/revamp-preview" not in routes
    assert "/revamp-assets" not in routes


def test_source_tree_has_one_backend_and_one_production_frontend():
    assert not (REPOSITORY_ROOT / "main.py").exists()
    assert not (REPOSITORY_ROOT / "templates" / "index.html").exists()
    assert not (REPOSITORY_ROOT / "static" / "js" / "app.js").exists()
    assert (SOURCE_ROOT / "beer_run" / "main.py").is_file()
    assert (SOURCE_ROOT / "frontend" / "app" / "index.html").is_file()
    assert not (SOURCE_ROOT / "frontend" / "app" / "assets" / "brand" / "review.html").exists()


def test_operator_script_help_works_from_another_working_directory(tmp_path):
    for script_name in (
        "build_wrapped_data.py",
        "manage_users.py",
        "migrate_db.py",
        "migrate_upload_paths.py",
    ):
        result = subprocess.run(
            [sys.executable, str(REPOSITORY_ROOT / "scripts" / script_name), "--help"],
            cwd=tmp_path,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{script_name}: {result.stderr}"
        assert "usage:" in result.stdout


def test_setup_script_defaults_remain_at_repository_root(tmp_path):
    script = (
        "import json, sys; "
        f"sys.path.insert(0, {str(REPOSITORY_ROOT)!r}); "
        "from scripts import setup_db; "
        "print(json.dumps({'database': setup_db.DB_FILE, "
        "'users': setup_db.CONFIG_FILE}))"
    )
    environment = os.environ.copy()
    environment.pop("BOOZERUN_DATABASE_PATH", None)
    environment.pop("SQLALCHEMY_DATABASE_URL", None)

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    defaults = json.loads(result.stdout)
    assert defaults == {
        "database": str(REPOSITORY_ROOT / "boozerun.db"),
        "users": str(REPOSITORY_ROOT / "users.json"),
    }


def test_configured_runtime_paths_are_absolute():
    assert paths.DEFAULT_DATABASE_PATH.is_absolute()
    assert paths.UPLOAD_ROOT.is_absolute()
    assert paths.ACCOUNT_DELETION_QUARANTINE_ROOT.is_absolute()
