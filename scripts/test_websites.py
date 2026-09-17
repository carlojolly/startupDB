"""Measure how many company websites are actually reachable.

This answers one question: is the `sito internet` column good enough to feed an
LLM enrichment step? If most homepages are dead or render nothing without
JavaScript, scraping them is not a viable input and we need another approach.

    python scripts/test_websites.py                    # 200 companies, seed 42
    python scripts/test_websites.py --sample-size 500 --concurrency 12

Measurement only — this writes nothing to the database.

Politeness: one request per company homepage, concurrency capped (default 16),
short timeouts, and no crawling beyond the landing page. At this volume that is
a rounding error for any host involved.

Note on content: pages are treated strictly as data. We count characters and
read the <title>; nothing fetched here is ever interpreted as an instruction.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import datetime
import pathlib
import random
import re
import sys
from dataclasses import dataclass, asdict, field
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from courlan import extract_domain
from lxml import html as lxml_html
from lxml.etree import ParserError
from trafilatura import extract

from db import connect, REPO_ROOT

# A real browser UA. Many small sites return 403 to anything that looks like a
# bot, which would show up as a false DEAD. Swap this for an identifying string
# like "StartupMapBot/1.0 (+contact)" if you ever raise the request volume.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# Below this many characters of visible text we call a page THIN: it loaded,
# but there is nothing for an LLM to read. Usually a JS-only shell, a parked
# domain, or a "coming soon" holding page.
THIN_TEXT_CHARS = 500

# Never read more than this from any single response.
MAX_BYTES = 2_000_000

DROP_TAGS = {
    "script", "style", "noscript", "template", "svg", "nav", "footer",
    "aside", "dialog", "form",
}
NOISE_TOKENS = {
    "cookie", "cookies", "cookie-banner", "cookie-modal", "cookie-notice",
    "cookie-consent", "consent-banner", "consent-modal", "gdpr-banner",
    "privacy-banner", "cc-window", "cc-banner", "newsletter-popup",
    "cc_div", "cm_inner",
}
NOISE_PREFIXES = (
    "onetrust", "iubenda", "cookiebot", "cmplz-", "cky-", "cookiefirst",
    "cookieyes", "cookie-setting", "cookiesetting",
)


def _noise_container(element) -> bool:
    attributes = " ".join((element.get("id") or "", element.get("class") or ""))
    tokens = {token for token in re.split(r"[^a-z0-9_-]+", attributes.lower())
              if token}
    return bool(
        tokens & NOISE_TOKENS
        or any(token.startswith(NOISE_PREFIXES) for token in tokens)
    )


def _normalise_text(text: str) -> str:
    return " ".join(text.split())


class TextExtractor:
    """Extract the page's own main content and title.

    A small structural pass removes known non-content containers. Semantic
    <main> content wins when present; Trafilatura handles pages without useful
    landmarks and malformed real-world markup.
    """

    def __init__(self) -> None:
        self.title: str = ""
        self._text: str = ""

    def feed(self, source: str) -> None:
        try:
            document = lxml_html.fromstring(source)
        except (ParserError, ValueError):
            self._text = _normalise_text(extract(
                source, output_format="txt", include_comments=False,
                include_tables=False, deduplicate=True, favor_recall=True,
            ) or "")
            return

        self.title = _normalise_text(" ".join(document.xpath("//title/text()")))
        descriptions = []
        for element in document.xpath("//meta[@content]"):
            key = (element.get("name") or element.get("property") or "").lower()
            if key not in {"description", "og:description", "twitter:description"}:
                continue
            value = _normalise_text(element.get("content") or "")
            if value and value not in descriptions:
                descriptions.append(value)
        for element in list(document.iter()):
            tag = element.tag.lower() if isinstance(element.tag, str) else ""
            role = (element.get("role") or "").lower()
            style = (element.get("style") or "").replace(" ", "").lower()
            hidden = (
                tag not in {"html", "body"}
                and (element.get("hidden") is not None
                     or (element.get("aria-hidden") or "").lower() == "true"
                     or "display:none" in style)
            )
            if (tag in DROP_TAGS or role in {"navigation", "contentinfo", "dialog"}
                    or hidden or _noise_container(element)):
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)

        main_nodes = document.xpath("//main | //*[@role='main']")
        main_text = _normalise_text(" ".join(
            node.text_content() for node in main_nodes
        ))
        cleaned_html = lxml_html.tostring(document, encoding="unicode")
        fallback = _normalise_text(extract(
            cleaned_html, output_format="txt", include_comments=False,
            include_tables=False, deduplicate=True, favor_recall=True,
        ) or "")
        self._text = main_text if len(main_text) >= THIN_TEXT_CHARS else fallback
        if len(self._text) < THIN_TEXT_CHARS and descriptions:
            # Password/coming-soon shells sometimes have no visible body while
            # retaining a first-party description of the actual business.
            self._text = _normalise_text(" ".join(
                [self.title, *descriptions, self._text]
            ))

    @property
    def text(self) -> str:
        return self._text


def registrable_domain(url: str) -> str:
    """Return the registrable domain, falling back to the normalized host."""
    domain = extract_domain(url)
    if domain:
        return domain.lower().rstrip(".")
    return (urlsplit(url).hostname or "").lower().rstrip(".")


def is_same_site(requested_url: str, final_url: str) -> bool:
    """Allow root/child-domain hops, but reject other domains and siblings."""
    requested = registrable_domain(requested_url)
    final = registrable_domain(final_url)
    if not requested or requested != final:
        return False

    requested_host = (urlsplit(requested_url).hostname or "").lower().rstrip(".")
    final_host = (urlsplit(final_url).hostname or "").lower().rstrip(".")
    requested_host = requested_host.removeprefix("www.")
    final_host = final_host.removeprefix("www.")
    return (
        requested_host == final_host
        or requested_host == requested
        or final_host == requested
    )


def _host_brands(url: str) -> set[str]:
    """Return distinctive hostname labels suitable for migration checks."""
    generic = {"www", "com", "net", "org", "cloud", "store", "app", "dev",
               "it", "eu", "io", "ai", "co", "launch", "shop"}
    return {
        "".join(character for character in label if character.isalnum())
        for label in (urlsplit(url).hostname or "").lower().split(".")
        if len(label) >= 5 and label not in generic
    }


def page_identifies_company(codice_fiscale: str, source: str, *,
                            company_name: str = "", requested_url: str = "",
                            final_url: str = "") -> bool:
    """Verify that a cross-domain destination still belongs to the company.

    The fiscal identifier remains the strongest signal. An exact normalized
    registered name on the destination is also strong evidence. Two narrow
    domain migration signals recover common registry staleness without
    accepting an arbitrary destination: the old and new host keep the same
    distinctive brand, or the new host begins with the company's distinctive
    name token.
    """
    expected = "".join(character for character in codice_fiscale.lower()
                       if character.isalnum())
    document = "".join(character for character in source.lower()
                       if character.isalnum())
    if len(expected) >= 8 and expected in document:
        return True

    normalized_name = "".join(
        character for character in company_name.lower()
        if character.isalnum()
    )
    if len(normalized_name) >= 10 and normalized_name in document:
        return True

    old_brands = _host_brands(requested_url)
    new_brands = _host_brands(final_url)
    if old_brands & new_brands:
        return True

    legal_words = {
        "societa", "responsabilita", "limitata", "semplificata", "benefit",
        "startup", "start", "costituita", "norma", "srl", "srls", "spa",
        "group", "holding", "italia", "italy", "innovation", "innovazione",
        "digital", "technology", "technologies",
    }
    name_tokens = [
        token for token in re.findall(r"[a-z0-9]+", company_name.lower())
        if len(token) >= 5 and token not in legal_words
    ]
    return any(
        brand == token or brand.startswith(token)
        for token in name_tokens for brand in new_brands
    )


ERROR_PAGE_TITLE_MARKERS = (
    "404 not found", "error 404", "database error", "ssl error",
    "reconnect your domain", "sito non installato", "dns resolution error",
    "web page blocked",
)
ERROR_PAGE_TEXT_MARKERS = (
    "cloudflare is currently unable to resolve your requested domain",
    "the domain is still pending setup",
)


def looks_like_error_page(title: str, text: str) -> bool:
    """Recognize infrastructure pages that can otherwise look text-rich."""
    normalized_title = _normalise_text(title).lower()
    normalized_text = _normalise_text(text[:2_000]).lower()
    return (
        any(marker in normalized_title for marker in ERROR_PAGE_TITLE_MARKERS)
        or any(marker in normalized_text for marker in ERROR_PAGE_TEXT_MARKERS)
    )


LINK_PRIORITIES = (
    (4, ("prodott", "product", "serviz", "service", "solution", "soluzion",
         "technology", "tecnologia", "platform", "piattaforma")),
    (3, ("chi-siamo", "chisiamo", "about", "azienda", "company",
         "cosa-facciamo", "what-we-do")),
)
LINK_REJECT = (
    "privacy", "cookie", "contact", "contatt", "login", "signin", "signup",
    "account", "cart", "checkout", "terms", "legal", "blog", "news",
    "press", "career", "lavora", "facebook", "instagram", "linkedin",
)


def promising_internal_links(source: str, base_url: str,
                             limit: int = 3) -> list[str]:
    """Find a few same-site pages likely to explain the company or offering."""
    try:
        document = lxml_html.fromstring(source)
    except (ParserError, ValueError):
        return []

    ranked: dict[str, int] = {}
    for anchor in document.xpath("//a[@href]"):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        parts = urlsplit(absolute)
        if parts.scheme not in {"http", "https"} or not is_same_site(base_url, absolute):
            continue
        clean_url = urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", ""))
        if clean_url.rstrip("/") == base_url.rstrip("/"):
            continue
        clue = " ".join((parts.path, anchor.text_content())).lower()
        if any(word in clue for word in LINK_REJECT):
            continue
        score = max((priority for priority, words in LINK_PRIORITIES
                     if any(word in clue for word in words)), default=0)
        if score:
            ranked[clean_url] = max(score, ranked.get(clean_url, 0))
    return [url for url, _score in sorted(
        ranked.items(), key=lambda item: (-item[1], len(item[0]), item[0])
    )[:limit]]


@dataclass
class Result:
    codice_fiscale: str
    denominazione: str
    url_tried: str
    final_url: str = ""
    bucket: str = ""          # OK | THIN | DEAD
    reason: str = ""          # short machine-ish label
    status_code: int | None = None
    text_chars: int = 0
    title: str = ""
    scheme_used: str = ""     # https | http (which one succeeded)
    redirected: bool = False
    elapsed_ms: int = 0
    detail: str = ""          # exception text, truncated
    # Populated only when check_one(..., keep_text=True). Off by default so a
    # reachability sweep does not hold hundreds of pages in memory, and so the
    # results CSV stays small. scripts/tag_companies.py opts in.
    page_text: str = ""
    followup_urls: list[str] = field(default_factory=list)


def classify_exception(exc: BaseException) -> str:
    """Turn an httpx exception into a short, groupable reason."""
    match exc:
        case httpx.ConnectTimeout() | httpx.ReadTimeout() | httpx.PoolTimeout():
            return "timeout"
        case httpx.ConnectError():
            text = str(exc).lower()
            if "name or service not known" in text or "nodename nor servname" in text \
                    or "temporary failure in name resolution" in text or "getaddrinfo" in text:
                return "dns_failure"
            if "connection refused" in text:
                return "connection_refused"
            if "certificate" in text or "ssl" in text or "tls" in text:
                return "tls_error"
            return "connection_error"
        case httpx.TooManyRedirects():
            return "too_many_redirects"
        case httpx.RemoteProtocolError() | httpx.LocalProtocolError():
            return "protocol_error"
        case httpx.UnsupportedProtocol() | httpx.InvalidURL():
            return "bad_url"
        case _:
            name = type(exc).__name__
            text = str(exc).lower()
            if "certificate" in text or "ssl" in text:
                return "tls_error"
            return f"other:{name}"


async def fetch_once(client: httpx.AsyncClient, url: str) -> tuple[httpx.Response | None, str, bytes]:
    """One attempt. Returns (response, reason, body_bytes)."""
    try:
        async with client.stream("GET", url) as response:
            body = b""
            async for chunk in response.aiter_bytes():
                body += chunk
                if len(body) >= MAX_BYTES:
                    break
            return response, "", body
    except Exception as exc:  # noqa: BLE001 - we deliberately group everything
        return None, classify_exception(exc), b""


def decode(body: bytes, response: httpx.Response) -> str:
    """Best-effort decode using the response's own charset, then UTF-8."""
    encoding = response.charset_encoding or "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return body.decode("utf-8", errors="replace")


async def check_one(client: httpx.AsyncClient, sem: asyncio.Semaphore,
                    cf: str, name: str, url: str,
                    keep_text: bool = False) -> Result:
    """Try https, fall back to http, then classify."""
    result = Result(codice_fiscale=cf, denominazione=name, url_tried=url)
    started = datetime.datetime.now()

    # The database already normalises everything to https://. If that fails for
    # a network/TLS reason (not an HTTP error code), retry the same host over
    # plain http — plenty of small Italian business sites are http-only or have
    # a broken certificate but are perfectly alive.
    attempts = [("https", url)]
    if url.startswith("https://"):
        attempts.append(("http", "http://" + url[len("https://"):]))

    last_reason = ""
    async with sem:
        for scheme, candidate in attempts:
            response, reason, body = await fetch_once(client, candidate)
            if response is None:
                last_reason = reason
                continue

            result.scheme_used = scheme
            result.status_code = response.status_code
            result.final_url = str(response.url)
            result.redirected = str(response.url).rstrip("/") != candidate.rstrip("/")

            if response.status_code >= 400:
                # An HTTP error is a definitive answer from a live server, so
                # there is no point retrying it over http.
                result.bucket = "DEAD"
                result.reason = f"http_{response.status_code}"
                break

            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type and not (content_type.startswith("text/")
                                     or content_type in ("application/xhtml+xml", "application/xml")):
                result.bucket = "THIN"
                result.reason = f"not_html:{content_type}"
                break

            source = decode(body, response)
            offsite_redirect = not is_same_site(candidate, result.final_url)
            if offsite_redirect:
                result.detail = (
                    f"{registrable_domain(candidate)} -> "
                    f"{registrable_domain(result.final_url)}"
                )
                if not page_identifies_company(
                    cf, source, company_name=name, requested_url=candidate,
                    final_url=result.final_url,
                ):
                    result.bucket = "DEAD"
                    result.reason = "offsite_redirect"
                    break

            parser = TextExtractor()
            try:
                parser.feed(source)
            except Exception as exc:  # malformed markup
                result.detail = f"parse:{type(exc).__name__}"
            result.text_chars = len(parser.text)
            result.title = " ".join(parser.title.split())[:120]
            if looks_like_error_page(result.title, parser.text):
                result.bucket = "DEAD"
                result.reason = "error_page"
                result.text_chars = 0
                result.page_text = ""
                break
            if keep_text:
                result.page_text = parser.text
                result.followup_urls = promising_internal_links(
                    source, result.final_url or candidate
                )

            if result.text_chars >= THIN_TEXT_CHARS:
                result.bucket = "OK"
                result.reason = (
                    "verified_offsite_redirect" if offsite_redirect else "ok"
                )
            else:
                result.bucket = "THIN"
                result.reason = (
                    "verified_offsite_redirect_little_text"
                    if offsite_redirect else "little_text"
                )
            break
        else:
            result.bucket = "DEAD"
            result.reason = last_reason or "unknown"

    result.elapsed_ms = int((datetime.datetime.now() - started).total_seconds() * 1000)
    return result


def load_sample(sample_size: int, seed: int) -> tuple[list[tuple[str, str, str]], int]:
    """Reproducible random sample of companies that have a usable website.

    Sampling happens in Python from a deterministically ordered query rather
    than with SQL's setseed(), so the same seed gives the same sample
    regardless of how Postgres plans the query.
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT codice_fiscale, denominazione, sito_internet_url
            FROM companies_current
            WHERE sito_internet_url IS NOT NULL
            ORDER BY codice_fiscale
        """)
        rows = cur.fetchall()
    if not rows:
        sys.exit("No companies with a website found. Has the import run?")
    rng = random.Random(seed)
    n = min(sample_size, len(rows))
    return rng.sample(rows, n), len(rows)


async def run(sample: list[tuple[str, str, str]], concurrency: int,
              timeout: float) -> list[Result]:
    limits = httpx.Limits(max_connections=concurrency,
                          max_keepalive_connections=concurrency)
    timeouts = httpx.Timeout(timeout, connect=min(timeout, 5.0))
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        follow_redirects=True,
        max_redirects=5,
        timeout=timeouts,
        limits=limits,
        headers={"User-Agent": USER_AGENT,
                 "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                 "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"},
        verify=True,
    ) as client:
        tasks = [check_one(client, sem, cf, name, url) for cf, name, url in sample]
        results: list[Result] = []
        for index, coro in enumerate(asyncio.as_completed(tasks), start=1):
            results.append(await coro)
            if index % 25 == 0 or index == len(tasks):
                print(f"  {index}/{len(tasks)} checked", flush=True)
    return results


def report(results: list[Result], total_eligible: int,
           seed: int, examples: int) -> None:
    n = len(results)
    buckets = collections.Counter(r.bucket for r in results)

    print("\n" + "=" * 64)
    print(f"SAMPLE: {n} of {total_eligible} companies with a usable website "
          f"(seed={seed})")
    print("=" * 64)
    for bucket in ("OK", "THIN", "DEAD"):
        count = buckets.get(bucket, 0)
        bar = "#" * round(40 * count / n) if n else ""
        print(f"  {bucket:5} {count:4}  {100*count/n:5.1f}%  {bar}")

    print("\nMost common reasons:")
    for reason, count in collections.Counter(r.reason for r in results).most_common(12):
        print(f"  {count:4}  {100*count/n:5.1f}%  {reason}")

    dead = [r for r in results if r.bucket == "DEAD"]
    if dead:
        print("\nDEAD breakdown:")
        for reason, count in collections.Counter(r.reason for r in dead).most_common():
            print(f"  {count:4}  {100*count/len(dead):5.1f}% of dead  {reason}")

    ok = [r for r in results if r.bucket == "OK"]
    if ok:
        chars = sorted(r.text_chars for r in ok)
        print(f"\nText extracted from OK pages (chars): "
              f"min={chars[0]}  median={chars[len(chars)//2]}  max={chars[-1]}")
    http_only = [r for r in results if r.scheme_used == "http"]
    print(f"Reachable only over plain http (https failed): {len(http_only)}")
    print(f"Followed a redirect: {sum(1 for r in results if r.redirected)}")

    for bucket in ("OK", "THIN", "DEAD"):
        rows = [r for r in results if r.bucket == bucket][:examples]
        if not rows:
            continue
        print(f"\n--- {examples} example {bucket} results ---")
        for r in rows:
            extra = (f"{r.text_chars:6} chars" if bucket != "DEAD"
                     else f"{r.reason:20}")
            print(f"  {extra}  {r.denominazione[:30]:30}  {r.url_tried[:44]}")
            if bucket == "THIN" and r.title:
                print(f"          title: {r.title[:70]}")


def save_csv(results: list[Result], out_path: pathlib.Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # page_text is deliberately excluded: it would balloon the file and it is
    # not what this measurement is about.
    fields = [f for f in asdict(results[0]).keys()
              if f not in {"page_text", "followup_urls"}]
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in sorted(results, key=lambda x: (x.bucket, -x.text_chars)):
            row = asdict(r)
            row.pop("page_text", None)
            row.pop("followup_urls", None)
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--concurrency", type=int, default=16,
                        help="Max simultaneous requests (default 16). Keep it modest.")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--examples", type=int, default=10,
                        help="How many example rows to print per bucket")
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args()

    sample, total_eligible = load_sample(args.sample_size, args.seed)
    print(f"Checking {len(sample)} websites "
          f"(concurrency={args.concurrency}, timeout={args.timeout}s) ...")

    results = asyncio.run(run(sample, args.concurrency, args.timeout))

    out = args.out or (REPO_ROOT / "data" /
                       f"website_check_{datetime.date.today():%Y-%m-%d}_seed{args.seed}.csv")
    save_csv(results, out)
    report(results, total_eligible, args.seed, args.examples)
    try:
        shown = out.relative_to(REPO_ROOT)
    except ValueError:      # --out pointed somewhere outside the repo
        shown = out
    print(f"\nFull per-URL results: {shown}  ({len(results)} rows)")


if __name__ == "__main__":
    main()
