"""Offline tests: parse recorded Diyanet fixtures (no network).

Fixtures (recorded live 2026-11-17, Google Maps key redacted):
- ankara-today-tr.html / ankara-today-en.html: the Ankara place page
  (today widget + monthly table + qibla cells), tr-TR and en-US.
- reglist-provinces.json: GetRegList ChangeType=country (81 provinces).
- reglist-ankara-districts.json: GetRegList ChangeType=state, StateId=506.

Run with:  python -m pytest tests/test_places.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from diyanet_mcp import places as P  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8", errors="ignore")


def _json(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ folding

def test_fold_turkish_insensitive():
    assert P.fold("ÇANKAYA") == "cankaya"
    assert P.fold("Cankaya") == "cankaya"
    assert P.fold("İSTANBUL") == "istanbul"
    assert P.fold("İstanbul") == "istanbul"
    assert P.fold("  Şanlıurfa ") == "sanliurfa"


def test_culture_for():
    assert P.culture_for("tr") == "tr-TR"
    assert P.culture_for("en") == "en-US"
    assert P.culture_for("ar") == "ar-SA"
    assert P.culture_for("de") == "de-DE"
    assert P.culture_for("fr") == "fr-FR"
    try:
        P.culture_for("xx")
    except ValueError as e:
        assert "lang must be one of" in str(e)
    else:
        raise AssertionError("expected ValueError for lang='xx'")


# ------------------------------------------------------------------ regions

def test_parse_provinces():
    rows = P.parse_provinces(_json("reglist-provinces.json"))
    assert len(rows) == 81
    by_id = {r["id"]: r for r in rows}
    assert by_id[506]["name_tr"] == "ANKARA"
    assert by_id[506]["name_en"] == "ANKARA"
    ist = [r for r in rows if r["name_tr"] == "İSTANBUL"]
    assert len(ist) == 1 and ist[0]["name_en"] == "ISTANBUL"
    assert all(r["id"] and r["name_tr"] for r in rows)


def test_parse_districts_ankara():
    rows = P.parse_districts(_json("reglist-ankara-districts.json"))
    assert len(rows) == 17
    by_id = {r["id"]: r for r in rows}
    assert by_id[9206]["name_tr"] == "ANKARA"
    assert by_id[9206]["url"] == "/tr-TR/9206/ankara-icin-namaz-vakti"
    assert by_id[9205]["name_tr"] == "AKYURT"
    names = [r["name_tr"] for r in rows]
    # Diyanet lists only districts with their own timetable — Ankara's
    # urban districts (Çankaya, Keçiören, …) are NOT here; the site
    # folds them into central ANKARA (see GetDestinationUrl fallback).
    assert "ÇANKAYA" not in names and "KEÇİÖREN" not in names
    assert "BEYPAZARI" in names and "ÇAMLIDERE" in names
    assert "CUBUK" in names  # site data itself is ASCII-folded here
    assert all(r["url"].startswith("/tr-TR/") for r in rows)


# ------------------------------------------------------------------ place page

def test_parse_today_times_tr():
    times = P.parse_today_times(_read("ankara-today-tr.html"))
    assert times == {
        "imsak": "06:02", "gunes": "07:28", "ogle": "12:38",
        "ikindi": "15:15", "aksam": "17:39", "yatsi": "19:00",
    }


def test_parse_today_times_en_matches_tr():
    tr = P.parse_today_times(_read("ankara-today-tr.html"))
    en = P.parse_today_times(_read("ankara-today-en.html"))
    assert tr == en


def test_parse_widget_cells_tr():
    cells = P.parse_widget_cells(_read("ankara-today-tr.html"))
    assert len(cells) == 10, cells
    assert [v for _, v in cells[:6]] == [
        "06:02", "07:28", "12:38", "15:15", "17:39", "19:00",
    ]
    assert cells[6] == ("Kıble Açısı", "155")
    assert cells[7] == ("Kıble Zamanı", "11:20")
    assert cells[8][1] == "07:35"  # Astronomik Güneş Doğuş
    assert cells[9][1] == "17:32"  # Astronomik Güneş Batış


def test_parse_widget_cells_en():
    cells = P.parse_widget_cells(_read("ankara-today-en.html"))
    assert len(cells) == 10
    assert cells[6] == ("Qibla Angle", "155")
    assert cells[7] == ("Qibla Time", "11:20")


def test_parse_qibla_tr():
    q = P.parse_qibla(_read("ankara-today-tr.html"))
    assert q["qibla_angle_deg"] == 155
    assert q["qibla_time"] == "11:20"
    assert q["astronomical_sunrise"] == "07:35"
    assert q["astronomical_sunset"] == "17:32"
    assert q["times"]["imsak"] == "06:02"


def test_parse_times_table_tr():
    rows = P.parse_times_table(_read("ankara-today-tr.html"))
    # Full calendar year 2026 (365 days). Page order: the coming month
    # first (17 Nov -> 17 Dec), then 1 Jan -> 16 Nov (fixture frozen
    # 2026-11-17).
    assert len(rows) == 365, len(rows)
    first, last = rows[0], rows[-1]
    assert first["date"] == "17 Kasım 2026 Salı"
    assert first["hijri"] == "8 Cemaziyelahir 1448"
    assert first["imsak"] == "06:02" and first["yatsi"] == "19:00"
    assert rows[30]["date"] == "17 Aralık 2026 Perşembe"
    assert rows[31]["date"] == "01 Ocak 2026 Perşembe"
    assert last["date"] == "31 Aralık 2026 Perşembe"
    assert len({r["date"] for r in rows}) == 365  # all distinct days
    assert all(set(r) == {
        "date", "hijri", "imsak", "gunes", "ogle",
        "ikindi", "aksam", "yatsi",
    } for r in rows)


def test_parse_times_table_en():
    rows = P.parse_times_table(_read("ankara-today-en.html"))
    assert len(rows) == 365
    assert rows[0]["imsak"] == "06:02"
    assert rows[0]["hijri"] == "8 Cemaziyelahir 1448"
    assert rows[0]["date"] == "17.11.2026"


def test_parse_place_page_tr():
    parsed = P.parse_place_page(_read("ankara-today-tr.html"))
    assert parsed["place"] == "Ankara"
    assert parsed["today"]["date"] == "17 Kasım 2026 Salı"
    assert parsed["today"]["hijri"] == "8 Cemaziyelahir 1448"
    assert parsed["times_today"]["aksam"] == "17:39"
    assert parsed["qibla_angle_deg"] == 155
    assert len(parsed["table"]) == 365


def test_parse_place_title_en():
    assert P.parse_place_title(_read("ankara-today-en.html")) == "Ankara"


# ------------------------------------------------------------------ resolution

def test_resolve_numeric_id_needs_no_network():
    res = P.resolve_place("9541")
    assert res["ilce_id"] == 9541
    assert res["url"] == (
        "https://namazvakitleri.diyanet.gov.tr/tr-TR/9541/icin-namaz-vakti"
    )
    res_en = P.resolve_place("9541", lang="en")
    assert res_en["url"] == (
        "https://namazvakitleri.diyanet.gov.tr/en-US/9541/icin-namaz-vakti"
    )


def test_resolve_bad_place_format():
    for bad in ["", "A/B/C", "   "]:
        try:
            P.resolve_place(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")
