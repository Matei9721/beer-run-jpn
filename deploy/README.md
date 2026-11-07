# BeerRun container deployment

Status: prepared locally. **Server installation, data transfer, GitHub publishing,
and the proxy cutover require the owner's confirmation before execution.**

Local development is unchanged: use the `uv` commands in the root README.
The image packages the Python app, frontend, operator scripts, and locked
dependencies. No database, uploads, secrets, or generated recaps enter the build.

## Observed server layout (7 November 2026)

- Tailscale: `lspataru@100.109.118.111`, hostname `Luca-Lenovo`, Linux x86_64.
- Docker 29.7.2 and Compose 5.4.0; projects live in
  `/home/lspataru/deployments/<service>`.
- Caddy already owns ports 80/443 and joins the external `caddy-net` network at
  reserved address `172.23.0.100`. Its existing mounts and named volumes stay intact.
- Both `beerrun.selfhaven.eu` and `beerrun.ddns.net` currently proxy to
  `192.168.178.225:8000`. The selfhaven hostname resolves through Cloudflare.
  No DNS change appears necessary; the Caddy upstream is the cutover point.
- The shared registry webhook invokes an updater across opt-in labeled services.
  BeerRun deliberately has no updater label and does not change that mechanism.
- Existing projects include Immich, Jellyfin, Vaultwarden, media services,
  monitoring, a portfolio backend, and a Discord bot. No existing project's
  image, ports, mounts, credentials, or lifecycle is part of this deployment.

## Proposed installation and cutover

1. Merge the reviewed repository changes and publish a tested image to
   `ghcr.io/matei9721/beer-run-jpn`. The workflow tests every PR and main update,
   builds and smoke-tests the image, then publishes `latest` and a commit-specific
   `sha-<full-commit>` tag on main. It uses GitHub's `GITHUB_TOKEN`; app secrets
   never go into Actions. Automated semantic tags are not the publish trigger.
2. After confirmation, create only
   `/home/lspataru/deployments/beer-run`. Copy `compose.yaml`, `update.py`, and
   the two systemd unit templates here. Use owner UID/GID 1000, mode 0700 for
   the directory and 0600 for private configuration. A private GHCR image
   needs read-only package access; prefer a public image when source is public.
   Do not clear or replace shared Docker credentials. If needed, use a
   BeerRun-only `DOCKER_CONFIG` and set it in its update service.
   The workflow publishes images only; future changes to host Compose files,
   the updater, or unit files must be reviewed and installed separately.
3. Pi Connect inspection confirmed user `bot`, source directory
   `/home/bot/Desktop/beer-run-jpn`, revision `c2cdd79`, and a manually started
   `uv run uvicorn beer_run.main:app --host 0.0.0.0 --port 8000` process in a
   shell session. The database is `boozerun.db` (157,944 bytes), passes SQLite
   integrity, and has migrations 001-009, 6 users, 177 entries, 3 beer runs,
   and 7 memberships. Uploads occupy about 62 MB. All four required config
   values are present. Preserve the modified Pi `data/drinks.json`; ignore
   the other stray/empty database files. Refresh these checks before transfer.
   Pi SSH is active, but the new server does not yet trust its host key and
   no Pi authorized-keys file was found. After approval, verify the fingerprint
   through Pi Connect and arrange a temporary transfer key, removing its Pi
   authorization after copying. Do not bypass host-key verification or expose
   a data archive over HTTP. No SSH trust or authorization was changed during inspection.
4. Rehearse with a **separate recoverable copy** of the Pi state. Preserve the
   original database, image paths, login secret, and signup/legal settings.
   Run SQLite `PRAGMA integrity_check`, migration readiness, representative row
   counts, login, photo reads, public/private run access, and Wrapped checks
   against the copy. Never export user rows or secrets into Git or build logs.
5. During an agreed short cutover window, stop only the Pi's BeerRun writer,
   capture a final consistent snapshot of its SQLite database (including any
   WAL state via SQLite backup), uploads, data, quarantine, and private config.
   Keep separately named recoverable backups on both machines. Transfer only
   over an authenticated private channel; do not put an archive behind a public
   download URL. Verify file checksums/counts and SQLite integrity after transfer.
   Restart the Pi service to keep its DDNS endpoint available.
6. Place the transferred state at the paths below. Start BeerRun and validate
   it through Docker's internal network before changing the public route.
   If migrations are pending, rehearse them against a disposable copy first,
   review the result, then explicitly use `python3 update.py --migrate`.
7. Save the exact existing Caddyfile and change **only** this site's upstream:

   ```caddyfile
   beerrun.selfhaven.eu {
       reverse_proxy beer-run:8000
   }
   ```

   Leave `beerrun.ddns.net` forwarding to `192.168.178.225:8000`. Validate the
   proposed complete Caddy configuration using the existing Caddy binary before
   writing it. Preserve the inode of its file bind mount when installing the
   update. Use `caddy reload` in the existing container; do not recreate or
   restart the shared proxy. Check the new hostname and baseline HTTP status
   of the other existing hostnames before and after the reload. If verification
   fails, restore the saved file and reload it.
8. Once the public app and persistent writes pass verification, install only
   `beer-run-update.service` and `beer-run-update.timer` in `/etc/systemd/system`,
   then enable the new timer. No existing service or timer is restarted.
   The host requires a sudo password for this one-time installation. Its user
   manager has lingering disabled, so a user timer would not reliably survive
   logout. Do not change existing user-session behavior to work around this.

The owner confirmed nobody is currently using the app, so a one-time snapshot
is sufficient. DDNS stays on the Pi's retained copy; use the selfhaven domain
for entries after cutover. There is no bidirectional database synchronization.

## Host-owned persistent layout

```text
/home/lspataru/deployments/beer-run/
  compose.yaml
  update.py
  app.env                 # private auth/signup/legal values, read-only in container
  .env                    # optional BOOZERUN_IMAGE override; no app secrets here
  state/
    boozerun.db           # SQLite; keep any SQLite sidecars in this directory
    uploads/              # original static/uploads tree; URLs are unchanged
    data/
      drinks.json
      wrapped.json        # legacy recap, if present
      wrapped/            # run-scoped recaps, if present
    quarantine/           # original .account-deletion-quarantine, if present
  backups/                # full stopped-state archives; includes private app.env
  release.json            # current/previous image IDs and last backup
```

Copy only the four required app values from the Pi's private configuration to
`app.env`, preserving their values. Do not carry old database/path overrides:
container paths are fixed in the image. Application secrets load from the
read-only file rather than being baked into the image or Compose environment.
Docker administrators can still read the mounted file.

The container runs as UID/GID 1000 with a read-only application filesystem and
bounded temporary storage, CPU, memory, and logs. It publishes **no host ports**;
Caddy reaches `beer-run:8000` on `caddy-net`. The image trusts forwarded headers
only from the existing Caddy address configured in Compose.

For a deliberately empty installation, create and own `state`, `state/data`,
and `state/uploads`, provide private `app.env`, copy
`/app/seed-data/drinks.json` from the image to `state/data/drinks.json`, and run
`docker compose run --rm beer-run python scripts/migrate_db.py` explicitly.
Never use fresh-install commands as a substitute for transferring the Pi data.

## Updates and future migrations

The timer pulls every five minutes using only this Compose project and service.
Unchanged healthy images are left running. Before replacing a changed image:

1. Pin the pulled image ID and check its migration readiness against host state.
2. If that check fails, keep the old app running and fail the update visibly in
   the systemd journal. Review the release; rehearse migrations on a copy.
3. With `python3 update.py --migrate`, stop only BeerRun, create a unique full
   database/media/config backup, then apply migrations in a one-off container.
   Ordinary updates also take a stopped-state backup before replacing the app.
4. Wait for the candidate's health check. Code-only failures restore the old
   image while keeping current host data. After a migration attempt, a failure
   leaves BeerRun stopped with a `recovery-required.json` marker that blocks
   subsequent timer runs until explicit recovery. It never automatically rewinds
   user data or starts older code against a changed schema.

```sh
cd /home/lspataru/deployments/beer-run
python3 update.py                      # routine guarded update
python3 update.py --migrate            # explicitly reviewed migration release
systemctl status beer-run-update.timer
journalctl -u beer-run-update.service -n 100 --no-pager
docker compose ps
docker compose logs --tail 100 beer-run
```

Each update briefly stops BeerRun while archiving its state. Monitor backup
space and archive duration; backups are never automatically pruned. Copy
verified backups to separate protected storage regularly: same-disk archives
are useful rollback copies, not protection from loss of the server. On a
migration/health failure, inspect the journal and retained backup before recovery.

## Rollback and recovery

Stop the BeerRun timer first so it cannot undo a rollback. For a code-only
rollback, set `BOOZERUN_IMAGE=ghcr.io/matei9721/beer-run-jpn:sha-<known-good-sha>`
in the deployment's `.env`, then run `python3 update.py`. Review any schema
compatibility first: readiness verifies required migrations, not downgrade
compatibility. An older image may accept a newer schema but fail at runtime.

After a migration failure, stop BeerRun and retain the failed state separately.
Restore a selected archive into a **new staging directory**, inspect its database
integrity and ownership, and explicitly choose whether to replace live state.
Restore matching database, uploads, recaps, quarantine, and config as a set;
do not extract over a live application. Use the recorded previous image and
verify it before enabling traffic or the timer. Image rollback alone does not
undo database migrations. No automatic destructive restore is provided.
Remove `recovery-required.json` only after reviewing the failure and completing
the chosen recovery, then run the updater explicitly before re-enabling its timer.

The upload-path file migration remains a separate, explicitly authorized
maintenance operation; neither image startup nor `update.py` invokes it.

## Local container verification

```sh
docker build -t beer-run:local .
bash deploy/smoke-test.sh beer-run:local
```

The smoke test uses only a newly named Docker volume and container, synthetic
secrets, an empty migrated database, and seeded drink configuration. It checks
HTTP routes, non-root execution, and persistence across restart, then removes
only its own disposable resources. The normal host FastAPI workflow and live
repository data remain untouched.
