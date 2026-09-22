"""Browser automation with Playwright (Lecture 12 §6): when search + fetch isn't
enough — JavaScript-rendered pages and multi-step flows behind a login.

Two demos:
1. `render_vs_fetch` — a plain HTTP GET of a JS page returns an empty shell;
   a real browser runs the JavaScript and the content appears.
2. `automate_login` — the four browser primitives (goto, fill, click, read)
   sequenced into a login flow, with the ACT/OBS trace the lecture shows.

Target site: https://quotes.toscrape.com — a sandbox built for scraping practice
(its /js/ page renders with JavaScript; its /login accepts any credentials).

Why the SYNC Playwright API in a worker thread (not the async API)?
    Playwright spawns a driver **subprocess**. Under some server event loops —
    Windows' SelectorEventLoop, or certain uvicorn/uvloop thread setups — the
    async API's `loop.subprocess_exec` hits `_make_subprocess_transport` and
    raises `NotImplementedError`. Running the *sync* API via `asyncio.to_thread`
    dispatches it to a fresh worker thread that has **no running event loop**, so
    Playwright creates its own and handles the subprocess correctly everywhere
    (Linux/macOS/Windows, uvloop or not). This keeps the FastAPI handlers async
    while the browser work runs off the request loop.
"""
from __future__ import annotations

import asyncio

import httpx
import trafilatura
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from .config import Settings

_UA = "kmitl-web-automation/1.0 (teaching demo)"
JS_DEMO_URL = "https://quotes.toscrape.com/js/"
LOGIN_URL = "https://quotes.toscrape.com/login"


class BrowserUnavailable(RuntimeError):
    """The browser couldn't start — almost always because it wasn't installed."""


def _launch_hint(exc: Exception) -> str:
    return (
        "Could not start the browser. In the backend/ folder run:\n"
        "    uv run playwright install chromium\n"
        "(on Linux you may also need: uv run playwright install-deps)\n"
        f"Original error: {exc}"
    )


def _launch_chromium(p):
    """Launch chromium, turning the cryptic 'Executable doesn't exist' / missing-lib
    failure into a clear, actionable BrowserUnavailable message."""
    try:
        return p.chromium.launch()
    except PlaywrightError as exc:
        raise BrowserUnavailable(_launch_hint(exc)) from exc


# --- sync workers (run inside a worker thread via asyncio.to_thread) ------------

def _render_vs_fetch_sync(url: str, settings: Settings) -> dict:
    # 1) plain HTTP GET — what search+fetch would see
    try:
        raw_html = httpx.get(url, timeout=settings.request_timeout,
                             headers={"User-Agent": _UA}, follow_redirects=True).text
    except httpx.HTTPError as exc:
        raw_html = f"(fetch failed: {exc})"
    raw_text = (trafilatura.extract(raw_html) or "").strip()

    # 2) real browser — runs the page's JavaScript, then reads the DOM
    with sync_playwright() as p:
        browser = _launch_chromium(p)
        page = browser.new_page(user_agent=_UA)
        page.goto(url, wait_until="networkidle", timeout=30000)
        rendered_text = page.inner_text("body").strip()
        try:
            quote_count = page.locator(".quote").count()   # quotes.toscrape specific
        except Exception:  # noqa: BLE001
            quote_count = None
        browser.close()

    return {
        "url": url,
        "raw_len": len(raw_text),
        "raw_preview": raw_text[:400] or "(a plain GET returned no readable content — "
                                         "the page is built by JavaScript)",
        "rendered_len": len(rendered_text),
        "rendered_preview": rendered_text[:400],
        "quotes_visible_after_render": quote_count,
    }


def _automate_login_sync(username: str, password: str, settings: Settings) -> dict:
    trace: list[dict] = []

    def log(act: str, obs: str) -> None:
        trace.append({"act": act, "obs": obs})

    with sync_playwright() as p:
        browser = _launch_chromium(p)
        page = browser.new_page(user_agent=_UA)

        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        log(f'goto("{LOGIN_URL}")', f"ok ({page.url})")

        page.fill("input#username", username)
        log('fill("input#username", …)', f"typed {username!r}")

        page.fill("input#password", password)
        log('fill("input#password", …)', "typed ••••••")

        page.click("input[type=submit]")
        page.wait_for_load_state("domcontentloaded")
        log('click("input[type=submit]")', f"navigated -> {page.url}")

        logged_in = page.locator("a[href='/logout']").count() > 0
        log('read("a[href=/logout]")', "Logout link present" if logged_in
            else "not logged in (no Logout link)")

        first_author = ""
        if page.locator(".quote .author").count():
            first_author = page.locator(".quote .author").first.inner_text()
            log('read(".quote .author")', f"{first_author!r}")

        browser.close()

    return {
        "logged_in": logged_in,
        "result": (f"Logged in as {username!r}; the first quote on the page is by "
                   f"{first_author}.") if logged_in else "Login did not succeed.",
        "trace": trace,
    }


# --- async wrappers the FastAPI handlers await ---------------------------------

async def render_vs_fetch(url: str, settings: Settings) -> dict:
    """Compare a plain GET (no JavaScript) with a real browser render."""
    return await asyncio.to_thread(_render_vs_fetch_sync, url, settings)


async def automate_login(username: str, password: str, settings: Settings) -> dict:
    """Drive the goto → fill → fill → click → read flow, recording every ACT/OBS."""
    return await asyncio.to_thread(_automate_login_sync, username, password, settings)
