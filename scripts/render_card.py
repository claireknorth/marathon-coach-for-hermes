#!/usr/bin/env python3
"""
Marathon Morning Check-in Card Renderer
Produces a beautiful terminal-native card using Unicode box-drawing + emoji.
Stdlib only — no dependencies. Outputs plain text; on CLI it renders inline,
on Telegram it goes in a ``` block.

Usage:
  echo '{"date":"July 9, 2026","week_n":4,...}' | python3 scripts/render_card.py
  python3 scripts/render_card.py path/to/card.json
"""

import json, sys, os
from datetime import datetime

# ── Layout constants ──────────────────────────────────────────────────
W = 54  # card width in chars


def hr(char="─"):
    return char * W


def row(label, value, icon=""):
    """Two-column row: icon label ………… value"""
    lhs = f"{icon} {label}" if icon else label
    dots = W - len(lhs) - len(value) - 2
    if dots < 1:
        dots = 1
    return f"  {lhs}  {'·' * dots}  {value}"


def banner(text, width=W):
    """Generate a simple ASCII banner using a block font."""
    # Mini block-letters (5x3 pixel map per char, fits in ~5 lines)
    CHARS = {}
    # Define a simple 5x4 block font for A-Z, 0-9
    glyphs = {
        "A": [" ██ ", "█  █", "████", "█  █", "█  █"],
        "B": ["███ ", "█  █", "███ ", "█  █", "███ "],
        "C": [" ███", "█   ", "█   ", "█   ", " ███"],
        "D": ["███ ", "█  █", "█  █", "█  █", "███ "],
        "E": ["████", "█   ", "███ ", "█   ", "████"],
        "F": ["████", "█   ", "███ ", "█   ", "█   "],
        "G": [" ███", "█   ", "█ ██", "█  █", " ███"],
        "H": ["█  █", "█  █", "████", "█  █", "█  █"],
        "I": ["███", " █ ", " █ ", " █ ", "███"],
        "J": ["  ██", "   █", "   █", "█  █", " ██ "],
        "K": ["█  █", "█ █ ", "██  ", "█ █ ", "█  █"],
        "L": ["█   ", "█   ", "█   ", "█   ", "████"],
        "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
        "N": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
        "O": [" ██ ", "█  █", "█  █", "█  █", " ██ "],
        "P": ["███ ", "█  █", "███ ", "█   ", "█   "],
        "Q": [" ██ ", "█  █", "█  █", "█ ██", " ██▄"],
        "R": ["███ ", "█  █", "███ ", "█ █ ", "█  █"],
        "S": [" ███", "█   ", " ██ ", "   █", "███ "],
        "T": ["████", " █  ", " █  ", " █  ", " █  "],
        "U": ["█  █", "█  █", "█  █", "█  █", " ██ "],
        "V": ["█  █", "█  █", "█  █", " ██ ", "  █ "],
        "W": ["█   █", "█   █", "█ █ █", "██ ██", "█   █"],
        "X": ["█  █", " ██ ", "  █ ", " ██ ", "█  █"],
        "Y": ["█  █", " ██ ", "  █ ", "  █ ", "  █ "],
        "Z": ["████", "  █ ", " █  ", "█   ", "████"],
        " ": ["    ", "    ", "    ", "    ", "    "],
    }
    for d in "0123456789":
        glyphs[d] = glyphs.get(d, [" ??? "] * 5)

    chars = [c.upper() for c in text if c.upper() in glyphs]
    lines = []
    for row_i in range(5):
        line = ""
        for c in chars:
            line += glyphs[c][row_i] + " "
        lines.append(line.rstrip())
    return "\n".join(lines)


def dew_label(dp):
    if dp is None:
        return "—"
    dp = float(dp)
    if dp < 55:
        return "dry ✨"
    elif dp < 60:
        return "comfy 🙂"
    elif dp < 65:
        return "noticeable 💧"
    elif dp < 70:
        return "hard 😓"
    else:
        return "oppressive 🥵"


def rain_label(pct):
    if pct is None:
        return "—"
    pct = int(pct)
    if pct < 10:
        return "clear ☀️"
    elif pct < 30:
        return "slight 🌤️"
    elif pct < 60:
        return "likely 🌧️"
    else:
        return "wet ⛈️"


def wind_label(mph):
    if mph is None:
        return "—"
    mph = float(mph)
    if mph < 8:
        return "calm 🍃"
    elif mph < 15:
        return "breezy 🌬️"
    else:
        return "gusty 💨"


def session_emoji(title):
    t = (title or "").lower()
    if "quality" in t or "tempo" in t or "interval" in t:
        return "⚡"
    if "long run" in t or "long" in t:
        return "🏃‍♀️"
    if "hill" in t:
        return "⛰️"
    if "strength" in t or "core" in t or "legs" in t:
        return "🏋️"
    if "rest" in t or "off" in t:
        return "😴"
    if "easy" in t or "run" in t:
        return "🏃"
    return "📋"


def render_card(data):
    """
    data dict keys:
      date_long, week_n, week_total, session_title, session_sub,
      wx_location, temp, feels, dew, rain_pct, wind_mph,
      optimal_title, optimal_sub, pace_note, fuel_note
    """
    d = data
    icon = session_emoji(d.get("session_title", ""))
    date_str = d.get("date_long", datetime.now().strftime("%A, %B %d"))
    week_str = f"Week {d.get('week_n','?')}/{d.get('week_total','20')}"

    lines = []
    # ── Top border ──
    lines.append(f"╔{'═' * W}╗")

    # ── Banner ──
    lines.append(f"║  {'MARATHON CHECK-IN':^{W - 2}}  ║")
    lines.append(f"║  {date_str:^{W - 2}}  ║")
    lines.append(f"╠{'═' * W}╣")

    # ── Session ──
    lines.append(f"║  {icon}  TODAY: {d.get('session_title', 'Rest Day'):<{W - 13}} ║")
    sub = d.get("session_sub", "")
    if sub:
        lines.append(f"║  {sub:^{W - 2}}  ║")
    lines.append(f"║  {week_str:^{W - 2}}  ║")
    lines.append(f"╟{hr('─')}╢")

    # ── Weather ──
    loc = d.get("wx_location", "NYC")
    temp = d.get("temp", "—")
    feels = d.get("feels", "—")
    dew = d.get("dew", None)
    dew_str = f"{dew}°F" if dew else "—"
    rain = d.get("rain_pct", None)
    rain_str = f"{rain}%" if rain is not None else "—"
    wind = d.get("wind_mph", None)
    wind_str = f"{wind}mph" if wind is not None else "—"

    lines.append(f"║  {'🌤  WEATHER  —  ' + loc:<{W - 3}} ║")
    lines.append(f"║  🌡  Temp: {temp}°F     Feels: {feels}°F     Dew: {dew_str} {dew_label(dew):<14} ║")
    lines.append(f"║  🌧  Rain: {rain_str} {rain_label(rain):<12}  Wind: {wind_str} {wind_label(wind):<12} ║")
    lines.append(f"╟{hr('─')}╢")

    # ── Timing ──
    lines.append(f"║  ⏰  {d.get('optimal_title', 'Run by 7:00 AM'):<{W - 8}} ║")
    opt_sub = d.get("optimal_sub", "")
    if opt_sub:
        lines.append(f"║  {opt_sub:^{W - 2}}  ║")
    lines.append(f"╟{hr('─')}╢")

    # ── Pace & Fuel ──
    pace = d.get("pace_note", "")
    fuel = d.get("fuel_note", "")
    if pace:
        lines.append(f"║  👟  {pace:<{W - 8}} ║")
    if fuel:
        lines.append(f"║  🍌  {fuel:<{W - 8}} ║")
    if pace or fuel:
        lines.append(f"╟{hr('─')}╢")

    # ── Bottom border ──
    lines.append(f"╚{'═' * W}╝")

    # ── Coaching note placeholder ──
    lines.append("")
    lines.append("💬  COACH'S NOTE  ───────────────────────────────────────")
    lines.append("")

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        with open(sys.argv[1]) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)
    print(render_card(data))
