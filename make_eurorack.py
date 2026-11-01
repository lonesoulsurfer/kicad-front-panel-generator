"""Writes Eurorack.pretty: one start-here template per HP size.

Place a template on an empty PCB at 0 degrees. It gives you:
  - the PCB outline on Edge.Cuts (0.5 mm in from each panel side, 106.5 mm tall, clear of the rails)
  - the panel outline, rail zones and rail holes on User.Comments, so you can see the rails while placing parts
panelgen then builds a Eurorack panel lined up with it.

    py make_eurorack.py            (rewrites every template)
"""
import os, sys, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from panelgen import (eurorack_spec, ER_SIZES, ER_HEIGHT, ER_RAIL, ER_PCB_INSET, ER_HOLE_Y, ER_HOLE_DIA)

LIB = os.path.join(HERE, 'Eurorack.pretty')
FONT = '(effects (font (size 1 1) (thickness 0.15)))'
SMALL = '(effects (font (size 0.8 0.8) (thickness 0.12)))'


def u():
    return f'(uuid "{uuid.uuid4()}")'


def g(v):
    return f'{v:.4f}'.rstrip('0').rstrip('.') if v != 0 else '0'


def rect(x1, y1, x2, y2, layer, width=0.1):
    return (f'\t(fp_rect (start {g(x1)} {g(y1)}) (end {g(x2)} {g(y2)}) (stroke (width {width}) (type solid)) '
            f'(fill no) (layer "{layer}") {u()})')


def circle(x, y, r, layer):
    return (f'\t(fp_circle (center {g(x)} {g(y)}) (end {g(x + r)} {g(y)}) (stroke (width 0.1) (type solid)) '
            f'(fill no) (layer "{layer}") {u()})')


def text(t, x, y, layer, eff=FONT):
    return f'\t(fp_text user "{t}" (at {g(x)} {g(y)} 0) (layer "{layer}") {u()} {eff})'


def template(hp):
    w, holes, src = eurorack_spec(hp)
    h, rail = ER_HEIGHT, ER_RAIL
    name = f'Eurorack_{hp}HP'
    c = 'Cmts.User'
    body = [rect(ER_PCB_INSET, rail, w - ER_PCB_INSET, h - rail, 'Edge.Cuts', 0.05),   # the PCB
            rect(0, 0, w, h, c),                                                      # the panel
            rect(0, 0, w, rail, c), rect(0, h - rail, w, h, c)]                         # rail zones
    for x, side in holes:
        body.append(circle(x, ER_HOLE_Y if side == 't' else h - ER_HOLE_Y, ER_HOLE_DIA / 2, c))
    eff = SMALL if w < 25 else FONT
    body += [text('RAIL', w / 2, rail - 2.5, c, eff), text('RAIL', w / 2, h - rail + 2.5, c, eff),
             text(f'{hp}HP panel {g(w)} x {g(h)}', w / 2, -2, c, eff)]
    descr = (f"Eurorack {hp}HP start-here template: PCB outline on Edge.Cuts ({g(w - 2 * ER_PCB_INSET)} x "
             f"{g(h - 2 * rail)} mm), panel {g(w)} x {g(h)} mm and rail zones on User.Comments. "
             f"Panel width: {'Doepfer table' if src == 'Doepfer' else 'estimated, not in the Doepfer table'}. "
             f"Origin = panel top-left. Keep at 0 degrees.")
    return f'''(footprint "{name}"
\t(version 20241229)
\t(generator "panelgen")
\t(generator_version "9.0")
\t(layer "F.Cu")
\t(descr "{descr}")
\t(tags "eurorack panel template {hp}HP")
\t(property "Reference" "PNL1" (at {g(w / 2)} {g(h + 2)} 0) (layer "F.Fab") (hide yes) {u()} {FONT})
\t(property "Value" "{name}" (at {g(w / 2)} {g(h + 3.5)} 0) (layer "F.Fab") (hide yes) {u()} {FONT})
\t(attr board_only exclude_from_pos_files exclude_from_bom)
{chr(10).join(body)}
)
'''


def main():
    os.makedirs(LIB, exist_ok=True)
    for hp in ER_SIZES:
        open(os.path.join(LIB, f'Eurorack_{hp}HP.kicad_mod'), 'w', encoding='utf-8').write(template(hp))
    print(f"wrote {len(ER_SIZES)} templates to {LIB}")


if __name__ == '__main__':
    main()
