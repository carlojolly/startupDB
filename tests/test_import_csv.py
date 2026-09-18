"""Tests for the parts of the importer that run before the database.

None of these need Postgres: they cover parsing, counting and the guard
rails that decide whether a file is safe to load at all.
"""
from __future__ import annotations

import csv
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import clean  # noqa: E402
import import_csv  # noqa: E402

# One real header per logical field (the first alias), in registry order.
HEADERS = [aliases[0] for aliases in clean.COLUMN_ALIASES.values()]
FIELDS = list(clean.COLUMN_ALIASES)


def company(**overrides) -> dict[str, str]:
    row = {field: "" for field in FIELDS}
    row.update({
        "denominazione": "ACME S.R.L.",
        "natura_giuridica": "SOCIETA' A RESPONSABILITA' LIMITATA",
        "codice_fiscale": "00976660944",
        "pv": "MI",
        "comune": "MILANO",
        "data_iscrizione_sezione_startup": "12/06/2023",
        "data_iscrizione_registro_imprese": "04/06/2023",
        "data_inizio_attivita": "01/07/2023",
        "ateco_raw": "621000",
        "settore": "Servizi",
        "attivita_label": "J 62 PRODUZIONE DI SOFTWARE, CONSULENZA",
        "classe_produzione": "A",
        "classe_capitale": "3",
        "sito_internet_raw": "www.acme.it",
        "req_ricerca_sviluppo": "SI",
        "data_dichiarazione": "01/01/2024",
        "prevalenza_femminile": "NO",
        "prevalenza_giovanile": "NO",
        "prevalenza_straniera": "NO",
    })
    row.update(overrides)
    return row


def write_export(path: pathlib.Path, rows: list[dict[str, str]]) -> pathlib.Path:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADERS)
        for row in rows:
            writer.writerow([row[field] for field in FIELDS])
    return path


def test_read_and_clean_counts_every_skip_reason_and_keeps_leading_zeros(tmp_path):
    export = write_export(tmp_path / "startup.csv", [
        company(),
        {field: "" for field in FIELDS},                       # spreadsheet padding
        company(codice_fiscale="RSSMRA80A01H501U"),            # a personal CF
        company(),                                             # duplicate of row 1
        company(codice_fiscale="01234567890", denominazione="BETA S.R.L.",
                data_dichiarazione="2024-01-01"),              # ISO date: unparseable
    ])

    rows, stats, columns = import_csv.read_and_clean(export)

    assert [row["codice_fiscale"] for row in rows] == ["00976660944", "01234567890"]
    assert rows[0]["codice_fiscale"].startswith("0")
    assert stats["rows_in_file"] == 5
    assert stats["rows_valid"] == 2
    assert stats["skipped_blank"] == 1
    assert stats["skipped_bad_cf"] == 1
    assert stats["skipped_duplicate_in_file"] == 1
    assert stats["unparsed_dates"] == 1
    assert rows[1]["data_dichiarazione"] is None
    assert columns["ateco_raw"] == "ateco 2007"


def test_blank_dates_are_not_counted_as_unparseable(tmp_path):
    export = write_export(tmp_path / "startup.csv", [company(data_inizio_attivita="")])

    rows, stats, _columns = import_csv.read_and_clean(export)

    assert len(rows) == 1
    assert stats["unparsed_dates"] == 0


def test_unparsed_dates_block_the_import_unless_allowed():
    import_csv.check_unparsed_dates(0, allow=False)
    import_csv.check_unparsed_dates(3, allow=True)
    with pytest.raises(SystemExit, match="3 date value"):
        import_csv.check_unparsed_dates(3, allow=False)
