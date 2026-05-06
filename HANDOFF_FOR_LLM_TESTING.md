# ATS Parking Discount App Handoff

## Project

- Local path: `C:\Users\HOME\Downloads\MINUS-Praking-20260424T053504Z-3-001\MINUS-Praking`
- Stack: FastAPI, SQLite, static HTML/JavaScript frontend, Playwright ATS automation
- Main app URL: `http://127.0.0.1:8000/`
- External demo URL is a temporary Cloudflare Tunnel URL and may change after restart.

## Current Working Flow

1. User logs in to the parking discount web app.
2. User enters car number, requester, department, company, and purpose.
3. User clicks `Check Entry`.
4. App queries ATS current entry records through `POST /discount/registration/listForDiscount`.
5. App displays matched ATS entry rows.
6. User selects one ATS entry row.
7. User clicks `Submit`.
8. App calculates 30-minute and 60-minute coupon counts.
9. App applies coupons to the selected ATS entry through `POST /discount/registration/save`.

## Confirmed ATS API Behavior

### Entry Search

ATS list search may return an empty list when the full Korean plate is used.
For example, `224호9784` can fail, while `9784` succeeds.

The app therefore tries these search terms:

- normalized full plate
- last four digits
- leading digits before the last four digits

### Save Discount

Endpoint:

```text
POST /discount/registration/save
```

Form fields:

```text
peId=<ATS entry id>
discountType=3 or 4
saveCnt=1
carNo=<plate>
acPlate2=
memo=
```

Discount type IDs:

- `3`: 30-minute coupon
- `4`: 60-minute coupon

## Coupon Calculation Rule

The business rule is based on the current parking elapsed time and a 10-minute exit buffer.

```text
effective_minutes = elapsed_minutes + 10
coupon_units_30 = floor(effective_minutes / 30) + 1
coupon_units_30 is capped at 48 units, equal to 24 hours.
60-minute coupons are allocated first.
30-minute coupon is used only for one remaining 30-minute unit.
```

Examples:

| Elapsed Parking Time | Coupon Result |
| --- | --- |
| 0-19 min | 30m x 1 |
| 20-49 min | 60m x 1 |
| 50-79 min | 60m x 1, 30m x 1 |
| 80-109 min | 60m x 2 |
| 3h 11m | 60m x 3, 30m x 1 |
| 24h or more | capped at 60m x 24 |

Important bug fixed:

- Old logic effectively added the 10-minute threshold twice.
- That made 3h 11m become 60m x 4.
- Correct result is 60m x 3 and 30m x 1.

## Files Most Relevant For Testing

- `app/discount.py`: coupon calculation logic
- `tests/test_discount.py`: coupon boundary tests
- `app/ats/registrar.py`: ATS search, selected entry, save/delete automation
- `app/main.py`: FastAPI routes and application processing
- `frontend/index.html`: Check Entry, Select, Submit UI

## Test Commands

```powershell
cd C:\Users\HOME\Downloads\MINUS-Praking-20260424T053504Z-3-001\MINUS-Praking
.\.venv\Scripts\python.exe -m unittest tests.test_discount
.\.venv\Scripts\python.exe -m py_compile app\main.py app\discount.py app\ats\registrar.py
```

## Runtime Notes

If Playwright browser errors occur, run:

```powershell
.\scripts\setup_runtime.ps1
```

Start server:

```powershell
.\scripts\start_server.ps1
```

Health check:

```text
http://127.0.0.1:8000/api/health
```

## Safety Notes

- Do not expose ATS credentials in the frontend.
- Do not commit `.env`.
- Avoid logging ATS session cookies, password hashes, phone numbers, or vehicle images.
- Any live `Submit` test applies real ATS discount coupons.
