"""Tests for homepage content extraction and redirect ownership."""
from __future__ import annotations

import asyncio
import pathlib
import sys

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from test_websites import (  # noqa: E402
    TextExtractor, check_one, is_same_site, promising_internal_links,
)


def test_extractor_removes_navigation_cookie_and_footer_boilerplate():
    extractor = TextExtractor()
    extractor.feed("""
        <html><head><title>Useful Company</title></head><body>
          <nav>Products About Contact Products About Contact</nav>
          <div class="cookie-banner">Accept every cookie Privacy Settings</div>
          <div id="cookieSetting" class="cookie-setting">
            Necessary Analytics Marketing Personalisation
          </div>
          <main><h1>Industrial water recovery</h1>
            <p>We build mobile filtration systems for factories.</p></main>
          <footer>Privacy Legal Social Contact</footer>
        </body></html>
    """)

    assert extractor.title == "Useful Company"
    assert "Industrial water recovery" in extractor.text
    assert "mobile filtration systems" in extractor.text
    assert "Accept every cookie" not in extractor.text
    assert "Necessary Analytics Marketing" not in extractor.text
    assert "Products About Contact" not in extractor.text
    assert "Privacy Legal Social" not in extractor.text


def test_extractor_uses_first_party_description_when_visible_page_is_empty():
    extractor = TextExtractor()
    extractor.feed("""
        <html><head>
          <title>Convivium — Ecommerce contadino</title>
          <meta property="og:description"
                content="Frutta, verdura e prodotti di produttori locali, dal campo alla tavola.">
          <meta name="description"
                content="Frutta, verdura e prodotti di produttori locali, dal campo alla tavola.">
        </head><body><form>Password</form></body></html>
    """)

    assert extractor.text == (
        "Convivium — Ecommerce contadino Frutta, verdura e prodotti di "
        "produttori locali, dal campo alla tavola."
    )


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


def test_offsite_redirect_accepts_same_brand_domain_migration():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "steelgrim.ddns.net":
            return httpx.Response(302, headers={"location": "https://steelgrim.com"})
        return httpx.Response(200, text="<main>" + "Steel products. " * 50 + "</main>")

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=True,
        ) as client:
            return await check_one(
                client, asyncio.Semaphore(1), "02777080397", "STEELGRIM S.R.L.",
                "https://steelgrim.ddns.net", keep_text=True,
            )

    result = asyncio.run(exercise())
    assert result.bucket == "OK"
    assert result.reason == "verified_offsite_redirect"


def test_offsite_redirect_accepts_same_brand_across_tlds_and_subdomain():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "lacrimedicoccodrillo.store":
            return httpx.Response(
                302,
                headers={"location": "https://launch.lacrimedicoccodrillo.eu/lp"},
            )
        return httpx.Response(200, text="<main>" + "Circular products. " * 40 + "</main>")

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=True,
        ) as client:
            return await check_one(
                client, asyncio.Semaphore(1), "01917880336", "CALLEGARI SRL",
                "https://lacrimedicoccodrillo.store", keep_text=True,
            )

    result = asyncio.run(exercise())
    assert result.bucket == "OK"
    assert result.reason == "verified_offsite_redirect"


def test_offsite_redirect_accepts_company_brand_in_new_domain():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "execstop.com":
            return httpx.Response(302, headers={"location": "https://bizzynow.com"})
        return httpx.Response(200, text="<main>" + "Business software. " * 40 + "</main>")

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=True,
        ) as client:
            return await check_one(
                client, asyncio.Semaphore(1), "02608010977", "BIZZY S.R.L.",
                "https://execstop.com", keep_text=True,
            )

    result = asyncio.run(exercise())
    assert result.bucket == "OK"
    assert result.reason == "verified_offsite_redirect"


def test_offsite_redirect_accepts_exact_registered_name_on_destination():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.ia-project.com":
            return httpx.Response(301, headers={"location": "https://www.iatech.it"})
        return httpx.Response(
            200,
            text=("<main>Augmented-reality social application. " * 30
                  + "</main><footer>iA technologies Srl</footer>"),
        )

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=True,
        ) as client:
            return await check_one(
                client, asyncio.Semaphore(1), "01237730864",
                "IA TECHNOLOGIES S.R.L.", "https://www.ia-project.com",
                keep_text=True,
            )

    result = asyncio.run(exercise())
    assert result.bucket == "OK"
    assert result.reason == "verified_offsite_redirect"
    assert "Augmented-reality" in result.page_text


def test_promising_internal_links_are_same_site_ranked_and_limited():
    links = promising_internal_links("""
      <a href="/contact">Contact</a>
      <a href="https://other.example/products">Other products</a>
      <a href="/about-us?tracking=1">About us</a>
      <a href="/technology#top">Technology</a>
      <a href="/products">Products</a>
      <a href="/services">Services</a>
    """, "https://example.it")

    assert links == [
        "https://example.it/products",
        "https://example.it/services",
        "https://example.it/technology",
    ]


def test_text_rich_cloudflare_dns_error_is_dead():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "<title>DNS resolution error | example.it | Cloudflare</title>"
                "<main>Cloudflare is currently unable to resolve your requested "
                "domain. " + "Troubleshooting information. " * 40 + "</main>"
            ),
        )

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=True,
        ) as client:
            return await check_one(
                client, asyncio.Semaphore(1), "12345678901", "EXAMPLE",
                "https://example.it", keep_text=True,
            )

    result = asyncio.run(exercise())
    assert result.bucket == "DEAD"
    assert result.reason == "error_page"
    assert result.text_chars == 0
    assert result.page_text == ""
