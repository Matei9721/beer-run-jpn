# BeerRun deployment plan

Revised 7 November 2026. This replaces the proposal for a separate BeerRun
updater and systemd timer. Normal updates will use the existing signed registry
webhook and `scripts/autoupdate.py`.

**Status: implementation validated locally; deployment authorized on 7 November
2026.** Publishing and cutover progress are recorded separately during rollout.
The timer templates were removed. `release.py` is an explicit maintenance
command; routine updates use the existing server webhook. The files under
`registry-updater/` are narrowly patched copies of the server's existing scripts;
`original-sha256.json` records the source hashes that installation must verify.

## What the inspection established

- Independent Compose stacks live under `/home/lspataru/deployments`.
- Caddy already serves both BeerRun domains, forwarding to the Pi at
  `192.168.178.225:8000`. No DNS change appears necessary.
- The signed webhook serializes runs of `scripts/autoupdate.py`. The script
  discovers running containers labeled
  `com.centurylinklabs.watchtower.enable=true`, pulls images, and recreates
  services whose image changed. It expects `docker-compose.yml`.
- The script currently scans every opted-in container. Its log check does
  not provide database backups, migration gating, or health-based rollback.
- The Pi app is in `/home/bot/Desktop/beer-run-jpn` at `c2cdd79`. SQLite
  integrity passed and migrations 001-009 are applied: 6 users, 177 entries,
  3 runs, 7 memberships, and 365 uploaded files totaling about 62 MB.
  Preserve its modified `data/drinks.json` and private configuration.
- The owner confirmed nobody currently uses the app, so a one-time transfer
  is sufficient. DDNS will remain on the Pi copy without synchronization.

## 1. Keep development unchanged and publish schema-compatible image tags

Retain the local FastAPI workflow and Docker packaging. GitHub Actions tests,
builds, and smoke-tests the image, then publishes that exact image to GHCR.
No live database, photos, secrets, or generated recaps enter the image.

Publish `sha-<full-commit>`, `latest`, and a schema-channel tag such as
`schema-009-<migration-hash>`. Compute the hash from the ordered migration
files and runner, so any migration-content change creates a different channel.
Models must continue to have corresponding migrations.

The server follows the reviewed schema channel, rather than `latest`.
Code-only releases update that channel automatically. A schema-changing release
publishes a new channel while leaving the running server on its old channel.
Startup retains its readiness check and never migrates automatically.

## 2. Add one isolated BeerRun stack with host-owned data

Create `/home/lspataru/deployments/beer-run` with `docker-compose.yml`, a
non-secret `.env` selecting the image channel, private `app.env`, `state/`,
and `backups/`. Use UID/GID 1000 and private file permissions.

`state/` contains `boozerun.db`, `uploads/`, `data/` (including drink config
and recaps), and quarantine if present. Mount it read-write into the app,
and mount `app.env` read-only. Keep secrets, user data, and existing upload
URL strings independent of image replacement. The container joins `caddy-net`
with alias `beer-run`, publishes no host ports, and retains resource/log limits.

## 3. Integrate with the existing updater

Add the existing updater label. Mount only BeerRun's Compose file and
non-secret image-selection `.env` read-only into `registry-updater`, at
their exact host paths. Do not mount its database, photos, or `app.env`
into that container. Verify this layout locally with the actual updater.

To prevent a BeerRun publication from updating unrelated services, prepare
a small additive extension to the existing updater:

- An optional exact image-repository filter in `autoupdate.py`, applied
  before any pull or Compose operation. No-argument behavior stays unchanged.
- A signed `/update/beer-run` route in the existing webhook handler that passes
  the fixed `ghcr.io/matei9721/beer-run-jpn` filter and uses the existing lock.
- Preserve signature validation and the existing `/update` route unchanged.
  Register BeerRun's package webhook against the scoped route. Existing
  unfiltered runs may still update BeerRun within its selected schema channel.

Prepare exact patches and tests locally before applying these shared changes.
Reusing `/update` without this extension is possible, but it can also update
other opted-in services; that is not the proposed default.

**Existing service affected:** the new mounts require recreating only the
`registry-updater` container once, briefly pausing webhook delivery. Check it
is idle, retain its configuration, validate the proposed Compose file, and
verify both webhook routes afterward. No hosted application is restarted.
Do not trigger the global live updater as a test. Do not replace shared
registry credentials. No new timer, daemon, or sudo installation is needed.

## 4. Make database migrations deliberate maintenance releases

The schema channel prevents an automatic rollout that requires migration.
For a future schema-changing release:

1. Rehearse migrations against a disposable copy; verify integrity, counts,
   API behavior, photo reads, and recaps.
2. Temporarily remove BeerRun from automatic updates, allow any active update
   operation to finish, retain the previous image, and stop only BeerRun.
3. Make and verify a unique consistent backup of database, uploads, data,
   quarantine, private configuration, and current image selection.
4. Explicitly run `scripts/migrate_db.py` in the candidate image. The upload-path
   file migration remains a separate operator action.
5. Start and verify the candidate, persist its new schema-channel selection,
   and re-enable the updater label. The running container must record that
   channel tag, rather than a bare image ID, for future shared updates.
6. After a failed migration attempt, keep BeerRun out of automatic updates for
   explicit recovery. Preserve failed state and backup; never automatically
   rewind user data or start older code against a changed schema.

The local `release.py` is a manual command for this maintenance. It does not
poll, schedule, or replace the shared routine pull/recreate path.
Code-only rollback can use a compatible commit tag; schema rollback requires
a reviewed restore of matching state. Backups are never automatically pruned.

## 5. Transfer the Pi state and switch only the selfhaven upstream

After approval, verify the Pi SSH fingerprint through Pi Connect and authorize
a temporary transfer key, removing its authorization after copying. Pi SSH
is active, but the new server has no recorded host trust and no Pi authorized
keys file was found. Do not bypass host-key verification.

Briefly stop only the Pi app to take a final recoverable snapshot of its
database and media, accounting for SQLite WAL state through SQLite backup.
Transfer over authenticated private SSH, verify checksums and integrity,
and restart the Pi app. Preserve its modified drink config and original
auth/signup/legal settings without printing secrets.

Validate the new container against a separate copy before public traffic.
The current snapshot needs no additional schema migration. Save Caddy's
original configuration, validate the full proposed file, and change only:

```caddyfile
beerrun.selfhaven.eu {
    reverse_proxy beer-run:8000
}
```

Keep `beerrun.ddns.net` forwarding to `192.168.178.225:8000`. Preserve the
inode of Caddy's bind-mounted file and reload Caddy without recreating it.
Verify both BeerRun domains and baseline responses from the other sites.
Restore the saved configuration if verification fails.

## Verification and approval

Local verification passed: 575 Windows tests (one Linux-only test skipped),
all 13 focused deployment/integration tests in Linux including real file-lock
concurrency, the final image smoke test, and the real Docker CLI reading only
the proposed Compose and image-selection file mounts. The initial packaging
also passed an isolated image-replacement rehearsal. Rollout additionally checks:

- Code-only changes retain the schema channel; migration-content changes
  create a new channel; publishing uses exactly the tested image.
- The real updater can read the proposed stack with only the two file mounts.
- Scoped BeerRun events cannot pull/recreate other services, while existing
  webhook authentication, locking, and unfiltered behavior remain unchanged.
- Image replacement preserves persistent data; migration and backup failures
  cannot silently re-enable updates or destroy recoverable state.

The owner authorized the revised implementation and server rollout after review.
Remote source pushes retain their separate immediate confirmation gate.
The owner chose to arrange the Pi archive transfer; do not add an SSH key.

For a reviewed maintenance release, pause the shared webhook after its current
update run finishes, then run:

```sh
python3 release.py --image ghcr.io/matei9721/beer-run-jpn:schema-NEW-HASH --migrate
```

The helper records the selected tag in `.env` without replacing its inode.
It refuses migration maintenance while `registry-updater` is running. Verify
the application and its new channel before resuming the shared webhook.
