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

1. Copy `.env.example` to `.env`.
2. Set `SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD`.
3. Set `ATS_ID`, `ATS_PW`, and `ATS_URL` when ATS automation is ready.
4. Set Gmail SMTP values when result emails are ready.
5. Install dependencies from `requirements.txt`.
6. Run:

```powershell
python run.py
```

Open `http://127.0.0.1:8000`.

Default development login:

- ID: `admin`
- Password: `admin1234`

Change this in `.env` before real use.

## Always-on Local Run

See `SERVICE_GUIDE.md`.

Quick options:

- Windows startup task: `.\scripts\install_startup_task.ps1`
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
