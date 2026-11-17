"""HTTP layer for diyanet_mcp.

Data source: the Presidency of Religious Affairs (Diyanet) prayer-times
site, https://namazvakitleri.diyanet.gov.tr — the OFFICIAL published
timetable for Türkiye (81 provinces, all districts) and 300+ countries.
No login, no API key. Everything used here was verified live 2026-11-17:

- GET /tr-TR (or /en-US, /ar-SA, /de-DE, /fr-FR) — place home page,
  server-rendered; today's 6 times live in the ``_imsakTime`` … 
  ``_yatsiTime`` JS vars and in the ``.tpt-cell`` widget; the monthly
  table (Miladi + Hicri date + 6 times per day, today → 31 Dec) is
  server-rendered on the same page; qibla angle/time and astronomical
  sunrise/sunset are extra widget cells.
- GET /{culture}/home/GetRegList?ChangeType=country&CountryId=2&Culture=…
  — JSON {StateList: [{SehirID, SehirAdi, SehirAdiEn}]} — the 81
  provinces. (CountryId 2 = Türkiye; the country select lists 307
  countries, but v1 covers Türkiye only.)
- GET /{culture}/home/GetRegList?ChangeType=state&CountryId=2&StateId={id}
  &Culture=… — JSON {StateRegionList: [{IlceID, IlceAdi, IlceAdiEn,
  IlceUrl}]} — the districts of a province. NOTE: Diyanet lists only
  the districts it publishes separate timetables for — a province's
  urban districts (e.g. Ankara's Çankaya) are NOT in the list; the
  site folds them into the central district (see GetDestinationUrl).
- GET /Tr-tr/home/GetDestinationUrl?CountryName=..&StateName=..&
  StateRegionName=..&Culture=… — resolves a (possibly folded-in)
  district name to {Url, IlceId}. LENIENT: unknown names silently fall
  back to the province centre (or to Adana, id 9146, for a bad
  province) — callers must verify the returned IlceId belongs to the
  requested province and always report the district actually served.
- Place pages: /{culture}/{ilceId}/{slug}-icin-namaz-vakti — the slug
  is optional: /{culture}/{ilceId}/icin-namaz-vakti also answers 200.

Transport uses curl-cffi Chrome impersonation with a plain-requests
fallback (the proven Turkey-factory pattern), even though the site
currently answers plain HTTP 200. Requests are kept gentle (one at a
time, ~0.5s apart) and read-only.
"""
from __future__ import annotations

import time

from curl_cffi import requests as _creq
import requests as _plain

BASE = "https://namazvakitleri.diyanet.gov.tr"
TIMEOUT = 30.0
MIN_INTERVAL = 0.5  # seconds between requests — be polite

_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_last_fetch = 0.0


class DiyanetError(RuntimeError):
    pass


def _throttle() -> None:
    global _last_fetch
    wait = MIN_INTERVAL - (time.monotonic() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    _last_fetch = time.monotonic()


_PROFILES = ("chrome120", "chrome131", "safari17_0")
_MAX_ATTEMPTS = 2  # one retry with the next profile
_RETRY_BACKOFF = 1.0  # seconds between attempts
_profile_idx = 0  # sticky: profile that last succeeded


def _request(url: str, headers: dict, timeout: float = TIMEOUT):
    """GET with fingerprint rotation.

    Starts at the sticky profile (chrome120 on a fresh process), retries
    once with the next profile on HTTP 403/429 or a transport error, then
    returns the last response (so the caller raises the specific 403/429
    error) or raises a network error if every attempt failed at the
    transport.
    """
    global _profile_idx
    last_exc: Exception | None = None
    for k in range(_MAX_ATTEMPTS):
        profile = _PROFILES[(_profile_idx + k) % len(_PROFILES)]
        try:
            resp = _creq.get(url, impersonate=profile, headers=headers, timeout=timeout)
        except Exception as e:
            last_exc = e
            if k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            raise DiyanetError(f"network error fetching {url}: {e}") from e
        if resp.status_code in (403, 429):
            if k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            return resp
        _profile_idx = (_profile_idx + k) % len(_PROFILES)
        return resp
    raise DiyanetError(f"network error fetching {url}: {last_exc}") from last_exc


def _get_text(url: str) -> str:
    """GET a URL, return the decoded text body.

    Raises DiyanetError with a human-readable message for HTTP errors.
    """
    _throttle()
    headers = dict(_HEADERS)
    try:
        resp = _request(url, headers)
        status, text = resp.status_code, resp.text
    except Exception:
        # Fallback transport: plain requests with a browser UA.
        try:
            resp = _plain.get(url, headers={**headers, "User-Agent": _UA}, timeout=TIMEOUT)
            status, text = resp.status_code, resp.text
        except DiyanetError:
            raise
        except Exception as e:
            raise DiyanetError(f"network error fetching {url}: {e}") from e
    if status == 403:
        raise DiyanetError(
            "namazvakitleri.diyanet.gov.tr refused the request (HTTP 403, bot wall)"
            " — try again later"
        )
    if status == 429:
        raise DiyanetError(
            "namazvakitleri.diyanet.gov.tr rate-limited the request (HTTP 429)"
            " — try again later"
        )
    if status == 404:
        raise DiyanetError(f"namazvakitleri.diyanet.gov.tr has no page at {url} (HTTP 404)")
    if status != 200:
        raise DiyanetError(
            f"namazvakitleri.diyanet.gov.tr returned HTTP {status} for {url}"
        )
    return text


def _get_json(url: str) -> dict:
    """GET a URL, return the decoded JSON object."""
    import json

    text = _get_text(url)
    try:
        data = json.loads(text)
    except ValueError as e:
        raise DiyanetError(
            f"namazvakitleri.diyanet.gov.tr returned non-JSON for {url}: {text[:200]}"
        ) from e
    if not isinstance(data, dict):
        raise DiyanetError(f"unexpected JSON response for {url}: {str(data)[:200]}")
    return data


def fetch_place_page(url: str) -> str:
    """Fetch one place page (today + monthly table + qibla widget)."""
    return _get_text(url)


def fetch_reg_list(change_type: str, country_id: int = 2,
                   state_id: int | None = None, culture: str = "tr-TR") -> dict:
    """The site's own region-list JSON endpoint.

    change_type "country" -> provinces of a country (StateList);
    change_type "state" -> districts of a province (StateRegionList).
    """
    url = (
        f"{BASE}/{culture}/home/GetRegList"
        f"?ChangeType={change_type}&CountryId={country_id}&Culture={culture}"
    )
    if state_id is not None:
        url += f"&StateId={state_id}"
    data = _get_json(url)
    if data.get("Result") == "error":
        raise DiyanetError(
            f"GetRegList rejected the request ({url}) — bad ChangeType/CountryId/StateId?"
        )
    return data


def fetch_destination_url(country_name: str, state_name: str,
                          state_region_name: str, culture: str = "tr-TR") -> dict:
    """The site's own name->URL resolver (see module docstring: lenient).

    Returns the raw JSON {Result, Url, IlceId}. Callers MUST check that
    IlceId belongs to the requested province — the endpoint silently
    falls back to the province centre, or to Adana (9146), on bad input.
    """
    from urllib.parse import quote

    url = (
        f"{BASE}/Tr-tr/home/GetDestinationUrl"
        f"?CountryName={quote(country_name)}"
        f"&StateName={quote(state_name)}"
        f"&StateRegionName={quote(state_region_name)}"
        f"&Culture={culture}"
    )
    return _get_json(url)


def health_check() -> dict:
    """Two polite probes: the home page and the province list.

    Returns {"status": "ok"|"blocked"|"error", "http_status": int|None,
    "url": ..., "detail": ...}. Used by the `diyanet_health` tool
    and the daily smoke CI.
    """
    url = f"{BASE}/tr-TR"
    try:
        html = fetch_place_page(url)
        if "Namaz Vakitleri" not in html and "Prayer Times" not in html:
            return {
                "status": "error",
                "http_status": 200,
                "url": url,
                "detail": "home page returned 200 but no prayer-times content",
            }
        data = fetch_reg_list("country")
        states = data.get("StateList") or []
        if len(states) < 81:
            return {
                "status": "error",
                "http_status": 200,
                "url": url,
                "detail": f"province list returned only {len(states)} provinces",
            }
    except DiyanetError as e:
        msg = str(e)
        if "403" in msg:
            return {"status": "blocked", "http_status": 403, "url": url, "detail": msg}
        if "429" in msg:
            return {"status": "blocked", "http_status": 429, "url": url, "detail": msg}
        return {"status": "error", "http_status": None, "url": url, "detail": msg}
    return {"status": "ok", "http_status": 200, "url": url}
