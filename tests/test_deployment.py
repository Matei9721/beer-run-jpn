"""Exercise deployment failure boundaries with disposable state and a fake engine."""

import json
from subprocess import CompletedProcess
import tarfile

import pytest

from deploy.update import Deployment, DeploymentError


class FakeDeployment(Deployment):
    def __init__(self, directory, *, migration_required=False, fail_start=False):
        super().__init__(directory)
        self.migration_required = migration_required
        self.fail_start = fail_start
        self.events = []
        self.current = "sha256:old"

    def compose(self, *arguments, image=None, check=True):
        self.events.append((arguments, image))
        if arguments == ("config", "--images"):
            return CompletedProcess(arguments, 0, "ghcr.io/example/beer-run:latest\n", "")
        if arguments[0] == "ps":
            return CompletedProcess(arguments, 0, "beer-run-container\n", "")
        if arguments[0] == "run" and arguments[-1] == "--check":
            return CompletedProcess(arguments, int(self.migration_required), "", "pending schema" if self.migration_required else "")
        if arguments[0] == "up" and image == "sha256:new" and self.fail_start:
            raise DeploymentError("health check failed")
        return CompletedProcess(arguments, 0, "", "")

    def command(self, *arguments, image=None, check=True):
        if arguments[1] == "image":
            return CompletedProcess(arguments, 0, "sha256:new\n", "")
        return CompletedProcess(arguments, 0, json.dumps([{
            "Image": self.current,
            "State": {"Running": True, "Health": {"Status": "healthy"}},
        }]), "")

    def backup(self):
        self.events.append((("backup",), None))
        return super().backup()


@pytest.fixture
def deployment_root(tmp_path):
    (tmp_path / "state/data").mkdir(parents=True)
    (tmp_path / "state/uploads").mkdir()
    (tmp_path / "state/boozerun.db").write_bytes(b"database snapshot")
    (tmp_path / "state/data/drinks.json").write_text("{}")
    (tmp_path / "state/uploads/photo.jpg").write_bytes(b"photo snapshot")
    (tmp_path / "app.env").write_text("private-config")
    return tmp_path


def test_pending_migration_leaves_running_service_untouched(deployment_root):
    deployment = FakeDeployment(deployment_root, migration_required=True)
    with pytest.raises(DeploymentError, match="left running"):
        deployment.update()
    assert all(event[0][0] not in {"stop", "up", "backup"} for event in deployment.events)
    assert not (deployment_root / "backups").exists()


def test_backup_precedes_explicit_migration_and_candidate_start(deployment_root):
    deployment = FakeDeployment(deployment_root, migration_required=True)
    assert deployment.update(migrate=True)
    events = [event[0][0] for event in deployment.events]
    assert events.index("stop") < events.index("backup") < events.index("up")
    migration = next(index for index, (args, _) in enumerate(deployment.events)
                     if args[0] == "run" and args[-1] == "scripts/migrate_db.py")
    assert events.index("backup") < migration < events.index("up")
    release = json.loads((deployment_root / "release.json").read_text())
    with tarfile.open(release["backup"]) as archive:
        assert archive.extractfile("state/boozerun.db").read() == b"database snapshot"
        assert archive.extractfile("state/uploads/photo.jpg").read() == b"photo snapshot"
        assert archive.extractfile("app.env").read() == b"private-config"
    assert release["previous_image"] == "sha256:old"
    assert release["image"] == "sha256:new"


def test_failed_code_update_restarts_previous_image_without_replacing_data(deployment_root):
    deployment = FakeDeployment(deployment_root, fail_start=True)
    with pytest.raises(DeploymentError, match="health check"):
        deployment.update()
    starts = [image for arguments, image in deployment.events if arguments[0] == "up"]
    assert starts == ["sha256:new", "sha256:old"]
    assert (deployment_root / "state/boozerun.db").read_bytes() == b"database snapshot"
    assert not (deployment_root / "release.json").exists()


def test_failed_migrating_release_stays_stopped_for_explicit_recovery(deployment_root):
    deployment = FakeDeployment(deployment_root, migration_required=True, fail_start=True)
    with pytest.raises(DeploymentError, match="health check"):
        deployment.update(migrate=True)
    starts = [image for arguments, image in deployment.events if arguments[0] == "up"]
    assert starts == ["sha256:new"]
    assert deployment.events[-1][0] == ("stop", "beer-run")
    assert list((deployment_root / "backups").glob("*.tar.gz"))
    assert (deployment_root / "recovery-required.json").is_file()
    deployment.events.clear()
    with pytest.raises(DeploymentError, match="explicit recovery"):
        deployment.update()
    assert deployment.events == []


def test_backup_failure_restarts_old_service_before_any_migration(deployment_root, monkeypatch):
    deployment = FakeDeployment(deployment_root, migration_required=True)

    def fail_backup():
        raise OSError("disk full")

    monkeypatch.setattr(deployment, "backup", fail_backup)
    with pytest.raises(OSError, match="disk full"):
        deployment.update(migrate=True)
    assert deployment.events[-1][1] == "sha256:old"
    assert not any(args[0] == "run" and args[-1] == "scripts/migrate_db.py"
                   for args, _ in deployment.events)


def test_current_healthy_image_skips_backups_and_restart(deployment_root):
    deployment = FakeDeployment(deployment_root)
    deployment.current = "sha256:new"
    assert not deployment.update()
    assert not any(args[0] in {"stop", "run", "up", "backup"} for args, _ in deployment.events)


def test_missing_database_cannot_silently_create_empty_production_state(deployment_root):
    (deployment_root / "state/boozerun.db").unlink()
    deployment = FakeDeployment(deployment_root)
    with pytest.raises(DeploymentError, match="Refusing an empty deployment"):
        deployment.update(migrate=True)
    assert deployment.events == []
