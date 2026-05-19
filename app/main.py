import asyncio
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from app.ats.registrar import ATSRegistrar
from app.config import settings
from app.discount import calculate_discount_plan, calculate_discount_plan_from_minutes
from app.integrations.mailer import send_result_email
from app.models import (
    AccountCreate,
    AccountUpdate,
    ATSDiscountDeleteRequest,
    DepartmentCreate,
    DepartmentUpdate,
    DivisionCreate,
    DivisionUpdate,
    EmailRecipientCreate,
    EmailSettingsUpdate,
    LoginRequest,
    ManualApplyRequest,
    ParkingApplicationCreate,
    PasswordChangeRequest,
    RegisterRequest,
    RegisterResponse,
)
from app.security import create_token, decode_token, hash_password, verify_password
from app.storage import audit, connect, init_db, row_to_dict, rows_to_dicts, utc_now


app = FastAPI(title="ATS Parking Discount API")
origins = ["*"] if settings.cors_origins == "*" else [
    item.strip() for item in settings.cors_origins.split(",") if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_ats_lock = asyncio.Lock()
registrar = ATSRegistrar()
ENV_PATH = Path(".env")


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"Internal server error: {exc}"})


@app.on_event("startup")
async def startup() -> None:
    init_db()


def _is_admin(user: dict) -> bool:
    return user["role"] in ("super_admin", "admin")


def _has_all_scope(user: dict) -> bool:
    return _is_admin(user) or user.get("division") == "admin"


def _password_error(password: str) -> str:
    if len(password) < 8:
        return "비밀번호는 8자 이상이어야 합니다."
    if not any(ch.isupper() for ch in password):
        return "비밀번호에는 영문 대문자가 포함되어야 합니다."
    if not any(ch.islower() for ch in password):
        return "비밀번호에는 영문 소문자가 포함되어야 합니다."
    if not any(ch.isdigit() for ch in password):
        return "비밀번호에는 숫자가 포함되어야 합니다."
    if not any(not ch.isalnum() for ch in password):
        return "비밀번호에는 특수문자가 포함되어야 합니다."
    return ""


def _can_manage_account(user: dict, target: dict) -> bool:
    if target["id"] == user["id"]:
        return True
    if _has_all_scope(user):
        return True
    return user["role"] == "division_admin" and target.get("division", "") == user.get("division", "")


def get_current_user(authorization: Annotated[str, Header()] = "") -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Login required")
    payload = decode_token(authorization.removeprefix("Bearer ").strip())
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    with connect() as conn:
        user = row_to_dict(
            conn.execute(
                """
                SELECT id, username, display_name, division, department, role, is_active
                FROM accounts
                WHERE id = ?
                """,
                (payload["sub"],),
            ).fetchone()
        )
    if not user or not user["is_active"] or user["role"] == "inactive":
        raise HTTPException(status_code=401, detail="Inactive account")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def active_email_recipients() -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT email FROM email_recipients WHERE is_active = 1 ORDER BY email"
        ).fetchall()
    configured = [row["email"] for row in rows]
    fallback = [email.strip() for email in settings.alert_email.split(",") if email.strip()]
    return configured or fallback


def get_application(application_id: int) -> dict:
    with connect() as conn:
        app_row = row_to_dict(
            conn.execute("SELECT * FROM parking_applications WHERE id = ?", (application_id,)).fetchone()
        )
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    return app_row


def department_division(name: str) -> str:
    with connect() as conn:
        row = row_to_dict(conn.execute("SELECT division FROM departments WHERE name = ?", (name,)).fetchone())
    return row["division"] if row else ""


def update_email_status(application_id: int, sent: bool) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE parking_applications SET email_status = ?, updated_at = ? WHERE id = ?",
            ("sent" if sent else "failed", utc_now(), application_id),
        )


def update_env_values(values: dict[str, str]) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    pending = values.copy()
    updated: list[str] = []
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            updated.append(line)
            continue
        key = line.split("=", 1)[0]
        if key in pending:
            updated.append(f"{key}={pending.pop(key)}")
        else:
            updated.append(line)
    for key, value in pending.items():
        updated.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(updated) + "\n", encoding="utf-8")


@app.get("/")
async def root():
    return FileResponse("frontend/index.html")


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/health")
async def health():
    return RedirectResponse(url="/")


@app.get("/api/health")
async def api_health():
    return {"status": "ok"}


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    with connect() as conn:
        row = row_to_dict(
            conn.execute("SELECT * FROM accounts WHERE username = ?", (req.username,)).fetchone()
        )
    if not row or not row["is_active"] or row["role"] == "inactive" or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token({"sub": row["id"], "role": row["role"]})
    return {
        "token": token,
        "expires_in": 600,
        "user": {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "division": row.get("division", ""),
            "department": row["department"],
            "role": row["role"],
        },
    }


@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@app.get("/api/accounts")
async def list_accounts(_: dict = Depends(require_admin)):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, username, display_name, division, department, role, is_active, created_at, updated_at
            FROM accounts
            ORDER BY id ASC
            """
        ).fetchall()
    return rows_to_dicts(rows)


@app.get("/api/password-targets")
async def password_targets(user: dict = Depends(get_current_user)):
    with connect() as conn:
        if _has_all_scope(user):
            rows = conn.execute(
                "SELECT id, username, display_name, division, department, role, is_active FROM accounts ORDER BY id ASC"
            ).fetchall()
        elif user["role"] == "division_admin":
            rows = conn.execute(
                """
                SELECT id, username, display_name, division, department, role, is_active
                FROM accounts
                WHERE id = ? OR division = ?
                ORDER BY id ASC
                """,
                (user["id"], user.get("division", "")),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, username, display_name, division, department, role, is_active
                FROM accounts
                WHERE id = ?
                ORDER BY id ASC
                """,
                (user["id"],),
            ).fetchall()
    return rows_to_dicts(rows)


@app.post("/api/accounts")
async def create_account(req: AccountCreate, user: dict = Depends(require_admin)):
    now = utc_now()
    division = "admin" if req.role in ("super_admin", "admin") else req.division
    try:
        with connect() as conn:
            existing = row_to_dict(
                conn.execute("SELECT id FROM accounts WHERE username = ?", (req.username,)).fetchone()
            )
            if existing:
                conn.execute(
                    """
                    UPDATE accounts
                    SET password_hash = ?, display_name = ?, division = ?, department = ?,
                        role = ?, is_active = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        hash_password(req.password),
                        req.display_name,
                        division,
                        req.department,
                        req.role,
                        0 if req.role == "inactive" else 1,
                        now,
                        existing["id"],
                    ),
                )
                account_id = existing["id"]
                created = False
            else:
                created = True
                cur = conn.execute(
                    """
                    INSERT INTO accounts
                      (username, password_hash, display_name, division, department, role, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        req.username,
                        hash_password(req.password),
                        req.display_name,
                        division,
                        req.department,
                        req.role,
                        0 if req.role == "inactive" else (1 if req.is_active else 0),
                        now,
                        now,
                    ),
                )
                account_id = cur.lastrowid
        audit(user["id"], "create" if created else "update", "account", account_id, req.username)
        return {"id": account_id, "existing": not created}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not create account: {exc}")


@app.patch("/api/accounts/{account_id}")
async def update_account(account_id: int, req: AccountUpdate, user: dict = Depends(require_admin)):
    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone())
    if not existing:
        raise HTTPException(status_code=404, detail="Account not found")
    if account_id == user["id"] and req.is_active is False:
        raise HTTPException(status_code=400, detail="자기 계정은 비활성화할 수 없습니다.")

    role = req.role if req.role is not None else existing["role"]
    division = req.division if req.division is not None else existing.get("division", "")
    if role in ("super_admin", "admin"):
        division = "admin"
    is_active = int(req.is_active) if req.is_active is not None else existing["is_active"]
    if role == "inactive":
        is_active = 0
    elif req.is_active is True and existing["role"] == "inactive" and req.role is None:
        role = "user"
        is_active = 1
    elif req.role is not None and req.is_active is None:
        is_active = 1

    with connect() as conn:
        conn.execute(
            """
            UPDATE accounts
            SET display_name = ?, division = ?, department = ?, role = ?, is_active = ?, password_hash = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                req.display_name if req.display_name is not None else existing["display_name"],
                division,
                req.department if req.department is not None else existing["department"],
                role,
                is_active,
                hash_password(req.password) if req.password else existing["password_hash"],
                utc_now(),
                account_id,
            ),
        )
    audit(user["id"], "update", "account", account_id, existing["username"])
    return {"ok": True}


@app.post("/api/accounts/{account_id}/password")
async def change_account_password(account_id: int, req: PasswordChangeRequest, user: dict = Depends(get_current_user)):
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail="새 비밀번호와 재확인 비밀번호가 일치하지 않습니다.")
    password_error = _password_error(req.new_password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)
    with connect() as conn:
        actor = row_to_dict(conn.execute("SELECT id, password_hash FROM accounts WHERE id = ?", (user["id"],)).fetchone())
        target = row_to_dict(
            conn.execute(
                "SELECT id, username, division, role, is_active FROM accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
        )
        if not actor or not verify_password(req.current_password, actor["password_hash"]):
            raise HTTPException(status_code=401, detail="현재 비밀번호가 일치하지 않습니다.")
        if not target:
            raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
        if not _can_manage_account(user, target):
            raise HTTPException(status_code=403, detail="해당 계정의 비밀번호를 변경할 권한이 없습니다.")
        conn.execute(
            "UPDATE accounts SET password_hash = ?, updated_at = ? WHERE id = ?",
            (hash_password(req.new_password), utc_now(), account_id),
        )
    audit(user["id"], "change_password", "account", account_id, target["username"])
    return {"ok": True}


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int, user: dict = Depends(require_admin)):
    if account_id == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    with connect() as conn:
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    audit(user["id"], "delete", "account", account_id)
    return {"ok": True}


@app.get("/api/divisions")
async def list_divisions(_: dict = Depends(get_current_user)):
    with connect() as conn:
        rows = conn.execute("SELECT * FROM divisions ORDER BY id ASC").fetchall()
    return rows_to_dicts(rows)


@app.post("/api/divisions")
async def create_division(req: DivisionCreate, user: dict = Depends(require_admin)):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="본부명을 입력하세요.")
    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT id FROM divisions WHERE name = ?", (name,)).fetchone())
        if existing:
            return {"id": existing["id"], "ok": True, "existing": True}
        cur = conn.execute(
            "INSERT INTO divisions (name, is_active, created_at) VALUES (?, 1, ?)",
            (name, utc_now()),
        )
        division_id = cur.lastrowid
    audit(user["id"], "create", "division", division_id, name)
    return {"id": division_id}


@app.delete("/api/divisions/{division_id}")
async def delete_division(division_id: int, user: dict = Depends(require_admin)):
    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT id, name FROM divisions WHERE id = ?", (division_id,)).fetchone())
        if not existing:
            raise HTTPException(status_code=404, detail="본부를 찾을 수 없습니다.")
        conn.execute("DELETE FROM divisions WHERE id = ?", (division_id,))
        conn.execute("UPDATE departments SET division = '' WHERE division = ?", (existing["name"],))
        conn.execute("UPDATE accounts SET division = '' WHERE division = ?", (existing["name"],))
    audit(user["id"], "delete", "division", division_id)
    return {"ok": True}


@app.put("/api/divisions/{division_id}")
async def update_division(division_id: int, req: DivisionUpdate, user: dict = Depends(require_admin)):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="본부명을 입력하세요.")
    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT id, name FROM divisions WHERE id = ?", (division_id,)).fetchone())
        if not existing:
            raise HTTPException(status_code=404, detail="본부를 찾을 수 없습니다.")
        duplicate = row_to_dict(
            conn.execute("SELECT id FROM divisions WHERE name = ? AND id <> ?", (name, division_id)).fetchone()
        )
        if duplicate:
            raise HTTPException(status_code=400, detail="이미 등록된 본부명입니다.")
        old_name = existing["name"]
        conn.execute("UPDATE divisions SET name = ? WHERE id = ?", (name, division_id))
        conn.execute("UPDATE departments SET division = ? WHERE division = ?", (name, old_name))
        conn.execute("UPDATE accounts SET division = ? WHERE division = ?", (name, old_name))
    audit(user["id"], "update", "division", division_id, f"{old_name} -> {name}")
    return {"ok": True}


@app.get("/api/departments")
async def list_departments(user: dict = Depends(get_current_user)):
    with connect() as conn:
        if _has_all_scope(user):
            rows = conn.execute("SELECT * FROM departments ORDER BY id ASC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM departments WHERE division = ? ORDER BY id ASC",
                (user.get("division", ""),),
            ).fetchall()
    return rows_to_dicts(rows)


@app.post("/api/departments")
async def create_department(req: DepartmentCreate, user: dict = Depends(require_admin)):
    division = req.division.strip()
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="부서명을 입력하세요.")
    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT id FROM departments WHERE name = ?", (name,)).fetchone())
        if existing:
            if division:
                conn.execute(
                    "UPDATE departments SET division = ? WHERE id = ?",
                    (division, existing["id"]),
                )
            return {"id": existing["id"], "ok": True, "existing": True}
        cur = conn.execute(
            "INSERT INTO departments (division, name, is_active, created_at) VALUES (?, ?, 1, ?)",
            (division, name, utc_now()),
        )
        department_id = cur.lastrowid
    audit(user["id"], "create", "department", department_id, f"{division}/{name}")
    return {"id": department_id}


@app.delete("/api/departments/{department_id}")
async def delete_department(department_id: int, user: dict = Depends(require_admin)):
    with connect() as conn:
        conn.execute("DELETE FROM departments WHERE id = ?", (department_id,))
    audit(user["id"], "delete", "department", department_id)
    return {"ok": True}


@app.put("/api/departments/{department_id}")
async def update_department(department_id: int, req: DepartmentUpdate, user: dict = Depends(require_admin)):
    division = req.division.strip()
    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT id, name FROM departments WHERE id = ?", (department_id,)).fetchone())
        if not existing:
            raise HTTPException(status_code=404, detail="부서를 찾을 수 없습니다.")
        conn.execute("UPDATE departments SET division = ? WHERE id = ?", (division, department_id))
    audit(user["id"], "update", "department", department_id, f"{division}/{existing['name']}")
    return {"ok": True}


@app.get("/api/email-recipients")
async def list_email_recipients(_: dict = Depends(require_admin)):
    with connect() as conn:
        rows = conn.execute("SELECT * FROM email_recipients ORDER BY id ASC").fetchall()
    return rows_to_dicts(rows)


@app.post("/api/email-recipients")
async def create_email_recipient(req: EmailRecipientCreate, user: dict = Depends(require_admin)):
    email = req.email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="이메일을 입력하세요.")
    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT id FROM email_recipients WHERE email = ?", (email,)).fetchone())
        if existing:
            conn.execute(
                "UPDATE email_recipients SET name = ?, is_active = 1 WHERE id = ?",
                (req.name, existing["id"]),
            )
            return {"id": existing["id"], "ok": True, "existing": True}
        cur = conn.execute(
            "INSERT INTO email_recipients (email, name, is_active, created_at) VALUES (?, ?, ?, ?)",
            (email, req.name, 1 if req.is_active else 0, utc_now()),
        )
        recipient_id = cur.lastrowid
    audit(user["id"], "create", "email_recipient", recipient_id, email)
    return {"id": recipient_id}


@app.delete("/api/email-recipients/{recipient_id}")
async def delete_email_recipient(recipient_id: int, user: dict = Depends(require_admin)):
    with connect() as conn:
        conn.execute("DELETE FROM email_recipients WHERE id = ?", (recipient_id,))
    audit(user["id"], "delete", "email_recipient", recipient_id)
    return {"ok": True}


@app.get("/api/email-settings")
async def email_settings(_: dict = Depends(require_admin)):
    return {
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_user": settings.smtp_user,
        "smtp_password_configured": bool(settings.smtp_password),
        "alert_email": settings.alert_email,
    }


@app.post("/api/email-settings")
async def save_email_settings(req: EmailSettingsUpdate, user: dict = Depends(require_admin)):
    smtp_user = req.smtp_user.strip()
    password_required = bool(smtp_user) and (
        not settings.smtp_password or smtp_user != settings.smtp_user
    )
    if password_required and not req.smtp_password.strip():
        raise HTTPException(
            status_code=400,
            detail="Enter the SMTP app password when configuring a new sender email.",
        )

    values = {
        "SMTP_HOST": req.smtp_host.strip() or "smtp.gmail.com",
        "SMTP_PORT": str(req.smtp_port),
        "SMTP_USER": smtp_user,
        "ALERT_EMAIL": req.alert_email.strip(),
    }
    if req.smtp_password:
        values["SMTP_PASSWORD"] = req.smtp_password.strip()
    update_env_values(values)

    settings.smtp_host = values["SMTP_HOST"]
    settings.smtp_port = int(values["SMTP_PORT"])
    settings.smtp_user = values["SMTP_USER"]
    settings.alert_email = values["ALERT_EMAIL"]
    if req.smtp_password:
        settings.smtp_password = values["SMTP_PASSWORD"]

    audit(user["id"], "update", "email_settings", None, settings.smtp_user)
    return {"ok": True, "smtp_user": settings.smtp_user, "smtp_password_configured": bool(settings.smtp_password)}


@app.post("/api/applications")
async def create_application(req: ParkingApplicationCreate, user: dict = Depends(get_current_user)):
    entry_time = req.entry_time or datetime.now()
    exit_time = req.exit_time or datetime.now(entry_time.tzinfo)
    if exit_time < entry_time:
        raise HTTPException(status_code=400, detail="출차 시간은 입차 시간 이후여야 합니다.")
    plan = calculate_discount_plan(entry_time, now=exit_time)
    now = utc_now()
    division = department_division(req.dept) or user.get("division", "")
    if not _has_all_scope(user) and division != user.get("division", ""):
        raise HTTPException(status_code=403, detail="같은 본부의 부서만 선택할 수 있습니다.")

    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO parking_applications
              (car_number, entry_time, ats_entry_id, division, dept, requester, visitor_company, visit_purpose,
               elapsed_minutes, effective_minutes, coupon_30_count, coupon_60_count,
               total_discount_minutes, status, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                req.car_number,
                entry_time.isoformat(timespec="seconds"),
                req.ats_entry_id.strip(),
                division,
                req.dept,
                req.requester,
                req.visitor_company,
                req.visit_purpose,
                plan.elapsed_minutes,
                plan.effective_minutes,
                plan.coupon_30_count,
                plan.coupon_60_count,
                plan.total_discount_minutes,
                user["id"],
                now,
                now,
            ),
        )
        application_id = cur.lastrowid
    audit(user["id"], "create", "application", application_id, req.car_number)

    if req.auto_apply:
        return await process_application(application_id, user)
    return get_application(application_id)


@app.post("/api/applications/{application_id}/process")
async def process_application(application_id: int, user: dict = Depends(get_current_user)):
    application = get_application(application_id)
    with connect() as conn:
        conn.execute(
            "UPDATE parking_applications SET status = 'processing', updated_at = ? WHERE id = ?",
            (utc_now(), application_id),
        )

    req = RegisterRequest(
        car_number=application["car_number"],
        ats_entry_id=application.get("ats_entry_id", ""),
        discount_type="60" if application["coupon_60_count"] else "30",
        coupon_30_count=application["coupon_30_count"],
        coupon_60_count=application["coupon_60_count"],
        dept=application["dept"],
        requester=application["requester"],
        visitor_company=application["visitor_company"],
        reason=application["visit_purpose"],
    )
    async with _ats_lock:
        result = await registrar.run(req)

    status = "succeeded" if result.success else "failed"
    with connect() as conn:
        conn.execute(
            """
            UPDATE parking_applications
            SET status = ?, failure_reason = ?, screenshot_path = ?, processed_by = ?,
                processed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                "" if result.success else result.message,
                result.screenshot_path,
                user["id"],
                utc_now(),
                utc_now(),
                application_id,
            ),
        )
    audit(user["id"], "process", "application", application_id, status)
    updated = get_application(application_id)
    sent = await send_result_email(updated, active_email_recipients())
    update_email_status(application_id, sent)
    return get_application(application_id)


@app.post("/api/applications/{application_id}/resend-email")
async def resend_application_email(application_id: int, user: dict = Depends(require_admin)):
    application = get_application(application_id)
    sent = await send_result_email(application, active_email_recipients())
    update_email_status(application_id, sent)
    audit(user["id"], "resend_email", "application", application_id, "sent" if sent else "failed")
    updated = get_application(application_id)
    if not sent:
        raise HTTPException(
            status_code=502,
            detail="Email send failed. Check SMTP sender settings and active recipients.",
        )
    return updated


@app.post("/api/applications/{application_id}/manual-apply")
async def manual_apply(application_id: int, req: ManualApplyRequest, user: dict = Depends(get_current_user)):
    application = get_application(application_id)
    if req.effective_minutes is not None:
        plan = calculate_discount_plan_from_minutes(req.effective_minutes)
    else:
        plan = calculate_discount_plan_from_minutes(application["elapsed_minutes"])

    with connect() as conn:
        conn.execute(
            """
            UPDATE parking_applications
            SET status = 'manual', failure_reason = ?, effective_minutes = ?,
                coupon_30_count = ?, coupon_60_count = ?, total_discount_minutes = ?,
                processed_by = ?, processed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                req.reason,
                plan.effective_minutes,
                plan.coupon_30_count,
                plan.coupon_60_count,
                plan.total_discount_minutes,
                user["id"],
                utc_now(),
                utc_now(),
                application_id,
            ),
        )
    audit(user["id"], "manual_apply", "application", application_id, req.reason)
    updated = get_application(application_id)
    sent = await send_result_email(updated, active_email_recipients())
    update_email_status(application_id, sent)
    return get_application(application_id)


def _filter_conditions(filters: dict[str, str]) -> tuple[str, list[str]]:
    conditions = []
    values: list[str] = []
    for column, value in filters.items():
        if value:
            conditions.append(f"{column} = ?")
            values.append(value)
    return (f"WHERE {' AND '.join(conditions)}" if conditions else "", values)


@app.get("/api/applications")
async def list_applications(
    user: dict = Depends(get_current_user),
    division: str = "",
    dept: str = "",
    requester: str = "",
    visitor_company: str = "",
    visit_purpose: str = "",
    status: str = "",
):
    filters = {
        "division": division,
        "dept": dept,
        "requester": requester,
        "visitor_company": visitor_company,
        "visit_purpose": visit_purpose,
    }
    if status:
        filters["status"] = status
    if not _has_all_scope(user):
        filters["division"] = user.get("division", "")
    where, values = _filter_conditions(filters)
    if not status:
        clause = "status IN ('pending', 'succeeded')"
        where = f"{where} AND {clause}" if where else f"WHERE {clause}"
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM parking_applications {where} ORDER BY id ASC LIMIT 500",
            values,
        ).fetchall()
    return rows_to_dicts(rows)


@app.get("/api/stats")
async def stats(
    user: dict = Depends(get_current_user),
    division: str = Query(default=""),
    dept: str = Query(default=""),
    requester: str = Query(default=""),
    visitor_company: str = Query(default=""),
    visit_purpose: str = Query(default=""),
    status: str = Query(default=""),
):
    applications = await list_applications(
        user=user,
        division=division,
        dept=dept,
        requester=requester,
        visitor_company=visitor_company,
        visit_purpose=visit_purpose,
        status=status,
    )
    return {
        "count": len(applications),
        "subtotal_effective_minutes": sum(row["effective_minutes"] for row in applications),
        "subtotal_discount_minutes": sum(row["total_discount_minutes"] for row in applications),
        "coupon_30_count": sum(row["coupon_30_count"] for row in applications),
        "coupon_60_count": sum(row["coupon_60_count"] for row in applications),
        "items": applications,
    }


@app.get("/api/ats/entries")
async def search_ats_entries(
    car_number: str = Query(min_length=2, max_length=30),
    entry_date: str = Query(default=""),
    _: dict = Depends(get_current_user),
):
    async with _ats_lock:
        rows = await registrar.search_entries(car_number, entry_date)
    return {"items": rows}


@app.post("/api/ats/discount-delete")
async def delete_ats_discount(req: ATSDiscountDeleteRequest, user: dict = Depends(require_admin)):
    async with _ats_lock:
        result = await registrar.delete_discount(req)
    audit(user["id"], "delete", "ats_discount", None, f"{req.tckttrns_id}/{req.idno}")
    if not result.success:
        raise HTTPException(status_code=502, detail=result.message)
    return result


@app.post("/register", response_model=RegisterResponse)
async def legacy_register(req: RegisterRequest, x_api_key: Annotated[str, Header()] = ""):
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    async with _ats_lock:
        return await registrar.run(req)
