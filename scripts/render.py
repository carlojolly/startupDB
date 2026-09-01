"""Pass 2 of the fetch pipeline: render pages in a real browser.

Roughly 17% of company homepages return HTTP 200 with almost no text — they
are JavaScript shells that only assemble their content in a browser. Plain
HTTP cannot read them. This module re-fetches those pages with Chromium so
the JS runs, and hands back the text.

Measured on the 14 THIN pages of the 50-company sample: 4 went from 0
characters to 1.7k-8.6k. The other 10 were genuinely empty or unreachable,
so rendering is worth doing only for pages pass 1 could not read.

Requires the Chromium binary:  playwright install chromium
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from test_websites import TextExtractor, USER_AGENT

# Assets that cannot contribute text. Blocking them cuts render time
# substantially on image-heavy marketing sites and changes no extracted text.
BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}


@dataclass
class Rendered:
    url: str
    text: str = ""
    title: str = ""
    ok: bool = False
    note: str = ""          # 'via-http', 'no-networkidle', or an exception name
    elapsed_ms: int = 0


def candidates(url: str) -> list[str]:
    """https first, then the same host over plain http.

    Mirrors check_one() in test_websites.py. Several companies have expired or
    misconfigured certificates and are only reachable over http; without this
    the browser pass reports 0 characters for pages that do have content.
    """
    urls = [url]
    if url.startswith("https://"):
        urls.append("http://" + url[len("https://"):])
    return urls


async def _render_one(context, url: str, settle_ms: int, timeout_ms: int) -> Rendered:
    loop = asyncio.get_event_loop()
    started = loop.time()
    result = Rendered(url=url)
    page = await context.new_page()
    try:
        await page.route(
            "**/*",
            lambda route: asyncio.ensure_future(
                route.abort() if route.request.resource_type in BLOCKED_RESOURCE_TYPES
                else route.continue_()
            ),
        )
        last = ""
        for candidate in candidates(url):
            note = "" if candidate.startswith("https") else "via-http"
            try:
                await page.goto(candidate, wait_until="domcontentloaded", timeout=timeout_ms)
                try:
                    await page.wait_for_load_state("networkidle", timeout=settle_ms)
                except Exception:
                    # A page that polls forever never goes idle; take what has
                    # rendered by now rather than failing the whole fetch.
                    note = (note + " no-networkidle").strip()
                parser = TextExtractor()
                parser.feed(await page.content())
                result.text = parser.text
                result.title = " ".join((await page.title() or "").split())[:120]
                result.ok = True
                result.note = note
                break
            except Exception as exc:  # noqa: BLE001
                last = type(exc).__name__
        else:
            result.note = last
    finally:
        await page.close()
        result.elapsed_ms = int((loop.time() - started) * 1000)
    return result


async def render_many(urls: list[str], concurrency: int = 4, settle_ms: int = 8000,
                      timeout_ms: int = 30000,
                      progress_every: int = 25) -> dict[str, Rendered]:
    """Render a list of URLs, returning {url: Rendered}."""
    if not urls:
        return {}
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise SystemExit(
            "Playwright is not installed. It is part of the fetch pipeline:\n"
            "    pip install -r requirements.txt\n"
            "    playwright install chromium"
        )

    results: dict[str, Rendered] = {}
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(headless=True)
        except Exception as exc:
            raise SystemExit(
                f"Could not start Chromium ({type(exc).__name__}).\n"
                "The browser binary is installed separately from the Python package:\n"
                "    playwright install chromium"
            )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            locale="it-IT",
            viewport={"width": 1366, "height": 900},
            # Several of these companies have expired or self-signed
            # certificates. Chromium blocks those by default while the HTTP
            # pass reaches them over plain http, which would make the browser
            # pass look falsely worse. We are extracting text, not auditing TLS.
            ignore_https_errors=True,
        )
        semaphore = asyncio.Semaphore(concurrency)

        async def guarded(url: str) -> Rendered:
            async with semaphore:
                return await _render_one(context, url, settle_ms, timeout_ms)

        done = 0
        tasks = [asyncio.create_task(guarded(u)) for u in urls]
        for coro in asyncio.as_completed(tasks):
            rendered = await coro
            results[rendered.url] = rendered
            done += 1
            if progress_every and (done % progress_every == 0 or done == len(tasks)):
                print(f"    rendered {done}/{len(tasks)}", flush=True)
        await context.close()
        await browser.close()
    return results
