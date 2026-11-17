"""MCP server: unofficial read-only access to Diyanet prayer times."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from . import http as _http
from . import places as _P

mcp = FastMCP("diyanet-mcp")

INSTRUCTIONS = """\
Unofficial read-only MCP server for the Presidency of Religious Affairs \
(Diyanet) prayer times — the OFFICIAL published timetable for Türkiye: \
today's 6 prayer times (İmsak, Güneş, Öğle, İkindi, Akşam, Yatsı) for \
any of the 81 provinces and their districts, the full-year table with \
Miladi + Hijri dates, and qibla angle/time plus astronomical sunrise/ \
sunset per place. Data comes from namazvakitleri.diyanet.gov.tr \
(server-rendered pages + its own region-list JSON) — no login, no API \
key. Place names work in Turkish or English, with or without Turkish \
characters ("Cankaya" finds "ÇANKAYA"); a province alone returns its \
central district, and urban districts Diyanet folds into the centre \
(e.g. Çankaya → Ankara) resolve to the central timetable — the served \
district is always reported. Read-only; transport uses Chrome TLS \
impersonation with a plain-requests fallback; requests are spaced \
~0.5s apart. Built by Mohammad Abbasi (mohammad-abbasi-sh) — https://almanibama.ir · https://mabbasi.ir — Turkey \
MCP factory.\
"""

_SOURCE = "namazvakitleri.diyanet.gov.tr"
_DISCLAIMER = (
    "Unofficial read-only prayer times from Diyanet's published "
    "timetable; verify on namazvakitleri.diyanet.gov.tr before acting "
    "on them. Times are Europe/Istanbul local time."
)


def _envelope() -> dict:
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": _SOURCE,
        "disclaimer": _DISCLAIMER,
    }


def _ok(payload: dict) -> str:
    return json.dumps({**_envelope(), **payload}, ensure_ascii=False)


def _err(e: Exception) -> str:
    return _ok({"error": str(e)})


def _validate_limit(limit: int, lo: int, hi: int) -> int:
    if not lo <= limit <= hi:
        raise ValueError(f"limit must be between {lo} and {hi}")
    return limit


def _place_summary(res: dict) -> dict:
    out = {
        "place": res["place"],
        "province": res["province"]["name_tr"] if res.get("province") else None,
        "district": res["district"]["name_tr"] if res.get("district") else None,
        "ilce_id": res["ilce_id"],
        "url": res["source_url"],
    }
    if res.get("requested_district"):
        # Asked for e.g. Çankaya, served the central district's table.
        out["requested_district"] = res["requested_district"]
        out["note"] = (
            f"no separate Diyanet timetable for "
            f"{res['requested_district']!r}; showing the "
            f"{res['district']['name_tr']} (central) timetable — "
            "the site's own fallback for this name"
        )
    return out


@mcp.tool()
def diyanet_prayer_times(place: str, lang: str = "tr") -> str:
    """Today's official Diyanet prayer times for a place in Türkiye.
    place: a province ("Ankara"), a province/district ("İstanbul/
    Beylikdüzü", "Ankara/Çankaya") or a numeric district id ("9541").
    A province alone returns its central district. lang: "tr" (default),
    "en", "ar", "de" or "fr" — the site's own language versions.
    Returns the 6 times (imsak, gunes, ogle, ikindi, aksam, yatsi),
    today's Miladi + Hijri dates, qibla angle/time and astronomical
    sunrise/sunset. Times are Europe/Istanbul local time."""
    try:
        res = _P.fetch_place(place, lang=lang)
        return _ok({
            **_place_summary(res),
            "date_miladi": res["today"]["date"],
            "date_hijri": res["today"]["hijri"],
            "times": res["times_today"],
            "qibla_angle_deg": res["qibla_angle_deg"],
            "qibla_time": res["qibla_time"],
            "astronomical_sunrise": res["astronomical_sunrise"],
            "astronomical_sunset": res["astronomical_sunset"],
        })
    except (ValueError, _http.DiyanetError) as e:
        return _err(e)


@mcp.tool()
def diyanet_yearly_times(place: str, lang: str = "tr", limit: int = 45) -> str:
    """The Diyanet full-year prayer-times table for a place in Türkiye:
    one row per day (Miladi date + Hijri date + the 6 times) — 365
    rows: the coming month first, then 1 January through the rest of
    the year.
    place: a province ("Ankara"), a province/district ("İstanbul/
    Beylikdüzü") or a numeric district id ("9541"). lang: "tr"
    (default), "en", "ar", "de" or "fr". limit 1..365 (default 45)."""
    try:
        _validate_limit(limit, 1, 365)
        res = _P.fetch_place(place, lang=lang)
        rows = res["table"][:limit]
        return _ok({
            **_place_summary(res),
            "count": len(rows),
            "total_days": len(res["table"]),
            "days": rows,
        })
    except (ValueError, _http.DiyanetError) as e:
        return _err(e)


@mcp.tool()
def diyanet_list_provinces(query: str | None = None, lang: str = "tr") -> str:
    """The 81 Turkish provinces with their Diyanet ids and Turkish +
    English names. query: optional substring filter (Turkish-insensitive,
    e.g. "ank" matches Ankara). lang: "tr" (default), "en", "ar", "de"
    or "fr". Use the id or name with diyanet_list_districts."""
    try:
        rows = _P.list_provinces(query=query, lang=lang)
        return _ok({"count": len(rows), "provinces": rows})
    except (ValueError, _http.DiyanetError) as e:
        return _err(e)


@mcp.tool()
def diyanet_list_districts(province: str, query: str | None = None,
                           lang: str = "tr") -> str:
    """The districts of one Turkish province, with Diyanet ids, Turkish
    + English names and the prayer-times page URL of each.
    province: province name ("Ankara") or id ("506"). query: optional
    substring filter (Turkish-insensitive). lang: "tr" (default), "en",
    "ar", "de" or "fr"."""
    try:
        rows = _P.list_districts(province, query=query, lang=lang)
        prov = _P.find_province(province, lang=lang)
        return _ok({
            "province": prov,
            "count": len(rows),
            "districts": rows,
        })
    except (ValueError, _http.DiyanetError) as e:
        return _err(e)


@mcp.tool()
def diyanet_qibla(place: str, lang: str = "tr") -> str:
    """Qibla direction for a place in Türkiye, from Diyanet's own data:
    the qibla angle in degrees (clockwise from north), the daily qibla
    time (when the sun is aligned with the qibla), and astronomical
    sunrise/sunset.
    place: a province ("Ankara"), a province/district ("İstanbul/
    Beylikdüzü") or a numeric district id ("9541"). lang: "tr"
    (default), "en", "ar", "de" or "fr"."""
    try:
        res = _P.fetch_place(place, lang=lang)
        return _ok({
            **_place_summary(res),
            "date_miladi": res["today"]["date"],
            "date_hijri": res["today"]["hijri"],
            "qibla_angle_deg": res["qibla_angle_deg"],
            "qibla_time": res["qibla_time"],
            "astronomical_sunrise": res["astronomical_sunrise"],
            "astronomical_sunset": res["astronomical_sunset"],
        })
    except (ValueError, _http.DiyanetError) as e:
        return _err(e)


@mcp.tool()
def diyanet_health() -> str:
    """Check whether Diyanet's prayer-times site is reachable right now.

    Returns status ok (HTTP 200), blocked (HTTP 403/429 — bot wall or
    rate limit) or error, plus the HTTP status and the probed URL.
    Two polite requests; it does not fetch any prayer times."""
    return _ok(_http.health_check())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    import sys

    sys.exit(main())
