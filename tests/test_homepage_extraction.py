"""Tests for homepage content extraction and redirect ownership."""
from __future__ import annotations

import asyncio
import pathlib
import sys

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from test_websites import TextExtractor, check_one, is_same_site  # noqa: E402


def test_extractor_removes_navigation_cookie_and_footer_boilerplate():
    extractor = TextExtractor()
    extractor.feed("""
        <html><head><title>Useful Company</title></head><body>
          <nav>Products About Contact Products About Contact</nav>
          <div class="cookie-banner">Accept every cookie Privacy Settings</div>
          <main><h1>Industrial water recovery</h1>
            <p>We build mobile filtration systems for factories.</p></main>
          <footer>Privacy Legal Social Contact</footer>
        </body></html>
    """)

    assert extractor.title == "Useful Company"
    assert "Industrial water recovery" in extractor.text
    assert "mobile filtration systems" in extractor.text
    assert "Accept every cookie" not in extractor.text
    assert "Products About Contact" not in extractor.text
    assert "Privacy Legal Social" not in extractor.text


def test_redirect_domain_comparison_allows_subdomains_but_not_other_sites():
    assert is_same_site("https://example.it", "https://www.example.it/about")
    assert is_same_site("https://www.example.co.uk", "https://shop.example.co.uk")
    assert not is_same_site(
        "https://sites.google.com/view/company", "https://accounts.google.com/login"
    )
    assert not is_same_site("https://g-lab.cloud", "https://goo.su/example")


def test_offsite_redirect_is_dead_and_its_text_is_discarded():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "g-lab.cloud":
            return httpx.Response(302, headers={"location": "https://goo.su/video"})
        return httpx.Response(
            200,
            text="<main>" + "YouTube interface text " * 100 + "</main>",
        )

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=True,
        ) as client:
            return await check_one(
                client, asyncio.Semaphore(1), "cf", "G-LAB",
                "https://g-lab.cloud", keep_text=True,
            )

    result = asyncio.run(exercise())
    assert result.bucket == "DEAD"
    assert result.reason == "offsite_redirect"
    assert result.detail == "g-lab.cloud -> goo.su"
    assert result.page_text == ""


def test_offsite_redirect_is_accepted_when_page_has_exact_fiscal_code():
    codice_fiscale = "02744830205"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.chillbit.it":
            return httpx.Response(302, headers={"location": "https://chillb.it"})
        return httpx.Response(
            200,
            text=(
                "<main><h1>Software integration</h1>"
                + "We build custom business applications. " * 20
                + "</main><footer>Partita IVA 02744830205</footer>"
            ),
        )

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=True,
        ) as client:
            return await check_one(
                client, asyncio.Semaphore(1), codice_fiscale, "CHILL BIT",
                "https://www.chillbit.it", keep_text=True,
            )

    result = asyncio.run(exercise())
    assert result.bucket == "OK"
    assert result.reason == "verified_offsite_redirect"
    assert result.detail == "chillbit.it -> chillb.it"
    assert "custom business applications" in result.page_text
