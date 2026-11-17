# diyanet-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/diyanet-mcp

Unofficial **read-only** MCP server for **Diyanet prayer times** (namazvakitleri.diyanet.gov.tr) — the **official published timetable** of the Presidency of Religious Affairs (Diyanet İşleri Başkanlığı) for Türkiye: today's 6 prayer times for any of the **81 provinces and their districts**, the full-year table with Miladi + Hijri dates, and qibla angle/time plus astronomical sunrise/sunset per place.

> Part of the "Turkey MCP factory". Not affiliated with Diyanet. Data comes from Diyanet's own prayer-times site (server-rendered pages + its region-list JSON) — no login, no API key, read-only. This serves the **official timetable**, not a computed approximation: generic prayer-times servers calculate times (Aladhan method 13 "Diyanet" can differ from the official times by a minute or two) and the only other Diyanet-based tool covers just 20 cities.

## For AI agents

- **Places**: a province (`"Ankara"`), a province/district (`"İstanbul/Beylikdüzü"`, `"Ankara/Çankaya"`) or a numeric district id (`"9541"` for İstanbul). A province alone returns its central district.
- **Names are Turkish-insensitive**: `"Cankaya"` finds `"ÇANKAYA"`, `"istanbul"` finds `"İSTANBUL"`. Both Turkish and English names work.
- **Folded districts**: Diyanet publishes separate timetables only for some districts — a province's urban districts (e.g. Ankara's Çankaya) are folded into the central district. The tools resolve them to the central timetable and say so in the response (`requested_district` + `note`); the served district is always reported.
- **Languages**: `lang` is `"tr"` (default), `"en"`, `"ar"`, `"de"` or `"fr"` — the site's own language versions. Times are identical across languages.
- **Yearly table**: `diyanet_yearly_times` returns the full calendar year (365 rows) — the coming month first, then 1 January through the rest of the year. Each row carries its Miladi + Hijri date.
- Every response carries `fetched_at` (UTC) and `source: namazvakitleri.diyanet.gov.tr`. Times are Europe/Istanbul local time.

## Install

```bash
uvx diyanet-mcp
```

Or add to your MCP client config (e.g. Claude Desktop):

```json
{
  "mcpServers": {
    "diyanet": {
      "command": "uvx",
      "args": ["diyanet-mcp"]
    }
  }
}
```

## Tools

| Tool | What it does |
| --- | --- |
| `diyanet_prayer_times` | Today's 6 times (imsak, gunes, ogle, ikindi, aksam, yatsi) + Miladi/Hijri dates + qibla angle/time + astronomical sunrise/sunset for a place |
| `diyanet_yearly_times` | Full-year table: one row per day (Miladi + Hijri + 6 times), 365 rows (limit 1–365) |
| `diyanet_list_provinces` | The 81 provinces with Diyanet ids and Turkish + English names (optional substring filter) |
| `diyanet_list_districts` | Districts of one province (by name or id) with ids, names and page URLs |
| `diyanet_qibla` | Qibla angle (degrees from north), qibla time, astronomical sunrise/sunset for a place |
| `diyanet_health` | Is Diyanet's prayer-times site reachable right now? |

## Example

İstanbul, 17 November 2026 (8 Cemaziyelahir 1448):

```json
{ "place": "İstanbul", "ilce_id": 9541,
  "times": { "imsak": "06:18", "gunes": "07:47", "ogle": "12:54",
             "ikindi": "15:28", "aksam": "17:51", "yatsi": "19:15" },
  "qibla_angle_deg": 147, "qibla_time": "11:01" }
```

## Caveats

- Times are Diyanet's official timetable — verify on namazvakitleri.diyanet.gov.tr before acting on them.
- Diyanet lists only 17 districts for Ankara (its urban districts share the central timetable); the tools report the district actually served.
- The yearly table's row order is the page's order (coming month first, then 1 January onward) — each row carries its own date, so sort by date if you need chronology.
- Transport uses Chrome TLS impersonation with a plain-requests fallback; requests are spaced ~0.5s apart.

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/python -m pytest tests/test_places.py -v   # offline, recorded fixtures
.venv/bin/python -m pytest tests/test_live.py -v     # live, against namazvakitleri.diyanet.gov.tr
.venv/bin/python tests/smoke_live.py                 # daily CI probe
```

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
