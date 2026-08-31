"""Measurement only: does running JavaScript rescue the THIN homepages?

scripts/test_websites.py found that ~17% of company homepages load but yield
almost no text — JS-rendered shells that plain HTTP cannot read. This script
re-fetches those pages in a real browser and reports, per page:

    chars before (plain HTTP)  vs  chars after (browser)  and how long each took

It changes nothing: no database writes, no edits to the fetch pipeline.

    python scripts/probe_playwright.py --run-id 2

Method note: the browser's rendered HTML is passed through the SAME
TextExtractor that test_websites.py uses. Comparing that parser's output to
Playwright's own innerText would compare two different extractors and make the
before/after numbers meaningless.

Pages are visited sequentially so the per-page timings are not distorted by
contention with each other.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import re
import time

import httpx

from db import connect, REPO_ROOT
from test_websites import TextExtractor, USER_AGENT, decode

_BUCKET = re.compile(r"fetch=(\w+)")
_CHARS = re.compile(r"\|\s*(\d+) chars")


def load_thin(run_id: int) -> list[tuple[str, str, str, int]]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT c.codice_fiscale, c.denominazione, c.sito_internet_url, max(t.evidence)
            FROM company_tags t JOIN companies_current c USING (codice_fiscale)
            WHERE t.run_id = %s GROUP BY 1,2,3 ORDER BY c.denominazione
        """, (run_id,))
        out = []
        for cf, name, url, ev in cur.fetchall():
            bucket = _BUCKET.search(ev or "")
            chars = _CHARS.search(ev or "")
            if bucket and bucket.group(1) == "THIN":
                out.append((cf, name, url, int(chars.group(1)) if chars else 0))
    return out


def candidates(url: str) -> list[str]:
    """https first, then the same host over plain http.

    This mirrors check_one() in test_websites.py. Several of these companies
    have expired or misconfigured certificates and are only reachable over
    http — without the fallback both columns read 0 and the comparison is
    silently wrong.
    """
    urls = [url]
    if url.startswith("https://"):
        urls.append("http://" + url[len("https://"):])
    return urls


def fetch_plain(url: str, timeout: float) -> tuple[int, float, str]:
    """Re-run the plain-HTTP fetch now, so 'before' is measured in the same
    conditions as 'after' rather than read from a stale database row."""
    started = time.perf_counter()
    last = ""
    for candidate in candidates(url):
        try:
            with httpx.Client(follow_redirects=True, timeout=timeout,
                              headers={"User-Agent": USER_AGENT}) as client:
                response = client.get(candidate)
                parser = TextExtractor()
                parser.feed(decode(response.read(), response))
                scheme = "" if candidate.startswith("https") else "via-http"
                return len(parser.text), (time.perf_counter() - started) * 1000, scheme
        except Exception as exc:  # noqa: BLE001
            last = type(exc).__name__
    return 0, (time.perf_counter() - started) * 1000, last


def fetch_rendered(page, url: str, settle_ms: int) -> tuple[int, float, str, str]:
    started = time.perf_counter()
    last = ""
    for candidate in candidates(url):
        note = "" if candidate.startswith("https") else "via-http"
        try:
            page.goto(candidate, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=settle_ms)
            except Exception:
                note = (note + " no-networkidle").strip()  # still polling; take what rendered
            html = page.content()
            title = (page.title() or "")[:70]
            parser = TextExtractor()
            parser.feed(html)
            return len(parser.text), (time.perf_counter() - started) * 1000, note, title
        except Exception as exc:  # noqa: BLE001
            last = type(exc).__name__
    return 0, (time.perf_counter() - started) * 1000, last, ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=8.0, help="plain-HTTP timeout (s)")
    ap.add_argument("--settle-ms", type=int, default=8000,
                    help="how long to wait for network idle after DOM load")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "Playwright is not installed. It is an optional dependency used only "
            "by this probe:\n"
            "    pip install playwright && playwright install chromium\n"
            "(downloads a ~95MB Chromium binary)"
        )

    targets = load_thin(args.run_id)
    if not targets:
        raise SystemExit(f"No THIN companies found in tag_run {args.run_id}.")
    print(f"Re-fetching {len(targets)} THIN homepages from tag_run {args.run_id} "
          f"in a real browser (sequential, for clean timings)\n")

    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="it-IT",
            viewport={"width": 1366, "height": 900},
            # Several of these companies have expired or self-signed certs.
            # Chromium blocks those by default while the httpx path reaches
            # them over plain http, which would make the browser column look
            # falsely worse. We are measuring whether content exists, not
            # auditing TLS, so accept them here. Do NOT copy this into the
            # production pipeline without thinking about it.
            ignore_https_errors=True,
        )
        page = context.new_page()
        for i, (cf, name, url, stored) in enumerate(targets, 1):
            before, before_ms, before_err = fetch_plain(url, args.timeout)
            after, after_ms, note, title = fetch_rendered(page, url, args.settle_ms)
            gain = after - before
            flag = "RESCUED" if before < 500 <= after else (
                   "improved" if gain > 200 else "no change")
            rows.append(dict(codice_fiscale=cf, denominazione=name, url=url,
                             chars_stored_run2=stored, chars_http=before,
                             chars_browser=after, gain=gain,
                             http_ms=round(before_ms), browser_ms=round(after_ms),
                             outcome=flag, note=note or before_err, title=title))
            print(f"{i:3}. {name[:34]:34} {before:5} -> {after:6} chars "
                  f"({before_ms:5.0f}ms -> {after_ms:6.0f}ms)  {flag}"
                  + (f"  [{note}]" if note else ""))
        context.close()
        browser.close()

    out = args.out or (REPO_ROOT / "data" /
                       f"playwright_probe_run{args.run_id}_{datetime.date.today():%Y-%m-%d}.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print("\n" + "=" * 74)
    rescued = [r for r in rows if r["outcome"] == "RESCUED"]
    improved = [r for r in rows if r["outcome"] == "improved"]
    nochange = [r for r in rows if r["outcome"] == "no change"]
    print(f"RESCUED (crossed the 500-char usable threshold): {len(rescued)}/{len(rows)}")
    print(f"improved but still under 500 chars             : {len(improved)}")
    print(f"no meaningful change                           : {len(nochange)}")
    http_ms = sorted(r["http_ms"] for r in rows)
    br_ms = sorted(r["browser_ms"] for r in rows)
    print(f"\nmedian time: plain HTTP {http_ms[len(http_ms)//2]}ms   "
          f"browser {br_ms[len(br_ms)//2]}ms   "
          f"({br_ms[len(br_ms)//2]/max(http_ms[len(http_ms)//2],1):.1f}x slower)")
    print(f"total browser wall-clock: {sum(r['browser_ms'] for r in rows)/1000:.1f}s "
          f"for {len(rows)} pages")
    if rescued:
        print("\nrescued pages:")
        for r in sorted(rescued, key=lambda x: -x["chars_browser"]):
            print(f"   {r['chars_browser']:6} chars  {r['denominazione'][:32]:32} {r['title'][:38]}")
    print(f"\n{out}")


if __name__ == "__main__":
    main()
