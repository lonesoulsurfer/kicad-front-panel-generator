#!/usr/bin/env python3
"""panelpart - make a panel-only cutout footprint in one line, saved into PanelParts.pretty.

Examples:
  py panelpart.py slot 12x4.3 --name USB-C_Charge_Slot --holes 2.5@-8,0 2.5@8,0
  py panelpart.py rect 74x50 --name TFT_3.5in --hole-grid 2.2 78x46
  py panelpart.py rect 30x10 --radius 2 --name Rounded_Window
  py panelpart.py circle 9.5 --name Big_Pot

Shapes are centred on the footprint origin, so the X/Y you type when placing it is the
centre of the cutout. Sizes are in mm, width x height as the part sits on the panel.
  circle D          round hole, diameter D
  rect WxH          rectangle; add --radius R for rounded corners
  slot WxH          slot with fully rounded ends (drilled/routed as a slot by the fab)
  --holes D@X,Y     extra round holes, relative to the centre (repeatable)
  --hole-grid D WxH four holes of diameter D at the corners of a W x H rectangle (screen screws)
"""
import argparse, math, os, re, sys, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
S = '(stroke (width 0.05) (type solid))'


def u():
    return f'(uuid "{uuid.uuid4()}")'


def g(v):
    return f'{v:.4f}'.rstrip('0').rstrip('.') if v != 0 else '0'


def size_pair(text):
    m = re.fullmatch(r'([\d.]+)x([\d.]+)', text.lower())
    if not m:
        raise argparse.ArgumentTypeError(f"expected WxH, e.g. 12x4.3 (got '{text}')")
    return float(m.group(1)), float(m.group(2))


def hole_spec(text):
    m = re.fullmatch(r'([\d.]+)@(-?[\d.]+),(-?[\d.]+)', text)
    if not m:
        raise argparse.ArgumentTypeError(f"expected D@X,Y, e.g. 2.5@-8,0 (got '{text}')")
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def edge_circle(x, y, d):
    return f'\t(fp_circle (center {g(x)} {g(y)}) (end {g(x + d / 2)} {g(y)}) {S} (fill no) (layer "Edge.Cuts") {u()})'


def npth_round(x, y, d):
    return f'\t(pad "" np_thru_hole circle (at {g(x)} {g(y)}) (size {g(d)} {g(d)}) (drill {g(d)}) (layers "*.Cu" "*.Mask") {u()})'


def npth_slot(w, h):
    return f'\t(pad "" np_thru_hole oval (at 0 0) (size {g(w)} {g(h)}) (drill oval {g(w)} {g(h)}) (layers "*.Cu" "*.Mask") {u()})'


def rect(w, h, r=0):
    x1, y1, x2, y2 = -w / 2, -h / 2, w / 2, h / 2
    if r <= 0:
        return [f'\t(fp_rect (start {g(x1)} {g(y1)}) (end {g(x2)} {g(y2)}) {S} (fill no) (layer "Edge.Cuts") {u()})']
    r = min(r, w / 2, h / 2)
    k = r * (1 - math.sqrt(0.5))
    out = []
    line = lambda a, b: out.append(f'\t(fp_line (start {g(a[0])} {g(a[1])}) (end {g(b[0])} {g(b[1])}) {S} (layer "Edge.Cuts") {u()})')
    arc = lambda a, m, b: out.append(f'\t(fp_arc (start {g(a[0])} {g(a[1])}) (mid {g(m[0])} {g(m[1])}) (end {g(b[0])} {g(b[1])}) {S} (layer "Edge.Cuts") {u()})')
    line((x1 + r, y1), (x2 - r, y1)); arc((x2 - r, y1), (x2 - k, y1 + k), (x2, y1 + r))
    line((x2, y1 + r), (x2, y2 - r)); arc((x2, y2 - r), (x2 - k, y2 - k), (x2 - r, y2))
    line((x2 - r, y2), (x1 + r, y2)); arc((x1 + r, y2), (x1 + k, y2 - k), (x1, y2 - r))
    line((x1, y2 - r), (x1, y1 + r)); arc((x1, y1 + r), (x1 + k, y1 + k), (x1 + r, y1))
    return out


def fab_box(w, h):
    """Thin F.Fab outline so the part is visible and has a clear centre (never fabricated)."""
    return [f'\t(fp_rect (start {g(-w / 2)} {g(-h / 2)}) (end {g(w / 2)} {g(h / 2)}) {S} (fill no) (layer "F.Fab") {u()})']


def footprint(name, descr, body, w, h):
    font = '(effects (font (size 1 1) (thickness 0.15)))'
    ty = h / 2 + 1.5
    return f'''(footprint "{name}"
\t(version 20241229)
\t(generator "panelgen")
\t(generator_version "9.0")
\t(layer "F.Cu")
\t(descr "{descr}")
\t(tags "panel cutout")
\t(property "Reference" "P**" (at 0 {g(-ty)} 0) (layer "F.Fab") {u()} {font})
\t(property "Value" "{name}" (at 0 {g(ty)} 0) (layer "F.Fab") {u()} {font})
\t(attr board_only exclude_from_pos_files exclude_from_bom)
\t(fp_line (start -1 0) (end 1 0) {S} (layer "F.Fab") {u()})
\t(fp_line (start 0 -1) (end 0 1) {S} (layer "F.Fab") {u()})
{chr(10).join(body)}
)
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('shape', choices=['circle', 'rect', 'slot'])
    ap.add_argument('size', help='D for circle, WxH for rect/slot')
    ap.add_argument('--name', required=True, help='footprint name; "Panel_" is added in front')
    ap.add_argument('--radius', type=float, default=0, help='corner radius for rect')
    ap.add_argument('--holes', nargs='+', type=hole_spec, default=[], metavar='D@X,Y')
    ap.add_argument('--hole-grid', nargs=2, metavar=('D', 'WxH'))
    ap.add_argument('--lib', default=os.path.join(HERE, 'PanelParts.pretty'))
    ap.add_argument('--force', action='store_true', help='overwrite an existing footprint of that name')
    a = ap.parse_args(argv)
    try:
        return build(a)
    except argparse.ArgumentTypeError as e:
        ap.error(str(e))


def build(a):

    name = a.name if a.name.startswith('Panel_') else 'Panel_' + a.name
    name = re.sub(r'[^\w.\-]+', '_', name)
    body, desc = [], []
    if a.shape == 'circle':
        d = float(a.size); w = h = d
        body.append(edge_circle(0, 0, d)); desc.append(f'{g(d)} mm hole')
    else:
        w, h = size_pair(a.size)
        if a.shape == 'rect':
            body += rect(w, h, a.radius)
            desc.append(f'{g(w)} x {g(h)} mm window' + (f', {g(a.radius)} mm corners' if a.radius else ''))
        else:
            body.append(npth_slot(w, h)); desc.append(f'{g(w)} x {g(h)} mm slot')
    holes = list(a.holes)
    if a.hole_grid:
        hd = float(a.hole_grid[0]); gw, gh = size_pair(a.hole_grid[1])
        holes += [(hd, sx * gw / 2, sy * gh / 2) for sx in (-1, 1) for sy in (-1, 1)]
    for d, x, y in holes:
        body.append(npth_round(x, y, d))
    if holes:
        desc.append(f'{len(holes)} x {"/".join(sorted({g(d) for d, _, _ in holes}))} mm holes')
    ext_w = max([w] + [2 * abs(x) + d for d, x, _ in holes]); ext_h = max([h] + [2 * abs(y) + d for d, _, y in holes])
    body += fab_box(ext_w, ext_h)

    os.makedirs(a.lib, exist_ok=True)
    path = os.path.join(a.lib, name + '.kicad_mod')
    if os.path.exists(path) and not a.force:
        sys.exit(f"{name} already exists in {os.path.basename(a.lib)} - pick another --name, or add --force to replace it")
    open(path, 'w', encoding='utf-8').write(footprint(name, ', '.join(desc), body, ext_w, ext_h))
    print(f"made  {name}: {', '.join(desc)}")
    print(f"      {path}")
    print("In KiCad: press A in the panel, search for it, place it. (If it doesn't show, close and reopen the panel.)")


if __name__ == '__main__':
    main()
