# Running the ATS Parking App

## Option A: Start the app at Windows login

Use this on a local PC. Install the runtime and register the app task:

```powershell
.\scripts\setup_runtime.ps1
.\scripts\install_startup_task.ps1
```

The app should answer at `http://127.0.0.1:8000`. Check it with:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Logs are written under `data\`. The server and Tunnel start scripts rotate their active log when it reaches 10 MB and keep one prior copy.

## Option B: Windows app with a named Cloudflare Tunnel

This is the documented employee access path. The app and `cloudflared.exe` run on the same Windows PC, and the Tunnel origin should point to `http://127.0.0.1:8000`.

### Move the Tunnel token out of .env

Run this once. It migrates `CLOUDFLARE_TUNNEL_TOKEN` from `.env` into an ignored, current-user-only file at `secrets\cloudflared-token`. If the token is not in `.env`, the script prompts for it without echoing the input.

```powershell
.\scripts\migrate_cloudflare_tunnel_token.ps1
```

Do not commit or copy the `secrets\` directory. The startup task now reads the token with `--token-file`, so it does not appear as a command-line argument.

### Check and update cloudflared

Check the executable used by the task. By default it is `%USERPROFILE%\Downloads\cloudflared\cloudflared.exe`; set `CLOUDFLARED_PATH` if yours is elsewhere.

```powershell
$cloudflared = Join-Path $env:USERPROFILE "Downloads\cloudflared\cloudflared.exe"
& $cloudflared --version
```

The startup script refuses versions older than `2026.10.2`. Stage the official Windows 64-bit release `2026.10.5`; the updater verifies its SHA-256 checksum before accepting it:

```powershell
.\scripts\update_cloudflared.ps1
```

Before replacing the running connector, add a temporary replica for the same Tunnel in Cloudflare Zero Trust. Confirm it is healthy and can reach the same origin. If the origin is only reachable on this PC, arrange a replica host that can reach it or use a maintenance window; a replica that cannot reach the origin does not protect the app.

Stop the scheduled task or close the existing Tunnel process, then apply the staged executable:

```powershell
Stop-ScheduledTask -TaskName "ATS Parking Cloudflare Tunnel"
.\scripts\update_cloudflared.ps1 -Apply
& $cloudflared --version
Start-ScheduledTask -TaskName "ATS Parking Cloudflare Tunnel"
```

If you use the Startup folder shortcut instead of Task Scheduler, stop that Tunnel process after confirming the replica is healthy, then run the apply command and start the Tunnel again with:

```powershell
.\scripts\start_cloudflare_tunnel.ps1
```

Verify the Tunnel is Healthy in the dashboard, check `data\cloudflared.err.log` for errors, and test the public app URL and a test registration. Keep the previous executable backup until the checks pass. If the new connector fails, stop it, restore the `.bak` executable over `cloudflared.exe`, and restart the Tunnel.

Remove the temporary replica after the updated connector is healthy. If the app is confirmed to use only one connector and a replica cannot be made to reach the origin, update during a maintenance window and expect a brief registration API interruption while the Tunnel reconnects.

### Temporary demonstration tunnel

A Quick Tunnel has a changing public URL and is for demonstrations only. Start it explicitly:

```powershell
.\scripts\start_cloudflare_tunnel.ps1 -Quick
```

For a fixed employee URL, use the named Tunnel and token file above. The daily publish check starts a Quick Tunnel only when no named token file exists.

## Option C: Docker

Run the app locally:

```powershell
.\scripts\run_docker.ps1
```

The host port is bound to `127.0.0.1`, and Docker log files are capped at 10 MB with three retained files.

To run the named Tunnel in Docker, first create `secrets\cloudflared-token` using the migration script above. In the Cloudflare Tunnel dashboard, set the service origin to `http://app:8000` for the Compose network. Then run:

```powershell
docker compose --profile tunnel up -d --build
docker compose --profile tunnel ps
docker compose --profile tunnel exec cloudflared cloudflared --version
docker compose --profile tunnel logs --tail=50 cloudflared
```

The Compose Tunnel image is pinned to `cloudflare/cloudflared:2026.10.5`. Do not configure its origin as `127.0.0.1:8000`: inside the connector container, localhost is the connector itself.

## HTTPS origin certificate check

The documented Windows and Docker origins use HTTP on a private local/Compose network. In that configuration there is no HTTPS origin certificate for `cloudflared` to validate. The public browser-to-Cloudflare connection is a separate TLS leg.

If the Tunnel dashboard instead points to an `https://` origin, check that the certificate hostname matches the configured origin hostname and that the certificate chain is trusted. For diagnosis, inspect Tunnel logs for `x509: certificate is valid for ... not ...` (hostname mismatch) or `x509: certificate signed by unknown authority` (CA trust issue). Fix the hostname or CA chain; do not leave origin TLS verification disabled.

## Legacy API key endpoint

The old `POST /register` endpoint is disabled when `API_KEY` is blank. The current app uses authenticated `/api/*` routes. Do not put `API_KEY` in browser JavaScript; anything sent by a browser is visible to users.

## Data and log cleanup

The automatic cleanup is limited to log rotation. Keep `data\parking_app.db` (application and audit history), `data\storage_state.json` (ATS login session), and screenshots until the owner-approved retention period is defined. They can contain operational evidence or credentials; do not delete them as part of a routine memory cleanup.

## Daily health check

Install the daily task if the PC should check the app and Tunnel at 9:00 AM while Windows is on:

```powershell
.\scripts\install_daily_publish_task.ps1 -ExpectedPublicUrl "https://YOUR-NAMED-HOSTNAME"
```

The script checks `/api/health`, starts the app if needed, checks Tunnel logs and emails an alert when SMTP is configured. A Quick Tunnel URL changes after a restart; a named Tunnel is required for a fixed URL.

## Remove startup tasks

```powershell
.\scripts\uninstall_all_startup_tasks.ps1
```
