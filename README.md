# ATS Parking Discount Web App

This project is a small FastAPI web app for internal parking discount requests.

## Main Features

- Login with admin and department manager roles
- Department account creation and deactivation
- Department registration and deletion
- Result email recipient registration and deletion
- Parking discount application form
- Automatic 30-minute / 60-minute coupon calculation with a 10-minute exit buffer
- ATS browser automation through Playwright
- Manual application completion screen
- Filtered usage statistics with subtotal minutes
- SQLite audit and application history

## First Run

Recommended: run `setup.ps1`. It creates a unique `SECRET_KEY`, generates a one-time administrator password, and asks for the ATS credentials.

If you configure the environment manually:

1. Copy `.env.example` to `.env`.
2. Set `SECRET_KEY` to a random value of at least 32 characters. Generate one with `python -c "import secrets; print(secrets.token_hex(48))"`.
3. Set `ADMIN_USERNAME` and a unique `ADMIN_PASSWORD` of at least 24 characters before the first startup.
4. Set `ATS_ID`, `ATS_PW`, and `ATS_URL` when ATS automation is ready.
5. Set Gmail SMTP values when result emails are ready.
6. Install dependencies from `requirements.txt` and run:

```powershell
python run.py
```

Open `http://127.0.0.1:8000`. The app refuses first startup with a known/default admin password or a missing signing key. There is no shared development login.

## Always-on Local Run

See `SERVICE_GUIDE.md`.

Quick options:

- Windows startup task: `.\scripts\install_startup_task.ps1`
- Local PC + Cloudflare Tunnel: `.\scripts\install_all_startup_tasks.ps1`
- Docker: `.\scripts\run_docker.ps1`

## ATS Maintenance

If ATS changes its HTML, update `app/ats/selectors.py` first. The rest of the automation code expects the selectors in that file.

## Discount Rule

The app adds a 10-minute exit buffer to the elapsed parking time, then rounds up by 30-minute units. 60-minute coupons are used first.

Examples:

- 0-19 effective minutes: one 30-minute coupon
- 20-49 effective minutes: one 60-minute coupon
- 50-79 effective minutes: one 60-minute coupon and one 30-minute coupon
- 80-109 effective minutes: two 60-minute coupons
