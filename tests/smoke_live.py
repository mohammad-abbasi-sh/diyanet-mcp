"""Daily smoke probe (CI): prayer times + health must answer 200.

Run with:  python tests/smoke_live.py
Exit 0 = site reachable, exit 1 = blocked/error (visible in CI).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from diyanet_mcp.server import diyanet_health, diyanet_prayer_times  # noqa: E402


def main() -> int:
    try:
        out = json.loads(diyanet_prayer_times("Ankara"))
        assert "error" not in out, out.get("error")
        t = out["times"]
        assert t["imsak"] < t["gunes"] < t["ogle"] < t["ikindi"] < t["aksam"] < t["yatsi"]
        health = json.loads(diyanet_health())
        assert health["status"] == "ok", health
        print(
            f"SMOKE OK: Ankara {out['date_miladi']} imsak={t['imsak']} "
            f"aksam={t['aksam']} qibla={out['qibla_angle_deg']}°"
        )
        return 0
    except Exception as e:  # noqa: BLE001 — smoke must report, not crash
        print(f"SMOKE FAIL: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
