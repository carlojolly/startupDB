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
import sys
from dataclasses import dataclass, asdict
from html.parser import HTMLParser

import httpx

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

SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head"}


class TextExtractor(HTMLParser):
    """Pull visible text and the <title> out of an HTML document.

    Uses the standard library rather than BeautifulSoup/lxml so the repo keeps
    a small, reliably-installable dependency set.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self.title: str = ""
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        # <head> is in SKIP_TAGS, so title text is captured above but not
        # counted toward the visible-text total.
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.chunks.append(text)

    @property
    def text(self) -> str:
        return " ".join(self.chunks)


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

            parser = TextExtractor()
            try:
                parser.feed(decode(body, response))
            except Exception as exc:  # malformed markup
                result.detail = f"parse:{type(exc).__name__}"
            result.text_chars = len(parser.text)
            result.title = " ".join(parser.title.split())[:120]
            if keep_text:
                result.page_text = parser.text

            if result.text_chars >= THIN_TEXT_CHARS:
                result.bucket, result.reason = "OK", "ok"
            else:
                result.bucket, result.reason = "THIN", "little_text"
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
    fields = [f for f in asdict(results[0]).keys() if f != "page_text"]
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in sorted(results, key=lambda x: (x.bucket, -x.text_chars)):
            row = asdict(r)
            row.pop("page_text", None)
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
