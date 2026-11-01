#!/usr/bin/env python3
"""Builds PanelParts.pretty: footprints for parts mounted on the panel only (jacks, charge port, screws).
Each footprint is pure Edge.Cuts geometry, board-only and excluded from BOM/position files.
Reference and value sit on F.Fab, so nothing prints on the panel's silkscreen."""
import os, uuid

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PanelParts.pretty')
S = '(stroke (width 0.05) (type solid)) (fill no) (layer "Edge.Cuts")'

def u(): return f'(uuid "{uuid.uuid4()}")'

def circle(x, y, d):
    return f'\t(fp_circle (center {x} {y}) (end {x + d / 2:g} {y}) {S} {u()})'

def rect(w, h, x=0, y=0):
    return f'\t(fp_rect (start {x - w / 2:g} {y - h / 2:g}) (end {x + w / 2:g} {y + h / 2:g}) {S} {u()})'

def footprint(name, descr, body, ref_y):
    font = '(effects (font (size 1 1) (thickness 0.15)))'
    return f'''(footprint "{name}"
\t(version 20241229)
\t(generator "panelgen")
\t(generator_version "9.0")
\t(layer "F.Cu")
\t(descr "{descr}")
\t(tags "panel cutout")
\t(property "Reference" "P**" (at 0 {-ref_y:g} 0) (layer "F.Fab") {u()} {font})
\t(property "Value" "{name}" (at 0 {ref_y:g} 0) (layer "F.Fab") {u()} {font})
\t(attr board_only exclude_from_pos_files exclude_from_bom)
\t(fp_line (start -1 0) (end 1 0) (stroke (width 0.05) (type solid)) (layer "F.Fab") {u()})
\t(fp_line (start 0 -1) (end 0 1) (stroke (width 0.05) (type solid)) (layer "F.Fab") {u()})
{chr(10).join(body)}
)
'''

PARTS = {
    'Panel_Jack_6.2mm':      ('3.5 mm panel jack, 6.2 mm hole', [circle(0, 0, 6.2)], 5),
    'Panel_Jack_7.2mm':      ('Larger panel jack, 7.2 mm hole', [circle(0, 0, 7.2)], 5.5),
    'Panel_Toggle_5.2mm':    ('Panel-mounted toggle switch, 5.2 mm hole', [circle(0, 0, 5.2)], 4.5),
    'Panel_LED_3.2mm':       ('3 mm LED, 3.2 mm hole', [circle(0, 0, 3.2)], 3),
    'Panel_LED_5.2mm':       ('5 mm LED, 5.2 mm hole', [circle(0, 0, 5.2)], 4.5),
    'Panel_USB-C_Charge_12x4.3mm': (
        'USB-C panel charge port: 12 x 4.3 mm slot, 2 x 2.5 mm screw holes at 16.0 mm spacing',
        [rect(12, 4.3), circle(-8, 0, 2.5), circle(8, 0, 2.5)], 4),
    'Panel_Screw_2.2mm':     ('Case screw hole, 2.2 mm (M2)', [circle(0, 0, 2.2)], 2.5),
    'Panel_Screw_3.2mm':     ('Case screw hole, 3.2 mm (M3)', [circle(0, 0, 3.2)], 3),
}

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for name, (descr, body, ry) in PARTS.items():
        open(os.path.join(OUT, name + '.kicad_mod'), 'w').write(footprint(name, descr, body, ry))
        print('wrote', name)
