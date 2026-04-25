from datetime import datetime

from app.config import settings


async def append_history(req, result) -> None:
    if not settings.gsheet_id:
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(
            settings.gsheet_creds_path, scopes=scopes
        )
        gc = gspread.authorize(creds)
        ws = gc.open_by_key(settings.gsheet_id).sheet1
        ws.append_row(
            [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                req.car_number,
                req.coupon_60_count,
                req.coupon_30_count,
                req.dept,
                req.requester,
                req.reason,
                "success" if result.success else "failed",
                result.message,
            ]
        )
    except Exception as exc:
        print(f"[gsheets] append failed: {exc}")

