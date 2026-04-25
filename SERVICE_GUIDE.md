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

## Option B: Docker

Use this when Docker Desktop is available and set to start with Windows.

```powershell
.\scripts\run_docker.ps1
```

The compose file uses `restart: unless-stopped`, so Docker restarts the app automatically after Docker Desktop starts.

## Notes

- The PC must be on.
- The ATS app must be able to reach the ATS website from this PC.
- If other employees need access from their PCs, expose this app through a company-approved tunnel, VPN, reverse proxy, or internal network address.

