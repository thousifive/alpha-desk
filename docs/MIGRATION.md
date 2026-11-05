# Moving the backend to the Linux laptop

From "the Mac runs `make serve` sometimes" to "the Linux laptop runs it always". About 30
minutes. Devices keep the same API URL, so nothing changes on them except the hostname that
`/health` reports.

**Two rules:**

1. Only one server is live at a time, and the database only moves forward. Never start a server
   on an older copy of `alpha.db` than the one devices last synced with (see
   [Why the database only moves forward](#why-the-database-only-moves-forward)).
2. The API stays private: `tailscale serve` only, never `tailscale funnel`.

## Keeping the URL stable

Netlify's `VITE_API_URL` is baked into the app at build time, e.g.
`https://alpha-desk.tailf48ab9.ts.net`. Two ways to handle the move:

| | How | Cost |
|---|---|---|
| **(a) Move the name (recommended)** | The Mac gives up the Tailscale machine name `alpha-desk`, and the laptop takes it. | Nothing changes in Netlify or on devices. MagicDNS points the same name at the laptop within a minute. |
| (b) Change the URL | The laptop keeps its own name, and you update `VITE_API_URL` in Netlify. | One deploy (~15 credits). Every installed PWA must pick up the update ("Update available · tap to reload") before it can sync again; until then it just shows offline. |

Machine names are unique in a tailnet. A second machine asking for `alpha-desk` gets
`alpha-desk-1`, so the Mac must be renamed **first**. Use the admin console for both renames
(Machines → the machine → **⋯** → **Edit machine name**, and untick "Auto-generate from OS
hostname"). That way an OS hostname change never steals or drops the name.

The steps below use (a).

## 0. Before you start

On the Mac:

- Let every device sync once (Settings → SYNC NOW, pill shows "Synced"), so nothing important
  waits only on a phone. This isn't strictly needed (devices keep their own log and upload
  later), but it makes step 7 easy to check.
- Note the current numbers to compare later:
  ```sh
  make serve-status                                  # Health host = the Mac
  sqlite3 data/alpha.db 'select max(seq) from syncevent'
  ```

## 1. Prepare the laptop

```sh
# Docker Engine + the compose plugin: follow docs.docker.com/engine/install for your distro
docker compose version                   # v2.x
sudo usermod -aG docker "$USER"          # then log out and back in

# Tailscale: same account (tailnet) as the Mac
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
sudo tailscale set --operator="$USER"    # lets scripts manage `tailscale serve` without sudo

git clone <repo-url> ~/alpha-desk && cd ~/alpha-desk
```

No Python, uv or Node is needed on the laptop: everything runs in the container. The dataset
(`data/meridian/`) is in git. MagicDNS and HTTPS certificates are tailnet-wide settings and are
already on from the Mac setup.

## 2. Stop the Mac server

In the Mac's `make serve` terminal press **Ctrl+C**. It turns `tailscale serve` off, stops the
container, and writes a fresh backup. Note its name from the output
(`backup: /backups/alpha-<timestamp>.db`).

From here until step 6 the server is down. That's fine: devices keep working offline and
queue their events.

## 3. Copy the data

Copy the **backup**, not the live file. A backup is a single self-contained file; the live
database may still have a `-wal` sidecar.

```sh
# on the Mac, from the repo root
B=$(ls backups/alpha-*.db | tail -1)
scp "$B"         laptop:~/alpha-desk/data/alpha.db
scp backend/.env laptop:~/alpha-desk/backend/.env
```

`backend/.env` holds the password hash, session secret, `CORS_ORIGINS` and (from M4) the
Anthropic key. Copy it only over `scp`/`ssh`: never email it or put it in the repo. Keeping
the same `SESSION_SECRET` means every device's login token stays valid.

You don't copy any Tailscale state: the laptop has its own identity, and only the name moves.

## 4. Try it on the laptop under its own name

```sh
cd ~/alpha-desk
make serve      # first run builds the image (a few minutes), runs migrations, starts,
                # serves https://<laptop-name>.<tailnet>.ts.net and checks /api/health there
```

In a second terminal:

```sh
make serve-status                                        # everything up, Funnel off
sqlite3 data/alpha.db 'select max(seq) from syncevent'   # same number as on the Mac
```

Then **Ctrl+C** `make serve`. That also removes the temporary serve handler, so no stale
config is left under the laptop's old name.

## 5. Move the name

In the admin console (login.tailscale.com → Machines):

1. Mac: **Edit machine name** → e.g. `thousif-mac`. This frees `alpha-desk`.
2. Laptop: **Edit machine name** → `alpha-desk`.

Check on the laptop:

```sh
tailscale status --peers=false    # shows alpha-desk
```

## 6. Make it permanent

```sh
scripts/install-systemd.sh       # installs + starts alpha-desk.service and the daily backup timer
systemctl status alpha-desk      # active (exited) = compose is up and serve is on
systemctl list-timers | grep alpha-desk
make serve-status                # URL https://alpha-desk.<tailnet>.ts.net, Via tailnet: ok
```

Why this survives reboots:

- Docker starts at boot (`systemctl is-enabled docker`).
- `alpha-desk.service` runs `docker compose up` and then `scripts/tailscale-serve.sh on`, which
  is idempotent.
- `tailscaled` also keeps the serve setting in its own state across reboots.
- Unlike `make serve` on the Mac, stopping the service leaves serve on. A stopped backend then
  just reads as "offline" on devices.

Laptop settings worth changing:

- Don't suspend on lid close: `HandleLidSwitch=ignore` in `/etc/systemd/logind.conf`.
- Enable automatic security updates.
- In the admin console, **Disable key expiry** for the laptop, so it never silently drops off
  the tailnet after 180 days.

## 7. Check from the iPhone on mobile data

Turn **Wi-Fi off** on the iPhone (so it can't take a LAN shortcut), with Tailscale connected:

1. In Safari, open `https://alpha-desk.<tailnet>.ts.net/health`. It should show `"db":"ok"`
   and the **laptop's** hostname in `host`.
2. Open the Alpha Desk app. Settings → SYNC shows **Server: on** and Address
   `alpha-desk.<tailnet>.ts.net`. Anything done offline during the move uploads (the queued
   count drops to 0).

## 8. Retire the Mac server

```sh
# on the Mac
. scripts/env.sh && docker compose down      # removes the container (data/ stays)
mv data/alpha.db data/alpha.db.moved-to-laptop
```

Renaming the old database means a stray `make serve` on the Mac starts empty instead of
quietly serving stale data. It also can't take over the URL: the Mac no longer has the
`alpha-desk` name. Keep `backups/` for a few weeks.

## Rollback: serve from the Mac again

Something wrong on the laptop? Move the **laptop's** data back, never the Mac's old copy:

```sh
# on the laptop: stop, back up, release the URL
sudo systemctl disable --now alpha-desk.service alpha-desk-backup.timer   # stop writes a backup
scripts/tailscale-serve.sh off
ls -t ~/alpha-desk/backups/alpha-*.db | head -1                           # the newest backup
```

In the admin console: rename the laptop away from `alpha-desk` (e.g. `thinkpad`), then rename
the Mac back to `alpha-desk`.

```sh
# on the Mac
scp laptop:~/alpha-desk/backups/<that file> data/alpha.db
rm -f data/alpha.db-wal data/alpha.db-shm
make serve        # serves https://alpha-desk.<tailnet>.ts.net from the Mac again
```

If the laptop died and its backups are lost, read the next section before starting the Mac on
its old database.

## Why the database only moves forward

The server numbers every event it receives (`seq`), and each device remembers the highest
number it has downloaded (its cursor). On the next sync it asks only for "everything after my
cursor".

Start a server on an older database and its numbering restarts from that older, lower point.
New events get numbers the devices think they already have, so they never download them. Each
device still keeps and uploads its own events, so nothing is lost, but devices stop seeing
each other's progress until the numbering passes their cursor.

If you ever have to do it (the newest database is gone), clear the app's data on each device:
iOS Settings → Safari → Advanced → Website Data, or remove and re-add the Home Screen app.
**Export your progress first** (Settings → EXPORT MY PROGRESS) and import it afterwards. The
device then downloads everything again and re-uploads its own events on the next sync. (A
server-side guard for this is a possible follow-up.)
