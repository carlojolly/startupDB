"""End-to-end checks for the dashboard in web/.

These drive the real app over HTTP and assert the behaviours the dashboard
exists to guarantee: that VC relevance ranks high -> medium -> low -> unclear,
that stronger homepage evidence wins inside a level, that `unclear` is never
rendered as if it were a tag value, and that the sourcing-signal disclaimer is
on the page.

Skipped unless a dev server is already listening, so `pytest` stays green with
nothing running. To include them:

    cd web && npm run dev          # in one terminal
    pytest tests/test_dashboard.py # in another
"""
from __future__ import annotations

import html
import pathlib
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from db import get_database_url  # noqa: E402

BASE = "http://localhost:3000"
RELEVANCE = ["high", "medium", "low", "unclear"]
EVIDENCE = ["OK", "THIN", "DEAD"]


def _server_is_up() -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", 3000)) == 0


pytestmark = pytest.mark.skipif(
    not _server_is_up(), reason="dashboard not running; start it with `cd web && npm run dev`"
)


def fetch(path: str) -> str:
    with urllib.request.urlopen(BASE + path, timeout=30) as response:
        return response.read().decode()


def listing(**params: str) -> str:
    return fetch("/?" + urllib.parse.urlencode(params) if params else "/")


def text_of(markup: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", markup)))


def signals(markup: str) -> list[tuple[str | None, str | None]]:
    """The (VC relevance, homepage evidence) pair of each row, in page order."""
    pairs = []
    for row in re.findall(r"<article\b.*?</article>", markup, re.S):
        found = re.search(r"Homepage evidence: (OK|THIN|DEAD)", text_of(row))
        evidence = found.group(1) if found else None
        if "Not assessed" in text_of(row):
            relevance = "unclear"
        else:
            relevance = next(
                (word.lower() for word in ("High", "Medium", "Low")
                 if re.search(rf"\b{word} VC relevance", row)),
                None,
            )
        pairs.append((relevance, evidence))
    return pairs


def names(markup: str) -> list[str]:
    return [html.unescape(name) for name in re.findall(r"<h3[^>]*>([^<]+)</h3>", markup)]


def result_count(markup: str) -> int:
    # Anchored on the results header specifically: the masthead above it also
    # quotes a company count, which is the unfiltered total.
    found = re.search(r"([\d,]+) (?:companies|company) · sorted by", text_of(markup))
    assert found, "results header not found"
    return int(found.group(1).replace(",", ""))


# --- ranking ---------------------------------------------------------------

@pytest.mark.parametrize("region", ["Lombardia", "Campania", "Molise", "Sardegna"])
def test_default_sort_never_breaks_the_relevance_order(region):
    order = [pair[0] for pair in signals(listing(region=region))]
    assert order == sorted(order, key=RELEVANCE.index)


@pytest.mark.parametrize("region", ["Lombardia", "Lazio", "Emilia-Romagna"])
def test_stronger_homepage_evidence_wins_inside_a_relevance_level(region):
    rows = signals(listing(region=region))
    keys = [(RELEVANCE.index(r), EVIDENCE.index(e)) for r, e in rows]
    assert keys == sorted(keys)


def test_evidence_sort_runs_ok_then_thin_then_dead():
    order = [pair[1] for pair in signals(listing(sort="evidence", region="Molise"))]
    assert order == sorted(order, key=EVIDENCE.index)


def test_name_sort_matches_the_databases_own_collation():
    import psycopg

    with psycopg.connect(get_database_url()) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT c.denominazione FROM companies_current c
            JOIN (SELECT DISTINCT codice_fiscale FROM current_company_tags) t
              USING (codice_fiscale)
            ORDER BY c.denominazione LIMIT 50
        """)
        expected = [row[0] for row in cur.fetchall()]

    assert names(listing(sort="name")) == expected


# --- filtering and search --------------------------------------------------

def test_unfiltered_list_covers_every_tagged_company():
    assert result_count(listing()) == 9620


@pytest.mark.parametrize(
    "params",
    [
        {"sector": "health_life_sciences"},
        {"quality": "DEAD"},
        {"customer": "b2g"},
        {"vc": "high"},
        {"product": "marketplace"},
    ],
)
def test_each_filter_narrows_the_set(params):
    assert 0 < result_count(listing(**params)) < 9620


def test_filters_combine():
    narrow = result_count(listing(sector="health_life_sciences", vc="high", quality="OK"))
    assert narrow < result_count(listing(sector="health_life_sciences"))
    assert narrow < result_count(listing(vc="high"))


def test_search_returns_only_matching_names():
    matches = names(listing(q="robot"))
    assert matches and all("ROBOT" in name.upper() for name in matches)


def test_search_with_no_match_shows_an_empty_state():
    page = listing(q="zzzznotacompany")
    assert result_count(page) == 0
    assert "No companies match these filters" in text_of(page)


def test_pages_do_not_overlap():
    first = names(listing(sort="name"))
    second = names(listing(sort="name", page="2"))
    assert len(first) == 50
    assert not set(first) & set(second)


# --- how the tags are presented -------------------------------------------

def test_unclear_is_never_rendered_as_a_tag_value():
    page = text_of(listing(sector="health_life_sciences", sort="name")).lower()
    assert " unclear " not in page


def test_multi_value_tags_keep_their_stored_order():
    # ALPHRA: product_type is professional_services|software_product.
    page = text_of(fetch("/company/01002810941"))
    assert page.index("Professional services") < page.index("Software product")
    assert "the first is the primary one" in page


def test_detail_view_states_that_relevance_is_not_a_recommendation():
    assert "not an investment recommendation" in text_of(fetch("/company/01002810941"))


def test_a_dead_homepage_is_explained_rather_than_guessed_at():
    page = text_of(fetch("/company/00977110949"))
    assert "Homepage could not be reached" in page
    assert page.count("Not classified") >= 4


def test_unknown_company_is_a_404():
    with pytest.raises(urllib.error.HTTPError) as caught:
        fetch("/company/00000000000")
    assert caught.value.code == 404
