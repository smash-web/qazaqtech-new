"""Оригинальный 2D-диктор TechTalQ. Один SVG со всеми фазами рта и век:
JS анимации переключает группы #m-* (рот) и #lids (моргание), двигает #head."""
SKIN, SKIN_SH, BLUSH = "#EFC4A0", "#DDA883", "#F09A8C"
HAIR, HAIR_HI = "#1E1612", "#3A2A22"
INK, SKY, GOLD, DEEP = "#0B1B3A", "#00AFCA", "#FFC72C", "#007A99"
IRIS = "#3B2416"

def mouths(cx, cy):
    lip = "#B4545A"; inside = "#5A1E24"; teeth = "#FFFFFF"; tongue = "#D9707A"
    m = {}
    m["closed"] = f'<path d="M{cx-34} {cy} Q{cx} {cy+16} {cx+34} {cy}" fill="none" stroke="{lip}" stroke-width="7" stroke-linecap="round"/>'
    def open_(w, h, ty):
        return (f'<path d="M{cx-w} {cy} Q{cx} {cy-6} {cx+w} {cy} Q{cx+w*0.6} {cy+h} {cx} {cy+h} Q{cx-w*0.6} {cy+h} {cx-w} {cy} Z" fill="{inside}" stroke="{lip}" stroke-width="6" stroke-linejoin="round"/>'
                f'<path d="M{cx-w+8} {cy+1} Q{cx} {cy-3} {cx+w-8} {cy+1} L{cx+w-12} {cy+ty} Q{cx} {cy+ty+3} {cx-w+12} {cy+ty} Z" fill="{teeth}"/>'
                + (f'<ellipse cx="{cx}" cy="{cy+h-8}" rx="{w*0.45}" ry="{max(4,h*0.18)}" fill="{tongue}"/>' if h > 24 else ""))
    m["small"] = open_(30, 16, 6)
    m["mid"] = open_(36, 30, 8)
    m["wide"] = open_(40, 44, 9)
    m["o"] = (f'<ellipse cx="{cx}" cy="{cy+12}" rx="18" ry="22" fill="{inside}" stroke="{lip}" stroke-width="6"/>'
              f'<ellipse cx="{cx}" cy="{cy+24}" rx="9" ry="6" fill="{tongue}"/>')
    m["smile"] = (f'<path d="M{cx-42} {cy-4} Q{cx} {cy+38} {cx+42} {cy-4} Q{cx} {cy+12} {cx-42} {cy-4} Z" fill="{inside}" stroke="{lip}" stroke-width="6" stroke-linejoin="round"/>'
                  f'<path d="M{cx-34} {cy+1} Q{cx} {cy+14} {cx+34} {cy+1} L{cx+30} {cy+8} Q{cx} {cy+19} {cx-30} {cy+8} Z" fill="{teeth}"/>')
    return "".join(f'<g id="m-{k}" style="display:{"inline" if k=="smile" else "none"}">{v}</g>' for k, v in m.items())

def eye(cx, cy, flip=1):
    return (f'<g>'
            f'<path d="M{cx-34} {cy} Q{cx} {cy-30} {cx+34} {cy} Q{cx} {cy+22} {cx-34} {cy} Z" fill="#FFFFFF"/>'
            f'<circle cx="{cx+2*flip}" cy="{cy-1}" r="17" fill="{IRIS}"/>'
            f'<circle cx="{cx+2*flip}" cy="{cy-1}" r="8" fill="#120B08"/>'
            f'<circle cx="{cx+8*flip}" cy="{cy-8}" r="5" fill="#FFFFFF"/>'
            f'<path d="M{cx-38} {cy+2} Q{cx} {cy-34} {cx+38} {cy-2}" fill="none" stroke="#1A120E" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M{cx+30*flip} {cy-8} l{12*flip} -8" stroke="#1A120E" stroke-width="5" stroke-linecap="round"/>'
            f'</g>')

def lids(cx, cy):
    return (f'<path d="M{cx-46} {cy+6} L{cx-54} {cy-16} Q{cx} {cy-54} {cx+54} {cy-16} L{cx+46} {cy+6} Q{cx} {cy+32} {cx-46} {cy+6} Z" fill="{SKIN}"/>'
            f'<path d="M{cx-36} {cy+3} Q{cx} {cy+16} {cx+36} {cy}" fill="none" stroke="#1A120E" stroke-width="6" stroke-linecap="round"/>')

def logo_pin(x, y, s=1.0):
    return (f'<g transform="translate({x} {y}) scale({s})">'
            f'<circle cx="0" cy="0" r="30" fill="{INK}"/>'
            f'<circle cx="-2" cy="-2" r="14" fill="none" stroke="#fff" stroke-width="6"/>'
            f'<circle cx="-2" cy="-2" r="3.2" fill="{SKY}"/><path d="M7 7l9 9" stroke="{GOLD}" stroke-width="5.5" stroke-linecap="round"/></g>')

def presenter(gender="f"):
    W, H = 800, 1000
    hx, hy = 400, 420
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">']
    # body (static) — blazer, shirt, neck
    p.append('<g id="body">')
    if gender == "f":
        p.append(f'<path d="M190 560 Q150 760 170 1000 L630 1000 Q650 760 610 560 Q560 610 400 600 Q240 610 190 560 Z" fill="{HAIR}"/>')  # long hair behind
    p.append(f'<rect x="352" y="560" width="96" height="150" rx="40" fill="{SKIN}"/>')
    p.append(f'<path d="M352 600 Q400 650 448 600 L448 640 Q400 680 352 640 Z" fill="{SKIN_SH}"/>')
    p.append(f'<path d="M40 1000 Q60 790 230 735 L400 700 L570 735 Q740 790 760 1000 Z" fill="{DEEP}"/>')
    p.append(f'<path d="M330 700 L400 830 L470 700 Q400 728 330 700 Z" fill="#F5F7FA"/>')
    p.append(f'<path d="M230 735 L400 700 L330 700 L372 900 L300 1000 L200 1000 Z" fill="#00657F"/>')
    p.append(f'<path d="M570 735 L400 700 L470 700 L428 900 L500 1000 L600 1000 Z" fill="#00657F"/>')
    p.append(logo_pin(520, 820, 1.0))
    p.append('</g>')
    # head group (moves)
    p.append(f'<g id="head" style="transform-origin:{hx}px 640px">')
    if gender == "f":
        p.append(f'<path d="M230 380 Q224 214 400 192 Q576 214 570 380 Q584 520 604 700 Q566 722 524 700 L516 600 L284 600 L276 700 Q234 722 196 700 Q216 520 230 380 Z" fill="{HAIR}"/>')
    else:
        p.append(f'<ellipse cx="238" cy="450" rx="26" ry="40" fill="{SKIN_SH}"/><ellipse cx="562" cy="450" rx="26" ry="40" fill="{SKIN_SH}"/>')
    jaw = "M240 400 Q238 300 400 262 Q562 300 560 400 Q560 540 470 610 Q400 650 330 610 Q240 540 240 400 Z" if gender == "f" else \
          "M238 400 Q236 290 400 258 Q564 290 562 400 Q566 545 478 615 Q400 660 322 615 Q234 545 238 400 Z"
    p.append(f'<path d="{jaw}" fill="{SKIN}"/>')
    p.append(f'<ellipse cx="318" cy="520" rx="30" ry="16" fill="{BLUSH}" opacity=".35"/><ellipse cx="482" cy="520" rx="30" ry="16" fill="{BLUSH}" opacity=".35"/>')
    if gender == "f":
        p.append(f'<path d="M230 410 Q228 262 366 224 Q326 292 298 356 Q276 424 272 548 Q224 488 230 410 Z" fill="{HAIR}"/>')
        p.append(f'<path d="M366 224 Q522 214 562 330 Q570 380 562 430 Q544 344 474 304 Q414 276 366 224 Z" fill="{HAIR}"/>')
        p.append(f'<path d="M392 232 Q500 236 540 312" fill="none" stroke="{HAIR_HI}" stroke-width="7" stroke-linecap="round"/>')
        p.append(f'<circle cx="244" cy="520" r="9" fill="{GOLD}"/><circle cx="556" cy="520" r="9" fill="{GOLD}"/>')
    else:
        p.append(f'<path d="M234 392 Q220 240 372 204 Q470 186 536 226 Q578 258 566 392 Q540 324 500 296 Q458 314 404 298 Q346 280 300 302 Q254 322 234 392 Z" fill="{HAIR}"/>')
        p.append(f'<path d="M330 232 Q420 206 500 232" fill="none" stroke="{HAIR_HI}" stroke-width="8" stroke-linecap="round"/>')
    # brows
    bw = 7 if gender == "f" else 11
    p.append(f'<g id="brows"><path d="M292 378 Q330 360 366 374" fill="none" stroke="{HAIR}" stroke-width="{bw}" stroke-linecap="round"/>'
             f'<path d="M434 374 Q470 360 508 378" fill="none" stroke="{HAIR}" stroke-width="{bw}" stroke-linecap="round"/></g>')
    p.append(eye(330, 430, -1) + eye(470, 430, 1))
    p.append(f'<g id="lids" style="display:none">{lids(330,430)}{lids(470,430)}</g>')
    p.append(f'<path d="M402 455 Q392 500 384 510 Q400 520 414 512" fill="none" stroke="{SKIN_SH}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>')
    p.append(f'<g id="mouth">{mouths(400, 560)}</g>')
    p.append('</g></svg>')
    return "".join(p)

if __name__ == "__main__":
    for g in ("f", "m"):
        open(f"presenter_{g}.svg", "w").write(presenter(g))
