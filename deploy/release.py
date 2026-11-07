#!/usr/bin/env python3
"""Explicit BeerRun release maintenance; routine updates use the shared webhook."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import uuid


class DeploymentError(RuntimeError):
    pass


class Deployment:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()

    def command(self, *arguments: str, image: str | None = None, check=True):
        environment = os.environ.copy()
        if image:
            environment["BOOZERUN_IMAGE"] = image
        result = subprocess.run(
            arguments, cwd=self.directory, env=environment,
            capture_output=True, text=True, timeout=600,
        )
        if check and result.returncode:
            raise DeploymentError(result.stderr.strip() or result.stdout.strip())
        return result

    def compose(self, *arguments: str, image: str | None = None, check=True):
        return self.command(
            "docker", "compose", "--project-name", "beer-run",
            "--file", str(self.directory / "docker-compose.yml"),
            *arguments, image=image, check=check,
        )

    def backup(self) -> Path:
        backup_root = self.directory / "backups"
        backup_root.mkdir(mode=0o700, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = backup_root / f"{stamp}-{uuid.uuid4().hex[:8]}.tar.gz"
        partial = target.with_name(target.name + ".partial")
        # The caller has stopped BeerRun; SQLite and media form one recoverable set.
        with partial.open("xb") as output:
            with tarfile.open(fileobj=output, mode="w:gz") as archive:
                archive.add(self.directory / "state", arcname="state")
                archive.add(self.directory / "app.env", arcname="app.env")
                release = self.directory / "release.json"
                if release.exists():
                    archive.add(release, arcname="release.json")
                selection = self.directory / ".env"
                if selection.exists():
                    archive.add(selection, arcname=".env")
            output.flush()
            os.fsync(output.fileno())
        partial.rename(target)
        return target

    def start(self, image: str):
        self.compose(
            "up", "--detach", "--no-deps", "--pull", "never",
            "--wait", "--wait-timeout", "120", "beer-run", image=image,
        )

    def update(self, *, migrate=False) -> bool:
        recovery = self.directory / "recovery-required.json"
        if recovery.exists():
            raise DeploymentError(
                "A previous migration deployment needs explicit recovery. "
                "Inspect recovery-required.json and the backup before allowing further updates."
            )
        for relative in ("app.env", "state/boozerun.db", "state/data/drinks.json"):
            if not (self.directory / relative).is_file():
                raise DeploymentError(f"Required file missing: {relative}. Refusing an empty deployment.")
        if not (self.directory / "state/uploads").is_dir():
            raise DeploymentError("Required directory missing: state/uploads")

        # Only request image names; never render private application configuration.
        configured = self.compose("config", "--images").stdout.strip().splitlines()
        if len(configured) != 1:
            raise DeploymentError("Expected exactly one BeerRun service image.")
        self.compose("pull", "beer-run")
        candidate = self.command(
            "docker", "image", "inspect", "--format", "{{.Id}}", configured[0],
        ).stdout.strip()
        container = self.compose("ps", "--all", "--quiet", "beer-run").stdout.strip()
        previous = None
        previous_reference = None
        was_running = False
        if container:
            details = json.loads(self.command("docker", "inspect", container).stdout)[0]
            previous = details["Image"]
            previous_reference = details.get("Config", {}).get("Image", previous)
            was_running = details["State"]["Running"]
            if (previous == candidate and details.get("Config", {}).get("Image", configured[0]) == configured[0] and was_running
                    and details["State"].get("Health", {}).get("Status") == "healthy"):
                print("BeerRun is already healthy on the current image.")
                return False

        readiness = self.compose(
            "run", "--rm", "--no-deps", "--pull", "never", "-T", "beer-run",
            "python", "scripts/migrate_db.py", "--check", image=candidate, check=False,
        )
        if readiness.returncode and not migrate:
            raise DeploymentError(
                "Candidate database check failed; existing BeerRun was left running. "
                "Review the release and run release.py --migrate if migrations are required.\n"
                + (readiness.stderr.strip() or readiness.stdout.strip())
            )

        if previous and readiness.returncode:
            updater = self.command(
                "docker", "inspect", "registry-updater", "--format", "{{.State.Running}}",
                check=False,
            )
            if updater.returncode == 0 and updater.stdout.strip() == "true":
                raise DeploymentError("Pause the shared updater after its current run finishes before migration maintenance.")

        # Migration commands use the exact inspected image. Keep the public tag
        # on the resulting container so the existing updater can follow it.
        migration_attempted = False
        try:
            self.compose("stop", "beer-run")
            backup = self.backup()
            print(f"Stopped-state backup: {backup}")
            if readiness.returncode:
                recovery.write_text(json.dumps({
                    "image": candidate, "previous_image": previous,
                    "backup": str(backup),
                }, indent=2) + "\n", encoding="utf-8")
                migration_attempted = True
                self.compose(
                    "run", "--rm", "--no-deps", "--pull", "never", "-T", "beer-run",
                    "python", "scripts/migrate_db.py", image=candidate,
                )
            self.start(configured[0])
            if migration_attempted:
                recovery.unlink()
        except Exception:
            # Never rewind a live database or put an older app on a changed schema.
            self.compose("stop", "beer-run", check=False)
            if previous and was_running and not migration_attempted:
                self.start(previous_reference)
                print("Previous image restored; current host data retained.", file=sys.stderr)
            elif migration_attempted:
                print(
                    "BeerRun remains stopped after a migration attempt. "
                    "Review the backup and recover explicitly; no data was restored automatically.",
                    file=sys.stderr,
                )
            raise

        release = {
            "image": candidate, "previous_image": previous,
            "backup": str(backup), "migration_attempted": migration_attempted,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
        }
        temporary = self.directory / "release.json.tmp"
        temporary.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.directory / "release.json")
        selection = self.directory / ".env"
        selection.write_text(
            f"BOOZERUN_IMAGE={configured[0]}\nBOOZERUN_AUTOUPDATE=true\n", encoding="utf-8"
        )
        print(f"BeerRun is healthy on {candidate}.")
        return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--migrate", action="store_true", help="Allow reviewed schema migrations after backup.")
    parser.add_argument("--image", help="Reviewed image tag to deploy and persist for future updates.")
    args = parser.parse_args(argv)
    if sys.platform == "win32":
        parser.error("Run this operator tool on the Linux Docker host.")
    import fcntl

    os.umask(0o077)
    if args.image:
        if not args.image.startswith("ghcr.io/matei9721/beer-run-jpn:"):
            parser.error("--image must name this application's reviewed GHCR tag")
        os.environ["BOOZERUN_IMAGE"] = args.image
    try:
        with (args.directory / ".update.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("Another BeerRun update is already running.")
                return 0
            Deployment(args.directory).update(migrate=args.migrate)
        return 0
    except (DeploymentError, OSError, subprocess.SubprocessError) as exc:
        print(f"BeerRun update failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
