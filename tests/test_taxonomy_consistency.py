"""The closed vocabularies are declared in three places. They must agree.

1. `scripts/tag_companies.py`  — the Pydantic `Literal`s the model output is
   validated against (what can be written to the database).
2. `web/lib/taxonomy.ts`       — the values the dashboard filters on and the
   labels it shows (what can be read back).
3. `docs/tagging-contract-v5.md` — the contract both bake-off sides build to.

Nothing cross-checked them before, so a value added to the prompt but not to
the dashboard would be stored and then silently hidden from every filter.
These tests read all three sources as text, so they need no database, no
network and no Node.
"""
from __future__ import annotations

import pathlib
import re
import sys
import typing

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import score_vc_relevance  # noqa: E402
import tag_companies  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
TAXONOMY_TS = REPO / "web" / "lib" / "taxonomy.ts"
CONTRACT_MD = REPO / "docs" / "tagging-contract-v5.md"

UNCLEAR = "unclear"


# --- the three readers ------------------------------------------------------

def python_values(field: str) -> set[str]:
    """Values the Pydantic model accepts for a list[Literal[...]] field."""
    annotation = tag_companies.CompanyTags.model_fields[field].annotation
    (literal,) = typing.get_args(annotation)          # list[Literal[...]] -> Literal
    return set(typing.get_args(literal))


def typescript_values(const_name: str) -> list[str]:
    """Values of one `facet([...])` declaration, in declared order."""
    source = TAXONOMY_TS.read_text(encoding="utf-8")
    match = re.search(
        rf"export const {const_name} = facet\(\[(.*?)\]\);", source, re.S,
    )
    assert match, f"{const_name} not found in {TAXONOMY_TS.name}"
    return re.findall(r'\[\s*"([A-Za-z0-9_]+)",', match.group(1))


def contract_section(heading_prefix: str) -> str:
    """Body of one `### \\`field\\`` section of the contract, up to the next heading."""
    text = CONTRACT_MD.read_text(encoding="utf-8")
    match = re.search(
        rf"^### `{heading_prefix}`[^\n]*\n(.*?)(?=^### |^## )", text, re.S | re.M,
    )
    assert match, f"section for {heading_prefix} not found in {CONTRACT_MD.name}"
    return match.group(1)


def contract_values(field: str) -> set[str]:
    body = contract_section(field)
    if field == "parent_sector":
        # An indented code block listing the values in two columns.
        block = "\n".join(line for line in body.splitlines() if line.startswith("    "))
        return set(block.split())
    if field == "product_type":
        # A table whose first column is the value in backticks.
        return set(re.findall(r"^\| `([a-z0-9_]+)` \|", body, re.M))
    if field == "customer_model":
        # A single line: `b2b` · `b2c` · ...
        return set(re.findall(r"`([a-z0-9_]+)`", body))
    raise ValueError(field)


# --- the checks -------------------------------------------------------------

FACETS = [
    ("parent_sector", "PARENT_SECTOR"),
    ("product_type", "PRODUCT_TYPE"),
    ("customer_model", "CUSTOMER_MODEL"),
]


def test_every_facet_is_declared_in_all_three_places():
    for field, const in FACETS:
        py = python_values(field)
        ts = set(typescript_values(const))
        doc = contract_values(field)

        assert UNCLEAR in py, f"{field}: the model must be allowed to say unclear"
        assert UNCLEAR not in ts, (
            f"{field}: taxonomy.ts deliberately omits unclear; it is rendered as "
            "missing, never as a filter value"
        )
        assert ts == py - {UNCLEAR}, (
            f"{field}: dashboard and model disagree.\n"
            f"  only in tag_companies.py: {sorted(py - {UNCLEAR} - ts)}\n"
            f"  only in taxonomy.ts:      {sorted(ts - py)}"
        )
        assert doc == py, (
            f"{field}: contract and model disagree.\n"
            f"  only in tag_companies.py:      {sorted(py - doc)}\n"
            f"  only in tagging-contract-v5.md: {sorted(doc - py)}"
        )


def test_typescript_values_are_unique_and_snake_case():
    for _field, const in FACETS:
        values = typescript_values(const)
        assert len(values) == len(set(values)), f"{const} has a duplicate value"
        assert all(re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", v) for v in values), const


def test_vc_relevance_levels_match_between_scorer_and_dashboard():
    annotation = score_vc_relevance.VCRelevance.model_fields["vc_relevance"].annotation
    py = set(typing.get_args(annotation))
    ts = typescript_values("VC_RELEVANCE")

    assert py == set(ts) | {UNCLEAR}
    # Strongest first: this array is the dashboard's default ranking.
    assert ts == ["high", "medium", "low"]


def test_fetch_quality_buckets_match_the_pipeline():
    ts = typescript_values("FETCH_QUALITY")
    assert ts == ["OK", "THIN", "DEAD"]
    # The pipeline's own bucket names, as _bucket() assigns them (best first).
    assert {tag_companies._bucket(5000), tag_companies._bucket(10),
            tag_companies._bucket(0)} == set(ts)
    assert tag_companies._bucket(5000) == "OK"
    assert tag_companies._bucket(0) == "DEAD"
