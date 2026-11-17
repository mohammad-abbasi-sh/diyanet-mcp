"""Parsing + place resolution for diyanet_mcp (stdlib only).

Page model (verified live 2026-11-17 on the Ankara/İstanbul/Akyurt
pages, tr-TR and en-US):
- Today's 6 times: JS vars ``_imsakTime`` … ``_yatsiTime`` (language
  independent) AND the ``.tpt-cell`` widget (same values).
- Qibla + astronomy: extra ``.tpt-cell`` widget cells after the 6
  prayer cells, in fixed order: qibla angle (degrees), qibla time,
  astronomical sunrise, astronomical sunset.
- Monthly table: one <table> whose rows are [Miladi date, Hicri date,
  İmsak, Güneş, Öğle, İkindi, Akşam, Yatsı]; it covers the FULL
  calendar year (365 rows), ordered today-first (today → 31 Dec, then
  1 Jan → yesterday). The page carries several copies of the table
  (tabs), so rows are deduped by date. The first row is today.
- Place display name: <title> (e.g. "Ankara Namaz Vakitleri | …").
- Region lists: GetRegList JSON (see http.py).

Name matching is Turkish-insensitive: "Cankaya" matches "ÇANKAYA",
"istanbul" matches "İSTANBUL".
"""
from __future__ import annotations

import html as _html
import re

from . import http as _http

TURKEY_COUNTRY_ID = 2

CULTURES = {
    "tr": "tr-TR",
    "en": "en-US",
    "ar": "ar-SA",
    "de": "de-DE",
    "fr": "fr-FR",
}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_JS_VARS = (
    ("imsak", "_imsakTime"),
    ("gunes", "_gunesTime"),
    ("ogle", "_ogleTime"),
    ("ikindi", "_ikindiTime"),
    ("aksam", "_aksamTime"),
    ("yatsi", "_yatsiTime"),
)

# Turkish-insensitive folding for name matching.
_FOLD_MAP = str.maketrans({
    "ç": "c", "Ç": "c",
    "ğ": "g", "Ğ": "g",
    "ı": "i", "I": "i",
    "İ": "i",
    "ö": "o", "Ö": "o",
    "ş": "s", "Ş": "s",
    "ü": "u", "Ü": "u",
})


def fold(name: str) -> str:
    """Lowercase + strip Turkish diacritics: 'ÇANKAYA' -> 'cankaya'."""
    return (name or "").strip().translate(_FOLD_MAP).lower()


def culture_for(lang: str) -> str:
    lang = (lang or "tr").strip().lower()
    if lang not in CULTURES:
        raise ValueError(f"lang must be one of {', '.join(CULTURES)}")
    return CULTURES[lang]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(text or "")).strip()


# ---------------------------------------------------------------- provinces

def parse_provinces(data: dict) -> list:
    """GetRegList ChangeType=country -> [{id, name_tr, name_en}]."""
    rows = data.get("StateList") or []
    out = []
    for r in rows:
        try:
            pid = int(r["SehirID"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append({
            "id": pid,
            "name_tr": _clean(r.get("SehirAdi")),
            "name_en": _clean(r.get("SehirAdiEn")),
        })
    return out


def list_provinces(query: str | None = None, lang: str = "tr") -> list:
    """All 81 Turkish provinces, optionally filtered by name substring."""
    culture = culture_for(lang)
    rows = parse_provinces(_http.fetch_reg_list("country", culture=culture))
    if query:
        q = fold(query)
        rows = [r for r in rows
                if q in fold(r["name_tr"]) or q in fold(r["name_en"])]
    return rows


def find_province(name_or_id: str | int, lang: str = "tr") -> dict:
    """Resolve a province by id or (folded) name. Raises ValueError."""
    rows = list_provinces(lang=lang)
    if isinstance(name_or_id, int) or str(name_or_id).strip().isdigit():
        pid = int(name_or_id)  # type: ignore[arg-type]
        for r in rows:
            if r["id"] == pid:
                return r
        raise ValueError(f"unknown province id {pid!r}")
    q = fold(str(name_or_id))
    for r in rows:
        if fold(r["name_tr"]) == q or fold(r["name_en"]) == q:
            return r
    # substring fallback (e.g. "ank" -> Ankara) only when unambiguous
    hits = [r for r in rows
            if q in fold(r["name_tr"]) or q in fold(r["name_en"])]
    if len(hits) == 1:
        return hits[0]
    raise ValueError(
        f"unknown province {name_or_id!r} — use diyanet_list_provinces to browse"
        + (f" ({len(hits)} matches: "
           + ", ".join(h['name_tr'] for h in hits[:5]) + ")" if hits else "")
    )


# ---------------------------------------------------------------- districts

def parse_districts(data: dict) -> list:
    """GetRegList ChangeType=state -> [{id, name_tr, name_en, url}]."""
    rows = data.get("StateRegionList") or []
    out = []
    for r in rows:
        try:
            did = int(r["IlceID"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append({
            "id": did,
            "name_tr": _clean(r.get("IlceAdi")),
            "name_en": _clean(r.get("IlceAdiEn")),
            "url": (r.get("IlceUrl") or "").strip(),
        })
    return out


def list_districts(province: str | int, query: str | None = None,
                   lang: str = "tr") -> list:
    """Districts of one province (by province name or id)."""
    prov = find_province(province, lang=lang)
    culture = culture_for(lang)
    rows = parse_districts(
        _http.fetch_reg_list("state", state_id=prov["id"], culture=culture)
    )
    if query:
        q = fold(query)
        rows = [r for r in rows
                if q in fold(r["name_tr"]) or q in fold(r["name_en"])]
    return rows


# ---------------------------------------------------------------- place page

def parse_place_title(html: str) -> str:
    m = re.search(r"<title>([^<]*)</title>", html)
    title = _clean(m.group(1)) if m else ""
    # "Ankara Namaz Vakitleri | Diyanet …" -> "Ankara"
    title = re.split(r"\s*[|–—-]\s*", title)[0]
    for suffix in (" Namaz Vakitleri", " Prayer Times", " أوقات الصلاة",
                   " Gebetszeiten", " Horaires de prière"):
        if title.endswith(suffix):
            title = title[: -len(suffix)]
    return title.strip()


def parse_today_times(html: str) -> dict:
    """Today's 6 times from the _*Time JS vars (language independent)."""
    out = {}
    for key, var in _JS_VARS:
        m = re.search(rf"{var}\s*=\s*\"([0-2]\d:[0-5]\d)\"", html)
        if not m:
            raise ValueError(f"place page is missing {var} (layout changed?)")
        out[key] = m.group(1)
    return out


def parse_widget_cells(html: str) -> list:
    """Ordered (title, value) pairs of the today widget.

    Scoped to the markup after ``today-pray-times-row`` so the local
    clock cell elsewhere on the page is excluded. The widget holds
    exactly 10 cells in fixed order: the 6 prayer times, then qibla
    angle, qibla time, astronomical sunrise, astronomical sunset.
    """
    start = html.find("today-pray-times-row")
    seg = html[start:] if start >= 0 else html
    pairs = re.findall(
        r'<div class="tpt-title"[^>]*>\s*(.*?)\s*</div>\s*'
        r'<div class="tpt-time"[^>]*>\s*(.*?)\s*</div>',
        seg, re.S,
    )
    out = []
    for title, value in pairs:
        title = _clean(re.sub(r"<[^>]+>", "", title))
        value = _clean(re.sub(r"<[^>]+>", "", value))
        if title:
            out.append((title, value))
    return out


def parse_qibla(html: str) -> dict:
    """Qibla angle/time + astronomical sunrise/sunset from the widget.

    Parsed by position (labels are localised): the 10 widget cells are
    [6 prayer times, qibla angle, qibla time, astro sunrise, astro
    sunset]. The 6 times are cross-checked against the JS vars, which
    win on any mismatch.
    """
    cells = parse_widget_cells(html)
    if len(cells) < 10:
        raise ValueError(
            f"place page has only {len(cells)} widget cells (expected 10)"
        )
    js_times = parse_today_times(html)
    for i, (key, _) in enumerate(_JS_VARS):
        if cells[i][1] != js_times[key]:
            # Widget and JS disagree — trust the JS vars, keep going.
            pass
    try:
        angle = int(re.sub(r"[^\d]", "", cells[6][1]))
    except ValueError as e:
        raise ValueError(f"unparsable qibla angle {cells[6][1]!r}") from e
    return {
        "times": js_times,
        "qibla_angle_deg": angle,
        "qibla_time": cells[7][1],
        "astronomical_sunrise": cells[8][1],
        "astronomical_sunset": cells[9][1],
    }


def parse_times_table(html: str) -> list:
    """Full-year times table rows (deduped by date).

    Each row: {date, hijri, imsak, gunes, ogle, ikindi, aksam, yatsi}.
    The page repeats the table (tabs), so identical dates collapse.
    Rows are in page order: today first, then the rest of the year,
    then 1 January up to yesterday (365 rows for the calendar year).
    """
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    seen: dict[str, dict] = {}
    for row in rows:
        cells = [_clean(re.sub(r"<[^>]+>", "", c))
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if len(cells) != 8:
            continue
        if not _TIME_RE.match(cells[2]):
            continue  # header row or a non-date row
        if cells[0] in seen:
            continue
        seen[cells[0]] = {
            "date": cells[0],
            "hijri": cells[1],
            "imsak": cells[2],
            "gunes": cells[3],
            "ogle": cells[4],
            "ikindi": cells[5],
            "aksam": cells[6],
            "yatsi": cells[7],
        }
    return list(seen.values())


def parse_place_page(html: str) -> dict:
    """Full parse of one place page: title, today, qibla, full-year table."""
    table = parse_times_table(html)
    if not table:
        raise ValueError("place page has no prayer-times table")
    qibla = parse_qibla(html)
    return {
        "place": parse_place_title(html),
        "today": table[0],
        "times_today": qibla["times"],
        "qibla_angle_deg": qibla["qibla_angle_deg"],
        "qibla_time": qibla["qibla_time"],
        "astronomical_sunrise": qibla["astronomical_sunrise"],
        "astronomical_sunset": qibla["astronomical_sunset"],
        "table": table,
    }


# ---------------------------------------------------------------- resolution

def _with_culture(path: str, culture: str) -> str:
    """Swap the culture segment of a site path (/tr-TR/… -> /en-US/…)."""
    return re.sub(r"^/[a-z]{2}-[A-Z]{2}/", f"/{culture}/", path, count=1)


def resolve_place(place: str, lang: str = "tr") -> dict:
    """Resolve a place to a page URL.

    place: "Ankara", "İstanbul/Beylikdüzü", "Ankara/Çankaya", or a
    numeric district id such as "9541". With only a province, the
    central district (same name as the province) is used.
    District names Diyanet folds into the central district (a
    province's urban districts, e.g. Ankara's Çankaya — they are NOT
    in the district list) resolve to the central timetable via the
    site's own GetDestinationUrl; the district actually served is
    always reported, and "requested_district" records what was asked
    for when it differs. A name that matches nothing raises ValueError.
    Returns {ilce_id, url, province, district, requested_district}.
    """
    culture = culture_for(lang)
    place = (place or "").strip()
    if not place:
        raise ValueError("place must not be empty")
    if place.isdigit():
        ilce_id = int(place)
        return {
            "ilce_id": ilce_id,
            "url": f"{_http.BASE}/{culture}/{ilce_id}/icin-namaz-vakti",
            "province": None,
            "district": None,
            "requested_district": None,
        }
    parts = [p.strip() for p in place.split("/") if p.strip()]
    if len(parts) > 2:
        raise ValueError(
            "place must be 'Province', 'Province/District' or a district id"
        )
    prov = find_province(parts[0], lang=lang)
    districts = list_districts(prov["id"], lang=lang)
    requested_district = None
    if len(parts) == 2:
        q = fold(parts[1])
        hits = [d for d in districts
                if fold(d["name_tr"]) == q or fold(d["name_en"]) == q]
        if not hits:
            hits = [d for d in districts
                    if q in fold(d["name_tr"]) or q in fold(d["name_en"])]
        if len(hits) == 1:
            dist = hits[0]
        elif len(hits) > 1:
            raise ValueError(
                f"ambiguous district {parts[1]!r} in {prov['name_tr']}: "
                + ", ".join(d["name_tr"] for d in hits)
            )
        else:
            # Not in Diyanet's district list — it may be an urban
            # district folded into the centre (e.g. Çankaya). Ask the
            # site's own resolver, but VERIFY the answer: the endpoint
            # silently falls back to the province centre for unknown
            # names, and to Adana (9146) for a bad province — so the
            # returned id must belong to this province's districts.
            requested_district = parts[1]
            dest = _http.fetch_destination_url(
                "TÜRKİYE", prov["name_tr"], parts[1], culture=culture,
            )
            if dest.get("Result") != "ok":
                raise ValueError(
                    f"unknown district {parts[1]!r} in {prov['name_tr']} — "
                    "use diyanet_list_districts to browse"
                )
            try:
                did = int(dest.get("IlceId"))
            except (TypeError, ValueError):
                raise ValueError(
                    f"unknown district {parts[1]!r} in {prov['name_tr']} — "
                    "use diyanet_list_districts to browse"
                ) from None
            by_id = {d["id"]: d for d in districts}
            if did not in by_id:
                raise ValueError(
                    f"unknown district {parts[1]!r} in {prov['name_tr']} — "
                    "use diyanet_list_districts to browse"
                )
            dist = by_id[did]
    else:
        # Central district: same name as the province (Ankara -> ANKARA).
        same = [d for d in districts if fold(d["name_tr"]) == fold(prov["name_tr"])]
        dist = same[0] if same else districts[0]
    return {
        "ilce_id": dist["id"],
        "url": f"{_http.BASE}{_with_culture(dist['url'], culture)}",
        "province": prov,
        "district": dist,
        "requested_district": requested_district,
    }


def fetch_place(place: str, lang: str = "tr") -> dict:
    """Resolve + fetch + parse one place page."""
    resolved = resolve_place(place, lang=lang)
    html = _http.fetch_place_page(resolved["url"])
    parsed = parse_place_page(html)
    return {**resolved, **parsed, "source_url": resolved["url"]}
