"""Live tests: hit the real Diyanet prayer-times site (no key, read-only).

Kept small and polite (~0.5s between requests, one call per tool).
Assertions are date-independent (times are checked for shape, order
and cross-consistency, not for a frozen date).

Run with:  python -m pytest tests/test_live.py -v
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from diyanet_mcp.server import (  # noqa: E402
    diyanet_health,
    diyanet_list_districts,
    diyanet_list_provinces,
    diyanet_prayer_times,
    diyanet_qibla,
    diyanet_yearly_times,
)

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _parse(out: str) -> dict:
    return json.loads(out)


def _assert_times_shape(times: dict):
    assert set(times) == {"imsak", "gunes", "ogle", "ikindi", "aksam", "yatsi"}
    assert all(_TIME.match(v) for v in times.values())
    ordered = [times[k] for k in
               ("imsak", "gunes", "ogle", "ikindi", "aksam", "yatsi")]
    assert ordered == sorted(ordered), ordered  # times increase through the day


def test_live_provinces():
    out = _parse(diyanet_list_provinces())
    assert "error" not in out
    assert out["count"] == 81
    names = [p["name_tr"] for p in out["provinces"]]
    assert "ANKARA" in names and "İSTANBUL" in names and "İZMİR" in names
    ank = [p for p in out["provinces"] if p["name_tr"] == "ANKARA"][0]
    assert ank["id"] == 506


def test_live_provinces_query():
    out = _parse(diyanet_list_provinces(query="ank"))
    assert "error" not in out
    assert any(p["name_tr"] == "ANKARA" for p in out["provinces"])
    assert out["count"] >= 1


def test_live_districts_ankara():
    out = _parse(diyanet_list_districts("Ankara"))
    assert "error" not in out
    assert out["province"]["name_tr"] == "ANKARA"
    assert out["count"] == 17
    names = [d["name_tr"] for d in out["districts"]]
    # Diyanet lists only districts with their own timetable; urban
    # districts (Çankaya, Keçiören, …) are folded into central ANKARA.
    assert "ÇANKAYA" not in names
    assert "BEYPAZARI" in names and "AYAŞ" in names
    bala = [d for d in out["districts"] if d["name_tr"] == "BALA"][0]
    assert bala["url"].endswith("/bala-icin-namaz-vakti")


def test_live_districts_by_province_id():
    out = _parse(diyanet_list_districts("506", query="bala"))
    assert "error" not in out
    assert out["count"] == 1
    assert out["districts"][0]["name_tr"] == "BALA"


def test_live_prayer_times_ankara():
    out = _parse(diyanet_prayer_times("Ankara"))
    assert "error" not in out, out
    assert out["place"] == "Ankara"
    assert out["district"] == "ANKARA" and out["ilce_id"] == 9206
    assert out["date_miladi"] and out["date_hijri"]
    _assert_times_shape(out["times"])
    assert out["qibla_angle_deg"] == 155
    assert _TIME.match(out["qibla_time"])
    assert _TIME.match(out["astronomical_sunrise"])
    assert _TIME.match(out["astronomical_sunset"])


def test_live_prayer_times_bare_district_name_fails_cleanly():
    # A bare district name is treated as a province name; "Cankaya" is
    # no province, so this must fail cleanly with a hint, not crash.
    out = _parse(diyanet_prayer_times("Cankaya"))
    assert "error" in out
    assert "unknown province" in out["error"]


def test_live_prayer_times_folded_district():
    # Çankaya has no separate Diyanet timetable — the site folds it
    # into central Ankara. The tool must say so, not silently pretend.
    out = _parse(diyanet_prayer_times("Ankara/Çankaya"))
    assert "error" not in out, out
    assert out["district"] == "ANKARA"
    assert out["ilce_id"] == 9206
    assert out["requested_district"] == "Çankaya"
    assert "note" in out
    _assert_times_shape(out["times"])
    central = _parse(diyanet_prayer_times("Ankara"))
    assert central["times"] == out["times"]


def test_live_prayer_times_unknown_district_falls_back_transparently():
    # The site folds unknown district names to the province centre —
    # the tool follows the site but labels it, so a typo is visible
    # instead of silently returning the centre's times as the district's.
    out = _parse(diyanet_prayer_times("Ankara/Atlantis"))
    assert "error" not in out, out
    assert out["district"] == "ANKARA"
    assert out["requested_district"] == "Atlantis"
    assert "note" in out


def test_live_prayer_times_by_id():
    out = _parse(diyanet_prayer_times("9541"))
    assert "error" not in out, out
    assert out["place"] == "İstanbul"
    assert out["ilce_id"] == 9541
    _assert_times_shape(out["times"])
    assert 140 <= out["qibla_angle_deg"] <= 155


def test_live_prayer_times_english():
    tr = _parse(diyanet_prayer_times("Ankara"))
    en = _parse(diyanet_prayer_times("Ankara", lang="en"))
    assert "error" not in en, en
    assert en["times"] == tr["times"]
    assert en["qibla_angle_deg"] == tr["qibla_angle_deg"]


def test_live_yearly_times():
    out = _parse(diyanet_yearly_times("Ankara", limit=5))
    assert "error" not in out, out
    assert out["count"] == 5
    assert out["total_days"] == 365  # full calendar year, today-first
    first = out["days"][0]
    assert first["imsak"] == _parse(diyanet_prayer_times("Ankara"))["times"]["imsak"]
    assert first["date"] and first["hijri"]
    assert all(_TIME.match(d["yatsi"]) for d in out["days"])


def test_live_qibla():
    out = _parse(diyanet_qibla("İstanbul/Beylikdüzü"))
    assert "error" not in out, out
    assert out["place"] == "Beylikdüzü"
    assert out["qibla_angle_deg"] == 146
    assert _TIME.match(out["qibla_time"])


def test_live_unknown_place_errors_cleanly():
    out = _parse(diyanet_prayer_times("Atlantis"))
    assert "error" in out
    assert "unknown province" in out["error"]
    out2 = _parse(diyanet_list_districts("Atlantis"))
    assert "error" in out2


def test_live_health():
    out = _parse(diyanet_health())
    assert out["status"] == "ok", out
    assert out["http_status"] == 200
