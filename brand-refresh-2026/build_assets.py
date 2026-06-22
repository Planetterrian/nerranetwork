#!/usr/bin/env python3
"""
Nerra Network brand asset builder.
Outlines the "Nerra" / "Network" wordmark to vector paths (font-independent),
and emits the full SVG asset suite. The constellation mark is pure geometry.

Wordmark display font: Poppins Bold (outlined -> no runtime font dependency).
UI/body font (site, live text): DM Sans. Editorial: Source Serif 4.
"""
import os
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"

GRAD = '''<linearGradient id="nerra" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#6B47FF"/><stop offset="100%" stop-color="#00D4FF"/></linearGradient>
  <linearGradient id="nerraText" x1="0%" y1="0%" x2="100%" y2="0%">
    <stop offset="0%" stop-color="#8B6BFF"/><stop offset="100%" stop-color="#00D4FF"/></linearGradient>'''

_tt = TTFont(FONT)
_upm = _tt["head"].unitsPerEm
_cmap = _tt.getBestCmap()
_gs = _tt.getGlyphSet()
_hmtx = _tt["hmtx"]

def word_path(text):
    """Return (path_d_in_font_units_yUp, advance_in_font_units)."""
    pen = SVGPathPen(_gs)
    x = 0
    for ch in text:
        gname = _cmap[ord(ch)]
        # translate pen origin by drawing each glyph offset via transform-on-path
        glyph = _gs[gname]
        # Use a transform pen to offset by current x
        from fontTools.pens.transformPen import TransformPen
        tpen = TransformPen(pen, (1, 0, 0, 1, x, 0))
        glyph.draw(tpen)
        x += _hmtx[gname][0]
    return pen.getCommands(), x

NERRA_D, NERRA_ADV = word_path("Nerra")
NETW_D,  NETW_ADV  = word_path("Network")

def wm(x, baseline, px, fill_nerra, fill_net, gap_px=14):
    """Emit outlined wordmark starting at x (left), sitting on `baseline`,
    cap rendered at pixel font-size px. Returns (svg, total_width_px)."""
    s = px / _upm
    nerra_w = NERRA_ADV * s
    netw_w = NETW_ADV * s
    g = (
        f'<g transform="translate({x:.2f},{baseline:.2f}) scale({s:.5f},{-s:.5f})">'
        f'<path d="{NERRA_D}" fill="{fill_nerra}"/></g>'
        f'<g transform="translate({x+nerra_w+gap_px:.2f},{baseline:.2f}) scale({s:.5f},{-s:.5f})">'
        f'<path d="{NETW_D}" fill="{fill_net}"/></g>'
    )
    return g, nerra_w + gap_px + netw_w

def wm_centered(cx, baseline, px, fill_nerra, fill_net, gap_px=14):
    s = px / _upm
    total = NERRA_ADV * s + gap_px + NETW_ADV * s
    return wm(cx - total / 2, baseline, px, fill_nerra, fill_net, gap_px)[0], total

# ---- constellation mark (local 100x100). glow optional. ----
def mark(tx, ty, scale=1.0, glow=True):
    glowc = '<circle cx="50" cy="50" r="38" fill="url(#nerraGlow)"/>' if glow else ''
    return f'''<g transform="translate({tx},{ty}) scale({scale})">
    <rect width="100" height="100" rx="24" fill="#0B0F1A"/>{glowc}
    <circle cx="50" cy="50" r="33" fill="none" stroke="url(#nerra)" stroke-width="1" opacity="0.18"/>
    <g stroke="url(#nerra)" stroke-width="2.4" stroke-linecap="round" opacity="0.55">
      <line x1="50" y1="50" x2="50" y2="26"/><line x1="50" y1="50" x2="70.8" y2="38"/>
      <line x1="50" y1="50" x2="70.8" y2="62"/><line x1="50" y1="50" x2="50" y2="74"/>
      <line x1="50" y1="50" x2="29.2" y2="62"/><line x1="50" y1="50" x2="29.2" y2="38"/></g>
    <circle cx="50" cy="26" r="5.2" fill="#00D4FF"/><circle cx="70.8" cy="38" r="5.2" fill="#6B47FF"/>
    <circle cx="70.8" cy="62" r="5.2" fill="#00D4FF"/><circle cx="50" cy="74" r="5.2" fill="#6B47FF"/>
    <circle cx="29.2" cy="62" r="5.2" fill="#00D4FF"/><circle cx="29.2" cy="38" r="5.2" fill="#6B47FF"/>
    <circle cx="50" cy="50" r="10" fill="url(#nerra)"/><circle cx="50" cy="50" r="4.2" fill="#FFFFFF" opacity="0.95"/></g>'''

GLOWDEF = '''<radialGradient id="nerraGlow" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#6B47FF" stop-opacity="0.35"/><stop offset="100%" stop-color="#6B47FF" stop-opacity="0"/></radialGradient>'''

def write(name, svg):
    with open(os.path.join(OUT, name), "w") as f:
        f.write(svg)
    print("wrote", name)

# ---------- 1. Horizontal (dark bg use / transparent) ----------
w, _ = wm(150, 92, 62, "#FFFFFF", "url(#nerraText)")
desc = '<text x="151" y="124" textLength="406" lengthAdjust="spacingAndGlyphs" font-family="\'DM Sans\',Arial,sans-serif" font-weight="600" font-size="15" fill="#94A3B8">INDEPENDENT PODCAST NETWORK</text>'
write("nerra-logo-horizontal.svg", f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 160" width="600" height="160" role="img" aria-label="Nerra Network">
  <defs>{GRAD}</defs>
  {mark(20,30,glow=False)}
  {w}
  {desc}
</svg>''')

# ---------- 1b. Horizontal light bg ----------
w2, _ = wm(150, 92, 62, "#0B0F1A", "url(#nerra)")
descL = '<text x="151" y="124" textLength="406" lengthAdjust="spacingAndGlyphs" font-family="\'DM Sans\',Arial,sans-serif" font-weight="600" font-size="15" fill="#475569">INDEPENDENT PODCAST NETWORK</text>'
write("nerra-logo-horizontal-light.svg", f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 160" width="600" height="160" role="img" aria-label="Nerra Network">
  <defs>{GRAD}</defs>
  {mark(20,30,glow=False)}
  {w2}
  {descL}
</svg>''')

# ---------- 2. Stacked ----------
ws, _ = wm_centered(190, 205, 58, "#FFFFFF", "url(#nerraText)")
write("nerra-logo-stacked.svg", f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 340" width="380" height="340" role="img" aria-label="Nerra Network">
  <defs>{GRAD}{GLOWDEF}</defs>
  {mark(140,20)}
  {ws}
  <text x="190" y="238" text-anchor="middle" textLength="300" lengthAdjust="spacingAndGlyphs" font-family="'DM Sans',Arial,sans-serif" font-weight="600" font-size="14" fill="#94A3B8">INDEPENDENT PODCAST NETWORK</text>
</svg>''')

# ---------- 3. YouTube banner 2560x1440 ----------
wy, _ = wm_centered(1280, 770, 118, "#FFFFFF", "url(#nerraText)", gap_px=26)
write("nerra-youtube-banner.svg", f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2560 1440" width="2560" height="1440" role="img" aria-label="Nerra Network YouTube banner">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#0B0F1A"/><stop offset="55%" stop-color="#0F172A"/><stop offset="100%" stop-color="#161B2E"/></linearGradient>
    {GRAD}{GLOWDEF}
    <radialGradient id="glowL" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#6B47FF" stop-opacity="0.22"/><stop offset="100%" stop-color="#6B47FF" stop-opacity="0"/></radialGradient>
    <radialGradient id="glowR" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#00D4FF" stop-opacity="0.16"/><stop offset="100%" stop-color="#00D4FF" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="2560" height="1440" fill="url(#bg)"/>
  <ellipse cx="560" cy="500" rx="900" ry="700" fill="url(#glowL)"/>
  <ellipse cx="2050" cy="980" rx="900" ry="700" fill="url(#glowR)"/>
  <g opacity="0.5" stroke="url(#nerra)" stroke-width="2" fill="none">
    <line x1="300" y1="300" x2="520" y2="430" opacity="0.25"/><line x1="520" y1="430" x2="360" y2="640" opacity="0.2"/>
    <line x1="2260" y1="1120" x2="2040" y2="980" opacity="0.25"/><line x1="2040" y1="980" x2="2230" y2="820" opacity="0.2"/>
    <line x1="2180" y1="360" x2="2360" y2="300" opacity="0.2"/></g>
  <g>
    <circle cx="300" cy="300" r="7" fill="#00D4FF" opacity="0.5"/><circle cx="520" cy="430" r="9" fill="#6B47FF" opacity="0.5"/>
    <circle cx="360" cy="640" r="6" fill="#00D4FF" opacity="0.4"/><circle cx="2260" cy="1120" r="7" fill="#00D4FF" opacity="0.5"/>
    <circle cx="2040" cy="980" r="9" fill="#6B47FF" opacity="0.5"/><circle cx="2230" cy="820" r="6" fill="#00D4FF" opacity="0.4"/>
    <circle cx="2180" cy="360" r="7" fill="#6B47FF" opacity="0.45"/><circle cx="2360" cy="300" r="6" fill="#00D4FF" opacity="0.4"/></g>
  {mark(1180,470,scale=1.6)}
  {wy}
  <text x="1280" y="858" text-anchor="middle" textLength="640" lengthAdjust="spacingAndGlyphs" font-family="'DM Sans',Arial,sans-serif" font-weight="500" font-size="38" fill="#CBD5E1">Feed your curiosity — not your anxiety.</text>
  <text x="1280" y="918" text-anchor="middle" textLength="980" lengthAdjust="spacingAndGlyphs" font-family="'DM Sans',Arial,sans-serif" font-weight="600" font-size="24" fill="#94A3B8">NEW EPISODES DAILY&#160;&#160;·&#160;&#160;100% AD-FREE&#160;&#160;·&#160;&#160;EN · FR · RU · ZH</text>
</svg>''')

# ---------- 4. Social banner 1500x500 ----------
wb, _ = wm(310, 235, 78, "#FFFFFF", "url(#nerraText)")
nodes = [(-120,-70,"#E31937",9),(-30,-130,"#0B6FD6",9),(80,-110,"#1E40AF",9),(150,-40,"#7C5CFF",9),
         (150,55,"#018DB1",9),(90,120,"#16A34A",9),(-10,150,"#1B5E20",9),(-110,100,"#8B5CF6",9),
         (-160,10,"#F59E0B",9),(-70,-40,"#EC4899",8),(55,-55,"#0EA5E9",8),(60,50,"#B45309",8)]
nlines = "".join(f'<line x1="0" y1="0" x2="{x}" y2="{y}"/>' for x,y,_,_ in nodes)
ncircs = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>' for x,y,c,r in nodes)
write("nerra-social-banner.svg", f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1500 500" width="1500" height="500" role="img" aria-label="Nerra Network banner">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#0B0F1A"/><stop offset="100%" stop-color="#161B2E"/></linearGradient>
    {GRAD}
    <radialGradient id="glow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#6B47FF" stop-opacity="0.18"/><stop offset="100%" stop-color="#6B47FF" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="1500" height="500" fill="url(#bg)"/>
  <ellipse cx="1100" cy="250" rx="520" ry="420" fill="url(#glow)"/>
  <line x1="0" y1="3" x2="1500" y2="3" stroke="url(#nerra)" stroke-width="5"/>
  <line x1="0" y1="497" x2="1500" y2="497" stroke="url(#nerra)" stroke-width="5"/>
  {mark(90,150,scale=1.95,glow=False)}
  {wb}
  <text x="312" y="280" textLength="520" lengthAdjust="spacingAndGlyphs" font-family="'DM Sans',Arial,sans-serif" font-weight="600" font-size="19" fill="#94A3B8">INDEPENDENT PODCAST NETWORK · EN · FR · RU · ZH</text>
  <text x="312" y="372" font-family="'DM Sans',Arial,sans-serif" font-weight="700" font-size="40" fill="#FFFFFF">Daily<tspan font-weight="500" font-size="22" fill="#94A3B8" dx="8">new</tspan><tspan font-weight="700" font-size="40" fill="#FFFFFF" dx="30">900+</tspan><tspan font-weight="500" font-size="22" fill="#94A3B8" dx="8">episodes</tspan><tspan font-weight="700" font-size="40" fill="#FFFFFF" dx="30">100%</tspan><tspan font-weight="500" font-size="22" fill="#94A3B8" dx="8">independent</tspan><tspan font-weight="700" font-size="40" fill="url(#nerraText)" dx="30">0</tspan><tspan font-weight="500" font-size="22" fill="#94A3B8" dx="8">ads</tspan></text>
  <g transform="translate(1140,250)">
    <g stroke="url(#nerra)" stroke-width="1.5" opacity="0.28">{nlines}</g>
    {ncircs}
    <circle cx="0" cy="0" r="16" fill="url(#nerra)"/><circle cx="0" cy="0" r="6.5" fill="#FFFFFF" opacity="0.95"/></g>
</svg>''')

# ---------- 5. OG preview 1200x630 ----------
wo, _ = wm_centered(600, 320, 92, "#FFFFFF", "url(#nerraText)", gap_px=18)
write("nerra-og-preview.svg", f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630" role="img" aria-label="Nerra Network">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#0B0F1A"/><stop offset="100%" stop-color="#161B2E"/></linearGradient>
    {GRAD}
    <radialGradient id="glow" cx="50%" cy="40%" r="55%"><stop offset="0%" stop-color="#6B47FF" stop-opacity="0.22"/><stop offset="100%" stop-color="#6B47FF" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <ellipse cx="600" cy="250" rx="640" ry="420" fill="url(#glow)"/>
  <line x1="0" y1="4" x2="1200" y2="4" stroke="url(#nerra)" stroke-width="6"/>
  {mark(550,90,glow=False)}
  {wo}
  <text x="600" y="392" text-anchor="middle" textLength="560" lengthAdjust="spacingAndGlyphs" font-family="'DM Sans',Arial,sans-serif" font-weight="500" font-size="34" fill="#CBD5E1">Feed your curiosity — not your anxiety.</text>
  <text x="600" y="468" text-anchor="middle" textLength="600" lengthAdjust="spacingAndGlyphs" font-family="'DM Sans',Arial,sans-serif" font-weight="600" font-size="22" fill="#94A3B8">AD-FREE&#160;&#160;·&#160;&#160;NEW EVERY DAY&#160;&#160;·&#160;&#160;EN · FR · RU · ZH</text>
  <g transform="translate(600,520)">
    <circle cx="-150" cy="0" r="7" fill="#E31937"/><circle cx="-100" cy="0" r="7" fill="#0B6FD6"/><circle cx="-50" cy="0" r="7" fill="#1E40AF"/>
    <circle cx="0" cy="0" r="7" fill="#7C5CFF"/><circle cx="50" cy="0" r="7" fill="#16A34A"/><circle cx="100" cy="0" r="7" fill="#F59E0B"/><circle cx="150" cy="0" r="7" fill="#EC4899"/></g>
</svg>''')

print("DONE")
