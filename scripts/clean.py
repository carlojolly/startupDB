"""Pure functions that turn raw CSV strings into typed Python values.

No database code lives here on purpose: everything below is a plain function
you can call in a REPL or a test. If a value looks wrong in the database, this
is the file to look at first.

Everything here is driven by what is actually in the registry export — see the
"Known data quirks" section of the README.
"""
from __future__ import annotations

import datetime
import hashlib
import re
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# Logical field name -> the header text as it appears in the CSV, normalised.
#
# We match headers by a normalised form (lowercased, whitespace collapsed)
# because three of the real headers contain literal newline characters —
# e.g. "1° req.\n(6)" — and because the registry occasionally reflows them.
# ---------------------------------------------------------------------------
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "denominazione":        ("denominazione",),
    "natura_giuridica":     ("nat.giuridica", "natura giuridica"),
    "codice_fiscale":       ("codice fiscale",),
    "pv":                   ("pv",),
    "comune":               ("comune",),
    "data_iscrizione_sezione_startup":  ("data iscrizione alla sezione delle startup",),
    "data_iscrizione_registro_imprese": ("data iscrizione al registro imprese",),
    "data_inizio_attivita": ("data inizio dell'esercizio effettivo dell'attività",),
    "ateco_raw":            ("ateco 2007",),
    "settore":              ("settore",),
    "attivita_label":       ("attività",),
    "classe_produzione":    ("classe di produzione ultimo anno (1)", "classe val.prod."),
    "classe_addetti":       ("classe di addetti ultimo anno (2)", "classe addetti"),
    "vocazione_sociale":    ("impresa a vocazione sociale (5)", "vocazione sociale"),
    "alto_valore_tecnologico_energetico": (
        "impresa ad alto valore tecnologico in ambito energetico(4)",
        "impresa ad alto valore tecnologico in ambito energetico (4)",
        "alto valore tecnologico",
    ),
    "classe_capitale":      ("classe di capitale (3)", "classe cap.sociale"),
    "sito_internet_raw":    ("sito internet",),
    "req_ricerca_sviluppo":      ("1° req. (6)", "spese in ricerca e sviluppo"),
    "req_personale_qualificato": ("2° req. (6)", "forza lavoro con titoli"),
    "req_brevetto":              ("3° req. (6)", "possesso di brevetti"),
    "data_dichiarazione":   ("data dichiarazione (7)", "data dichiarazione"),
    "prevalenza_femminile": ("prevalenza femminile (8)", "prevalenza femminile"),
    "prevalenza_giovanile": ("prevalenza giovanile (8)", "prevalenza giovanile"),
    "prevalenza_straniera": ("prevalenza straniera (8)", "prevalenza straniera"),
}

# Fields that feed the change-detection hash. Deliberately excludes anything
# about *when* we looked (observed_on, import_id) and the raw JSON blob, so
# that re-importing an unchanged company produces no new snapshot row.
HASHED_FIELDS: tuple[str, ...] = (
    "denominazione", "natura_giuridica", "in_liquidazione",
    "pv", "comune",
    "data_iscrizione_sezione_startup", "data_iscrizione_registro_imprese",
    "data_inizio_attivita", "data_dichiarazione",
    "ateco_raw", "ateco_division", "settore", "attivita_label",
    "classe_produzione", "classe_addetti", "classe_capitale",
    "req_ricerca_sviluppo", "req_personale_qualificato", "req_brevetto",
    "vocazione_sociale", "alto_valore_tecnologico_energetico",
    "prevalenza_femminile", "prevalenza_giovanile", "prevalenza_straniera",
    "sito_internet_raw", "sito_internet_url", "sito_internet_domain",
)

_WS = re.compile(r"\s+")
_CF = re.compile(r"^[0-9]{11}$")
_ATTIVITA = re.compile(r"^([A-Z])\s+(\d{2})\s+(.*)$")
_LIQUIDAZIONE = re.compile(r"\bIN (LIQUIDAZIONE|SCIOGLIMENTO)\b", re.IGNORECASE)


def normalise_header(name: str) -> str:
    """Lowercase, turn any run of whitespace (incl. newlines) into one space."""
    return _WS.sub(" ", (name or "").replace("﻿", "")).strip().lower()


def resolve_columns(fieldnames: list[str]) -> dict[str, str]:
    """Map our logical field names onto the CSV's actual header strings.

    Raises with a readable message if a required column is missing, rather
    than failing later with a confusing KeyError.
    """
    by_normalised = {normalise_header(f): f for f in fieldnames}
    resolved: dict[str, str] = {}
    missing: list[str] = []

    for logical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            actual = by_normalised.get(normalise_header(alias))
            if actual is not None:
                resolved[logical] = actual
                break
        else:
            missing.append(f"{logical} (looked for: {', '.join(aliases)})")

    if missing:
        raise ValueError(
            "The CSV is missing expected columns:\n  - "
            + "\n  - ".join(missing)
            + "\n\nHeaders actually present:\n  - "
            + "\n  - ".join(sorted(by_normalised))
            + "\n\nIf the registry changed its export format, update "
              "COLUMN_ALIASES in scripts/clean.py."
        )
    return resolved


# ---------------------------------------------------------------------------
# Scalar cleaners
# ---------------------------------------------------------------------------

def text(value: str | None) -> str | None:
    """Strip, collapse internal runs of whitespace, empty string -> None.

    Collapsing matters: 644 company names in the file contain double spaces,
    which would otherwise split one company into two in any name search.
    """
    if value is None:
        return None
    cleaned = _WS.sub(" ", value).strip()
    return cleaned or None


def parse_date(value: str | None) -> datetime.date | None:
    """Parse the registry's dd/mm/yyyy. Returns None for blanks or junk."""
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.datetime.strptime(raw, "%d/%m/%Y").date()
    except ValueError:
        return None


def parse_si_no(value: str | None) -> bool | None:
    """'SI' -> True, 'NO' -> False, blank -> None (genuinely unknown)."""
    raw = (value or "").strip().upper()
    if raw == "SI":
        return True
    if raw == "NO":
        return False
    return None


def parse_si_flag(value: str | None) -> bool:
    """'SI' -> True, anything else -> False.

    Used for the three `req.` columns and `vocazione sociale`, which the
    registry encodes as 'SI' or blank and never as 'NO'. Blank means the
    criterion does not apply, so False is the correct reading — not NULL.
    """
    return (value or "").strip().upper() == "SI"


def parse_int(value: str | None) -> int | None:
    raw = (value or "").strip()
    return int(raw) if raw.isdigit() else None


def ateco_division(ateco_raw: str | None) -> str | None:
    """First two digits of the ATECO code, or None.

    The raw column mixes 2/3/4/5/6-digit codes with the literal string 'NC'.
    Short codes are genuinely coarser levels of the hierarchy, NOT truncated
    six-digit codes — verified: zero of them zero-pad to a code that exists
    elsewhere in the file. So we never pad; we only take the division, which
    matches the `attivita` label in 100% of rows.
    """
    raw = (ateco_raw or "").strip()
    if len(raw) >= 2 and raw[:2].isdigit():
        return raw[:2]
    return None


def parse_attivita(label: str | None) -> tuple[str | None, str | None, str | None]:
    """Split "J 62 PRODUZIONE DI SOFTWARE, ..." -> ('J', '62', 'PRODUZIONE...').

    Note the description arrives truncated at ~57 characters from the source.
    """
    raw = text(label)
    if not raw:
        return None, None, None
    match = _ATTIVITA.match(raw)
    if not match:
        return None, None, raw
    return match.group(1), match.group(2), match.group(3).strip() or None


def is_in_liquidazione(denominazione: str | None) -> bool:
    """The export has no status column, so the name is the only signal.

    277 companies carry 'IN LIQUIDAZIONE' and 7 'IN SCIOGLIMENTO'.
    """
    return bool(_LIQUIDAZIONE.search(denominazione or ""))


def clean_website(value: str | None) -> tuple[str | None, str | None]:
    """Turn the messy `sito internet` cell into (url, bare_domain).

    Real examples this has to survive:
        'www. siepegrande.it'                    -> space inside the domain
        ': www.kriton.cloud'                     -> leading punctuation
        'eidoslab.io - eidoslab.eu'              -> several domains in one cell
        'www.langaponica.it e www.langaponica.com'
        'non presente' / 'non presente attualmente'  -> not a URL at all
        'hotelsalina@hotelsalina.com'            -> an email address
    Returns (None, None) when nothing usable can be salvaged.
    """
    raw = (value or "").strip()
    if not raw:
        return None, None

    # Repair the common 'www. domain.it' typo before we tokenise on whitespace.
    candidate = re.sub(r"\bwww\.\s+", "www.", raw)

    # Several sites crammed into one cell: keep the first usable token.
    token = None
    for part in re.split(r"[\s,;|]+", candidate):
        part = part.strip().strip(".,;:-|")
        if not part or "." not in part:
            continue
        token = part
        break
    if token is None:
        return None, None

    # Strip any leading scheme, correct or mangled, then put a clean one back.
    # The file contains 'htps://', 'http//', 'ps://' and bare '//' prefixes;
    # all of them describe a perfectly good domain behind a typo.
    # Anchored on the literal 'http' so these can never eat a real domain:
    token = re.sub(r"^https?[:.]//", "", token, flags=re.IGNORECASE)   # 'https.//x'
    token = re.sub(r"^https?:(?!//)", "", token, flags=re.IGNORECASE)  # 'http:www.x'
    # General case, incl. mangled schemes like 'htps://' and 'ps://':
    token = re.sub(r"^[a-zA-Z][a-zA-Z0-9+\-]{0,9}:?//", "", token)
    token = re.sub(r"^//", "", token)

    # An '@' left over at this point means somebody typed an email address.
    if "@" in token:
        return None, None

    token = "https://" + token

    try:
        parts = urlsplit(token)
    except ValueError:
        return None, None

    host = (parts.hostname or "").lower().strip(".")
    if "." not in host or host.endswith("."):
        return None, None
    # Reject hosts with characters no domain can contain.
    if not re.match(r"^[a-z0-9.\-]+$", host):
        return None, None
    # Must have a plausible TLD (letters, at least 2 chars).
    if not re.match(r"^[a-z]{2,}$", host.rsplit(".", 1)[-1]):
        return None, None

    domain = host[4:] if host.startswith("www.") else host
    path = parts.path.rstrip("/")
    url = f"https://{host}{path}" if path else f"https://{host}"
    return url, domain


# ---------------------------------------------------------------------------
# Row-level transformation
# ---------------------------------------------------------------------------

def clean_row(row: dict[str, str], columns: dict[str, str]) -> dict:
    """Turn one raw CSV row into the dict we insert as a snapshot."""
    def raw(field: str) -> str | None:
        return row.get(columns[field])

    denominazione = text(raw("denominazione"))
    ateco_raw = text(raw("ateco_raw"))
    section_letter, division_from_label, _ = parse_attivita(raw("attivita_label"))
    url, domain = clean_website(raw("sito_internet_raw"))

    # Prefer the numeric code; fall back to the division in the text label if a
    # future export ever codes them differently. Note the 58 rows coded 'NC' in
    # the Aug-2026 file recover nothing: their label is the literal 'N.S.' and
    # their `settore` is blank, so they end up with a NULL division. That is
    # correct — the registry genuinely has not classified them.
    division = ateco_division(ateco_raw) or division_from_label

    return {
        "denominazione": denominazione,
        "natura_giuridica": text(raw("natura_giuridica")),
        "in_liquidazione": is_in_liquidazione(denominazione),
        "pv": (text(raw("pv")) or "").upper() or None,
        "comune": text(raw("comune")),
        "data_iscrizione_sezione_startup":  parse_date(raw("data_iscrizione_sezione_startup")),
        "data_iscrizione_registro_imprese": parse_date(raw("data_iscrizione_registro_imprese")),
        "data_inizio_attivita":  parse_date(raw("data_inizio_attivita")),
        "data_dichiarazione":    parse_date(raw("data_dichiarazione")),
        "ateco_raw": ateco_raw,
        "ateco_division": division,
        "ateco_section_letter": section_letter,   # used to seed ref_ateco_division
        "settore": text(raw("settore")),
        "attivita_label": text(raw("attivita_label")),
        "classe_produzione": text(raw("classe_produzione")),
        "classe_addetti": text(raw("classe_addetti")),
        "classe_capitale": parse_int(raw("classe_capitale")),
        "req_ricerca_sviluppo":      parse_si_flag(raw("req_ricerca_sviluppo")),
        "req_personale_qualificato": parse_si_flag(raw("req_personale_qualificato")),
        "req_brevetto":              parse_si_flag(raw("req_brevetto")),
        "vocazione_sociale":         parse_si_flag(raw("vocazione_sociale")),
        "alto_valore_tecnologico_energetico": parse_si_no(raw("alto_valore_tecnologico_energetico")),
        "prevalenza_femminile": text(raw("prevalenza_femminile")),
        "prevalenza_giovanile": text(raw("prevalenza_giovanile")),
        "prevalenza_straniera": text(raw("prevalenza_straniera")),
        "sito_internet_raw": text(raw("sito_internet_raw")),
        "sito_internet_url": url,
        "sito_internet_domain": domain,
    }


def content_hash(cleaned: dict) -> str:
    """Stable SHA-256 over the business fields only.

    Two imports of the same unchanged company must produce the same hash, so
    the value is built from a fixed field order with a delimiter that cannot
    appear in the data (unit separator, 0x1f).
    """
    parts = []
    for field in HASHED_FIELDS:
        value = cleaned.get(field)
        if value is None:
            parts.append("")
        elif isinstance(value, bool):
            parts.append("1" if value else "0")
        elif isinstance(value, datetime.date):
            parts.append(value.isoformat())
        else:
            parts.append(str(value))
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def is_valid_codice_fiscale(value: str | None) -> bool:
    """Exactly 11 digits. Matches the CHECK constraint on the companies table."""
    return bool(_CF.match((value or "").strip()))
