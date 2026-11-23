"""Диктор по картинке студии (reels/assets/host.jpg, 941×1672 в координатах накладки; файл — вдвое крупнее).

Накладка SVG: фазы рта (#m-*), веки (#lids), свечение экрана с глобусом (#glow).
Рот на картинке стёрт — его рисуем поверх по таймкодам озвучки.
"""
W, H = 941, 1672
MOUTH = (473, 707, 0.93)            # центр рта и масштаб рисунка
EYES = [(422, 612), (523, 610)]
GLOBE = (800, 640)                  # центр экрана с глобусом — пульсирующее свечение
LINE, INSIDE, TEETH, TONGUE, LIP = "#1b0f0e", "#2a0f0f", "#F4F6F7", "#C9675F", "#E0907A"
SKIN = "#FBBC9E"


def _open(w: float, top: float, bot: float, teeth: float, tongue: bool, uid: str) -> str:
    shape = f"M{-w} {top} Q0 {top-3} {w} {top-1} Q{w*0.55} {bot} 0 {bot} Q{-w*0.55} {bot} {-w} {top} Z"
    s = f'<path d="{shape}" fill="{INSIDE}" stroke="{LINE}" stroke-width="2.4" stroke-linejoin="round"/>'
    s += f'<clipPath id="{uid}"><path d="{shape}"/></clipPath><g clip-path="url(#{uid})">'
    s += f'<rect x="{-w}" y="{top-4}" width="{2*w}" height="{teeth+4}" fill="{TEETH}"/>'
    if tongue:
        s += f'<ellipse cx="0" cy="{bot}" rx="{w*0.55}" ry="{(bot-top)*0.42}" fill="{TONGUE}"/>'
    s += "</g>"
    s += f'<path d="M{-w*0.45} {bot+5} Q0 {bot+9} {w*0.45} {bot+5}" fill="none" stroke="{LIP}" stroke-width="2.2" stroke-linecap="round" opacity=".8"/>'
    return s


def mouths(prefix: str) -> dict[str, str]:
    return {
        "closed": f'<path d="M-34 0 Q0 7 34 -1" fill="none" stroke="{LINE}" stroke-width="2.4" stroke-linecap="round"/>'
                  f'<path d="M-14 9 Q0 12 14 9" fill="none" stroke="{LIP}" stroke-width="2.2" stroke-linecap="round"/>',
        "small": _open(30, -1, 8, 4, False, f"{prefix}cs"),
        "mid": _open(34, -2, 15, 5, True, f"{prefix}cm"),
        "wide": _open(38, -3, 23, 6, True, f"{prefix}cw"),
        "o": f'<ellipse cx="0" cy="6" rx="13" ry="13" fill="{INSIDE}" stroke="{LINE}" stroke-width="2.4"/>'
             f'<ellipse cx="0" cy="13" rx="7" ry="4" fill="{TONGUE}"/>'
             f'<path d="M-8 24 Q0 27 8 24" fill="none" stroke="{LIP}" stroke-width="2" stroke-linecap="round"/>',
        "smile": _open(40, -4, 18, 7, True, f"{prefix}cx"),
    }


def lids() -> str:
    s = ""
    for ex, ey in EYES:
        s += (f'<ellipse cx="{ex}" cy="{ey-1}" rx="28" ry="14" fill="{SKIN}"/>'
              f'<path d="M{ex-26} {ey+1} Q{ex} {ey+9} {ex+26} {ey}" fill="none" stroke="{LINE}" stroke-width="3" stroke-linecap="round"/>')
    return s


def overlay_svg(prefix: str = "") -> str:
    mx, my, ms = MOUTH
    m = "".join(f'<g id="{prefix}m-{k}" style="display:{"inline" if k == "smile" else "none"}">{v}</g>'
                for k, v in mouths(prefix).items())
    gx, gy = GLOBE
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="position:absolute;left:0;top:0">'
            f'<defs><radialGradient id="{prefix}gl"><stop offset="0" stop-color="#5FD4FF" stop-opacity=".55"/>'
            f'<stop offset="1" stop-color="#5FD4FF" stop-opacity="0"/></radialGradient></defs>'
            f'<circle id="{prefix}glow" cx="{gx}" cy="{gy}" r="230" fill="url(#{prefix}gl)" style="mix-blend-mode:screen;opacity:.4"/>'
            f'<g transform="translate({mx} {my}) scale({ms})">{m}</g>'
            f'<g id="{prefix}lids" style="display:none">{lids()}</g></svg>')
