# Running the ATS Parking App Without Keeping PowerShell Open

You do not need to keep a PowerShell window open.

## Option A: Windows Startup Task

Use this when the app should run on this PC after Windows login.

Run PowerShell once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\scripts\install_startup_task.ps1
```

After that, the app starts automatically at login:

```text
http://127.0.0.1:8000
```

Logs:

```text
data/server.log
```

Remove the startup task:

```powershell
.\scripts\uninstall_startup_task.ps1
```

## Option B: Local PC + Cloudflare Tunnel

Use this when other employees need to access the app through a web URL while the
app still runs on this PC.

1. Install or place `cloudflared.exe` at:

```text
C:\Users\HOME\Downloads\cloudflared\cloudflared.exe
```

2. In Cloudflare Zero Trust, create a tunnel and route a hostname to:

```text
http://127.0.0.1:8000
```

3. Copy the tunnel token into `.env`:

```text
CLOUDFLARE_TUNNEL_TOKEN=your-cloudflare-token
```

4. Install both startup tasks:

```powershell
.\scripts\install_all_startup_tasks.ps1
```

If Windows blocks Task Scheduler registration, use the current-user Startup
folder instead:

```powershell
.\scripts\install_user_startup_shortcuts.ps1
```

After the next Windows login, both the app server and the tunnel start
automatically.

Logs:

```text
data/server.log
data/cloudflared.log
```

Remove the Startup folder shortcuts:

```powershell
.\scripts\uninstall_user_startup_shortcuts.ps1
```

For a temporary test URL without a token:

```powershell
.\scripts\start_cloudflare_tunnel.ps1
```

The temporary URL looks like:

```text
https://random-words.trycloudflare.com
```

It does not require domain ownership, but the URL changes whenever the tunnel
restarts. This is useful for demos, not production.

## Option B-2: Same Wi-Fi or Office LAN by IP Address

This works only when users are on the same office network or VPN.

1. Change `.env`:

```text
APP_HOST=0.0.0.0
APP_PORT=8000
```

2. Restart the app.

3. Find this PC's IPv4 address:

```powershell
ipconfig
```

4. Other users open:

```text
http://YOUR_PC_IPV4:8000
```

If it does not open, Windows Firewall must allow inbound TCP port `8000`.
Do not expose this directly to the public Internet without a VPN, tunnel, or
reverse proxy.

## Option C: Docker

Use this when Docker Desktop is available and set to start with Windows.

```powershell
.\scripts\run_docker.ps1
```

The compose file uses `restart: unless-stopped`, so Docker restarts the app automatically after Docker Desktop starts.

## Notes

- The PC must be on.
- The ATS app must be able to reach the ATS website from this PC.
- If other employees need access from their PCs, expose this app through a company-approved tunnel, VPN, reverse proxy, or internal network address.
