#!/usr/bin/env python3
"""
Fetch publications from DBLP for VCA lab members and generate papers.bib.

Reads:
  dblp_members.toml     – lab members with DBLP author PIDs
  papers_overrides.toml  – extra BibTeX fields, exclusion list
  papers_extra.bib       – additional entries not indexed by DBLP (preprints, etc.)

Writes:
  papers.bib             – combined BibTeX consumed by `make` / bibtex2html

Usage:
  python3 update_papers.py
"""

import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen, Request

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # pip install tomli  (Python < 3.11)
    except ModuleNotFoundError:
        sys.exit("Requires Python >= 3.11 (tomllib) or `pip install tomli`")

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parent
CFG       = ROOT / "dblp_members.toml"
OVERRIDES = ROOT / "papers_overrides.toml"
EXTRA     = ROOT / "papers_extra.bib"
OUTPUT    = ROOT / "papers.bib"

DBLP_XML_URL = "https://dblp.org/pid/{pid}.xml"
DELAY        = 1.0   # seconds between DBLP requests

# ── Venue abbreviation table ────────────────────────────────────────────────
# Maps the first two components of a DBLP key (e.g. "conf/asplos") to a short
# venue name used in the generated BibTeX keys shown on the website.
VENUE = {
    # Architecture
    "conf/asplos": "ASPLOS", "conf/isca": "ISCA", "conf/micro": "MICRO",
    "conf/hpca": "HPCA",
    # PL / Verification
    "conf/pldi": "PLDI", "conf/popl": "POPL", "conf/oopsla": "OOPSLA",
    "conf/icfp": "ICFP", "conf/cpp": "CPP", "conf/cade": "CADE",
    "conf/itp": "ITP", "conf/cav": "CAV", "conf/fmcad": "FMCAD",
    "conf/lics": "LICS",
    # Systems
    "conf/sosp": "SOSP", "conf/osdi": "OSDI", "conf/hotos": "HotOS",
    "conf/eurosys": "EuroSys", "conf/atc": "ATC", "conf/nsdi": "NSDI",
    # Security
    "conf/uss": "USENIX", "conf/sp": "S&amp;P", "conf/ccs": "CCS",
    "conf/ndss": "NDSS",
    # EDA / Hardware
    "conf/dac": "DAC", "conf/iccad": "ICCAD", "conf/fccm": "FCCM",
    "conf/fpga": "FPGA", "conf/date": "DATE", "conf/IEEEpact": "PACT",
    "conf/cgo": "CGO",
    # Journals (use &nbsp; instead of spaces — BibTeX keys cannot contain spaces)
    "journals/pacmpl": "PACMPL", "journals/ral": "IEEE&nbsp;RAL",
    "journals/dt": "IEEE&nbsp;D&amp;T", "journals/tc": "IEEE&nbsp;TC",
    "journals/tcad": "IEEE&nbsp;TCAD", "journals/tocs": "ACM&nbsp;TOCS",
    "journals/toplas": "ACM&nbsp;TOPLAS",
}
PACMPL_SUBS = {"PLDI", "POPL", "OOPSLA", "ICFP"}


# ── Helpers ──────────────────────────────────────────────────────────────────
def _fetch(url: str) -> str | None:
    """GET with polite delay and User-Agent."""
    hdr = {"User-Agent": "VCA-EPFL-PubScript/1.0 (thomas.bourgeat@epfl.ch)"}
    time.sleep(DELAY)
    try:
        with urlopen(Request(url, headers=hdr), timeout=30) as r:
            return r.read().decode()
    except Exception as exc:
        print(f"  WARNING  {url} -> {exc}", file=sys.stderr)
        return None


def _venue(dblp_key: str, number: str = "", journal: str = "") -> str:
    """Short venue name derived from DBLP key."""
    parts = dblp_key.split("/")
    pfx = "/".join(parts[:2]) if len(parts) >= 2 else ""
    v = VENUE.get(pfx, parts[1].upper() if len(parts) >= 2 else "??")
    # PACMPL publishes PLDI/POPL/OOPSLA/ICFP — check both fields for sub-venue
    if v == "PACMPL":
        for field in (number, journal):
            if field in PACMPL_SUBS:
                return field
    return v


def _bibkey(venue: str, year: str, suffix: str = "") -> str:
    """BibTeX key rendered as HTML label by bibtex2html, e.g. ASPLOS '26."""
    return f"{venue}&nbsp;&#39;{year[-2:]}{suffix}"


def _clean_name(name: str) -> str:
    """Strip DBLP disambiguation suffixes (e.g. 'Mengjia Yan 0001' -> 'Mengjia Yan')."""
    import re
    return re.sub(r'\s+\d{4}$', '', name)


def _lastfirst(name: str) -> str:
    """'First Mid Last' -> 'Last, First Mid'."""
    name = _clean_name(name)
    p = name.split()
    return f"{p[-1]}, {' '.join(p[:-1])}" if len(p) > 1 else name


# ── XML parsing ──────────────────────────────────────────────────────────────
def _parse(el, tag: str) -> dict | None:
    """Parse one DBLP XML element into a publication dict."""
    key = el.get("key", "")
    if key.startswith("journals/corr/"):      # skip arXiv duplicates
        return None

    doi = ""
    url = ""
    for ee in el.findall("ee"):
        t = (ee.text or "").strip()
        if "doi.org/" in t:
            doi = t.split("doi.org/", 1)[-1]
        elif not url:
            url = t

    return dict(
        dblp_key=key, type=tag,
        authors=[a.text.strip() for a in el.findall("author") if a.text],
        title=(el.findtext("title") or "").strip().rstrip("."),
        year=el.findtext("year") or "",
        booktitle=el.findtext("booktitle") or "",
        journal=el.findtext("journal") or "",
        volume=el.findtext("volume") or "",
        number=el.findtext("number") or "",
        pages=el.findtext("pages") or "",
        doi=doi, url=url,
    )


def _fetch_pubs(pid: str) -> list[dict]:
    """Fetch all publications for one DBLP author PID."""
    xml = _fetch(DBLP_XML_URL.format(pid=pid))
    if not xml:
        return []
    root = ET.fromstring(xml)
    out = []
    for r in root.findall(".//r"):
        for tag in ("inproceedings", "article", "incollection"):
            el = r.find(tag)
            if el is not None:
                p = _parse(el, tag)
                if p:
                    out.append(p)
    return out


# ── BibTeX serialisation ────────────────────────────────────────────────────
def _bibtex(pub: dict, key: str, extra: dict | None = None) -> str:
    """Render a publication dict as a BibTeX entry string."""
    lines = [f"@{pub['type']}{{{key},"]
    lines.append(f"author = {{{' and '.join(_lastfirst(a) for a in pub['authors'])}}},")
    lines.append(f"title = {{{{{pub['title']}}}}},")
    lines.append(f"year = {{{pub['year']}}},")
    for f in ("booktitle", "journal", "volume", "number", "pages"):
        if pub.get(f):
            lines.append(f"{f} = {{{pub[f]}}},")
    if pub["doi"]:
        lines.append(f"doi = {{{pub['doi']}}},")
    if pub["url"]:
        lines.append(f"url = {{{pub['url']}}},")
    for k, v in (extra or {}).items():
        lines.append(f"{k} = {{{v}}},")
    lines.append("}")
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    if not CFG.exists():
        sys.exit(f"Config not found: {CFG}")

    with open(CFG, "rb") as f:
        cfg = tomllib.load(f)
    members    = cfg.get("members", [])
    start_year = int(cfg.get("start_year", 0))

    if not members:
        sys.exit(f"No [[members]] in {CFG}")

    # Load overrides
    ov: dict = {}
    if OVERRIDES.exists():
        with open(OVERRIDES, "rb") as f:
            ov = tomllib.load(f)
    exclude  = set(ov.get("exclude", []))
    fmap     = {
        e["dblp_key"]: {k: v for k, v in e.items() if k != "dblp_key"}
        for e in ov.get("fields", [])
    }

    # Fetch publications from DBLP
    pubs: dict[str, dict] = {}
    for m in members:
        pid = m.get("pid", "")
        if not pid:
            continue
        name = m.get("name", pid)
        print(f"  {name}  (pid={pid})")
        for p in _fetch_pubs(pid):
            pubs.setdefault(p["dblp_key"], p)

    # Filter & sort
    kept = [
        p for k, p in pubs.items()
        if k not in exclude and int(p.get("year") or 0) >= start_year
    ]
    kept.sort(key=lambda p: (-int(p["year"]), p["title"]))
    print(f"\n{len(kept)} publications (year >= {start_year})")

    # Assign readable BibTeX keys  (e.g.  ASPLOS&nbsp;&#39;26)
    groups: dict[tuple, list] = {}
    for p in kept:
        v = _venue(p["dblp_key"], p.get("number", ""), p.get("journal", ""))
        groups.setdefault((v, p["year"]), []).append(p)

    for (v, y), ps in groups.items():
        if len(ps) == 1:
            ps[0]["_bk"] = _bibkey(v, y)
        else:
            for i, p in enumerate(ps):
                p["_bk"] = _bibkey(v, y, chr(ord("a") + i))

    # Serialise
    entries = [_bibtex(p, p["_bk"], fmap.get(p["dblp_key"])) for p in kept]

    # Append hand-written extra entries (preprints, etc.)
    if EXTRA.exists():
        extra_text = EXTRA.read_text().strip()
        if extra_text:
            entries.append(extra_text)

    OUTPUT.write_text("\n\n".join(entries) + "\n")
    print(f"-> {OUTPUT}  ({len(entries)} entries)")


if __name__ == "__main__":
    main()
