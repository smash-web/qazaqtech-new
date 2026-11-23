"""Диктор по картинке (студия 529×941 после вертикальной обрезки): накладка SVG с фазами рта и веками.
Координаты — в пикселях обрезанной картинки host_base (до увеличения до 1080×1920)."""
CX, CY = 236, 331          # центр рта
EYES = [(181, 233), (284, 231)]
LINE, INSIDE, TEETH, TONGUE, LIP = "#1b0f0e", "#2a0f0f", "#F4F6F7", "#C9675F", "#E0907A"
SKIN = "#F6AF88"


def _open(w: float, top: float, bot: float, teeth: float, tongue: bool) -> str:
    l, r = CX - w, CX + w
    shape = f"M{l} {CY+top} Q{CX} {CY+top-3} {r} {CY+top-1} Q{CX+w*0.55} {CY+bot} {CX} {CY+bot} Q{CX-w*0.55} {CY+bot} {l} {CY+top} Z"
    s = f'<path d="{shape}" fill="{INSIDE}" stroke="{LINE}" stroke-width="2.4" stroke-linejoin="round"/>'
    s += f'<clipPath id="c{int(w)}{int(bot)}"><path d="{shape}"/></clipPath><g clip-path="url(#c{int(w)}{int(bot)})">'
    s += f'<rect x="{l}" y="{CY+top-4}" width="{2*w}" height="{teeth+4}" fill="{TEETH}"/>'
    if tongue:
        s += f'<ellipse cx="{CX}" cy="{CY+bot}" rx="{w*0.55}" ry="{(bot-top)*0.42}" fill="{TONGUE}"/>'
    s += "</g>"
    s += f'<path d="M{CX-w*0.45} {CY+bot+5} Q{CX} {CY+bot+9} {CX+w*0.45} {CY+bot+5}" fill="none" stroke="{LIP}" stroke-width="2.2" stroke-linecap="round" opacity=".8"/>'
    return s


def mouths() -> dict[str, str]:
    return {
        "closed": f'<path d="M{CX-34} {CY} Q{CX} {CY+7} {CX+34} {CY-1}" fill="none" stroke="{LINE}" stroke-width="2.4" stroke-linecap="round"/>'
                  f'<path d="M{CX-14} {CY+9} Q{CX} {CY+12} {CX+14} {CY+9}" fill="none" stroke="{LIP}" stroke-width="2.2" stroke-linecap="round"/>',
        "small": _open(30, -1, 8, 4, False),
        "mid": _open(34, -2, 15, 5, True),
        "wide": _open(38, -3, 23, 6, True),
        "o": f'<ellipse cx="{CX}" cy="{CY+6}" rx="13" ry="13" fill="{INSIDE}" stroke="{LINE}" stroke-width="2.4"/>'
             f'<ellipse cx="{CX}" cy="{CY+13}" rx="7" ry="4" fill="{TONGUE}"/>'
             f'<path d="M{CX-8} {CY+24} Q{CX} {CY+27} {CX+8} {CY+24}" fill="none" stroke="{LIP}" stroke-width="2" stroke-linecap="round"/>',
        "smile": _open(40, -4, 18, 7, True).replace(f"Q{CX} {CY-7}", f"Q{CX} {CY-4}"),
    }


def lids() -> str:
    s = ""
    for ex, ey in EYES:
        s += (f'<ellipse cx="{ex}" cy="{ey-1}" rx="28" ry="14" fill="{SKIN}"/>'
              f'<path d="M{ex-26} {ey+1} Q{ex} {ey+9} {ex+26} {ey}" fill="none" stroke="{LINE}" stroke-width="3" stroke-linecap="round"/>')
    return s


def overlay_svg(prefix: str = "") -> str:
    ms = "".join(f'<g id="{prefix}m-{k}" style="display:{"inline" if k == "smile" else "none"}">{v}</g>' for k, v in mouths().items())
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 529 941" width="529" height="941" '
            f'style="position:absolute;left:0;top:0">{ms}<g id="{prefix}lids" style="display:none">{lids()}</g></svg>')
