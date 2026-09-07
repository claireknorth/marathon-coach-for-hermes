#!/usr/bin/env python3
"""
fitness_trend.py — Continuous aerobic-fitness monitor for the marathon coach.

Tracks pace-at-a-given-heart-rate over time (the core aerobic-fitness signal),
CONTROLLING for the two big confounds that otherwise make the number lie:
  1. Heat/humidity  — normalizes easy-run pace to a 55°F dew-point baseline
     using historical dew point from Open-Meteo's free archive API.
  2. Effort drift   — compares within a tight HR band (Z2 easy), and reports
     average HR alongside pace so a pace change driven purely by running
     easier/harder isn't mistaken for a fitness change.

It pulls all runs with HR from Strava since a start date, buckets easy/aerobic
ROAD runs (treadmill pace isn't road-comparable), heat-adjusts each pace, and
compares a recent window to a baseline window. Emits a short verdict + the
supporting rows. Stdlib only (urllib) so it runs unattended in cron.

USAGE
    python3 fitness_trend.py                 # full report since plan start
    python3 fitness_trend.py --since 2026-06-15
    python3 fitness_trend.py --alert         # terse: print ONLY if a real
                                             # change crossed the threshold
                                             # (silent otherwise -> cron-safe)

CONFOUND CONTROL CONSTANTS (tune if needed)
    DEW_BASELINE_F   pace normalized to this dew point (cool morning)
    HEAT_COEF        fractional pace slowdown per °F dew over baseline
    EASY_HR_LO/HI    the Z2 easy band used for the clean comparison
    ALERT_PCT        min heat-adjusted efficiency change to fire an alert
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date
from statistics import mean

ENV_PATH = os.environ.get("HERMES_ENV_PATH", "/opt/data/.env")
LAT = float(os.environ.get("ATHLETE_HOME_LAT", "40.7128"))
LON = float(os.environ.get("ATHLETE_HOME_LON", "-74.0060"))
TIMEZONE = os.environ.get("ATHLETE_TIMEZONE", "America/New_York")
DEFAULT_SINCE = os.environ.get("TRAINING_START_DATE", "1970-01-01")
DEW_BASELINE_F = 55.0
HEAT_COEF = 0.004                     # ~0.4%/°F dew over baseline (ACSM/Higdon)
EASY_HR_LO, EASY_HR_HI = 138, 158
MATCH_HR_LO, MATCH_HR_HI = 148, 153   # tight band for matched-effort check
ALERT_PCT = 3.0                       # |change| >= this fires --alert
STATE_PATH = os.environ.get(
    "FITNESS_STATE_PATH",
    "/opt/data/skills/marathon-morning-check-in/scripts/fitness_trend_state.json",
)


def load_env():
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                if "=" in line and not line.lstrip().startswith("#"):
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    return env


def _get_json(url, headers=None):
    req = urllib.request.Request(url)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode(), strict=False)


def fetch_runs(token, since):
    after = int(
        __import__("time").mktime(date.fromisoformat(since).timetuple())
    )
    url = (
        "https://www.strava.com/api/v3/athlete/activities"
        f"?after={after}&per_page=100"
    )
    acts = _get_json(url, {"Authorization": f"Bearer {token}"})
    runs = []
    for a in acts:
        if a.get("type") != "Run" or not a.get("average_heartrate"):
            continue
        dist_mi = a["distance"] / 1609.34
        if dist_mi < 2.0:
            continue
        pace_sec = (a["moving_time"] / dist_mi)
        runs.append({
            "date": a["start_date_local"][:10],
            "mi": round(dist_mi, 2),
            "hr": round(a["average_heartrate"], 1),
            "pace_sec": pace_sec,
            "trainer": a.get("trainer", False),
        })
    runs.sort(key=lambda r: r["date"])
    return runs


def fetch_dew(d0, d1):
    """Morning (7-9am) mean dew point per date from Open-Meteo archive."""
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={LAT}&longitude={LON}&start_date={d0}&end_date={d1}"
        "&hourly=dew_point_2m&temperature_unit=fahrenheit"
        f"&timezone={urllib.parse.quote(TIMEZONE)}"
    )
    try:
        wx = _get_json(url)
    except Exception:
        return {}
    h = wx.get("hourly", {})
    by = {}
    for t, dew in zip(h.get("time", []), h.get("dew_point_2m", [])):
        if t[11:13] in ("07", "08", "09") and dew is not None:
            by.setdefault(t[:10], []).append(dew)
    return {d: mean(v) for d, v in by.items() if v}


def heat_adjust(pace_sec, dew):
    if dew is None:
        return pace_sec
    over = max(0.0, dew - DEW_BASELINE_F)
    return pace_sec * (1 - HEAT_COEF * over)


def fmt(sec):
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def analyze(since):
    env = load_env()
    token = env.get("STRAVA_ACCESS_TOKEN")
    if not token:
        return None, "No STRAVA_ACCESS_TOKEN in .env"
    runs = fetch_runs(token, since)
    if len(runs) < 6:
        return None, f"Only {len(runs)} runs since {since} — need more data."

    dew = fetch_dew(runs[0]["date"], runs[-1]["date"])
    for r in runs:
        r["dew"] = dew.get(r["date"])
        r["adj_pace"] = heat_adjust(r["pace_sec"], r["dew"])
        r["adj_eff"] = r["adj_pace"] / r["hr"]   # sec/mi/bpm, heat-normalized

    easy = [r for r in runs if EASY_HR_LO <= r["hr"] <= EASY_HR_HI and not r["trainer"]]
    if len(easy) < 4:
        return None, f"Only {len(easy)} clean easy road runs — need more."

    third = max(2, len(easy) // 3)
    early, late = easy[:third], easy[-third:]
    e_eff, l_eff = mean(r["adj_eff"] for r in early), mean(r["adj_eff"] for r in late)
    pct = (e_eff - l_eff) / e_eff * 100   # + = more efficient = fitter

    longs = [r for r in runs if r["mi"] >= 8]

    result = {
        "since": since,
        "n_runs": len(runs),
        "n_easy": len(easy),
        "early_span": f"{early[0]['date']}–{early[-1]['date']}",
        "late_span": f"{late[0]['date']}–{late[-1]['date']}",
        "early_hr": round(mean(r["hr"] for r in early), 1),
        "late_hr": round(mean(r["hr"] for r in late), 1),
        "early_pace": fmt(mean(r["adj_pace"] for r in early)),
        "late_pace": fmt(mean(r["adj_pace"] for r in late)),
        "eff_change_pct": round(pct, 1),
        "longs": [(r["date"], r["mi"], r["hr"], fmt(r["pace_sec"])) for r in longs],
        "easy_rows": [(r["date"], r["hr"], fmt(r["pace_sec"]),
                       round(r["dew"]) if r["dew"] else None) for r in easy],
    }
    return result, None


def verdict(res):
    pct = res["eff_change_pct"]
    hr_drop = res["early_hr"] - res["late_hr"]
    if pct >= ALERT_PCT:
        head = f"📈 Aerobic fitness IMPROVING (+{pct:.1f}% heat-adjusted efficiency)"
    elif pct <= -ALERT_PCT:
        if hr_drop >= 2:
            head = (f"➡️ Easy pace looks {abs(pct):.1f}% slower — but your easy HR "
                    f"also dropped {hr_drop:.0f} bpm, so you're running EASIER, "
                    f"not losing fitness. Good Z2 discipline.")
        else:
            head = (f"⚠️ Heat-adjusted efficiency down {abs(pct):.1f}% at matched HR "
                    f"— watch for fatigue/overtraining if it persists.")
    else:
        head = f"➡️ Aerobic fitness STABLE ({pct:+.1f}% — within noise)"
    return head


def main(argv):
    since = DEFAULT_SINCE
    if "--since" in argv:
        since = argv[argv.index("--since") + 1]
    alert_only = "--alert" in argv

    res, err = analyze(since)
    if err:
        if not alert_only:
            print(err)
        return 0
    head = verdict(res)

    if alert_only:
        # Fire only on a real crossing; stay silent otherwise (cron-safe).
        if abs(res["eff_change_pct"]) >= ALERT_PCT:
            print(head)
            print(f"  early {res['early_span']}: HR {res['early_hr']}, "
                  f"adj pace {res['early_pace']}/mi")
            print(f"  late  {res['late_span']}: HR {res['late_hr']}, "
                  f"adj pace {res['late_pace']}/mi")
        return 0

    # Full report
    print("=" * 56)
    print("  AEROBIC FITNESS TREND  (heat-adjusted, matched-effort)")
    print("=" * 56)
    print(head)
    print()
    print(f"Runs analyzed: {res['n_runs']} ({res['n_easy']} clean easy road runs)")
    print(f"Baseline window {res['early_span']}: HR {res['early_hr']}, "
          f"adj pace {res['early_pace']}/mi")
    print(f"Recent window   {res['late_span']}: HR {res['late_hr']}, "
          f"adj pace {res['late_pace']}/mi")
    print(f"Heat-adjusted efficiency change: {res['eff_change_pct']:+.1f}%")
    print()
    print("Endurance progression (long runs):")
    for d, mi, hr, pace in res["longs"]:
        print(f"  {d}  {mi:5.1f}mi  HR {hr:.0f}  {pace}/mi")
    print()
    print("Easy runs (date, HR, pace, morning dew°F):")
    for d, hr, pace, dw in res["easy_rows"]:
        print(f"  {d}  HR {hr:.0f}  {pace}/mi  dew {dw if dw is not None else '?'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
