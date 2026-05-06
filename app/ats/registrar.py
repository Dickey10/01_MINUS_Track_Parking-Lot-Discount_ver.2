from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from playwright.async_api import APIResponse, BrowserContext, Page, async_playwright

from app.ats import selectors as sel
from app.ats.session import is_session_valid, save_session, session_exists
from app.config import settings
from app.integrations.gsheets import append_history
from app.integrations.mailer import send_failure_alert
from app.models import RegisterRequest, RegisterResponse


class ATSRegistrar:
    async def run(self, req: RegisterRequest) -> RegisterResponse:
        if not settings.ats_id or not settings.ats_pw:
            return RegisterResponse(
                success=False,
                message="ATS credentials are not configured.",
                car_number=req.car_number,
                discount_type=req.discount_type,
                coupon_30_count=req.coupon_30_count,
                coupon_60_count=req.coupon_60_count,
            )

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx_kwargs = {}
            if session_exists():
                ctx_kwargs["storage_state"] = str(Path(settings.session_path))

            context = await browser.new_context(ignore_https_errors=True, **ctx_kwargs)
            page = await context.new_page()

            try:
                if not await is_session_valid(page, settings.ats_url):
                    await self._login(page, context)

                result = await self._register(page, req)
                await append_history(req, result)
                return result
            except Exception as exc:
                screenshot_path = await self._take_screenshot(page, f"error_{req.car_number}")
                await send_failure_alert(req, str(exc), screenshot_path)
                return RegisterResponse(
                    success=False,
                    message=f"ATS automation error: {exc}",
                    car_number=req.car_number,
                    discount_type=req.discount_type,
                    coupon_30_count=req.coupon_30_count,
                    coupon_60_count=req.coupon_60_count,
                    screenshot_path=screenshot_path,
                )
            finally:
                await context.close()
                await browser.close()

    async def _login(self, page: Page, context: BrowserContext) -> None:
        await page.goto(f"{settings.ats_url}{sel.LOGIN_URL}")
        await page.wait_for_load_state("networkidle")

        await page.get_by_role("listitem").nth(1).click()
        await page.get_by_role("textbox", name="ID").fill(settings.ats_id)
        await page.get_by_role("textbox", name="PASSWORD").fill(settings.ats_pw)
        await page.get_by_role("button", name="Submit").click()
        await page.wait_for_load_state("networkidle")
        await self._dismiss_popups(page)
        await save_session(context)

    async def _dismiss_popups(self, page: Page) -> None:
        for label in ("OK", "확인", "닫기"):
            try:
                button = page.get_by_text(label).first
                if await button.is_visible(timeout=1500):
                    await button.click()
            except Exception:
                pass

    async def _register(self, page: Page, req: RegisterRequest) -> RegisterResponse:
        await page.goto(f"{settings.ats_url}{sel.DISCOUNT_URL}")
        await page.wait_for_load_state("networkidle")

        entry = await self._find_entry(page, req.car_number)
        if not entry:
            return RegisterResponse(
                success=False,
                message=f"Vehicle is not currently entered: {req.car_number}",
                car_number=req.car_number,
                discount_type=req.discount_type,
                coupon_30_count=req.coupon_30_count,
                coupon_60_count=req.coupon_60_count,
            )

        pe_id = str(entry.get("id") or entry.get("iID") or "")
        if not pe_id:
            return RegisterResponse(
                success=False,
                message=f"Vehicle was found, but ATS entry id is missing: {req.car_number}",
                car_number=req.car_number,
                discount_type=req.discount_type,
                coupon_30_count=req.coupon_30_count,
                coupon_60_count=req.coupon_60_count,
            )

        detail = await self._get_discount_detail(page, pe_id)
        discount_ids = self._discount_type_ids(detail)
        car_number = (
            detail.get("parkEntry", {}).get("acPlate1")
            or entry.get("carNo")
            or req.car_number
        )

        for _ in range(req.coupon_60_count):
            await self._save_discount(
                page=page,
                pe_id=pe_id,
                discount_type_id=discount_ids[60],
                car_number=car_number,
                memo=req.reason,
            )
        for _ in range(req.coupon_30_count):
            await self._save_discount(
                page=page,
                pe_id=pe_id,
                discount_type_id=discount_ids[30],
                car_number=car_number,
                memo=req.reason,
            )

        screenshot_path = await self._take_screenshot(page, f"success_{req.car_number}")
        return RegisterResponse(
            success=True,
            message="Discount coupons were applied through ATS save API.",
            car_number=req.car_number,
            discount_type="auto",
            coupon_30_count=req.coupon_30_count,
            coupon_60_count=req.coupon_60_count,
            screenshot_path=screenshot_path,
        )

    async def _find_entry(self, page: Page, car_number: str) -> dict[str, Any] | None:
        normalized = self._normalize_car_number(car_number)
        candidate_dates = [
            datetime.now().strftime("%Y%m%d"),
            (datetime.now() - timedelta(days=1)).strftime("%Y%m%d"),
        ]

        for entry_date in candidate_dates:
            rows = await self._list_for_discount(page, car_number, entry_date)
            for row in rows:
                row_car = self._normalize_car_number(str(row.get("carNo") or row.get("acPlate1") or ""))
                if normalized and normalized in row_car:
                    return row
            if rows:
                return rows[0]
        return None

    async def _list_for_discount(self, page: Page, car_number: str, entry_date: str) -> list[dict[str, Any]]:
        response = await self._post_ats_form(
            page,
            sel.LIST_FOR_DISCOUNT_URL,
            {
                "iLotArea": sel.DEFAULT_LOT_AREA,
                "entryDate": entry_date,
                "carNo": car_number,
            },
        )
        data = await self._json_response(response)
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        return []

    async def _get_discount_detail(self, page: Page, pe_id: str) -> dict[str, Any]:
        response = await self._post_ats_form(
            page,
            sel.GET_FOR_DISCOUNT_URL,
            {
                "id": pe_id,
                "member_id": settings.ats_id,
            },
        )
        data = await self._json_response(response)
        if not isinstance(data, dict):
            raise RuntimeError("ATS getForDiscount returned an unexpected response.")
        return data

    async def _save_discount(
        self,
        page: Page,
        pe_id: str,
        discount_type_id: str,
        car_number: str,
        memo: str = "",
    ) -> None:
        response = await self._post_ats_form(
            page,
            sel.SAVE_DISCOUNT_URL,
            {
                "peId": pe_id,
                "discountType": discount_type_id,
                "saveCnt": "1",
                "carNo": car_number,
                "acPlate2": "",
                "memo": memo or "",
            },
        )
        data = await self._json_response(response)
        if data is not True:
            raise RuntimeError(f"ATS save failed: {data}")

    async def _post_ats_form(self, page: Page, path: str, form: dict[str, Any]) -> APIResponse:
        response = await page.request.post(
            f"{settings.ats_url}{path}",
            form={key: str(value) for key, value in form.items()},
            headers={
                "Accept": "*/*",
                "Ajax": "true",
                "Amano_http_ajax": "true",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{settings.ats_url}{sel.DISCOUNT_URL}?SWversion=ATS3000V2.72_20220215",
            },
        )
        if not response.ok:
            raise RuntimeError(f"ATS request failed: {path} HTTP {response.status}")
        return response

    async def _json_response(self, response: APIResponse) -> Any:
        try:
            return await response.json()
        except Exception:
            return (await response.text()).strip()

    def _discount_type_ids(self, detail: dict[str, Any]) -> dict[int, str]:
        found: dict[int, str] = {}
        for item in detail.get("listDiscountType", []):
            try:
                value = int(item.get("discount_value"))
            except Exception:
                continue
            if value in (30, 60):
                found[value] = str(item.get("id"))

        missing = [value for value in (30, 60) if value not in found]
        if missing:
            raise RuntimeError(f"ATS discount type id is missing for: {missing}")
        return found

    def _normalize_car_number(self, value: str) -> str:
        return "".join(value.split())

    async def _has_no_result(self, page: Page) -> bool:
        for text in (sel.NO_RESULT_MESSAGE, "검색 결과가 없습니다", "No result"):
            try:
                await page.get_by_text(text).wait_for(timeout=1200)
                return True
            except Exception:
                pass
        return False

    async def _apply_coupon(self, page: Page, selector: str, count: int) -> None:
        if count <= 0:
            return
        await page.locator(selector).wait_for(timeout=5000)
        for _ in range(count):
            await page.locator(selector).click()
            await self._confirm_if_needed(page)

    async def _confirm_if_needed(self, page: Page) -> None:
        for label in (sel.SUCCESS_MESSAGE, "등록되었습니다", "적용되었습니다", "OK", "확인"):
            try:
                element = page.get_by_text(label).first
                if await element.is_visible(timeout=1200):
                    await element.click()
                    return
            except Exception:
                pass

    async def _take_screenshot(self, page: Page, name: str) -> str:
        directory = Path(settings.screenshot_dir)
        directory.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(ch for ch in name if ch.isalnum() or ch in ("_", "-"))
        path = directory / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}.png"
        await page.screenshot(path=str(path), full_page=True)
        return str(path)
