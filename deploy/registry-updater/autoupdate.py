#!/usr/bin/env python3
"""Autoupdate labeled containers to the latest image (floating tags only).

Source of truth: containers carrying the label
com.centurylinklabs.watchtower.enable=true (the "apps only" allowlist).
For each: pull the service's image and recreate the container if the digest
changed. Databases, caddy (custom build) and ddns carry no label and are
never touched.

There is no major-version gating — floating tags (:latest / :release) follow
the project's latest release, majors included. Check autoupdate.log after
runs that show updates.

Usage: python3 autoupdate.py [--dry-run]
"""

import argparse
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

LABEL = "com.centurylinklabs.watchtower.enable"
ANONYMOUS_LABEL = "io.selfhaven.registry.anonymous"
ANONYMOUS_IMAGE = "ghcr.io/matei9721/js-discord-bot"

# Log lines that mean the new image's code doesn't fit the old state
# (typically a DB schema drift: "column X does not exist").
DRIFT_PATTERNS = ("PSQLException", "ExposedSQLException", "does not exist",
                  "Unhandled failure")


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{ts} {msg}", flush=True)


def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if p.returncode != 0 and p.stderr.strip():
        # A failed pull used to read as "up to date" — surface it instead
        log(f"warn: {' '.join(cmd[:2])}: {p.stderr.strip()[-300:]}")
    return p.stdout.strip()


def prune_stale_log() -> None:
    """Drop autoupdate.log if idle >6h — entries never older than 6h."""
    log_file = Path(__file__).resolve().parent.parent / "autoupdate.log"
    try:
        if log_file.exists() and time.time() - log_file.stat().st_mtime > 6 * 3600:
            log_file.write_text("")
    except OSError:  # repo mounted read-only in the webhook container
        pass


def smoke_check(compose: list[str], service: str) -> None:
    """Grep the recreated container's fresh logs for schema-drift errors.

    Column drift only errors on the first request, so wait a bit for the
    app's own polling to trip it. Not a full health check — the webhook
    container has no network path into the stacks.
    """
    time.sleep(15)
    cid = run(compose + ["ps", "-q", service])
    if not cid:
        return
    lines = run(["docker", "logs", cid, "--since", "60s", "--tail", "500"])
    for line in lines.splitlines():
        if any(p in line for p in DRIFT_PATTERNS):
            log(f"warn {service}: post-update check found errors — schema drift? "
                f"{line.strip()[:200]}")
            return


def image_id(ref: str) -> str:
    return run(["docker", "image", "inspect", ref, "--format", "{{.Id}}"])


def labeled_containers() -> list[dict]:
    ids = run(["docker", "ps", "-q", "--filter", f"label={LABEL}=true"]).splitlines()
    out = []
    for cid in ids:
        fmt = ("{{.Config.Image}}\t"
               "{{.Image}}\t"
               "{{index .Config.Labels \"com.docker.compose.project.working_dir\"}}\t"
               "{{index .Config.Labels \"com.docker.compose.service\"}}\t"
               "{{eq (index .Config.Labels \"io.selfhaven.registry.anonymous\") \"true\"}}")
        image, container_image, workdir, service, anonymous = run(
            ["docker", "inspect", cid, "--format", fmt]
        ).split("\t", 4)
        out.append({
            "image": image,
            "container_image": container_image,
            "workdir": workdir,
            "service": service,
            "anonymous": anonymous == "true",
        })
    return out


def compose_command(container: dict) -> tuple[list[str], object]:
    """Only an explicitly labeled bot image gets an empty Docker client config."""
    compose = ["docker", "compose", "-f", f"{container['workdir']}/docker-compose.yml"]
    image = container["image"]
    bot_image = (image == ANONYMOUS_IMAGE or image.startswith(ANONYMOUS_IMAGE + ":")
                 or image.startswith(ANONYMOUS_IMAGE + "@"))
    if not container.get("anonymous") or not bot_image:
        return compose, None
    config = tempfile.TemporaryDirectory(prefix="docker-anonymous-")
    Path(config.name, "config.json").write_text('{"auths":{}}\n')
    return ["docker", "--config", config.name] + compose[1:], config


def image_repository(image: str) -> str:
    reference = image.split("@", 1)[0]
    return reference.rsplit(":", 1)[0] if reference.rfind(":") > reference.rfind("/") else reference


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--image-repository")
    args = parser.parse_args(argv)
    dry_run = args.dry_run
    prune_stale_log()
    log("autoupdate start" + (" (dry-run)" if dry_run else ""))
    for c in labeled_containers():
        if args.image_repository and image_repository(c["image"]) != args.image_repository:
            continue
        compose, anonymous_config = compose_command(c)
        try:
            before = image_id(c["image"])
            run(compose + ["pull", c["service"]])
            after = image_id(c["image"])
            if not before or not after or before == after:
                # Tag unchanged — but the container may still run an older
                # image than the local tag (e.g. recreated from a stale tag)
                if not dry_run and c["container_image"] != after:
                    log(f"update {c['service']}: container {c['container_image'][:12]} -> {after[:12]}")
                    run(compose + ["up", "-d", c["service"]])
                    smoke_check(compose, c["service"])
                else:
                    log(f"ok {c['service']}: up to date")
                continue
            log(f"update {c['service']}: {before[:12]} -> {after[:12]}")
            if not dry_run:
                run(compose + ["up", "-d", c["service"]])
                smoke_check(compose, c["service"])
        except Exception as e:
            log(f"error {c['service']}: {e}")
        finally:
            if anonymous_config is not None:
                anonymous_config.cleanup()
    log("autoupdate done")


if __name__ == "__main__":
    main()
