from datetime import datetime
from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright

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

        await page.locator(sel.CAR_SEARCH_INPUT).fill(req.car_number)
        await page.locator(sel.SEARCH_BUTTON).click()
        await page.wait_for_load_state("networkidle")

        if await self._has_no_result(page):
            return RegisterResponse(
                success=False,
                message=f"Vehicle is not currently entered: {req.car_number}",
                car_number=req.car_number,
                discount_type=req.discount_type,
                coupon_30_count=req.coupon_30_count,
                coupon_60_count=req.coupon_60_count,
            )

        row_index = await page.evaluate(
            """(carNo) => {
                try {
                    const normalized = carNo.replace(/\\s/g, '');
                    for (let i = 0; i < dataSetMst.length; i++) {
                        const row = dataSetMst[i];
                        for (const key in row) {
                            if (String(row[key]).replace(/\\s/g, '').includes(normalized)) {
                                XgridMst.selectRow(i, true);
                                return i;
                            }
                        }
                    }
                } catch(e) {}
                return -1;
            }""",
            req.car_number,
        )

        if row_index == -1:
            return RegisterResponse(
                success=False,
                message=f"Vehicle was not found in ATS grid: {req.car_number}",
                car_number=req.car_number,
                discount_type=req.discount_type,
                coupon_30_count=req.coupon_30_count,
                coupon_60_count=req.coupon_60_count,
            )

        await self._apply_coupon(page, sel.DISCOUNT_60MIN_SEL, req.coupon_60_count)
        await self._apply_coupon(page, sel.DISCOUNT_30MIN_SEL, req.coupon_30_count)

        screenshot_path = await self._take_screenshot(page, f"success_{req.car_number}")
        return RegisterResponse(
            success=True,
            message="Discount coupons were applied.",
            car_number=req.car_number,
            discount_type="auto",
            coupon_30_count=req.coupon_30_count,
            coupon_60_count=req.coupon_60_count,
            screenshot_path=screenshot_path,
        )

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

