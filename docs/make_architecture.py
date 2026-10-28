"""Generates the Melo + Melodi AI architecture diagram as a standalone SVG."""
import sys
from html import escape

W, H = 1400, 900
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
INK, SUB = "#1d1d27", "#555566"
PINK, PURPLE, BLUE = "#ff3d6e", "#8b5cff", "#2f80ed"

out: list[str] = []


def text(x, y, s, size=14, weight="normal", color=INK, anchor="start"):
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(s)}</text>')


def rect(x, y, w, h, fill, stroke, r=14, sw=2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')


def box(x, y, w, h, title, lines, fill="#ffffff", stroke="#c9c9d6"):
    rect(x, y, w, h, fill, stroke, r=10, sw=1.5)
    text(x + 14, y + 26, title, 16.5, "700")
    for i, line in enumerate(lines):
        text(x + 14, y + 47 + i * 18, line, 13.5, color=SUB)


def arrow(x1, y1, x2, y2, color=INK):
    out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2.2" marker-end="url(#head)"/>')


out.append(f'<rect width="{W}" height="{H}" rx="18" fill="#fbfbfd"/>')
text(W / 2, 48, "Melo + Melodi AI: system architecture", 26, "800", anchor="middle")

# Column 1: the iPhone app
rect(30, 80, 420, 610, "#fff3f6", PINK)
text(50, 114, "iPhone · Melo app", 21, "800", PINK)
text(50, 136, "React Native · Expo · TypeScript · Swift", 13.5, color=SUB)
app = [
    ("Screens (Expo Router)", ["Home · Melodi AI tab · Search · Library · Player"]),
    ("Context sensing  ·  context.ts", ["time · sunset · weather · driving / walking · city", "turned into labels on the phone"]),
    ("Melodi client  ·  melodi.ts", ["auto-mix when the app opens", "reuses the mix for 30 min · taste summary"]),
    ("Player  ·  expo-audio", ["queue · radio · lock screen · Dynamic Island"]),
    ("Native Swift modules", ["RemoteCommands (next / previous)", "WebCookies (Google sign-in)"]),
    ("On-device storage", ["likes · recents · downloads · Keychain"]),
]
y = 152
for title, lines in app:
    h = 40 + 18 * len(lines)
    box(45, y, 390, h, title, lines)
    y += h + 12

# Column 2: the Melodi AI server
rect(600, 80, 400, 610, "#f4f0ff", PURPLE)
text(620, 114, "Melodi AI server", 21, "800", PURPLE)
text(620, 136, "Python · FastAPI · Pydantic · runs on the Mac", 13.5, color=SUB)
box(615, 152, 370, 58, "POST /v1/plan", ["checks the app token · validates the request"])
steps = [
    ("1  Understand", "Claude: moods, keywords, languages, energy", True),
    ("2  Narrow", "code: 3,364 curated playlists → ~150", False),
    ("3  Pick", "Claude: 3–6 playlists (numbers checked)", True),
    ("4  Collect", "code: real songs + radio from your likes", False),
    ("5  Score", "code: merge duplicates, rank, top 40", False),
    ("6  Sequence", "Claude: order, title, a reason per song", True),
]
y = 224
for title, line, ai in steps:
    box(615, y, 370, 64, title, [line], "#ebe3ff" if ai else "#ffffff", PURPLE if ai else BLUE)
    y += 74

# Column 3: cloud services used by the server
rect(1080, 80, 290, 610, "#eef5ff", BLUE)
text(1100, 114, "Cloud services", 21, "800", BLUE)
box(1095, 190, 260, 104, "Claude API", ["Haiku 5.5 (default)", "structured outputs", "≈ $0.002 per mix"])
box(1095, 420, 260, 104, "YouTube Music", ["Moods & genres catalogue", "playlists and radio", "via ytmusicapi · cached 24 h"])

# Bottom row: services the phone talks to directly
box(30, 760, 200, 96, "Open-Meteo", ["weather + sunset", "free, no API key"], "#ffffff", BLUE)
box(250, 760, 200, 96, "YouTube InnerTube", ["search · home feed", "HLS audio for playback"], "#ffffff", BLUE)

# Arrows: phone <-> server
arrow(452, 330, 597, 330)
text(525, 300, "context labels", 13.5, "700", anchor="middle")
text(525, 318, "+ taste (no GPS)", 13.5, color=SUB, anchor="middle")
arrow(597, 378, 455, 378)
text(525, 400, "25 songs", 13.5, "700", anchor="middle")
text(525, 418, "+ reasons", 13.5, color=SUB, anchor="middle")

# Arrows: server -> cloud
arrow(1002, 242, 1092, 242)
text(1041, 230, "3 calls", 13.5, "700", anchor="middle")
arrow(1002, 472, 1092, 472)
text(1041, 460, "fetch", 13.5, "700", anchor="middle")

# Arrows: phone -> direct services
arrow(130, 692, 130, 757)
text(140, 732, "rounded location", 12.5, color=SUB)
arrow(350, 692, 350, 757)
text(360, 732, "stream", 12.5, color=SUB)

# Legend
lx, ly = 600, 735
text(lx, ly, "Legend", 15, "800")
rect(lx, ly + 14, 22, 16, "#ebe3ff", PURPLE, r=4, sw=1.5)
text(lx + 32, ly + 27, "Claude (LLM) step: structured output, every answer checked by code", 13.5)
rect(lx, ly + 40, 22, 16, "#ffffff", BLUE, r=4, sw=1.5)
text(lx + 32, ly + 53, "Plain code step: deterministic and unit-tested", 13.5)
text(lx, ly + 82, "Privacy: GPS stays on the phone · the API key stays on the server · nothing is stored", 13.5, color=SUB)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">
<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker></defs>
{chr(10).join(out)}
</svg>
'''
open(sys.argv[1], "w").write(svg)
