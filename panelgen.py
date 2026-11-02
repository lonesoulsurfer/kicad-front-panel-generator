#!/usr/bin/env python3
"""panelgen - generate a front panel .kicad_pcb from a synth PCB.

Reads the PCB, finds panel-facing parts (pots, switches, TFTs, ...) by rule,
and writes a panel board with the outline, margins, case screw holes and every
cutout on Edge.Cuts. Re-running only replaces what panelgen generated, so parts
you placed by hand in the panel file (jacks, charge slot, extra screws) are kept.

Usage:
  python panelgen.py Synth.kicad_pcb -o Synth_panel.kicad_pcb --margin 10 --margin-top 21.5

Footprint field "Panel" (optional; select the part in KiCad, press E, add a field):
  skip            ignore this part
  circle:6.0      override: round hole, diameter 6.0
  square:19.05    override: square
  rect:56x41      override: rectangle, width x height as seen on the panel (exact, no clearance added)
"""
import argparse, fnmatch, json, math, os, re, sys, uuid

# where panel_rules.json and the libraries live: next to the .exe when packaged, next to this file otherwise
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
from shapely.geometry import Point, Polygon, box, MultiPolygon, LineString
from shapely.ops import unary_union
from shapely import affinity

GROUP_NAME = "panelgen"
VERSION = "0.18.2"

# ---------------------------------------------------------------- s-expressions
class Sym(str):
    """Bare (unquoted) token."""

_TOK = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)

def parse(text):
    stack, cur = [], []
    pos = 0
    while True:
        m = _TOK.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        lp, rp, s, a = m.groups()
        if lp:
            stack.append(cur); cur = []
        elif rp:
            done = cur; cur = stack.pop(); cur.append(done)
        elif s is not None:
            cur.append(s.replace('\\"', '"').replace('\\\\', '\\'))
        else:
            try:
                cur.append(float(a) if re.fullmatch(r'-?\d+(\.\d+)?(e-?\d+)?', a) else Sym(a))
            except ValueError:
                cur.append(Sym(a))
    return cur[0]

def kids(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]

def kid(node, name):
    r = kids(node, name)
    return r[0] if r else None

def top_level_spans(text):
    """(start, end) character spans of each top-level child of (kicad_pcb ...)."""
    spans, depth, start, i, n = [], 0, None, 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            if c == '\\': i += 1
            elif c == '"': in_str = False
        elif c == '"':
            in_str = True
        elif c == '(':
            depth += 1
            if depth == 2: start = i
        elif c == ')':
            if depth == 2: spans.append((start, i + 1))
            depth -= 1
        i += 1
    return spans

# ---------------------------------------------------------------- geometry
def rot(x, y, a):
    """KiCad footprint-local -> board offset. Y points down, +angle is CCW on screen."""
    r = math.radians(a)
    return (x * math.cos(r) + y * math.sin(r), -x * math.sin(r) + y * math.cos(r))

def fmt(v):
    s = f"{v:.6f}".rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s

def new_uuid():
    return str(uuid.uuid4())

# ---------------------------------------------------------------- reading the PCB
class Footprint:
    def __init__(self, node):
        self.node = node
        self.lib = node[1]
        at = kid(node, 'at')[1:]
        self.x, self.y = at[0], at[1]
        self.angle = at[2] if len(at) > 2 and isinstance(at[2], float) else 0.0
        self.layer = kid(node, 'layer')[1]
        self.props = {p[1]: p[2] for p in kids(node, 'property') if len(p) > 2}
        self.ref = self.props.get('Reference', '?')
        self.uuid = (kid(node, 'uuid') or [None, None])[1]

    def world(self, lx, ly):
        dx, dy = rot(lx, ly, self.angle)
        return (self.x + dx, self.y + dy)

    def npth(self):
        """Round NPTH holes as (local x, local y, drill)."""
        return [(x, y, w) for x, y, ang, w, h in self.npth_all() if h is None]

    def npth_all(self):
        """Every NPTH hole: (local x, local y, absolute angle, drill w, drill h or None if round)."""
        out = []
        for p in kids(self.node, 'pad'):
            if len(p) > 2 and p[2] == 'np_thru_hole':
                d = kid(p, 'drill') or []
                at = kid(p, 'at')
                ang = at[3] if len(at) > 3 and isinstance(at[3], float) else 0.0
                nums = [v for v in d[1:] if isinstance(v, float)]
                if len(d) > 1 and d[1] == 'oval' and len(nums) >= 2:
                    out.append((at[1], at[2], ang, nums[0], nums[1]))
                elif nums:
                    out.append((at[1], at[2], ang, nums[0], None))
        return out

    def fab_box_centre(self):
        """Centre of the F.Fab outline's bounding box (local coords), or None."""
        pts = []
        for g in self.node:
            if isinstance(g, list) and g and g[0] in ('fp_line', 'fp_rect', 'fp_poly', 'fp_arc'):
                lay = kid(g, 'layer')
                if not lay or lay[1] not in ('F.Fab', 'B.Fab'):
                    continue
                if g[0] == 'fp_poly':
                    pts += [(p[1], p[2]) for p in kid(g, 'pts')[1:] if p[0] == 'xy']
                for k in ('start', 'end', 'mid'):
                    v = kid(g, k)
                    if v: pts.append((v[1], v[2]))
        if len(pts) < 2:
            return None
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

    def body_circle(self, layers=('F.Fab', 'B.Fab')):
        best = None
        for c in kids(self.node, 'fp_circle'):
            if kid(c, 'layer')[1] in layers:
                cx, cy = kid(c, 'center')[1:3]
                ex, ey = kid(c, 'end')[1:3]
                r = math.hypot(ex - cx, ey - cy)
                if best is None or r > best[2]:
                    best = (cx, cy, r)
        return best

def read_board(path):
    text = open(path, encoding='utf-8').read()
    return text, parse(text)

def board_outline(tree):
    """Bounding box of everything on Edge.Cuts (board-level graphics)."""
    pts = []
    for g in tree:
        if not (isinstance(g, list) and g and str(g[0]).startswith('gr_')):
            continue
        lay = kid(g, 'layer')
        if not lay or lay[1] != 'Edge.Cuts':
            continue
        if g[0] == 'gr_circle':
            cx, cy = kid(g, 'center')[1:3]; ex, ey = kid(g, 'end')[1:3]
            r = math.hypot(ex - cx, ey - cy)
            pts += [(cx - r, cy - r), (cx + r, cy + r)]
        elif g[0] == 'gr_poly':
            pts += [(p[1], p[2]) for p in kid(g, 'pts') if p[0] == 'xy']
        else:
            for k in ('start', 'end', 'mid'):
                v = kid(g, k)
                if v: pts.append((v[1], v[2]))
    if not pts:
        sys.exit("No Edge.Cuts outline found on the PCB.")
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

# ---------------------------------------------------------------- Eurorack
# Panel and PCB sizes: Doepfer A-100 widths, and Marcus's 4/8/14HP PCB drawing
# (PCB 0.5 mm in from each side, 11 mm rail zones top and bottom, holes 3 mm from top/bottom, 7.5 mm from left).
ER_HEIGHT, ER_RAIL, ER_PCB_INSET, ER_HOLE_Y, ER_HOLE_X, ER_HOLE_DIA, ER_HP = 128.5, 11.0, 0.5, 3.0, 7.5, 3.2, 5.08
ER_DOEPFER_WIDTH = {1: 5.0, 2: 9.8, 4: 20.0, 6: 30.0, 8: 40.3, 10: 50.5, 12: 60.6, 14: 70.8, 16: 80.9,
                    18: 91.3, 20: 101.3, 21: 106.3, 22: 111.4, 28: 141.9, 42: 213.0}
ER_SIZES = list(range(2, 21)) + [21, 22, 24, 26, 28, 32, 36, 42]

def eurorack_spec(hp):
    """Panel width, rail holes [(x, 't'|'b')] measured from the panel's top-left, and where the width came from."""
    if hp in ER_DOEPFER_WIDTH:
        w, src = ER_DOEPFER_WIDTH[hp], 'Doepfer'
    else:   # not in Doepfer's table: their widths run about 0.3 mm under HP x 5.08
        w, src = math.floor((hp * ER_HP - 0.3) * 10) / 10, 'estimated'
    if hp <= 3:                          # too narrow for 7.5 mm in: one hole top and bottom, centred
        holes = [(round(w / 2, 2), 't'), (round(w / 2, 2), 'b')]
    elif hp <= 5:                        # 4HP drawing: both holes on the left
        holes = [(ER_HOLE_X, 't'), (ER_HOLE_X, 'b')]
    elif hp <= 9:                        # 8HP drawing: top right, bottom left, on the 5.08 grid
        holes = [(round(ER_HOLE_X + (hp - 3) * ER_HP, 2), 't'), (ER_HOLE_X, 'b')]
    else:                                # 14HP drawing: four holes, right pair (HP-4) x 5.08 from the left pair
        xr = round(ER_HOLE_X + (hp - 4) * ER_HP, 2)
        holes = [(ER_HOLE_X, 't'), (xr, 't'), (ER_HOLE_X, 'b'), (xr, 'b')]
    return w, holes, src

def eurorack_template(pcb):
    """(footprint, HP) for a Eurorack_<N>HP template footprint on the PCB, or (None, None)."""
    found = [(fp, int(m.group(1))) for fp in map(Footprint, kids(pcb, 'footprint'))
             for m in [re.search(r'Eurorack_(\d+)HP', fp.lib)] if m]
    if len(found) > 1:
        sys.exit(f"Found {len(found)} Eurorack templates on the PCB ({', '.join(fp.ref for fp, _ in found)}) - keep one.")
    return found[0] if found else (None, None)

# ---------------------------------------------------------------- rules
def parse_override(text):
    """Panel field: 'skip' | 'circle:D' | 'square:S' | 'rect:WxH', then optional 'holes', 'holes=D', 'offset=X,Y'."""
    tokens = text.strip().lower().split()
    if tokens == ['skip']:
        return 'skip'
    if not tokens:
        return None
    m = re.fullmatch(r'(circle|square|rect):([\d.]+)(?:x([\d.]+))?', tokens[0])
    if not m:
        return None
    shape, a, b = m.group(1), float(m.group(2)), m.group(3)
    out = {'shape': 'rect', 'size': [a, float(b) if b else a]} if shape == 'rect' else {'shape': shape, 'size': a}
    for t in tokens[1:]:
        h = re.fullmatch(r'holes(?:=([\d.]+))?', t)
        o = re.fullmatch(r'offset=(-?[\d.]+),(-?[\d.]+)', t)
        if h:
            out['npth_holes'] = True
            if h.group(1):
                out['hole_size'] = float(h.group(1))
        elif o:
            out['offset'] = (float(o.group(1)), float(o.group(2)))
        else:
            return None
    return out

def find_centre(fp, method, log):
    if method == 'origin':
        return (0.0, 0.0)
    if method in ('body_circle', 'fab_circle'):
        c = fp.body_circle()
        if c:
            return (c[0], c[1])
        c = fp.body_circle(('F.SilkS', 'B.SilkS'))
        if c:
            log.append(f"CHECK {fp.ref}: no F.Fab circle in {fp.lib}, centred on its silkscreen circle instead")
            return (c[0], c[1])
        return None
    if method == 'fab_box':
        c = fp.fab_box_centre()
        if c is None:
            log.append(f"CHECK {fp.ref}: no F.Fab outline in {fp.lib}, centred on the footprint origin")
        return c or (0.0, 0.0)
    if method == 'npth_centre':           # middle of the footprint's mounting holes (e.g. a screen module)
        h = fp.npth()
        if h:
            return (sum(x for x, _, _ in h) / len(h), sum(y for _, y, _ in h) / len(h))
        log.append(f"CHECK {fp.ref}: no mounting holes in {fp.lib}, centred on its F.Fab outline instead")
        return fp.fab_box_centre() or (0.0, 0.0)
    if method.startswith('npth:'):
        d = float(method.split(':')[1])
        for x, y, drill in fp.npth():
            if abs(drill - d) < 0.01:
                return (x, y)
        return None
    raise ValueError(f"unknown centre method {method}")

def cutout_geom(fp, shape, size, local_centre, panel_frame=False, offset=(0, 0)):
    lx, ly = local_centre
    if shape == 'circle':
        wx, wy = fp.world(lx, ly)
        wx, wy = wx + offset[0], wy + offset[1]
        return Point(wx, wy).buffer(size / 2, quad_segs=64), (wx, wy, size / 2)
    if panel_frame:   # width x height as seen on the panel, whatever the footprint rotation
        w, h = (size, size) if shape == 'square' else size
        wx, wy = fp.world(lx, ly)
        wx, wy = wx + offset[0], wy + offset[1]
        return box(wx - w / 2, wy - h / 2, wx + w / 2, wy + h / 2), None
    else:
        w, h = (size, size) if shape == 'square' else size
        g = box(lx - w / 2, ly - h / 2, lx + w / 2, ly + h / 2)
    # rotate about footprint origin, then move to board position (KiCad rotation, y-down)
    g = affinity.affine_transform(g, [
        math.cos(math.radians(fp.angle)),  math.sin(math.radians(fp.angle)),
        -math.sin(math.radians(fp.angle)), math.cos(math.radians(fp.angle)),
        fp.x, fp.y])
    return g, None

def matches(lib, pattern):
    pats = pattern if isinstance(pattern, list) else [pattern]
    return any(fnmatch.fnmatch(lib, p) for p in pats)

def with_clearance(size, c):
    if not c:
        return size
    return [v + c for v in size] if isinstance(size, list) else size + c

def drawn_cutouts(tree, layer, log):
    """Shapes drawn on the panel layer (on the board, or inside footprints) become cutouts as drawn."""
    out = []
    for n, (g, circ, uid) in enumerate(edge_shapes(tree, 'gr_', layer=layer, detail=True)):
        key = f'drawn:{uid or n}'
        out.append({'id': key, 'key': key, 'ref': f'{layer} drawing', 'rule': f'drawn on {layer}',
                    'merge': False, 'geom': g, 'circle': circ, 'drawn': True})
    for idx, node in enumerate(kids(tree, 'footprint')):
        fp = Footprint(node)
        fid = fp.uuid or f'fp{idx}'
        if fp.props.get('Panel', '').strip().lower() == 'skip':
            continue
        for n, (g, circ, uid) in enumerate(edge_shapes(node, 'fp_', fp.world, layer=layer, detail=True)):
            key = f'{fid}:drawn{n}'
            out.append({'id': fid, 'key': key, 'ref': fp.ref, 'rule': f'drawn on {layer}',
                        'merge': False, 'geom': g, 'circle': circ, 'drawn': True})
    return out

def drop_markers(cutouts, log, layer):
    """Drawings on the panel layer that sit on a part panelgen already cuts are old markup, not holes.
    Nested or overlapping outlines are never valid on a panel, so they're ignored and reported."""
    solid = [c for c in cutouts if not c.get('drawn') and not c.get('shadow')]
    shadows = [c for c in cutouts if c.get('shadow')]
    cutouts = [c for c in cutouts if not c.get('shadow')]
    keep, inside, over = [], [], {}
    for c in cutouts:
        if not c.get('drawn'):
            keep.append(c); continue
        g = c['geom']
        hits = [o for o in solid if o['geom'].intersects(g)]
        if hits and all(o['geom'].buffer(0.01).contains(g) for o in hits[:1]) and len(hits) == 1:
            inside.append(c)                      # small centre marker inside a hole
        elif hits:
            over[id(c)] = (c, hits)               # outline marker around / over generated cutouts
        elif any(s['geom'].buffer(0.01).contains(g) and g.area < 0.25 * s['geom'].area for s in shadows):
            inside.append(c)                      # marker on a part you skipped
        else:
            keep.append(c)
    if inside:
        log.append(f"NOTE  ignored {len(inside)} {layer} drawing(s) that sit inside other cutouts (old markers?)")
    for c, hits in over.values():
        b = c['geom'].bounds
        refs = sorted({o['ref'] for o in hits}, key=natkey)
        names = refs[0] if len(refs) == 1 else f"{refs[0]}..{refs[-1]} ({len(refs)} parts)"
        log.append(f"NOTE  ignored a {layer} drawing {b[2]-b[0]:.2f} x {b[3]-b[1]:.2f} mm @({c['geom'].centroid.x:.2f}, "
                   f"{c['geom'].centroid.y:.2f}) - it sits on {names}, which panelgen already cuts (old markup?). "
                   f"To use the drawing as the cutout instead, add Panel=skip to {refs[0] if len(refs) == 1 else 'those parts'}")
    for c in keep:
        if c.get('drawn'):
            b = c['geom'].bounds
            log.append(f"drawn {c['ref']}: {b[2]-b[0]:.2f} x {b[3]-b[1]:.2f} mm @({c['geom'].centroid.x:.2f}, {c['geom'].centroid.y:.2f})")
    return keep

def collect_cutouts(tree, cfg, log):
    """Returns list of dicts: ref, rule, geom, merge."""
    out = []
    for idx, node in enumerate(kids(tree, 'footprint')):
        fp = Footprint(node)
        fid = fp.uuid or f'fp{idx}'
        override = parse_override(fp.props['Panel']) if 'Panel' in fp.props else None
        if 'Panel' in fp.props and override is None:
            log.append(f"WARN  {fp.ref}: Panel field '{fp.props['Panel']}' not understood, ignored")
        rule = next((r for r in cfg['rules'] if matches(fp.lib, r['match'])), None)
        if override == 'skip':
            log.append(f"skip  {fp.ref} (Panel=skip)")
            if rule:   # keep its footprint area as a 'shadow' so old markers on it are recognised
                c = find_centre(fp, rule['centre'], [])
                g, _ = cutout_geom(fp, rule['shape'], with_clearance(rule['size'], rule.get('clearance', 0)), c or (0.0, 0.0))
                out.append({'id': fid, 'key': f'{fid}:shadow', 'ref': fp.ref, 'rule': 'skipped', 'geom': g, 'shadow': True})
            continue
        if rule is None and override is None:
            continue
        if override is None and rule.get('shape') == 'none':     # a known part that stays behind the panel
            cfg.setdefault('_none_ids', set()).add(fid)
            continue
        rule = dict(rule or {'name': 'override', 'centre': 'fab_box'})
        if override:
            rule.update(override); rule['name'] += ' (Panel override)'
            rule['clearance'] = 0          # override is the exact final size
            rule['panel_frame'] = True
        if fp.layer != 'F.Cu':
            log.append(f"WARN  {fp.ref}: {rule['name']} is on the back of the board - check the panel side")
        centre = find_centre(fp, rule['centre'], log)
        if centre is None:
            log.append(f"WARN  {fp.ref}: couldn't find centre ({rule['centre']}) in {fp.lib}, using origin")
            centre = (0.0, 0.0)
        size = with_clearance(rule['size'], rule.get('clearance', 0))
        if cfg.get('grow') and not override and rule.get('name') != 'Mounting hole':
            size = with_clearance(size, cfg['grow'])
            cfg['_grown'] = cfg.get('_grown', 0) + 1
        geom, circ = cutout_geom(fp, rule['shape'], size, centre, rule.get('panel_frame', False), rule.get('offset', (0, 0)))
        out.append({'id': fid, 'key': f'{fid}:main', 'ref': fp.ref, 'rule': rule['name'],
                    'merge': rule.get('merge', False), 'geom': geom, 'circle': circ})
        if rule.get('npth_holes'):
            for n, (x, y, _) in enumerate(fp.npth()):
                wx, wy = fp.world(x, y)
                r = rule.get('hole_size', cfg['panel_hole_for_npth']) / 2
                out.append({'id': fid, 'key': f'{fid}:mount{n}', 'ref': fp.ref, 'rule': rule['name'] + ' mount', 'merge': False,
                            'geom': Point(wx, wy).buffer(r, quad_segs=64), 'circle': (wx, wy, r)})
    return out

# ---------------------------------------------------------------- shapes drawn by hand
def arc_points(s, m, e, step_deg=5):
    """Points along a 3-point arc."""
    (ax, ay), (bx, by), (cx, cy) = s, m, e
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [s, e]
    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a0, a1, am = (math.atan2(p[1] - uy, p[0] - ux) for p in (s, e, m))
    def ccw(a, b):
        return (b - a) % (2 * math.pi)
    sweep = ccw(a0, a1)
    if ccw(a0, am) > sweep:          # mid point says go the other way round
        sweep -= 2 * math.pi
    n = max(2, int(abs(math.degrees(sweep)) / step_deg) + 1)
    pts = [(ux + r * math.cos(a0 + sweep * i / n), uy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]
    pts[0], pts[-1] = s, e          # ends exactly where KiCad says, so outlines close
    return pts

def slot_geom(cx, cy, ang, w, h):
    """Obround slot w x h (KiCad oval drill), rotated by the pad's absolute angle."""
    from shapely.geometry import LineString
    if abs(w - h) < 1e-9:
        return Point(cx, cy).buffer(w / 2, quad_segs=64)
    half = (max(w, h) - min(w, h)) / 2
    seg = LineString([(-half, 0), (half, 0)] if w > h else [(0, -half), (0, half)])
    g = seg.buffer(min(w, h) / 2, quad_segs=32)
    r = math.radians(ang)
    return affinity.affine_transform(g, [math.cos(r), math.sin(r), -math.sin(r), math.cos(r), cx, cy])

def snap(p):
    return (round(p[0], 6), round(p[1], 6))

def edge_shapes(items, prefix, to_world=lambda x, y: (x, y), layer='Edge.Cuts', detail=False):
    """Closed shapes on a layer from circles, rects, polys and chains of lines/arcs.
    detail=True returns (geom, circle-or-None, uuid-or-None) tuples."""
    from shapely.geometry import LineString
    from shapely.ops import polygonize
    shapes, segs, seg_ids = [], [], []
    for g in items:
        if not (isinstance(g, list) and g and str(g[0]).startswith(prefix)):
            continue
        lay = kid(g, 'layer')
        if not lay or lay[1] != layer:
            continue
        uid = kid(g, 'uuid'); uid = uid[1] if uid else None
        kind = str(g[0])[len(prefix):]
        if kind == 'circle':
            cx, cy = kid(g, 'center')[1:3]; ex, ey = kid(g, 'end')[1:3]
            wx, wy = to_world(cx, cy); r = math.hypot(ex - cx, ey - cy)
            shapes.append((Point(wx, wy).buffer(r, quad_segs=64), (wx, wy, r), uid))
        elif kind == 'rect':
            (x1, y1), (x2, y2) = kid(g, 'start')[1:3], kid(g, 'end')[1:3]
            shapes.append((Polygon([to_world(x, y) for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))]), None, uid))
        elif kind == 'poly':
            pts = [to_world(p[1], p[2]) for p in kid(g, 'pts')[1:] if p[0] == 'xy']
            if len(pts) >= 3:
                shapes.append((Polygon(pts), None, uid))
        elif kind == 'line':
            segs.append(LineString([snap(to_world(*kid(g, 'start')[1:3])), snap(to_world(*kid(g, 'end')[1:3]))])); seg_ids.append(uid)
        elif kind == 'arc':
            pts = arc_points(tuple(kid(g, 'start')[1:3]), tuple(kid(g, 'mid')[1:3]), tuple(kid(g, 'end')[1:3]))
            segs.append(LineString([snap(to_world(x, y)) for x, y in pts])); seg_ids.append(uid)
    if segs:
        tag = min(i for i in seg_ids if i) if any(seg_ids) else None
        for n, p in enumerate(polygonize(unary_union(segs))):
            shapes.append((p, None, f'{tag}#{n}' if tag else None))
    return shapes if detail else [g for g, _, _ in shapes]

# ---------------------------------------------------------------- hand-placed panel items
def manual_cutouts(tree, names=None):
    """Cutouts you added in the panel file: PanelParts footprints and anything drawn on Edge.Cuts."""
    out = []
    for idx, node in enumerate(kids(tree, 'footprint')):
        fp = Footprint(node)
        fid = 'manual:' + (fp.uuid or f'fp{idx}')
        parts = []
        for x, y, ang, w, h in fp.npth_all():
            wx, wy = fp.world(x, y)
            parts.append(Point(wx, wy).buffer(w / 2, quad_segs=64) if h is None else slot_geom(wx, wy, ang, w, h))
        parts += edge_shapes(node, 'fp_', fp.world)
        for g in parts:
            out.append({'id': fid, 'ref': fp.ref, 'rule': 'hand-placed', 'merge': False, 'geom': g, 'manual': True, 'fp': fp})
    # shapes drawn straight onto the panel's Edge.Cuts (not part of the panelgen group)
    names = names or {}
    for n, (g, _, uid) in enumerate(edge_shapes(tree, 'gr_', detail=True)):
        base = (uid or '').split('#')[0]
        ref = names.get(base, 'drawn shape')
        out.append({'id': f'edited:{ref}' if base in names else f'drawn{n}', 'ref': ref,
                    'rule': 'edited in panel' if base in names else 'hand-drawn', 'merge': False,
                    'geom': g, 'manual': True})
    return out

# ---------------------------------------------------------------- checks
def merge_and_check(cutouts, outline, min_web, log, merge_tol=None):
    """Merge touching mergeable cutouts; flag overlaps, thin webs, cutouts off the panel."""
    mergeable = [c for c in cutouts if c['merge']]
    others = [c for c in cutouts if not c['merge']]
    groups = []
    if merge_tol is None:
        merge_tol = max(0.1, min_web)   # a sliver thinner than the minimum web can't be made: join it
    if mergeable:
        # gaps under merge_tol are treated as touching (morphological close, square corners kept)
        h = merge_tol / 2
        slivers = []
        for i, c1 in enumerate(mergeable):
            for c2 in mergeable[i + 1:]:
                d = c1['geom'].distance(c2['geom'])
                if 0.001 < d < 0.1:
                    log.append(f"NOTE  {c1['ref']} and {c2['ref']} miss touching by {d:.3f} mm - "
                               f"merged anyway (one is probably off-grid on the PCB)")
                elif 0.1 <= d < merge_tol:
                    slivers.append(d)
        if slivers:
            log.append(f"NOTE  {len(slivers)} gaps of {min(slivers):.2f}-{max(slivers):.2f} mm between switches are thinner "
                       f"than the {min_web} mm minimum web - joined into one slot")
        u = unary_union([c['geom'].buffer(h, join_style='mitre') for c in mergeable]).buffer(-h, join_style='mitre')
        for poly in (u.geoms if isinstance(u, MultiPolygon) else [u]):
            members = [c for c in mergeable if c['geom'].intersects(poly)]
            refs = {c['ref'] for c in members}
            groups.append({'ids': {c['id'] for c in members}, 'refs': refs,
                           'key': 'slot:' + '+'.join(sorted(c['key'] for c in members)),
                           'member_keys': sorted(c['key'] for c in members), 'geom': poly.simplify(1e-3), 'circle': None, 'manual': False})
            if len(members) > 1:
                b = poly.bounds
                log.append(f"slot  {len(members)} switches merged -> {b[2]-b[0]:.2f} x {b[3]-b[1]:.2f} mm "
                           f"({', '.join(sorted(refs, key=natkey))})")
    groups += [{'ids': {c['id']}, 'refs': {c['ref']}, 'key': c.get('key'), 'member_keys': [c.get('key')],
                'rule': c['rule'], 'geom': c['geom'], 'drawn': c.get('drawn', False), 'circle': c.get('circle'),
                'manual': c.get('manual', False)} for c in others]

    problems = 0
    for g in groups:
        if not outline.contains(g['geom']):
            log.append(f"ERROR {fmt_refs(g)} cutout crosses or sits outside the panel edge"); problems += 1
        else:
            d = outline.exterior.distance(g['geom'])
            if d < min_web:
                log.append(f"WARN  {fmt_refs(g)} only {d:.2f} mm from the panel edge"); problems += 1
    clash = {}
    for i, a in enumerate(groups):
        for b in groups[i + 1:]:
            if a['ids'] & b['ids']:
                continue  # same footprint: spacing is by design
            d = a['geom'].distance(b['geom'])
            if d == 0 and (a.get('drawn') or b.get('drawn')):
                dr, other = (a, b) if a.get('drawn') else (b, a)
                clash.setdefault(id(dr), (dr, []))[1].append(other)
                continue
            if d == 0:
                log.append(f"ERROR {fmt_refs(a)} overlaps {fmt_refs(b)}"); problems += 1
            elif d < min_web:
                log.append(f"WARN  {d:.2f} mm web between {fmt_refs(a)} and {fmt_refs(b)} (min {min_web})"); problems += 1
    for dr, others in clash.values():
        b = dr['geom'].bounds
        names = sorted({r for o in others for r in o['refs']}, key=natkey)
        what = names[0] if len(names) == 1 else f"{names[0]}..{names[-1]} ({len(names)} parts)"
        log.append(f"ERROR {fmt_refs(dr)} ({b[2]-b[0]:.2f} x {b[3]-b[1]:.2f} mm) overlaps {what}. "
                   f"Old markup? move it off the panel layer. Meant as the cutout? add Panel=skip to the parts it replaces")
        problems += 1
    return groups, problems

def natkey(s):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)]

def fmt_refs(g):
    r = sorted(g['refs'], key=natkey)
    c = g['geom'].centroid
    name = r[0] if len(r) == 1 else f"{r[0]}..{r[-1]} slot"
    return f"{name} @({c.x:.2f}, {c.y:.2f})"

# ---------------------------------------------------------------- writing
STROKE = '(stroke (width 0.05) (type solid)) (fill no) (layer "Edge.Cuts")'

def stable_uuid(key, n=0):
    """Same source part -> same ID on every run, so deletions in the panel can be detected."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'panelgen:{key}#{n}'))

def emit_geom(grp, uuids):
    """Cutout group -> list of KiCad Edge.Cuts items. Circles stay true circles."""
    items = []
    g = grp['geom']
    seq = iter(range(1000))
    new_uuid = lambda: stable_uuid(grp['key'], next(seq))
    if grp.get('circle'):
        cx, cy, r = grp['circle']
        u = new_uuid(); uuids.append(u)
        items.append(f'\t(gr_circle (center {fmt(cx)} {fmt(cy)}) (end {fmt(cx + r)} {fmt(cy)}) {STROKE} (uuid "{u}"))')
        return items
    if isinstance(g, Polygon) and not g.interiors and abs(g.area - g.envelope.area) < 1e-6:
        x1, y1, x2, y2 = g.bounds
        u = new_uuid(); uuids.append(u)
        items.append(f'\t(gr_rect (start {fmt(x1)} {fmt(y1)}) (end {fmt(x2)} {fmt(y2)}) {STROKE} (uuid "{u}"))')
        return items
    polys = g.geoms if isinstance(g, MultiPolygon) else [g]
    for p in polys:
        for ring in [p.exterior] + list(p.interiors):
            pts = list(ring.coords)[:-1]
            u = new_uuid(); uuids.append(u)
            xy = ' '.join(f'(xy {fmt(x)} {fmt(y)})' for x, y in pts)
            items.append(f'\t(gr_poly (pts {xy}) {STROKE} (uuid "{u}"))')
    return items

def outline_items(x1, y1, x2, y2, radius, uuids):
    seq = iter(range(100))
    new_uuid = lambda: stable_uuid('outline', next(seq))
    u = new_uuid(); uuids.append(u)
    if radius <= 0:
        return [f'\t(gr_rect (start {fmt(x1)} {fmt(y1)}) (end {fmt(x2)} {fmt(y2)}) {STROKE} (uuid "{u}"))']
    uuids.pop()
    r = radius; items = []
    def line(a, b):
        u = new_uuid(); uuids.append(u)
        items.append(f'\t(gr_line (start {fmt(a[0])} {fmt(a[1])}) (end {fmt(b[0])} {fmt(b[1])}) {STROKE.replace(" (fill no)", "")} (uuid "{u}"))')
    def arc(s, m, e):
        u = new_uuid(); uuids.append(u)
        items.append(f'\t(gr_arc (start {fmt(s[0])} {fmt(s[1])}) (mid {fmt(m[0])} {fmt(m[1])}) (end {fmt(e[0])} {fmt(e[1])}) {STROKE.replace(" (fill no)", "")} (uuid "{u}"))')
    k = r * (1 - math.sqrt(0.5))
    line((x1 + r, y1), (x2 - r, y1)); arc((x2 - r, y1), (x2 - k, y1 + k), (x2, y1 + r))
    line((x2, y1 + r), (x2, y2 - r)); arc((x2, y2 - r), (x2 - k, y2 - k), (x2 - r, y2))
    line((x2 - r, y2), (x1 + r, y2)); arc((x1 + r, y2), (x1 + k, y2 - k), (x1, y2 - r))
    line((x1, y2 - r), (x1, y1 + r)); arc((x1, y1 + r), (x1 + k, y1 + k), (x1 + r, y1))
    return items

def header_from(pcb_text, pcb_tree):
    """New board header: copy layers and setup from the source PCB so the stack-up matches."""
    spans = top_level_spans(pcb_text)
    keep = []
    for s, e in spans:
        head = pcb_text[s + 1:s + 20].split()[0]
        if head in ('layers', 'setup'):
            keep.append('\t' + pcb_text[s:e])
    return ('(kicad_pcb\n\t(version 20241229)\n\t(generator "panelgen")\n\t(generator_version "9.0")\n'
            '\t(general\n\t\t(thickness 1.6)\n\t\t(legacy_teardrops no)\n\t)\n\t(paper "A4")\n'
            + '\n'.join(keep) + '\n\t(net 0 "")\n')

def strip_generated(panel_text, panel_tree, extra_uuids=(), keep_uuids=()):
    """Remove items panelgen made last time; keep everything else byte-for-byte."""
    members = set(extra_uuids)
    for g in kids(panel_tree, 'group'):
        if g[1] == GROUP_NAME:
            members |= set(kid(g, 'members')[1:])
    members -= set(keep_uuids)
    spans = top_level_spans(panel_text)
    out, last, n = [], 0, 0
    for s, e in spans:
        chunk = panel_text[s:e]
        m = re.search(r'\(uuid "([^"]+)"\)\s*\)?\s*$', chunk)
        uid = m.group(1) if m else None
        if uid is None and chunk.startswith('(gr_'):
            try:
                u = kid(parse(chunk), 'uuid'); uid = u[1] if u else None
            except Exception:
                uid = None
        is_our_group = chunk.startswith('(group') and f'"{GROUP_NAME}"' in chunk[:40]
        if is_our_group or (uid and uid in members):
            n += 0 if is_our_group else 1
            out.append(panel_text[last:s].rstrip(' \t'))
            last = e
            # swallow trailing newline
            if panel_text[last:last + 1] == '\n': last += 1
    out.append(panel_text[last:])
    body = ''.join(out).rstrip()
    assert body.endswith(')'), "unexpected panel file ending"
    return body[:-1].rstrip() + '\n', n

# ---------------------------------------------------------------- memory of deletions
def item_boxes(tree):
    """(uuid, bbox) of every board-level Edge.Cuts item in a panel file."""
    out = []
    for g in tree:
        if not (isinstance(g, list) and g and str(g[0]).startswith('gr_')):
            continue
        lay = kid(g, 'layer')
        if not lay or lay[1] != 'Edge.Cuts':
            continue
        u = kid(g, 'uuid'); u = u[1] if u else None
        if g[0] == 'gr_circle':
            cx, cy = kid(g, 'center')[1:3]; ex, ey = kid(g, 'end')[1:3]
            r = math.hypot(ex - cx, ey - cy); b = (cx - r, cy - r, cx + r, cy + r)
        elif g[0] == 'gr_poly':
            pts = [(p[1], p[2]) for p in kid(g, 'pts')[1:] if p[0] == 'xy']
            b = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        elif g[0] == 'gr_rect':
            (ax, ay), (bx, by) = kid(g, 'start')[1:3], kid(g, 'end')[1:3]
            b = (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
        else:
            continue
        out.append((u, b))
    return out

def same_box(a, b, tol=0.01):
    return all(abs(p - q) <= tol for p, q in zip(a, b))

def find_deletions(memory, panel_tree, groups, log):
    """Keys of generated cutouts the user deleted in the panel since the last run."""
    present = item_boxes(panel_tree)
    uuids = {u for u, _ in present}
    deleted = {}
    if memory.get('generated'):
        for key, info in memory['generated'].items():
            gone_id = not (set(info['uuids']) & uuids)
            gone_shape = not any(same_box(b, info['box']) for _, b in present)
            if gone_id and gone_shape:
                deleted[key] = info
        return deleted
    # first run on a panel made before this feature: match by shape only
    had_group = any(g[1] == GROUP_NAME for g in kids(panel_tree, 'group'))
    if not had_group:
        return deleted
    missing = [g for g in groups if not any(same_box(b, g['geom'].bounds) for _, b in present)]
    if groups and len(missing) <= max(1, len(groups) // 5):
        for g in missing:
            deleted[g['key']] = describe(g)
        if missing:
            log.append(f"NOTE  first run with deletion memory: matched the panel by shape")
    elif missing:
        log.append(f"NOTE  {len(missing)} cutouts changed since this panel was made; not treating any as deleted")
    return deleted

def find_edits(memory, panel_tree):
    """Generated cutouts whose ID is still in the panel but whose shape you changed (resized/moved)."""
    boxes = {u: b for u, b in item_boxes(panel_tree) if u}
    edited = {}
    for key, info in memory.get('generated', {}).items():
        present = [u for u in info['uuids'] if u in boxes]
        if present and not same_box(boxes[present[0]], info['box']):
            edited[key] = dict(info, box_now=[round(v, 4) for v in boxes[present[0]]])
    return edited

def describe(g):
    b = g['geom'].bounds
    c = g['geom'].centroid
    return {'ref': fmt_refs_plain(g), 'refs': sorted(g['refs'], key=natkey), 'what': g.get('rule', 'slot'),
            'at': [round(c.x, 3), round(c.y, 3)],
            'box': [round(v, 4) for v in b], 'member_keys': g['member_keys']}

def fmt_refs_plain(g):
    r = sorted(g['refs'], key=natkey)
    return r[0] if len(r) == 1 else f"{r[0]}..{r[-1]} slot"

def load_memory(path):
    try:
        return json.load(open(path, encoding='utf-8'))
    except (OSError, ValueError):
        return {}

# ---------------------------------------------------------------- svg template
MARKER_LAYER = 'User.2'

def part_markers(pcb, ids, outline):
    """Where parts that don't get a cutout are (edge-mounted jacks and the like), plus shapes drawn on User.2:
    guides for lining up artwork. Never cut, never printed."""
    out = []
    for fp in map(Footprint, kids(pcb, 'footprint')):
        if fp.uuid not in ids:
            continue
        b = courtyard_box(fp) or (fp.x - 2, fp.y - 2, fp.x + 2, fp.y + 2)
        name = guess_label(fp)[0]
        out.append(dict(geom=box(*b), text=fp.ref + (f' {name}' if name else ''), at=(fp.x, fp.y)))
    for g in edge_shapes(pcb, 'gr_', layer=MARKER_LAYER):
        out.append(dict(geom=g, text='', at=None))
    return [m for m in out if m['geom'].intersects(outline.buffer(5))]

def write_svg(path, x1, y1, x2, y2, shapes, labels=(), a=None):
    markers = getattr(a, '_markers', []) if a is not None else []
    """1:1 template for Inkscape. 1 unit = 1 mm, and the page sits at the panel's own KiCad coordinates, so anything
    drawn on the Artwork layer lands exactly there when it's imported back."""
    w, h = x2 - x1, y2 - y1
    L = lambda i, label, extra='': (f'<g inkscape:groupmode="layer" id="{i}" inkscape:label="{label}"{extra}>')
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
             'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" '
             f'width="{fmt(w)}mm" height="{fmt(h)}mm" viewBox="{fmt(x1)} {fmt(y1)} {fmt(w)} {fmt(h)}">',
             '<sodipodi:namedview inkscape:document-units="mm" pagecolor="#d4d8dc" inkscape:pageopacity="1" '
             'inkscape:pagecheckerboard="false" showgrid="true">'
             '<inkscape:grid id="grid1" type="xygrid" units="mm" spacingx="1" spacingy="1" empspacing="5" '
             f'originx="0" originy="0" visible="true" enabled="true"/></sodipodi:namedview>',
             L('artwork', 'Artwork') + '</g>',
             L('panel', 'Panel cutouts (guide - rebuilt every Generate)', ' fill="none" stroke="#d40000" stroke-width="0.15"'),
             f'<rect x="{fmt(x1)}" y="{fmt(y1)}" width="{fmt(w)}" height="{fmt(h)}"/>']
    for grp in shapes:
        g = grp['geom']
        if grp.get('circle'):
            cx, cy, r = grp['circle']
            parts.append(f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}"/>')
        else:
            for p in (g.geoms if isinstance(g, MultiPolygon) else [g]):
                d = 'M' + ' L'.join(f'{fmt(x)},{fmt(y)}' for x, y in list(p.exterior.coords)[:-1]) + ' Z'
                parts.append(f'<path d="{d}"/>')
    parts += ['</g>']
    if markers:
        parts.append(L('markers', 'Part markers (guide - not printed or cut)',
                       ' fill="none" stroke="#1f6feb" stroke-width="0.2" stroke-dasharray="0.8,0.5"'))
        for mk in markers:
            g = mk['geom']
            for p in (g.geoms if hasattr(g, 'geoms') else [g]):
                d = 'M' + ' L'.join(f'{fmt(x)},{fmt(y)}' for x, y in list(p.exterior.coords)[:-1]) + ' Z'
                parts.append(f'<path d="{d}"/>')
            if mk['at']:
                x, y = mk['at']
                parts.append(f'<path d="M{fmt(x - 1.5)},{fmt(y)} L{fmt(x + 1.5)},{fmt(y)} M{fmt(x)},{fmt(y - 1.5)} L{fmt(x)},{fmt(y + 1.5)}" stroke-dasharray="none"/>')
            if mk['text']:
                bx = g.bounds
                t = mk['text'].replace('&', '&amp;').replace('<', '&lt;')
                parts.append(f'<text x="{fmt((bx[0] + bx[2]) / 2)}" y="{fmt(bx[3] + 2.2)}" font-family="sans-serif" '
                             f'font-size="1.8" text-anchor="middle" fill="#1f6feb" stroke="none">{t}</text>')
        parts.append('</g>')
    if labels:
        fam = (a.label_font or 'sans-serif').replace('"', '')
        parts.append(L('labels', 'Labels (made by Panel Generator - not imported)', ' style="display:inline;opacity:0.5"'))
        parts.append(f'<g font-family="{fam}" text-anchor="middle" dominant-baseline="central" fill="#000"'
                     + (' font-weight="bold"' if a.label_bold == 'on' else '') + '>')
        for lb in labels:
            t = lb['text'].replace('&', '&amp;').replace('<', '&lt;')
            parts.append(f'<text x="{fmt(lb["x"])}" y="{fmt(lb["y"])}" font-size="{fmt(lb["h"] * 1.4)}">{t}</text>')
        parts += ['</g>', '</g>']
    # the red cutouts go on top, so filled artwork can't hide them
    pi = next(i for i, p in enumerate(parts) if 'id="panel"' in p)
    pe = parts.index('</g>', pi) + 1
    panel_layer = parts[pi:pe]; del parts[pi:pe]
    parts += panel_layer + ['</svg>']
    open(path, 'w', encoding='utf-8').write('\n'.join(parts))

def artwork_path_for(out_path):
    return re.sub(r'\.kicad_pcb$', '', out_path) + '_artwork.svg'

def courtyard_box(fp):
    """World bounding box of a footprint's courtyard, or None."""
    pts = []
    for g in fp.node:
        if not (isinstance(g, list) and g and str(g[0]).startswith('fp_')):
            continue
        lay = kid(g, 'layer')
        if not lay or not str(lay[1]).endswith('CrtYd'):
            continue
        if g[0] == 'fp_circle':
            cx, cy = kid(g, 'center')[1:3]; ex, ey = kid(g, 'end')[1:3]
            r = math.hypot(ex - cx, ey - cy)
            local = [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
        elif g[0] == 'fp_poly':
            local = [(p[1], p[2]) for p in kid(g, 'pts') if p[0] == 'xy']
        elif g[0] == 'fp_rect':
            (sx, sy), (ex, ey) = kid(g, 'start')[1:3], kid(g, 'end')[1:3]
            local = [(sx, sy), (ex, sy), (ex, ey), (sx, ey)]
        else:
            local = [tuple(kid(g, k)[1:3]) for k in ('start', 'mid', 'end') if kid(g, k)]
        pts += [fp.world(x, y) for x, y in local]
    if not pts:
        return None
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)

def check_rails(pcb, tpl, x1, y1, x2, y2, log, bad=None):
    """Eurorack: nothing may sit in the rail zones behind the panel. Returns the number of problems."""
    top, bottom = y1 + ER_RAIL, y2 - ER_RAIL
    n = 0
    try:   # a PCB outline drawn on the board itself (the template's own outline is always clear)
        bx1, by1, bx2, by2 = board_outline(pcb)
        if by1 < top - 1e-3 or by2 > bottom + 1e-3 or bx1 < x1 - 1e-3 or bx2 > x2 + 1e-3:
            log.append(f"ERROR the PCB outline goes outside the area between the rails "
                       f"({x2 - x1 - 2 * ER_PCB_INSET:g} x {bottom - top:g} mm) - it won't fit in a case"); n += 1
    except SystemExit:
        pass
    for fp in map(Footprint, kids(pcb, 'footprint')):
        if fp.uuid == tpl.uuid:
            continue
        b = courtyard_box(fp)
        if not b:
            if not fp.props.get('Reference', '').startswith(('PNL', '#')):
                log.append(f"NOTE  {fp.ref} has no courtyard, so it wasn't checked against the rails")
            continue
        over = max(top - b[1], b[3] - bottom)
        if over > 1e-3:
            where = 'top' if top - b[1] >= b[3] - bottom else 'bottom'
            log.append(f"ERROR {fp.ref} @({fp.x:.2f}, {fp.y:.2f}) reaches {over:.2f} mm into the {where} rail zone - it will hit the rail"); n += 1
            if bad is not None:
                bad.append((fp.ref, b))
    return n

def fill_preview(pv, groups, outline, panel_box, a, log, problems, eurorack, pcb_box, rail_bad, uncut=(), **extra):
    """Geometry for the window's live preview, each cutout marked ok / warn / error."""
    status = ['ok'] * len(groups)
    def mark(i, st):
        if status[i] != 'error':
            status[i] = st
    edge = outline.exterior
    for i, g in enumerate(groups):
        if not outline.buffer(1e-6).contains(g['geom']):
            mark(i, 'error')
        elif edge.distance(g['geom']) < a.min_web - 1e-6:
            mark(i, 'warn')
        elif str(g.get('key') or '').startswith('case:') and edge.distance(g['geom']) < a.screw_dia - 1e-6:
            mark(i, 'warn')
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            gi, gj = groups[i]['geom'], groups[j]['geom']
            if gi.intersects(gj):
                mark(i, 'error'); mark(j, 'error')
            elif gi.distance(gj) < a.min_web - 1e-6:
                mark(i, 'warn'); mark(j, 'warn')
    pv.update(outline=outline, panel_box=panel_box, pcb_box=pcb_box, eurorack=eurorack, rail=ER_RAIL,
              rail_bad=rail_bad, uncut=list(uncut), log=list(log), problems=problems, label_font=a.label_font,
              label_bold=a.label_bold == 'on', **extra,
              shapes=[dict(geom=g['geom'], label=fmt_refs_plain(g), rule=g.get('rule') or 'slot',
                           manual=g.get('manual', False), status=st) for g, st in zip(groups, status)])

# footprint names that usually mean "this pokes through the panel"
PANEL_HINTS = re.compile(r'jack|audio|potentiometer|(^|[_\W])pot|encoder|switch|(^|[_\W])sw[_\W]|button|toggle|tact|'
                         r'(^|[_\W])led|tft|oled|lcd|display|screen|din[_-]?5|midi|slider|fader|knob')

def parts_without_cutouts(pcb, cutouts, tpl, log, found=None, ignore=None, none_ids=frozenset()):
    """CHECK lines for parts that look like they go through the panel but got no cutout."""
    covered_ids = {c['id'] for c in cutouts}
    geoms = [c['geom'] for c in cutouts if c.get('geom') is not None]
    missing = {}
    for fp in map(Footprint, kids(pcb, 'footprint')):
        if (tpl and fp.uuid == tpl.uuid) or fp.uuid in covered_ids or 'Panel' in fp.props:
            continue
        if ignore and fp.uuid in ignore:
            continue
        if fp.uuid in none_ids:
            continue
        name = fp.lib.split(':')[-1]
        if not PANEL_HINTS.search(name.lower()) or 'mountinghole' in name.lower():
            continue
        b = courtyard_box(fp)
        spot = box(*b) if b else Point(fp.x, fp.y).buffer(1)
        if any(g.intersects(spot) for g in geoms):      # e.g. a window drawn over it on User.1
            continue
        missing.setdefault(name, []).append(fp)
        if found is not None:
            found.append((fp.ref, b or (fp.x - 2, fp.y - 2, fp.x + 2, fp.y + 2), fp.uuid))
    for name, fps in sorted(missing.items()):
        log.append(f"CHECK no cutout for {', '.join(sorted((f.ref for f in fps), key=natkey))} ({name}) - there's no rule for this footprint")
    if missing:
        log.append("NOTE  if a part above pokes through the panel, give it a cutout: draw it on User.1, add a Panel field "
                   "(e.g. circle:6.2), or add a rule to panel_rules.json. If it doesn't need one, click it in the preview "
                   "(or add Panel=skip to it)")
    return missing

# ---------------------------------------------------------------- labels
COMPONENT_VALUE = re.compile(r'^\d+([.,]\d+)?\s*[pnuµmkKMGR]\d*[a-zA-ZΩ]{0,3}$')       # 10K, 100nF, 4K7, 220R
PART_NUMBER = re.compile(r'^[A-Z]{2,}[A-Z0-9-]*\d{2,}[A-Z0-9-]*$')                       # ILI9341, NE5532, TL072
GENERIC_VALUE = re.compile(r'^(~|led|pot(entiometer)?|jack|switch|encoder|button|display|screen|tft|oled|lcd|'
                           r'audiojack\w*|conn\w*|sw|rotary\w*|r_pot\w*|toggle|push|spdt|dpdt)$', re.I)
DESIGNATOR = re.compile(r'^[A-Z]{1,4}\d+[A-Z]?$')                                         # SW3, RV1, J2, TFT1
# standard reference prefixes: 'RV1' is a designator, but 'AMT1' or 'FX1' is a name someone gave the part
REF_PREFIXES = {'A', 'B', 'BT', 'BAT', 'BZ', 'C', 'CN', 'CON', 'CP', 'D', 'DS', 'DISP', 'E', 'ENC', 'F', 'FB', 'FL',
                'H', 'HS', 'IC', 'J', 'JP', 'K', 'L', 'LCD', 'LED', 'LS', 'M', 'MH', 'MK', 'MOD', 'NT', 'OLED', 'P',
                'POT', 'PS', 'Q', 'R', 'RN', 'RV', 'S', 'SW', 'T', 'TFT', 'TH', 'TP', 'U', 'VR', 'X', 'Y', 'Z'}

def guess_label(fp):
    """(text, where it came from): a Label field, else a Value that reads like a name, else a named Reference."""
    for k in ('Label', 'Panel Label', 'label'):
        if fp.props.get(k, '').strip():
            return fp.props[k].strip(), 'Label field'
    v = fp.props.get('Value', '').strip()
    if v and '_' not in v and not GENERIC_VALUE.match(v) and not COMPONENT_VALUE.match(v) and not PART_NUMBER.match(v):
        return v, 'Value'
    r = fp.ref.strip()
    prefix = re.sub(r'\d+[A-Z]?$', '', r)
    if r and not any(ch in r for ch in '*?') and prefix and (not DESIGNATOR.match(r) or prefix not in REF_PREFIXES):
        return re.sub(r'(?<=[A-Za-z])\d+$', '', r), 'Reference'
    return '', ''

def skipped_label(fp):
    """When guess_label finds nothing: (the text it passed over, why), so the window can say so."""
    v = fp.props.get('Value', '').strip()
    if v and v != '~':
        why = ('is a component value' if COMPONENT_VALUE.match(v) else 'is a generic name' if GENERIC_VALUE.match(v)
               else 'looks like a part name')
        return v, why
    if fp.ref.strip():
        return fp.ref.strip(), 'is a standard reference'
    return '', ''

KICAD_EM = 1.4      # KiCad draws TrueType text with an em square 1.4 x the text size (outline_font.h)
_font_files = {}

def font_file(family, bold=False):
    """Path of an installed TrueType/OpenType font, or None."""
    key = (family.lower(), bold)
    if key in _font_files:
        return _font_files[key]
    path = None
    try:
        import winreg
        hits = []
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                k = winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')
            except OSError:
                continue
            i = 0
            while True:
                try:
                    name, val, _ = winreg.EnumValue(k, i)
                except OSError:
                    break
                i += 1
                base = re.sub(r'\s*\((TrueType|OpenType)\)$', '', name).strip().lower()
                if base == family.lower() or base == family.lower() + (' bold' if bold else ' regular'):
                    if not os.path.isabs(val):
                        val = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', val)
                    hits.append((('bold' in base) == bold, val))
        if hits:
            path = sorted(hits, reverse=True)[0][1]
    except ImportError:
        import subprocess
        try:
            r = subprocess.run(['fc-match', '-f', '%{file}', f'{family}:bold' if bold else family],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout and family.lower().split()[0] in r.stdout.lower().replace('-', ' ').replace('_', ' '):
                path = r.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    _font_files[key] = path if path and os.path.exists(path) else None
    return _font_files[key]

def text_width(text, h, bold=False, font=''):
    """Width of a label in mm. Measured from the real font when it can be found; KiCad's own font runs about
    0.8 x the text size per character (an estimate)."""
    if font:
        f = font_file(font, bold)
        if f:
            try:
                from PIL import ImageFont
                return ImageFont.truetype(f, 1000).getlength(text) / 1000 * h * KICAD_EM
            except Exception:
                pass
        return max(1, len(text)) * h * KICAD_EM * 0.75          # unknown font: assume a wide-ish one
    return max(1, len(text)) * h * (0.9 if bold else 0.8)

def make_labels(pcb, cutouts, groups, outline, a, edits, log, no_hole=()):
    """Labels for every part that has a cutout, and for parts marked as needing none (edge jacks, a reset button
    behind the panel): (labels to place, table rows for the window)."""
    fps = {fp.uuid: fp for fp in map(Footprint, kids(pcb, 'footprint')) if fp.uuid}
    fps.update({c['id']: c['fp'] for c in cutouts if c.get('fp')})      # parts placed on the panel itself
    own = {}
    for c in cutouts:
        if c.get('shadow') or c['id'] not in fps or ':mount' in c.get('key', '') or c['rule'] == 'Mounting hole':
            continue
        own.setdefault(c['id'], []).append(c)
    ob_px, pb = {}, outline.bounds
    for fp in map(Footprint, kids(pcb, 'footprint')):
        if fp.uuid in no_hole and fp.uuid not in own:
            b = courtyard_box(fp) or (fp.x - 2, fp.y - 2, fp.x + 2, fp.y + 2)
            if not box(*b).intersects(outline):
                continue
            own[fp.uuid], fps[fp.uuid] = [], fp
            ob_px[fp.uuid] = (max(b[0], pb[0]), max(b[1], pb[1]), min(b[2], pb[2]), min(b[3], pb[3]), b[1] < pb[1], b[3] > pb[3])
    key_group = {k: g for g in groups for k in (g.get('member_keys') or []) if k}
    h, gap, bold = a.label_size, a.label_gap, a.label_bold == 'on'
    placed, rows = [], []
    for fid, cs in own.items():
        fp, e = fps[fid], edits.get(fid, {})
        guess, src = guess_label(fp)
        text = e['text'] if e.get('text') is not None else guess
        row = dict(fid=fid, ref=fp.ref + (' (panel)' if fid.startswith('manual:') else ' (no hole)' if fid in ob_px else ''), guess=guess, source=src, text=text, hide=bool(e.get('hide')),
                   skipped=skipped_label(fp) if not guess else ('', ''),
                   pos=e.get('pos', ''), dx=e.get('dx', 0.0), dy=e.get('dy', 0.0))
        rows.append(row)
        if not text.strip() and not row['hide'] and row['skipped'][0]:
            log.append(f"CHECK no label for {fp.ref}: \"{row['skipped'][0]}\" {row['skipped'][1]}, so it isn't used. "
                       f"Type one in Edit labels, or add a Label field to the part in KiCad")
        if row['hide'] or not text.strip():
            continue
        if a.label_caps == 'on':
            text = text.upper()
        pos = e.get('pos') if e.get('pos') in ('above', 'below') else a.label_pos
        if fid in ob_px:                          # no hole: label the part's outline, on the side inside the panel
            *ob, off_top, off_bottom = ob_px[fid]
            if not e.get('pos') and off_top != off_bottom:
                pos = 'below' if off_top else 'above'
            grp, gb = None, ob
        else:
            ob = unary_union([c['geom'] for c in cs]).bounds
            grp = next((key_group[c['key']] for c in cs if c.get('key') in key_group), None)
            gb = grp['geom'].bounds if grp else ob
        if grp and len(grp.get('member_keys') or []) > 1 and not e.get('pos'):
            at_top, at_bottom = abs(ob[1] - gb[1]) < 0.05, abs(ob[3] - gb[3]) < 0.05
            if at_top != at_bottom:               # a key in a merged slot: label on its own side of the slot
                pos = 'above' if at_top else 'below'
        ax = (ob[0] + ob[2]) / 2
        ay = gb[1] - gap - h / 2 if pos == 'above' else gb[3] + gap + h / 2
        if fid in ob_px and not e.get('pos'):     # no hole: the first of this side, the other side, or on the part
            w0 = text_width(text, h, bold, a.label_font)
            other = gb[3] + gap + h / 2 if pos == 'above' else gb[1] - gap - h / 2
            fits = lambda y: outline.contains(box(ax - w0 / 2, y - h / 2, ax + w0 / 2, y + h / 2)) and \
                not any(box(ax - w0 / 2, y - h / 2, ax + w0 / 2, y + h / 2).intersects(g['geom']) for g in groups)
            ay = next((y for y in (ay, other, (gb[1] + gb[3]) / 2) if fits(y)), ay)
        x, y = ax + row['dx'], ay + row['dy']
        placed.append(dict(fid=fid, ref=fp.ref, text=text, x=round(x, 4), y=round(y, 4), auto=(round(ax, 4), round(ay, 4)),
                           h=h, w=text_width(text, h, bold, a.label_font), status='ok'))
    # checks: over a cutout, off the panel, on top of another label (sizes are estimates)
    holes = [g['geom'] for g in groups]
    boxes = [box(L['x'] - L['w'] / 2, L['y'] - L['h'] / 2, L['x'] + L['w'] / 2, L['y'] + L['h'] / 2) for L in placed]
    for i, (L, b) in enumerate(zip(placed, boxes)):
        if any(b.intersects(g) for g in holes):
            L['status'] = 'warn'; log.append(f"WARN  label '{L['text']}' ({L['ref']}) runs into a cutout - move it, or set it above/below in Edit labels")
        elif not outline.contains(b):
            L['status'] = 'warn'; log.append(f"WARN  label '{L['text']}' ({L['ref']}) goes off the edge of the panel")
        for j in range(i + 1, len(placed)):
            if b.intersects(boxes[j]):
                L['status'] = placed[j]['status'] = 'warn'
                log.append(f"WARN  labels '{L['text']}' ({L['ref']}) and '{placed[j]['text']}' ({placed[j]['ref']}) overlap")
    rows.sort(key=lambda r: natkey(r['ref']))
    return placed, rows

def label_items(placed, a, uuids):
    font = f'(face "{a.label_font}") ' if a.label_font else ''
    t = a.label_size * (0.2 if a.label_bold == 'on' else 0.15)
    bold = ' (bold yes)' if a.label_bold == 'on' else ''
    out = []
    for L in placed:
        u = stable_uuid('label:' + L['fid'], 0); uuids.append(u); L['uuid'] = u
        txt = L['text'].replace('\\', '\\\\').replace('"', '\\"')
        out.append(f'\t(gr_text "{txt}" (at {fmt(L["x"])} {fmt(L["y"])} 0) (layer "F.SilkS") (uuid "{u}") '
                   f'(effects (font {font}(size {fmt(a.label_size)} {fmt(a.label_size)}) (thickness {fmt(t)}){bold})))')
    return out

def label_changes_in_panel(tree, memory, edits, log):
    """Labels you moved, retyped or deleted in KiCad since the last run: folded into the label edits."""
    if memory.get('settings', {}).get('labels') != 'on':
        return
    texts = {kid(g, 'uuid')[1]: g for g in kids(tree, 'gr_text') if kid(g, 'uuid')}
    for fid, info in memory.get('labels_generated', {}).items():
        g = texts.get(info['uuid'])
        e = edits.setdefault(fid, {})
        if g is None:
            if not e.get('hide'):
                e['hide'] = True
                log.append(f"label {info['ref']} '{info['text']}' deleted in the panel - now hidden (tick it in Edit labels to bring it back)")
            continue
        at = kid(g, 'at')
        if abs(at[1] - info['at'][0]) > 0.01 or abs(at[2] - info['at'][1]) > 0.01:
            e['dx'] = round(at[1] - info['auto'][0], 4); e['dy'] = round(at[2] - info['auto'][1], 4)
            log.append(f"label {info['ref']} '{info['text']}' moved in the panel - kept where you put it")
        if g[1] != info['text']:
            e['text'] = g[1]
            log.append(f"label {info['ref']} changed to '{g[1]}' in the panel - kept")
    for fid in [f for f, e in edits.items() if not e]:
        edits.pop(fid)

# ---------------------------------------------------------------- artwork from Inkscape
ART_LAYER_NAMES = ('artwork', 'silkscreen', 'silk')

def find_inkscape():
    """Inkscape's command-line program, or None."""
    import shutil
    for p in (os.environ.get('PANELGEN_INKSCAPE'), r'C:\Program Files\Inkscape\bin\inkscape.com',
              r'C:\Program Files\Inkscape\bin\inkscape.exe', r'C:\Program Files (x86)\Inkscape\bin\inkscape.exe',
              '/Applications/Inkscape.app/Contents/MacOS/inkscape', shutil.which('inkscape')):
        if p and os.path.exists(p):
            return p
    return None

def svg_page(text):
    """(page x, page y, width, height) in the SVG's own units, and mm per unit."""
    head = text[:text.find('>', text.find('<svg')) + 1]
    def attr(n):
        m = re.search(r'\s' + n + r'="([^"]*)"', head)
        return m.group(1) if m else None
    unit_mm = {'mm': 1, 'cm': 10, 'in': 25.4, 'pt': 25.4 / 72, 'pc': 25.4 / 6, 'px': 25.4 / 96, '': 25.4 / 96}
    def length(v):
        m = re.fullmatch(r'\s*([\d.]+)\s*([a-z%]*)\s*', v or '')
        if not m or m.group(2) == '%':
            return None
        return float(m.group(1)) * unit_mm.get(m.group(2), 25.4 / 96)
    w_mm, h_mm = length(attr('width')), length(attr('height'))
    vb = [float(x) for x in re.split(r'[\s,]+', attr('viewBox').strip())] if attr('viewBox') else None
    if not vb:
        vb = [0, 0, w_mm / (25.4 / 96), h_mm / (25.4 / 96)] if w_mm else None
    if not vb or not w_mm:
        return None, None
    return vb, w_mm / vb[2]

def art_layer(text):
    """(id, label) of the Inkscape layer to import: one called Artwork, or else Silkscreen."""
    layers = []
    for m in re.finditer(r'<g\b[^>]*>', text):
        t = m.group(0)
        if 'inkscape:groupmode="layer"' not in t:
            continue
        i = re.search(r'\sid="([^"]+)"', t); lab = re.search(r'inkscape:label="([^"]+)"', t)
        if i and lab and 'display:none' not in t.replace(' ', ''):
            layers.append((i.group(1), lab.group(1)))
    for want in ART_LAYER_NAMES:
        for i, lab in layers:
            if lab.strip().lower() == want:
                return i, lab, layers
    return None, None, layers

GUIDE_LAYERS = ('panel', 'labels', 'markers')    # layers Panel Generator draws as guides: never printed

def svg_element_span(text, el_id, tag='g'):
    """(start, end) of the <g ... id="el_id"> element in raw SVG text, or None. Keeps everything else byte-for-byte."""
    m = re.search(r'<' + tag + r'\b[^>]*\bid="' + re.escape(el_id) + r'"[^>]*>', text)
    if not m:
        return None
    if m.group(0).endswith('/>'):
        return m.start(), m.end()
    depth, pos = 1, m.end()
    pat = re.compile(r'<' + tag + r'(?=[\s>/])[^>]*?(/?)>|</' + tag + r'\s*>')
    while depth:
        n = pat.search(text, pos)
        if not n:
            return None
        if n.group(0).startswith('</'):
            depth -= 1
        elif n.group(1) != '/':
            depth += 1
        pos = n.end()
    return m.start(), pos

def refresh_artwork_guides(art_svg, template_svg, log):
    """Bring the red cutout layer, the labels guide and the page size in the artwork file up to date with the panel.
    Your drawing isn't touched: its coordinates are the panel's own, so it stays lined up."""
    try:
        art, tpl = open(art_svg, encoding='utf-8').read(), open(template_svg, encoding='utf-8').read()
    except OSError:
        return
    new = art
    for lid in ('labels', 'markers', 'panel'):   # labels and part-marker guides, then the red cutouts on top
        t_span, a_span = svg_element_span(tpl, lid), svg_element_span(new, lid)
        fresh = tpl[t_span[0]:t_span[1]] if t_span else ''
        if a_span:
            old_tag = re.match(r'<g\b[^>]*>', new[a_span[0]:a_span[1]]).group(0)
            style = re.search(r'\sstyle="([^"]*)"', old_tag)
            if fresh and style:             # keep your choice of showing or hiding the layer
                fresh = re.sub(r'(<g\b[^>]*?)(\sstyle="[^"]*")?(\s*/?>)', lambda m: f'{m.group(1)} style="{style.group(1)}"{m.group(3)}', fresh, count=1)
            if fresh and 'sodipodi:insensitive="true"' in old_tag and lid != 'panel':   # ...and of locking it
                fresh = fresh.replace('<g ', '<g sodipodi:insensitive="true" ', 1)
            end = a_span[1] + (1 if new[a_span[1]:a_span[1] + 1] == '\n' else 0)
            new = new[:a_span[0]] + new[end:]                 # take it out, and put it back on top below
        if fresh:
            close = new.rfind('</svg>')
            new = new[:close] + fresh + '\n' + new[close:]
    # page = the panel as it is now
    head = re.search(r'<svg\b[^>]*>', new)
    thead = re.search(r'<svg\b[^>]*>', tpl)
    if head and thead:
        h = head.group(0)
        for attr in ('width', 'height', 'viewBox'):
            v = re.search(r'\s' + attr + r'="([^"]*)"', thead.group(0))
            if v:
                h = re.sub(r'\s' + attr + r'="[^"]*"', f' {attr}="{v.group(1)}"', h) if re.search(r'\s' + attr + '=', h) \
                    else h[:-1] + f' {attr}="{v.group(1)}">'
        new = new[:head.start()] + h + new[head.end():]
    # a light grey page, so white artwork (which cuts out of black) is visible while you draw; it isn't printed
    nv = re.search(r'<sodipodi:namedview\b[^>]*>', new)
    if nv and re.search(r'pagecolor="#(?:fff|ffffff|FFFFFF)"', nv.group(0)):
        t = re.sub(r'pagecolor="#[0-9a-fA-F]{3,6}"', 'pagecolor="#d4d8dc"', nv.group(0))
        t = re.sub(r'inkscape:pageopacity="[^"]*"', 'inkscape:pageopacity="1"', t)
        new = new[:nv.start()] + t + new[nv.end():]
    if new != art:
        open(art_svg, 'w', encoding='utf-8').write(new)
        log.append(f"art   updated the cutout and label guides in {os.path.basename(art_svg)} (your artwork wasn't touched)")

def fracture(poly):
    """KiCad polygons can't have holes: cut a polygon with holes into pieces that have none (same area)."""
    from shapely.ops import split
    if not poly.interiors:
        return [poly]
    hx = poly.interiors[0].centroid.x
    _, y1, _, y2 = poly.bounds
    out = []
    for piece in split(poly, LineString([(hx, y1 - 1), (hx, y2 + 1)])).geoms:
        if piece.geom_type == 'Polygon' and piece.area > 1e-9:
            out += fracture(piece)
    return out

def trace_png(png, dpi, x0, y0, mm_per_unit=1.0):
    """Dark areas of a rendered PNG -> shapely polygons in panel mm (edges found to sub-pixel accuracy)."""
    import numpy as np
    from PIL import Image
    import contourpy
    from shapely.ops import polygonize
    im = Image.open(png).convert('L')
    z = np.asarray(im, dtype=np.float32) / 255.0
    z = np.pad(z, 1, constant_values=1.0)                 # white border so every outline closes
    px = 25.4 / dpi                                        # mm per pixel
    lines = contourpy.contour_generator(z=z, line_type=contourpy.LineType.Separate).lines(0.5)
    rings = [LineString([(x0 + (c - 1 + 0.5) * px, y0 + (r - 1 + 0.5) * px) for c, r in ln])
             for ln in lines if len(ln) >= 4]
    polys = []
    for face in polygonize(rings):
        p = face.representative_point()
        c = int(round((p.x - x0) / px - 0.5)) + 1; r = int(round((p.y - y0) / px - 0.5)) + 1
        if 0 <= r < z.shape[0] and 0 <= c < z.shape[1] and z[r, c] < 0.5:
            polys.append(face.simplify(px * 0.4, preserve_topology=True))
    return [p for p in polys if p.is_valid and p.area > px * px]

def import_artwork(svg_path, outline, log, cache_dir, dpi=600):
    """Inkscape renders the Artwork layer; its dark parts become silkscreen polygons (holes fractured for KiCad)."""
    import hashlib, subprocess, tempfile
    try:
        raw = open(svg_path, 'rb').read()
    except OSError:
        log.append(f"ERROR can't read the artwork file {svg_path}"); return []
    text = raw.decode('utf-8', 'replace')
    _, _, layers = art_layer(text)
    shown = [lab for i, lab in layers if i not in GUIDE_LAYERS]
    label = ', '.join(shown) or 'the page'
    vb, mmpu = svg_page(text)
    if not vb or abs(mmpu - 1) > 1e-3:
        log.append(f"ERROR {os.path.basename(svg_path)}: the page isn't 1 unit = 1 mm, so it can't be lined up. "
                   "Start from the panel's _template.svg (and don't change the page size in Inkscape)"); return []
    page = box(vb[0], vb[1], vb[0] + vb[2], vb[1] + vb[3])
    if 'id="panel"' not in text or not page.intersects(outline):
        log.append(f"ERROR {os.path.basename(svg_path)} wasn't made from this panel's template, so it can't be lined up with the "
                   "holes. Click 'Create artwork file', then copy your artwork into its Artwork layer and line it up with "
                   "the red cutouts"); return []
    if not page.equals_exact(box(*outline.bounds), 0.01):
        log.append("NOTE  the page in the artwork file is the panel's old size. The preview already uses the new size; "
                   "Generate updates the file too (then File > Revert in Inkscape if it's open)")
    px1, py1, px2, py2 = outline.bounds                      # always render the panel as it is now, whatever the file's page
    key = hashlib.sha1(raw + f'{dpi}:all-but-guides:{px1:.3f},{py1:.3f},{px2:.3f},{py2:.3f}'.encode()).hexdigest()
    cache = os.path.join(cache_dir, '.artwork_cache.json') if cache_dir else None
    if cache and os.path.exists(cache):
        try:
            c = json.load(open(cache))
            if c.get('key') == key:
                polys = [Polygon(p) for p in c['polys']]
                log.append(f"art   {len(polys)} shapes from {os.path.basename(svg_path)} (unchanged since last time)")
                return polys
        except (OSError, ValueError):
            pass
    try:
        import numpy, contourpy, PIL  # noqa: F401
    except ImportError:
        log.append("ERROR reading artwork needs three extra packages. In Command Prompt run:  py -m pip install contourpy numpy pillow")
        return []
    ink = find_inkscape()
    if not ink:
        log.append("ERROR Inkscape isn't installed (or wasn't found), and it's needed to read the artwork. "
                   "Install it from inkscape.org, or set PANELGEN_INKSCAPE to inkscape.exe"); return []
    # a copy with the guide layers switched off, next to the original so linked images still resolve
    hidden = text
    for gid in GUIDE_LAYERS:
        sp = svg_element_span(hidden, gid)
        if sp:
            tag = re.match(r'<g\b[^>]*?(/?)>', hidden[sp[0]:]).group(0)
            tag2 = re.sub(r'\sstyle="[^"]*"', '', tag)
            tag2 = tag2[:-2] + ' style="display:none"/>' if tag2.endswith('/>') else tag2[:-1] + ' style="display:none">'
            hidden = hidden[:sp[0]] + tag2 + hidden[sp[0] + len(tag):]
    head = re.search(r'<svg\b[^>]*>', hidden)
    if head:
        h = head.group(0)
        for attr, val in (('width', f'{fmt(px2 - px1)}mm'), ('height', f'{fmt(py2 - py1)}mm'),
                          ('viewBox', f'{fmt(px1)} {fmt(py1)} {fmt(px2 - px1)} {fmt(py2 - py1)}')):
            h = re.sub(r'\s' + attr + r'="[^"]*"', f' {attr}="{val}"', h) if re.search(r'\s' + attr + '=', h) else h[:-1] + f' {attr}="{val}">'
        hidden = hidden[:head.start()] + h + hidden[head.end():]
    tmp_svg = os.path.join(os.path.dirname(os.path.abspath(svg_path)), '.panelgen_render.svg')
    with tempfile.TemporaryDirectory() as tmp:
        open(tmp_svg, 'w', encoding='utf-8').write(hidden)
        png = os.path.join(tmp, 'art.png')
        cmd = [ink, tmp_svg, '--export-area-page', f'--export-dpi={dpi}',
               '--export-background=white', '--export-background-opacity=1', '--export-type=png', f'--export-filename={png}']
        try:
            subprocess.run(cmd, capture_output=True, timeout=180,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, subprocess.TimeoutExpired) as e:
            log.append(f"ERROR Inkscape couldn't render the artwork ({e})"); return []
        finally:
            try:
                os.remove(tmp_svg)
            except OSError:
                pass
        if not os.path.exists(png):
            log.append("ERROR Inkscape didn't produce an image of the artwork"); return []
        shapes = trace_png(png, dpi, px1, py1)
    pieces = []
    for s in shapes:
        s = s.intersection(outline)                         # nothing off the panel
        for g in (s.geoms if hasattr(s, 'geoms') else [s]):
            if g.geom_type == 'Polygon' and g.area > 1e-6:
                pieces += fracture(g)
    if cache:
        try:
            json.dump({'key': key, 'polys': [[(round(x, 4), round(y, 4)) for x, y in p.exterior.coords] for p in pieces]},
                      open(cache, 'w'))
        except OSError:
            pass
    log.append(f"art   {len(pieces)} shapes from {os.path.basename(svg_path)} (layers: {label})")
    if not pieces:
        log.append("WARN  the artwork is empty, or only white - nothing to put on the silkscreen")
    return pieces

def artwork_items(polys, uuids):
    out = []
    for n, p in enumerate(polys):
        u = stable_uuid('art', n); uuids.append(u)
        xy = ' '.join(f'(xy {fmt(x)} {fmt(y)})' for x, y in list(p.exterior.coords)[:-1])
        out.append(f'\t(gr_poly (pts {xy}) (stroke (width 0) (type solid)) (fill yes) (layer "F.SilkS") (uuid "{u}"))')
    return out

# ---------------------------------------------------------------- gerbers
GERBER_LAYERS = 'F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts'

def find_kicad_cli():
    """KiCad's command-line tool, newest version first, or None."""
    import glob, shutil
    def ver(p):
        m = re.search(r'KiCad[\\/]([\d.]+)[\\/]', p)
        return [int(x) for x in m.group(1).split('.') if x.isdigit()] if m else [0]
    hits = sorted(glob.glob(r'C:\Program Files\KiCad\*\bin\kicad-cli.exe'), key=ver, reverse=True)
    for p in hits + ['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli', shutil.which('kicad-cli')]:
        if p and os.path.exists(p):
            return p
    return None

def make_gerbers(panel_path, log):
    """Gerbers, drill files and a KiCad DRC check for the saved panel, zipped ready for the PCB maker.
    Returns the zip's path, or None."""
    import subprocess, zipfile, shutil
    cli = find_kicad_cli()
    if not cli:
        log.append("ERROR couldn't find KiCad's command-line tool (kicad-cli). It comes with KiCad 8 or later - "
                   "is KiCad installed in the usual place?"); return None
    if not os.path.exists(panel_path):
        log.append("ERROR there's no panel yet - generate it first"); return None
    try:
        v = subprocess.run([cli, 'version'], capture_output=True, text=True, timeout=60,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout.strip()
        if v and int(v.split('.')[0]) < 9:
            log.append(f"ERROR the KiCad found here is version {v}, which can't read the panel (it's saved in KiCad 9 format). "
                       "Install KiCad 9 or 10"); return None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    base = re.sub(r'\.kicad_pcb$', '', os.path.basename(panel_path))
    folder = os.path.dirname(os.path.abspath(panel_path))
    out = os.path.join(folder, base + '_gerbers')
    if os.path.isdir(out):
        shutil.rmtree(out)                    # only ever our own output folder: no stale layers left behind
    os.makedirs(out)
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    def run(args, what, fail='ERROR'):
        try:
            r = subprocess.run([cli] + args, capture_output=True, text=True, timeout=300, creationflags=flags)
        except (OSError, subprocess.TimeoutExpired) as e:
            log.append(f"{fail} KiCad couldn't make the {what} ({e})"); return False
        if r.returncode not in (0, 5):
            msg = (r.stderr or r.stdout or '').strip().splitlines()
            log.append(f"{fail} KiCad couldn't make the {what}: {msg[-1] if msg else 'exit code %d' % r.returncode}"
                       + (" (KiCad's DRC from the command line needs KiCad 8 or later)" if fail != 'ERROR' else ''))
            return False
        return True
    if not run(['pcb', 'export', 'gerbers', '-o', out + os.sep, '-l', GERBER_LAYERS, panel_path], 'gerbers'):
        return None
    if not run(['pcb', 'export', 'drill', '-o', out + os.sep, '--excellon-separate-th', '--generate-map',
                '--map-format', 'gerberx2', panel_path], 'drill files'):
        return None
    files = sorted(f for f in os.listdir(out) if os.path.isfile(os.path.join(out, f)))
    zpath = os.path.join(folder, base + '_gerbers.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(out, f), f)
    log.append(f"gerb  {len(files)} files -> {zpath}")
    # KiCad's own design rule check, as a second opinion (the report stays next to the panel)
    rpt = os.path.join(folder, base + '_drc.json')
    if run(['pcb', 'drc', '--format', 'json', '--severity-error', '--severity-warning', '-o', rpt, panel_path], 'DRC check', 'NOTE '):
        try:
            d = json.load(open(rpt, encoding='utf-8'))
            items = d.get('violations', []) + d.get('unconnected_items', []) + d.get('schematic_parity', [])
            errs = [v for v in items if v.get('severity') == 'error']
            warns = [v for v in items if v.get('severity') == 'warning']
            kinds = {}
            for v in errs + warns:
                kinds[v.get('description') or v.get('type', '?')] = kinds.get(v.get('description') or v.get('type', '?'), 0) + 1
            summary = '; '.join(f"{n} x {k}" for k, n in sorted(kinds.items(), key=lambda kv: -kv[1])[:4])
            if errs:
                log.append(f"WARN  KiCad's DRC found {len(errs)} error(s) and {len(warns)} warning(s): {summary}. "
                           f"Open the panel in KiCad and run Inspect > Design Rules Checker to see where")
            elif warns:
                log.append(f"NOTE  KiCad's DRC: no errors, {len(warns)} warning(s) ({summary})")
            else:
                log.append("drc   KiCad's DRC: no errors or warnings")
        except (OSError, ValueError):
            log.append("NOTE  KiCad's DRC ran, but its report couldn't be read")
    return zpath

# ---------------------------------------------------------------- where the panel lives
PANEL_DIR = 'Front Panel'
PANEL_SIDE_FILES = ('.kicad_pcb', '.panelgen.json', '_template.svg', '_artwork.svg', '.kicad_pro', '.kicad_prl', '.kicad_dru')

def default_panel_path(pcb):
    """<board folder>/Front Panel/<board>_panel.kicad_pcb"""
    d, f = os.path.split(os.path.abspath(pcb))
    return os.path.join(d, PANEL_DIR, re.sub(r'\.kicad_pcb$', '', f) + '_panel.kicad_pcb')

def old_panel_path(pcb):
    """Where panels went before v0.8: next to the board."""
    return re.sub(r'\.kicad_pcb$', '', os.path.abspath(pcb)) + '_panel.kicad_pcb'

def lock_path(path):
    d, f = os.path.split(path)
    return os.path.join(d, '~' + f + '.lck')

def move_old_panel(pcb, new_path, log):
    """Move a panel made next to the board (older versions) into the Front Panel folder, memory and all."""
    old = old_panel_path(pcb)
    if not os.path.exists(old) or os.path.exists(new_path):
        if os.path.exists(old) and os.path.exists(new_path):
            log.append(f"NOTE  an older panel is still next to the board ({os.path.basename(old)}) - "
                       f"the one in '{PANEL_DIR}' is used; delete the old one when you're happy")
        return
    if os.path.exists(lock_path(old)):
        print(f"panelgen {VERSION}: nothing done")
        print(f"  ERROR {os.path.basename(old)} is open in KiCad, so it can't be moved into the '{PANEL_DIR}' folder. "
              f"Close it in KiCad and generate again")
        raise SystemExit(1)
    import shutil
    old_stem, new_stem = old[:-len('.kicad_pcb')], new_path[:-len('.kicad_pcb')]
    moved = []
    for ext in PANEL_SIDE_FILES:
        src = old_stem + ext
        if os.path.exists(src) and not os.path.exists(new_stem + ext):
            shutil.move(src, new_stem + ext)
            moved.append(os.path.basename(src))
    log.append(f"moved {', '.join(moved)} into the '{PANEL_DIR}' folder")

# ---------------------------------------------------------------- main
def main(argv=None, preview=None):
    """preview: pass a dict to get the panel geometry back without writing or moving any files."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pcb', help='synth .kicad_pcb to read')
    ap.add_argument('-o', '--out', help="panel .kicad_pcb to write (default: 'Front Panel' folder next to the PCB)")
    ap.add_argument('--rules', default=os.path.join(APP_DIR, 'panel_rules.json'))
    ap.add_argument('--margin', type=float, help='extra panel beyond the PCB outline on every side, mm (default 0: panel = PCB outline)')
    for side in ('top', 'right', 'bottom', 'left'):
        ap.add_argument(f'--margin-{side}', type=float, help=f'override margin on the {side}')
    ap.add_argument('--corner-radius', type=float, help='rounded panel corners, mm (default 0)')
    ap.add_argument('--screw-dia', type=float, help='case screw hole diameter (default 2.2)')
    ap.add_argument('--screw-slot', type=float, help='make case holes slots this long, end to end, running along the edge (0 = round, default). --screw-inset is measured to the centre of the slot end nearest each edge')
    ap.add_argument('--rail-slot', type=float, help='Eurorack: make the rail holes horizontal slots this long, end to end (0 = round, default)')
    ap.add_argument('--screw-inset', type=float, help='case screw centre distance from panel edges (default 3.5)')
    ap.add_argument('--screws', choices=['none', 'corners', 'corners+mid'], help='case screw holes around the panel edge (default none)')
    ap.add_argument('--min-web', type=float, help='warn when material between cutouts is thinner (default 1.0 mm)')
    ap.add_argument('--svg', action='store_true', default=None, help='also write a 1:1 SVG template for Inkscape')
    ap.add_argument('--grow', type=float,
                    help='make every opening (screens, switches, pots, jacks, LEDs) this much bigger, in mm; screw holes unchanged')
    ap.add_argument('--panel-layer',
                    help='shapes drawn on this PCB layer become cutouts exactly as drawn (default User.1)')
    ap.add_argument('--restore', action='append', default=[], metavar='REF',
                    help='bring back a cutout you deleted in the panel (e.g. H1, CASE-tl, or "all"); repeatable')
    ap.add_argument('--no-uncut-check', dest='check_uncut', action='store_const', const='off', default=None,
                    help="don't list parts that look like they go through the panel but got no cutout")
    ap.add_argument('--labels', choices=['on', 'off'], help='add text labels from the PCB to the panel silkscreen (default off)')
    ap.add_argument('--label-size', type=float, help='label text height, mm (default 2.0)')
    ap.add_argument('--label-gap', type=float, help='gap between a cutout and its label, mm (default 1.5)')
    ap.add_argument('--label-pos', choices=['above', 'below'], help='labels above or below their cutout (default above)')
    ap.add_argument('--label-font', help='a font installed on your computer, e.g. Arial ("" = KiCad\'s own font, default)')
    ap.add_argument('--label-bold', choices=['on', 'off'])
    ap.add_argument('--label-caps', choices=['on', 'off'], help='ALL CAPS labels')
    ap.add_argument('--artwork', choices=['on', 'off'],
                    help="import the 'Artwork' layer of <panel>_artwork.svg (made in Inkscape from the template) onto the silkscreen")
    ap.add_argument('--artwork-file', help='a different artwork SVG to import (default: <panel>_artwork.svg in the Front Panel folder)')
    ap.add_argument('--make-artwork-file', action='store_true',
                    help='start <panel>_artwork.svg from the template (only if it does not exist yet)')
    ap.add_argument('--gerbers', action='store_true',
                    help="after writing the panel, make gerbers + drill files (zipped) and run KiCad's DRC, using kicad-cli")
    ap.add_argument('--ui-state', help=argparse.SUPPRESS)   # JSON from the window: ignored parts and label edits
    ap.add_argument('--again', action='store_true',
                    help='reuse the settings from the last run on this panel (any option you also give still wins)')
    a = ap.parse_args(argv)

    early = []
    if a.out:
        out_path = a.out
    elif preview is not None:   # read-only: use wherever the panel is now
        out_path = default_panel_path(a.pcb)
        if not os.path.exists(out_path) and os.path.exists(old_panel_path(a.pcb)):
            out_path = old_panel_path(a.pcb)
    else:
        out_path = default_panel_path(a.pcb)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        move_old_panel(a.pcb, out_path, early)
    mem_path = re.sub(r'\.kicad_pcb$', '', out_path) + '.panelgen.json'
    saved = load_memory(mem_path).get('settings', {}) if a.again else {}
    defaults = dict(margin=0.0, corner_radius=0.0, screw_dia=2.2, screw_inset=3.5, screw_slot=0.0, rail_slot=0.0, screws='none',
                    min_web=1.0, svg=False, grow=0.0, panel_layer='User.1', check_uncut='on',
                    artwork='off', artwork_file='',
                    labels='off', label_size=2.0, label_gap=1.5, label_pos='above', label_font='', label_bold='off', label_caps='off')
    for k, d in defaults.items():          # explicit option > saved (with --again) > built-in default
        if getattr(a, k) is None:
            setattr(a, k, saved.get(k, d))
    for side in ('top', 'right', 'bottom', 'left'):
        k = f'margin_{side}'
        if getattr(a, k) is None and a.margin == saved.get('margin', a.margin) and k in saved:
            setattr(a, k, saved[k])
    if a.again and not saved:
        print("note: no saved settings for this panel yet - using defaults")

    mem0 = load_memory(mem_path)
    ui = json.loads(a.ui_state) if a.ui_state else {}
    ignore_uncut = ui.get('ignore', mem0.get('ignore_uncut', {}))
    label_edits = ui.get('label_edits', mem0.get('label_edits', {}))
    cfg = json.load(open(a.rules))
    cfg['grow'] = a.grow
    pcb_text, pcb = read_board(a.pcb)
    log = early

    m = {s: getattr(a, f'margin_{s}') if getattr(a, f'margin_{s}') is not None else a.margin
         for s in ('top', 'right', 'bottom', 'left')}
    tpl, hp = eurorack_template(pcb)
    rail_holes, rail_warn, rail_bad = [], 0, []
    if tpl:
        if abs(tpl.angle) > 0.01:
            print(f"panelgen {VERSION}: nothing done")
            print(f"  ERROR the Eurorack template {tpl.ref} is rotated {tpl.angle:g} degrees. Set it back to 0 and generate again")
            return 1
        ew, rail_holes, src = eurorack_spec(hp)
        x1, y1 = tpl.x, tpl.y
        x2, y2 = x1 + ew, y1 + ER_HEIGHT
        log.append(f"eurorack {hp}HP panel {ew:g} x {ER_HEIGHT:g} mm" +
                   ("" if src == 'Doepfer' else f"  (CHECK: {hp}HP isn't in Doepfer's width table, {ew:g} mm is estimated)"))
        if any(m.values()) or a.screws != 'none':
            log.append("NOTE  Eurorack panel: the panel size and holes are standard, so expand-panel and case-hole settings are ignored")
        a.screws = 'none'
        rail_bad = []
        rail_warn = check_rails(pcb, tpl, x1, y1, x2, y2, log, rail_bad)
    else:
        bx1, by1, bx2, by2 = board_outline(pcb)
        x1, y1, x2, y2 = bx1 - m['left'], by1 - m['top'], bx2 + m['right'], by2 + m['bottom']
        log.append(f"pcb   {bx2-bx1:.2f} x {by2-by1:.2f} mm")
        log.append(f"panel {x2-x1:.2f} x {y2-y1:.2f} mm  (margins T{m['top']} R{m['right']} B{m['bottom']} L{m['left']})")
    outline = box(x1, y1, x2, y2)
    if a.corner_radius > 0:
        outline = outline.buffer(-a.corner_radius).buffer(a.corner_radius, quad_segs=32)

    cutouts = collect_cutouts(pcb, cfg, log)
    cutouts = drop_markers(cutouts + drawn_cutouts(pcb, a.panel_layer, log), log, a.panel_layer)
    uncut = []
    if a.check_uncut == 'on':
        parts_without_cutouts(pcb, cutouts, tpl, log, uncut, ignore_uncut, cfg.get('_none_ids', set()))

    # case screws
    case_warn = 0
    i = a.screw_inset
    spots = []
    if a.screws != 'none':
        spots += [('tl', x1 + i, y1 + i), ('tr', x2 - i, y1 + i), ('br', x2 - i, y2 - i), ('bl', x1 + i, y2 - i)]
    if a.screws == 'corners+mid':
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        spots += [('t', mx, y1 + i), ('b', mx, y2 - i), ('l', x1 + i, my), ('r', x2 - i, my)]
    slot = a.screw_slot > a.screw_dia + 1e-6
    if spots and 0 < a.screw_slot <= a.screw_dia:
        log.append(f"NOTE  case hole slot length {a.screw_slot:g} mm isn't longer than the {a.screw_dia:g} mm hole - using round holes")
    case_geoms = []
    for name, sx, sy in spots:
        if slot:
            # Runs along the edge: left/right sides vertical, top/bottom and corners horizontal.
            # Distance from edge is to the centre of the slot's end radius, so a slot is never closer to
            # any edge than a round hole would be: side slots are centred, corner slots grow inwards.
            n = a.screw_slot - a.screw_dia
            if name in ('l', 'r'):
                seg = [(sx, sy - n / 2), (sx, sy + n / 2)]
            elif name in ('t', 'b'):
                seg = [(sx - n / 2, sy), (sx + n / 2, sy)]
            else:
                inward = 1 if name in ('tl', 'bl') else -1
                seg = [(sx, sy), (sx + inward * n, sy)]
            geom, circ = LineString(seg).buffer(a.screw_dia / 2, quad_segs=32), None
        else:
            geom, circ = Point(sx, sy).buffer(a.screw_dia / 2, quad_segs=64), (sx, sy, a.screw_dia / 2)
        case_geoms.append(geom)
        cutouts.append({'id': f'CASE-{name}', 'key': f'case:{name}', 'ref': f'CASE-{name}', 'rule': 'case slot' if slot else 'case screw',
                        'merge': False, 'geom': geom, 'circle': circ})
    # Eurorack rail holes (standard positions; edge distance is fixed by the standard, so no case-hole warning)
    rslot = (a.rail_slot or 0) > ER_HOLE_DIA + 1e-6
    for x, side in rail_holes:
        name = side + ('c' if abs(x - (x2 - x1) / 2) < 0.01 else 'l' if x < (x2 - x1) / 2 else 'r')
        hx, hy = x1 + x, (y1 + ER_HOLE_Y if side == 't' else y2 - ER_HOLE_Y)
        if rslot:
            n = a.rail_slot - ER_HOLE_DIA
            geom, circ = LineString([(hx - n / 2, hy), (hx + n / 2, hy)]).buffer(ER_HOLE_DIA / 2, quad_segs=32), None
        else:
            geom, circ = Point(hx, hy).buffer(ER_HOLE_DIA / 2, quad_segs=64), (hx, hy, ER_HOLE_DIA / 2)
        cutouts.append({'id': f'RAIL-{name}', 'key': f'rail:{name}', 'ref': f'RAIL-{name}', 'rule': 'rail slot' if rslot else 'rail hole',
                        'merge': False, 'geom': geom, 'circle': circ})
    if spots:
        # rule of thumb: keep at least one hole-width of panel between a screw hole and the edge
        edge = min(outline.exterior.distance(g) for g in case_geoms)
        if a.min_web <= edge < a.screw_dia - 1e-6:
            if edge >= a.screw_inset - a.screw_dia / 2 - 0.01:
                fix = f"edge to hole centre {1.5 * a.screw_dia:g} mm or more"
            else:
                fix = "the rounded corners bring the corner holes closer - increase edge to hole centre, or reduce the corner radius"
            log.append(f"WARN  case holes: only {edge:.2f} mm of panel between hole and edge - easy to crack when tightening. "
                       f"Aim for at least {a.screw_dia:g} mm ({fix})")
            case_warn = 1

    # memory of what panelgen made last time, and what you deleted
    memory = load_memory(mem_path)
    suppressed = dict(memory.get('suppressed', {}))
    kept = dict(memory.get('kept', {}))
    restored_ids = []
    def wanted(v):
        return any(w.lower() == 'all' or v['ref'].lower() == w.lower() or w.lower() in (r.lower() for r in v.get('refs', []))
                   for w in a.restore)
    for want in a.restore:
        w = want.lower()
        match = lambda v: w == 'all' or v['ref'].lower() == w or w in (r.lower() for r in v.get('refs', []))
        hits = [k for k, v in suppressed.items() if match(v)]
        for k in hits:
            log.append(f"restore {suppressed.pop(k)['ref']} (was deleted)")
        khits = [k for k, v in kept.items() if match(v)]
        for k in khits:
            v = kept.pop(k); restored_ids += v['uuids']
            log.append(f"restore {v['ref']} (your edit replaced by a fresh cutout)")
        if not hits and not khits:
            names = [v['ref'] for v in list(suppressed.values()) + list(kept.values())]
            log.append(f"WARN  --restore {want}: nothing by that name was deleted or edited"
                       + (f" (yours: {', '.join(names)})" if names else ""))

    existing_text, removed, manual = None, 0, []
    if os.path.exists(out_path):
        t, tree = read_board(out_path)
        live = [c for c in cutouts if c['key'] not in {k for v in suppressed.values() for k in v['member_keys']}]
        trial, _ = merge_and_check(live, outline, a.min_web, [])
        for k, info in find_deletions(memory, tree, trial, log).items():
            if wanted(info):
                continue
            suppressed[k] = info
            log.append(f"gone  {info['ref']} - deleted in the panel, will stay off")
        for k, info in find_edits(memory, tree).items():
            if wanted(info):
                restored_ids += info['uuids']; continue
            kept[k] = info
            b = info['box_now']
            log.append(f"edit  {info['ref']} - changed in the panel to {b[2]-b[0]:.2f} x {b[3]-b[1]:.2f} mm, your version is kept")
        present_ids = {u for u, _ in item_boxes(tree)}
        for k in [k for k, v in kept.items() if not set(v['uuids']) & present_ids]:
            v = kept.pop(k); suppressed[k] = v
            log.append(f"gone  {v['ref']} - your edited cutout was deleted in the panel, will stay off")
        # an edited cutout whose part has since moved or changed on the PCB
        now = {g['key']: g['geom'].bounds for g in trial}
        for k, info in kept.items():
            if k in now and not same_box(now[k], info['box']):
                log.append(f"WARN  {info['ref']} moved or changed on the PCB since you edited its panel cutout - "
                           f"your edited version stays where it was (--restore {info['ref']} to regenerate it)")
        if memory.get('outline_box'):
            ob = [b for u, b in item_boxes(tree) if u in set(memory.get('outline', []))]
            if ob and not same_box(ob[0], memory['outline_box']):
                log.append("NOTE  the panel outline was changed in KiCad - it is always rebuilt from the margins; "
                           "use --margin / --margin-top etc. to change the size")
        label_changes_in_panel(tree, memory, label_edits, log)
        keep_ids = [u for v in kept.values() for u in v['uuids']]
        last_ids = [u for v in memory.get('generated', {}).values() for u in v['uuids']] + memory.get('outline', []) + restored_ids
        existing_text, removed = strip_generated(t, tree, last_ids, keep_ids)
        names = {u: v['ref'] for v in kept.values() for u in v['uuids']}
        manual = manual_cutouts(parse(existing_text + ')'), names)

    off = {k for v in list(suppressed.values()) + list(kept.values()) for k in v['member_keys']}
    for v in suppressed.values():
        log.append(f"off   {v['ref']} @({v['at'][0]:.2f}, {v['at'][1]:.2f}) - deleted in panel (--restore {v['ref']} to bring back)")
    for v in kept.values():
        log.append(f"yours {v['ref']} - edited in panel, kept as you left it (--restore {v['ref']} to regenerate)")
    if cfg.get('_grown'):
        log.append(f"grow  +{a.grow:g} mm on {cfg['_grown']} openings (screw and mounting holes unchanged)")
    cutouts = [c for c in cutouts if c['key'] not in off]

    groups, problems = merge_and_check(cutouts + manual, outline, a.min_web, log)
    problems += case_warn + rail_warn
    shapes = [g for g in groups if not g['manual']]
    placed, label_rows = [], []
    if a.labels == 'on':
        n0 = len(log)
        placed, label_rows = make_labels(pcb, cutouts + manual, groups, outline, a, label_edits, log,
                                         no_hole=set(cfg.get('_none_ids', set())) | set(ignore_uncut))
        problems += sum(1 for l in log[n0:] if l.startswith('WARN'))
        log.append(f"labels {len(placed)} on the silkscreen ({sum(1 for r in label_rows if r['hide'])} hidden, "
                   f"{sum(1 for r in label_rows if not r['hide'] and not r['text'].strip())} with no text)")
    a._markers = part_markers(pcb, set(cfg.get('_none_ids', set())) | set(ignore_uncut), outline)
    # the template and the artwork file's guides first, so the artwork is rendered on the panel's current page
    if preview is None and (a.svg or a.make_artwork_file or (a.artwork == 'on' and os.path.exists(artwork_path_for(out_path)))):
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        svg_path = re.sub(r'\.kicad_pcb$', '', out_path) + '_template.svg'
        write_svg(svg_path, x1, y1, x2, y2, groups, placed, a)
        log.append(f"svg   {svg_path}")
        art_svg = artwork_path_for(out_path)
        if os.path.exists(art_svg):
            refresh_artwork_guides(art_svg, svg_path, log)
        if a.make_artwork_file:
            if os.path.exists(art_svg):
                log.append(f"NOTE  {os.path.basename(art_svg)} already exists - left as it is, so your artwork is safe")
            else:
                import shutil
                shutil.copyfile(svg_path, art_svg)
                log.append(f"art   started {art_svg} - open it in Inkscape and draw on the 'Artwork' layer")
    art = []
    if a.artwork == 'on':
        art_svg = a.artwork_file or artwork_path_for(out_path)
        if not os.path.exists(art_svg):
            log.append(f"ERROR no artwork file yet ({os.path.basename(art_svg)}). Click 'Create artwork file' in the window "
                       f"(or use --make-artwork-file), draw on its Artwork layer in Inkscape, save, then generate")
        else:
            art = import_artwork(art_svg, outline, log, os.path.dirname(out_path) if os.path.isdir(os.path.dirname(out_path)) else None)
    if preview is not None and a.make_artwork_file:      # the window's 'Create artwork file' button: no panel written
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        svg_path = re.sub(r'\.kicad_pcb$', '', out_path) + '_template.svg'
        write_svg(svg_path, x1, y1, x2, y2, groups, placed, a)
        if not os.path.exists(artwork_path_for(out_path)):
            import shutil
            shutil.copyfile(svg_path, artwork_path_for(out_path))
    if preview is not None:
        fill_preview(preview, groups, outline, (x1, y1, x2, y2), a, log, problems,
                     eurorack=hp if tpl else None,
                     pcb_box=((x1 + ER_PCB_INSET, y1 + ER_RAIL, x2 - ER_PCB_INSET, y2 - ER_RAIL) if tpl else (bx1, by1, bx2, by2)),
                     rail_bad=rail_bad, uncut=uncut, labels=placed, label_rows=label_rows,
                     label_edits=label_edits, ignore_uncut=ignore_uncut, artwork=art, markers=a._markers)
        return 1 if any(l.startswith('ERROR') for l in log) else 0

    uuids, items, generated = [], [], {}
    items += outline_items(x1, y1, x2, y2, a.corner_radius, uuids)
    outline_ids = list(uuids)
    for g in shapes:
        start = len(uuids)
        items += emit_geom(g, uuids)
        generated[g['key']] = dict(describe(g), uuids=uuids[start:])
    items += label_items(placed, a, uuids)
    items += artwork_items(art, uuids)
    group = (f'\t(group "{GROUP_NAME}" (uuid "{stable_uuid("group")}") (members '
             + ' '.join(f'"{u}"' for u in uuids) + '))')

    if existing_text:
        text = existing_text + '\n'.join(items) + '\n' + group + '\n)\n'
        log.append(f"update {out_path}: replaced {removed} generated items, kept {len(manual)} hand-placed cutouts")
    else:
        text = header_from(pcb_text, pcb) + '\n'.join(items) + '\n' + group + '\n)\n'
        log.append(f"new   {out_path}")
    open(out_path, 'w', encoding='utf-8').write(text)
    json.dump({'panelgen': VERSION, 'note': 'panelgen memory: what it generated last run, and what you deleted or edited. Keep next to the panel.',
               'outline': outline_ids, 'outline_box': [round(v, 4) for v in (x1, y1, x2, y2)],
               'generated': generated, 'suppressed': suppressed, 'kept': kept,
               'labels_generated': {L['fid']: dict(uuid=L['uuid'], at=[L['x'], L['y']], auto=list(L['auto']), text=L['text'],
                                                    ref=L['ref']) for L in placed},
               'label_edits': label_edits, 'ignore_uncut': ignore_uncut,
               'settings': dict(margin=a.margin, **{f'margin_{k}': v for k, v in m.items()},
                                screws=a.screws, screw_dia=a.screw_dia, screw_inset=a.screw_inset, screw_slot=a.screw_slot, rail_slot=a.rail_slot,
                                corner_radius=a.corner_radius, grow=a.grow, min_web=a.min_web,
                                panel_layer=a.panel_layer, svg=bool(a.svg), check_uncut=a.check_uncut,
                                labels=a.labels, label_size=a.label_size, label_gap=a.label_gap, label_pos=a.label_pos,
                                label_font=a.label_font, label_bold=a.label_bold, label_caps=a.label_caps,
                                artwork=a.artwork, artwork_file=a.artwork_file)},
              open(mem_path, 'w', encoding='utf-8'), indent=1)


    if a.gerbers:
        if any(l.startswith('ERROR') for l in log):
            log.append("NOTE  no gerbers made - fix the ERRORs first")
        else:
            make_gerbers(out_path, log)

    n_parts = len({c['id'] for c in cutouts if not c['id'].startswith('CASE')})
    spots = [c for c in cutouts if c['id'].startswith('CASE')]
    extra = f"{len(rail_holes)} rail holes" if tpl else f"{len(spots)} case screws"
    print(f"panelgen {VERSION}: {n_parts} parts + {extra} -> {len(shapes)} cutouts, {problems} problem(s)")
    for line in log:
        print('  ' + line)
    return 1 if any(l.startswith('ERROR') for l in log) else 0

if __name__ == '__main__':
    sys.exit(main())
