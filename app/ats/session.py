from pathlib import Path

from playwright.async_api import Page

from app.config import settings
from app.ats import selectors as sel


def _session_path() -> Path:
    return Path(settings.session_path)


def session_exists() -> bool:
    path = _session_path()
    return path.exists() and path.stat().st_size > 0


async def save_session(context) -> None:
    path = _session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=str(path))


async def is_session_valid(page: Page, base_url: str) -> bool:
    await page.goto(f"{base_url}{sel.DISCOUNT_URL}")
    await page.wait_for_load_state("networkidle")
    return "login" not in page.url.lower()

