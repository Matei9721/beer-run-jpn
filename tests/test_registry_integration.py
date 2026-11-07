"""Validate the scoped addition against the server's actual updater implementation."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import types
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from scripts.container_schema_channel import schema_channel


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "deploy/registry-updater"
IMAGE = "ghcr.io/matei9721/beer-run-jpn"


def load_module(name, monkeypatch):
    if sys.platform == "win32":
        monkeypatch.setitem(sys.modules, "fcntl", types.SimpleNamespace(LOCK_EX=2, flock=lambda *_: None))
    spec = importlib.util.spec_from_file_location(f"review_{name}", INTEGRATION / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schema_channel_changes_for_historical_migrations_and_runner(tmp_path):
    source = ROOT / "src/beer_run/migrations"
    target = tmp_path / "migrations"
    shutil.copytree(source, target)
    channel = schema_channel(target)
    assert channel.startswith("schema-009-")
    historical = target / "versions/001_initial_schema.py"
    historical.write_text(historical.read_text() + "\n# changed migration\n")
    assert schema_channel(target) != channel
    shutil.copyfile(source / "versions/001_initial_schema.py", historical)
    assert schema_channel(target) == channel
    runner = target / "runner.py"
    runner.write_text(runner.read_text() + "\n# changed runner\n")
    assert schema_channel(target) != channel


@pytest.mark.parametrize("filtered", [True, False])
def test_filter_excludes_unrelated_images_before_any_compose_operation(monkeypatch, filtered):
    updater = load_module("autoupdate", monkeypatch)
    images = [IMAGE + ":schema-009-test", IMAGE + "-other:latest", "ghcr.io/example/existing:latest"]
    containers = [{"image": image, "container_image": "old", "workdir": f"/service/{i}",
                   "service": f"service-{i}", "anonymous": False} for i, image in enumerate(images)]
    commands = []
    checks = []
    count = {}
    def image_id(image):
        count[image] = count.get(image, 0) + 1
        return "old" if count[image] == 1 else "new"
    monkeypatch.setattr(updater, "labeled_containers", lambda: containers)
    monkeypatch.setattr(updater, "prune_stale_log", lambda: None)
    monkeypatch.setattr(updater, "image_id", image_id)
    monkeypatch.setattr(updater, "run", lambda args: commands.append(args) or "")
    monkeypatch.setattr(updater, "smoke_check", lambda command, service: checks.append(service))
    updater.main(["--image-repository", IMAGE] if filtered else [])
    assert checks == (["service-0"] if filtered else ["service-0", "service-1", "service-2"])
    assert len(commands) == (2 if filtered else 6)
    if filtered:
        assert all(command[-1] == "service-0" for command in commands)


@pytest.fixture
def webhook(monkeypatch, tmp_path):
    module = load_module("webhook", monkeypatch)
    monkeypatch.setattr(module, "SECRET", "synthetic-webhook-secret")
    monkeypatch.setattr(module, "LOCK", str(tmp_path / "update.lock"))
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda command, **_: calls.append(command) or subprocess.CompletedProcess(command, 0, "updated", ""))
    server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    def request(path, *, signed=True, action="published"):
        body = json.dumps({"action": action, "image": "attacker/unrelated:latest"}).encode()
        signature = "sha256=" + hmac.new(module.SECRET.encode(), body, hashlib.sha256).hexdigest()
        request = Request(f"http://127.0.0.1:{server.server_port}{path}", data=body,
                          headers={"X-Hub-Signature-256": signature if signed else "invalid",
                                   "X-GitHub-Event": "registry_package"})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()
    yield module, calls, request
    server.shutdown()
    server.server_close()
    worker.join(timeout=5)


def test_scoped_route_uses_fixed_filter_and_legacy_route_keeps_original_command(webhook):
    module, calls, request = webhook
    assert request("/update/beer-run")[0] == 200
    assert calls[-1] == ["python3", module.AUTOUPDATE, "--image-repository", IMAGE]
    assert request("/update")[0] == 200
    assert calls[-1] == ["python3", module.AUTOUPDATE]


def test_invalid_signatures_ignored_actions_and_unknown_paths_cannot_update(webhook):
    _, calls, request = webhook
    assert request("/update/beer-run", signed=False)[0] == 401
    assert request("/update", signed=False)[0] == 401
    assert request("/update/beer-run", action="deleted")[0] == 200
    assert request("/other")[0] == 404
    assert calls == []


@pytest.mark.skipif(sys.platform == "win32", reason="Verify actual fcntl locking in the Linux container")
def test_scoped_and_legacy_routes_share_the_existing_update_lock(webhook, monkeypatch):
    module, _, request = webhook
    active = 0
    peak = 0
    guard = threading.Lock()
    def run(command, **_):
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        time.sleep(0.1)
        with guard:
            active -= 1
        return subprocess.CompletedProcess(command, 0, "updated", "")
    monkeypatch.setattr(module.subprocess, "run", run)
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(request, ["/update", "/update/beer-run"]))
    assert all(status == 200 for status, _ in statuses)
    assert peak == 1
