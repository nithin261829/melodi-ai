"""Generates docs/architecture.svg: the Melo app, the Melodi AI server and the services they use.

Run: python3 docs/make_architecture.py docs/architecture.svg
"""

import sys
from html import escape

W, H = 1400, 1030
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
INK, SUB = "#1d1d27", "#555566"
PINK, PURPLE, BLUE, GREEN = "#ff3d6e", "#8b5cff", "#2f80ed", "#14a37f"

out: list[str] = []


def text(x, y, s, size=14, weight="normal", color=INK, anchor="start"):
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(s)}</text>')


def rect(x, y, w, h, fill, stroke, r=14, sw=2):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def box(x, y, w, h, title, lines, fill="#ffffff", stroke="#c9c9d6"):
    rect(x, y, w, h, fill, stroke, r=10, sw=1.5)
    text(x + 14, y + 27, title, 16.5, "700")
    for i, line in enumerate(lines):
        text(x + 14, y + 49 + i * 18, line, 13.5, color=SUB)


def arrow(points, color=INK):
    d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(points))
    head = "head-green" if color == GREEN else "head"
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.2" marker-end="url(#{head})"/>')


out.append(f'<rect width="{W}" height="{H}" rx="18" fill="#fbfbfd"/>')
text(W / 2, 48, "Melo + Melodi AI: system architecture", 26, "800", anchor="middle")

# Every block in the three columns has the same height.
BH, GAP = 76, 12
TOP = 152


def row(i):
    return TOP + i * (BH + GAP) + BH / 2


# Column 1: the iPhone app
rect(30, 80, 420, 610, "#fff3f6", PINK)
text(50, 114, "iPhone · Melo app", 21, "800", PINK)
text(50, 136, "React Native · Expo · TypeScript · Swift", 13.5, color=SUB)
app = [
    ("Screens (Expo Router)", ["Home · Melodi AI tab · Search · Library"]),
    ("Melodi client · melodi.ts", ["mix on open · reuse for 30 min"]),
    ("Player · expo-audio", ["queue · lock screen · Dynamic Island"]),
    ("Native Swift modules", ["RemoteCommands · WebCookies"]),
    ("On-device storage", ["likes · recents · downloads · Keychain"]),
    ("Taste summary", ["top artists from likes and recent plays"]),
]
for i, (title, lines) in enumerate(app):
    box(45, TOP + i * (BH + GAP), 390, BH, title, lines)

# Column 2: the Melodi AI server
rect(600, 80, 400, 610, "#f4f0ff", PURPLE)
text(620, 114, "Melodi AI server", 21, "800", PURPLE)
text(620, 136, "Python · FastAPI · Anthropic SDK", 13.5, color=SUB)
steps = [
    ("1  Understand", "Claude: moods, keywords, energy", True),
    ("2  Narrow", "code: 3,364 playlists → ~150", False),
    ("3  Pick", "Claude: 3–6 playlists, numbers checked", True),
    ("4  Collect", "code: real songs + radio from likes", False),
    ("5  Score", "code: merge duplicates, rank, top 40", False),
    ("6  Sequence", "Claude: order, title, reason per song", True),
]
for i, (title, line, ai) in enumerate(steps):
    box(615, TOP + i * (BH + GAP), 370, BH, title, [line], "#ebe3ff" if ai else "#ffffff", PURPLE if ai else BLUE)

# Column 3: cloud services
rect(1080, 80, 290, 610, "#eef5ff", BLUE)
text(1100, 114, "Cloud services", 21, "800", BLUE)
text(1100, 136, "used by the server or the app", 13.5, color=SUB)
for slot, title, lines in [
    (0, "Claude API", ["Haiku 5.5 · structured outputs"]),
    (2, "YouTube Music", ["curated playlists · radio"]),
    (4, "YouTube InnerTube", ["search · HLS audio (playback)"]),
]:
    box(1095, TOP + slot * (BH + GAP), 260, BH, title, lines)

# Arrows between columns, at block centres
arrow([(437, row(1) - 10), (612, row(1) - 10)])
text(525, row(1) - 22, "labels + taste", 13, "700", anchor="middle")
arrow([(612, row(1) + 14), (440, row(1) + 14)])
text(525, row(1) + 34, "25 songs + reasons", 13, "700", anchor="middle")
arrow([(987, row(0)), (1092, row(0))])
text(1039, row(0) - 10, "3 calls", 13, "700", anchor="middle")
arrow([(987, row(3)), (1040, row(3)), (1040, row(2)), (1092, row(2))])
text(1012, row(3) + 20, "fetch", 13, "700", anchor="middle")
arrow([(437, row(2)), (520, row(2)), (520, 712), (1225, 712), (1225, TOP + 4 * (BH + GAP) + BH + 4)])
text(820, 706, "the app streams audio from YouTube", 13, "700", anchor="middle")

# Location & context: everything location-related in one box, tiles of equal size
LX, LY, LW, LH = 30, 740, 1340, 190
rect(LX, LY, LW, LH, "#ecfaf5", GREEN)
text(LX + 20, LY + 34, "Location & context · sensed on the phone (context.ts)", 21, "800", GREEN)
text(LX + 20, LY + 56, "Only these labels leave the phone. GPS never does.", 13.5, color=SUB)
tiles = [
    ("Time & sunset", ["daypart · golden hour", "from the phone clock"]),
    ("Weather", ["Open-Meteo (free, no key)", "location rounded to ~1 km"]),
    ("Movement", ["still · walking · driving", "from GPS speed"]),
    ("City & country", ["reverse geocode on device", "picks the regional catalogue"]),
]
TW = (LW - 40 - 3 * 16) / 4
for i, (title, lines) in enumerate(tiles):
    box(LX + 20 + i * (TW + 16), LY + 74, TW, 96, title, lines, "#ffffff", GREEN)
arrow([(240, LY - 2), (240, 694)], GREEN)
text(252, LY - 12, "context labels", 13, "700", GREEN)

# Legend
ly = 965
rect(30, ly, 22, 16, "#ebe3ff", PURPLE, r=4, sw=1.5)
text(62, ly + 13, "Claude step (structured output, checked by code)", 13.5)
rect(430, ly, 22, 16, "#ffffff", BLUE, r=4, sw=1.5)
text(462, ly + 13, "Plain code step (deterministic, unit-tested)", 13.5)
rect(800, ly, 22, 16, "#ecfaf5", GREEN, r=4, sw=1.5)
text(832, ly + 13, "Location & context (on the phone)", 13.5)
text(30, ly + 46, "The API key stays on the server · requests need the app token · nothing is stored", 13.5, color=SUB)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">
<defs>
<marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>
<marker id="head-green" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{GREEN}"/></marker>
</defs>
{chr(10).join(out)}
</svg>
'''
open(sys.argv[1], "w").write(svg)
