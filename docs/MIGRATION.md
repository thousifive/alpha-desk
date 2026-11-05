# Moving the backend to the Linux laptop

From "the Mac runs `make serve` sometimes" to "the Linux laptop runs it always". About 30
minutes. The devices notice nothing except the server's hostname in Settings.

**The one rule:** only one server is live at a time, and the database only moves forward.
Never start a server on an older copy of `alpha.db` than the one devices last synced with
(see [Why the rule](#why-the-rule)).

> Remote access (Tailscale) isn't set up yet. Steps marked **[Tailscale]** become real once it
> is; until then skip them, and the move is just "same data, new machine".

## 0. Before you start

On the Mac:

- Let every device sync once (Settings → SYNC NOW, pill shows "Synced"), so nothing important
  waits only on a phone. Not strictly needed (devices keep their own log and upload later),
  but it makes step 6 easy to check.
- Note the current numbers to compare later:
  ```sh
  curl -s localhost:8000/health        # host = the Mac
  sqlite3 data/alpha.db 'select max(seq) from syncevent'
  ```

## 1. Prepare the laptop

```sh
# Docker Engine + the compose plugin: follow docs.docker.com/engine/install for your distro
docker compose version                 # v2.x
sudo usermod -aG docker "$USER"        # then log out and back in
git clone <repo-url> ~/alpha-desk && cd ~/alpha-desk
```

No Python, uv or Node needed on the laptop: everything runs in the container.

**[Tailscale]** Install Tailscale and log in with the same account as the Mac.

## 2. Stop the Mac server

In the `make serve` terminal press **Ctrl+C**. It stops the container and writes a fresh
backup; note its name from the output (`backup: /backups/alpha-<timestamp>.db`).

From here until step 5 the server is down. That's fine: devices keep working offline and
queue their events.

## 3. Copy the data

Copy the **backup**, not the live file: a backup is a single self-contained file, while the
live database may still have a `-wal` sidecar. The dataset (`data/meridian/`) is in git, so
the clone already has it.

```sh
# on the Mac, from the repo root
B=$(ls backups/alpha-*.db | tail -1)
ssh laptop 'mkdir -p ~/alpha-desk/backups'
scp "$B"             laptop:~/alpha-desk/data/alpha.db
scp backend/.env     laptop:~/alpha-desk/backend/.env
```

`backend/.env` holds the password hash, session secret and (from M4) the Anthropic key. Copy
it only over `scp`/`ssh`; never email it or put it in the repo. Keeping the same
`SESSION_SECRET` means every device's login token stays valid.

**[Tailscale]** Nothing else to copy: the laptop gets its own Tailscale identity when it logs in.

## 4. Start it on the laptop

```sh
cd ~/alpha-desk
make serve        # first run: builds the image (a few minutes), runs migrations, starts
```

Check it in a second terminal, then Ctrl+C `make serve` (it backs up on the way out):

```sh
curl -s localhost:8000/health
# {"status":"ok","version":"0.1.0+<sha>","db":"ok","host":"<laptop hostname>"}
sqlite3 data/alpha.db 'select max(seq) from syncevent'   # same number as on the Mac
```

## 5. Make it permanent

```sh
scripts/install-systemd.sh       # installs and starts alpha-desk.service + the daily backup timer
systemctl status alpha-desk      # active (exited) = compose is up
systemctl list-timers | grep alpha-desk
curl -s localhost:8000/health    # host = the laptop again
```

**[Tailscale]** Point the remote-access URL at the laptop (DEPLOY.md, "Remote access"). If
the URL changes, update `VITE_API_URL` in Netlify (triggers a rebuild) and `CORS_ORIGINS`
stays as it is.

Laptop settings worth changing: don't suspend on lid close
(`HandleLidSwitch=ignore` in `/etc/systemd/logind.conf`), and enable automatic security updates.

## 6. Check from a device

Open the app on a phone. Within a minute:

- Settings → SYNC shows **Server: on** and the laptop's hostname.
- Anything done offline during the move uploads (queued count drops to 0).

## 7. Retire the Mac server

```sh
# on the Mac
. scripts/env.sh && docker compose down      # removes the container (data/ stays)
mv data/alpha.db data/alpha.db.moved-to-laptop
```

Renaming the old database means a stray `make serve` on the Mac starts empty instead of
quietly serving stale data. Keep `backups/` for a few weeks.

**[Tailscale]** Stop the Mac from serving the remote-access URL.

## Rollback

Something wrong on the laptop? Move the **laptop's** data back, never the Mac's old copy:

```sh
# on the laptop
sudo systemctl disable --now alpha-desk.service alpha-desk-backup.timer   # stops + backs up
B=$(ls ~/alpha-desk/backups/alpha-*.db | tail -1)

# on the Mac
scp laptop:"$B" data/alpha.db
rm -f data/alpha.db-wal data/alpha.db-shm
make serve
```

**[Tailscale]** Point the remote-access URL back at the Mac.

If the laptop died and its backups are lost, see the next section before starting the Mac on
its old database.

## Why the rule

The server numbers every event it receives (`seq`), and each device remembers the highest
number it has downloaded (its cursor). On the next sync it asks only for "everything after my
cursor".

Start a server on an older database and its numbering restarts from that older, lower point.
New events get numbers the devices think they already have, so they never download them. Each
device still keeps and uploads its own events, so nothing is lost, but devices stop seeing
each other's progress until the numbering passes their cursor.

If you ever must do it (the newest database is gone): sign out and back in on every device
after the server starts. That doesn't reset the cursor yet, so for now clear the app's data
in the browser settings instead; the device downloads everything again and re-uploads its own
events on the next sync. (A server-side guard for this is a possible follow-up.)
