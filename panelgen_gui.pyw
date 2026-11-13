#!/usr/bin/env python3
"""Panel Generator - a window for panelgen. Double-click to run (or: py panelgen_gui.pyw [board.kicad_pcb])."""
import contextlib, glob, io, json, math, os, re, subprocess, sys, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont

HERE = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CONFIG = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'panelgen', 'gui.json')

DEFAULTS = dict(margin=0.0, margin_top=0.0, margin_right=0.0, margin_bottom=0.0, margin_left=0.0,
                screws='none', screw_dia=2.2, screw_inset=3.5, screw_slot=0.0, rail_slot=0.0,
                corner_radius=0.0, grow=0.0, svg=False, check_uncut='on',
                artwork='off', labels='off', label_size=2.0, label_gap=1.5, label_pos='above', label_font='', label_bold='off', label_caps='off',
                extras='on', auto_art='off', art_style='Classic synth', art_scale='ticks', art_rings='on', art_outputs='off', art_border='off',
                art_border_radius=0.0, art_border_gap=0.0, ring_width=0.8, ring_gap=0.8, art_groups='off', art_tabs='off',
                art_title='', art_maker='', title_size=5.0, knob_size=13.0)
ART_STYLES = {   # what each style switches on
    'None': dict(scale='None', rings=False, outputs=False, border=False, groups=False, tabs=False),
    'Minimal': dict(scale='Ticks', rings=False, outputs=False, border=False, groups=False, tabs=False),
    'Classic synth': dict(scale='Numbers 0-10', rings=True, outputs=False, border=True, groups=True, tabs=True),
    'Modular': dict(scale='Ticks', rings=False, outputs=True, border=False, groups=False, tabs=True),
}
STYLE_KEYS = ('scale', 'rings', 'outputs', 'border', 'tabs')
GROUP_KINDS = ('pot', 'button', 'jack')
TECH_URL = 'https://github.com/lonesoulsurfer/kicad-front-panel-generator/blob/main/docs/TECHNICAL.md'
HOW_PANEL = [("Change the size of one part's hole", "In KiCad, on the PCB, open the part's properties and add a field named Panel. Its value sets the hole: circle:6.5 (a 6.5 mm round hole), square:7, rect:8x6. The hole stays centred on the part and moves with it. For several parts the same (all the tactile switches with caps, say), add the field to the symbol in the schematic and use Update PCB from Schematic."), ("Give a hole to a part the generator doesn't know", 'Draw the hole on the User.1 layer of the PCB: any closed shape there is cut exactly as drawn. Or add a Panel field (above). If you use the part often, add a rule for it to panel_rules.json, next to the app.'), ('Stop a part getting a hole', "Add a Panel field with the value skip. Or, if it shows an orange 'no cutout?' box, click the box. Or delete its hole in the panel file in KiCad - it then stays off, and is listed under Holes you removed or changed."), ("Add a hole for something that isn't on the PCB", 'A jack or switch wired to the board: use Extra holes above. Or, in the panel file in KiCad, place a part from PanelParts.pretty (jacks, LEDs, toggles, tactile switch, screws, a USB-C charge slot).'), ('Move or resize a hole just on the panel', 'Change it in the panel file in KiCad and save. Your version is kept every time you generate, and listed under Holes you removed or changed - pick it there and click Bring back to undo it.'), ('Show where a part is without cutting a hole', 'Draw it on the User.2 layer of the PCB. It shows in the preview as a blue guide to line things up with, and is never cut or printed.'), ('Check the spacing by the size of the parts',
  "Right-click a hole and choose Show the part's size round it: a dashed blue circle or rectangle for the part's body, nut or knob. Drag its edge to set the size - the size and the gap to the nearest part show as you drag. Or put one on every hole that size at once. They're never cut or printed."),
 ('Start again from the PCB', 'Reset (above the preview) takes the panel back to the bare PCB: its own size and holes, nothing added. Undo brings it all back.')]
HOW_ART = [('Change what a label says', "Click it (or right-click, Change text). To set it on the PCB so it's the same every time, add a field named Label to the part in KiCad - it's used instead of the part's Value."), ('Line labels up', 'Drag a label: it snaps level with the others, to the middle of holes and of the keys under a window (the blue dotted outlines), and half way between two holes. Hold Alt to place it freely.'), ('Change several things at once', 'Drag a box round them, or Shift-click each. Then drag them together, copy them (Ctrl+C, Ctrl+V), or press Delete.'), ('White text on a black bar', "Click the text and set Box to A filled bar - the text is cut out of it. Drag the bar's ends to stretch it over a row of keys."), ('Put a shape round a hole', 'Set it up under Shapes, then right-click the hole and choose Add a shape round it. A filled box pulled over a label cuts the label out of it.'), ('Measure, or place something an exact distance away', 'Click Measure, click the first point, then type a length and press Enter. The ruler stays as a guide: things snap to its ends and middle. Hold Ctrl to keep it straight.'), ('Anything else', 'Switch on Artwork from Inkscape and draw it there: black prints, white cuts out of black.')]
MULTI = ('text', 'label', 'line', 'image')    # what a box or Shift-click can pick up, besides holes you added
MARKS = {'Circle': 'circle', 'Box': 'box', 'Triangle': 'triangle', 'Hexagon': 'hexagon', 'Diamond': 'diamond'}
LINE_ENDS = {'Plain': 'none', 'Arrow at the end': 'end', 'Arrows at both ends': 'both'}
MY_STYLE = 'My style'
STYLE_VARS = ('labels_on', 'label_pos', 'label_gap', 'label_size', 'label_font', 'label_bold', 'label_caps', 'art_scale',
              'knob_size', 'art_rings', 'ring_width', 'ring_gap', 'art_outputs', 'art_tabs', 'art_border', 'border_gap',
              'border_radius', 'title_size', 'title_dir', 'art_maker', 'line_w') + tuple('art_groups_' + k for k in GROUP_KINDS)
TITLE_DIRS = {'Across': 'off', 'Stacked': 'stacked', 'On its side': 'on', 'On its side, reading down': 'on-mirror'}
SCALES = {'None': 'none', 'Ticks': 'ticks', 'Numbers 0-10': 'numbers', 'Centre zero (- 0 +)': 'bipolar'}
KICAD_FONT = "KiCad's own font"
HOLE_SIZES = ('3.2  ·  3 mm LED or M3 screw', '5.2  ·  5 mm LED or small toggle', '6.2  ·  3.5 mm jack', '6.5  ·  mini toggle switch',
              '7.5  ·  pot or encoder', '4  ·  6x6 tactile switch', '10  ·  6.35 mm jack', '2.7  ·  M2.5 screw', '2.2  ·  M2 screw')
SHAPE_NAMES = {'hole': 'hole', 'rect': 'rectangle', 'slot': 'slot'}
ALT_MASK = 0x20000 if sys.platform == 'win32' else 0x0008   # Alt held (on Windows, 0x0008 is Num Lock)

# preview colours
C_BG, C_PANEL, C_PANEL_EDGE, C_HOLE = '#eef1f4', '#3b4754', '#1f262e', '#eef1f4'
C_PCB, C_RAIL = '#3d8bfd', '#8b97a4'
C_WARN, C_WARN_FILL, C_ERR, C_ERR_FILL = '#e8930c', '#fbe3b6', '#d93025', '#f6c3bf'
C_OK_TXT, C_WARN_TXT, C_ERR_TXT, C_DIM = '#1e7e34', '#b35c00', '#c00000', '#6b7580'


def panel_paths(board):
    """Panel and its memory file: in the Front Panel folder, or next to the board if it hasn't been moved yet."""
    import panelgen
    new = panelgen.default_panel_path(board)
    old = panelgen.old_panel_path(board)
    p = new if (os.path.exists(new) or not os.path.exists(old)) else old
    return p, p[:-len('.kicad_pcb')] + '.panelgen.json'


def lock_file(path):
    d, f = os.path.split(path)
    return os.path.join(d, '~' + f + '.lck')


def find_kicad():
    """Newest KiCad PCB editor on Windows, or None."""
    hits = glob.glob(r'C:\Program Files\KiCad\*\bin\pcbnew.exe')
    def ver(p):
        m = re.search(r'KiCad\\([\d.]+)\\', p)
        return [int(x) for x in m.group(1).split('.')] if m else [0]
    return sorted(hits, key=ver)[-1] if hits else None


def load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


class E_:
    """A stand-in mouse event at a known spot on the preview."""
    def __init__(self, xy, state=0):
        self.x, self.y, self.state = xy[0], xy[1], state


class Tip:
    """Hover help for a widget."""
    def __init__(self, widget, text):
        self.w, self.text, self.top = widget, text, None
        widget.bind('<Enter>', self.show, add='+')
        widget.bind('<Leave>', self.hide, add='+')

    def show(self, _=None):
        if self.top or not self.text:
            return
        x, y = self.w.winfo_rootx() + 12, self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.top = tk.Toplevel(self.w); self.top.wm_overrideredirect(True); self.top.wm_geometry(f'+{x}+{y}')
        tk.Label(self.top, text=self.text, justify='left', wraplength=340, bg='#fffbe6', fg='#222',
                 relief='solid', borderwidth=1, padx=8, pady=5).pack()

    def hide(self, _=None):
        if self.top:
            self.top.destroy(); self.top = None


class App(tk.Tk):
    def __init__(self, board=None):
        super().__init__()
        import panelgen
        self.pg = panelgen
        self.title(f'Panel Generator {panelgen.VERSION}')
        self.geometry('1200x800'); self.minsize(1000, 700)
        self.themed = self.apply_theme()
        self.cfg = load_json(CONFIG)
        self.board = tk.StringVar(value=board or self.cfg.get('last_board', ''))
        v = self.vars = {}
        v['margin'] = tk.StringVar(value='0')
        v['per_side'] = tk.BooleanVar()
        for s in ('top', 'right', 'bottom', 'left'):
            v[s] = tk.StringVar(value='0')
        v['screws'] = tk.StringVar(value='none')
        v['screw_dia'] = tk.StringVar(value='2.2'); v['screw_inset'] = tk.StringVar(value='3.5')
        v['case_shape'] = tk.StringVar(value='round'); v['slot'] = tk.StringVar(value='4')
        v['rail_shape'] = tk.StringVar(value='round'); v['rslot'] = tk.StringVar(value='5')
        v['radius'] = tk.StringVar(value='0')
        v['svg'] = tk.BooleanVar(); v['open'] = tk.BooleanVar(value=self.cfg.get('open_after', True))
        v['art_on'] = tk.BooleanVar()
        v['texts_on'] = tk.BooleanVar(value=True); v['pictures_on'] = tk.BooleanVar(value=True)
        v['art_style'] = tk.StringVar(value='None')
        v['art_scale'] = tk.StringVar(value='None'); v['art_rings'] = tk.BooleanVar()
        v['art_outputs'] = tk.BooleanVar(); v['art_border'] = tk.BooleanVar()
        for k in GROUP_KINDS:
            v['art_groups_' + k] = tk.BooleanVar()
        v['art_tabs'] = tk.BooleanVar(); v['border_radius'] = tk.StringVar(value='0')
        v['border_gap'] = tk.StringVar(value='0'); v['ring_width'] = tk.StringVar(value='0.8'); v['ring_gap'] = tk.StringVar(value='0.8')
        v['art_title'] = tk.StringVar(); v['art_maker'] = tk.StringVar(); v['title_mirror'] = tk.BooleanVar()
        v['line_w'] = tk.StringVar(value='0.5')
        v['mark_kind'] = tk.StringVar(value='Circle'); v['mark_fill'] = tk.BooleanVar(); v['mark_gap'] = tk.StringVar(value='1')
        v['mark_w'] = tk.StringVar(value='0.6'); v['mark_r'] = tk.StringVar(value='1')
        v['title_size'] = tk.StringVar(value='5'); v['knob_size'] = tk.StringVar(value='13')
        v['title_dir'] = tk.StringVar(value='Across')
        v['labels_on'] = tk.BooleanVar(); v['label_pos'] = tk.StringVar(value='above')
        v['label_gap'] = tk.StringVar(value='1.5'); v['label_size'] = tk.StringVar(value='2')
        v['label_font'] = tk.StringVar(value=KICAD_FONT); v['label_bold'] = tk.BooleanVar(); v['label_caps'] = tk.BooleanVar()
        self.ui = {'ignore': {}, 'label_edits': {}, 'texts': [], 'art_pos': {}, 'images': [], 'shapes': [], 'lines': [], 'titles': [], 'marks': [], 'bodies': []}   # ignored parts, label changes, your texts, moved title, pictures
        self.undo_stack, self.state_prev, self.restoring = [], None, False
        self.editor = None
        self.mode, self.pv, self.after_id, self.loading = None, None, None, False
        self.stamp = None
        self.guides_at = None        # when the guides in the artwork file were last brought up to date
        self.result_is_preview = True
        self.build()
        for k, var in v.items():
            if k != 'open':
                var.trace_add('write', lambda *_: self.settings_changed())
        if self.board.get():
            self.board_changed()
        else:
            self.show_boards()
        self.refresh_states()
        self.after(1500, self.watch_files)

    # ------------------------------------------------------------------ look
    def apply_theme(self):
        try:
            import sv_ttk
            sv_ttk.set_theme('light')
            themed = True
        except Exception:
            self.theme_error = traceback.format_exc()
            st = ttk.Style(self)
            for t in ('vista', 'clam'):
                if t in st.theme_names():
                    st.theme_use(t); break
            themed = False
        base = tkfont.nametofont('TkDefaultFont')
        fam = base.actual('family')
        self.f_title = tkfont.Font(family=fam, size=base.actual('size') + 3, weight='bold')
        self.f_head = tkfont.Font(family=fam, size=base.actual('size') + 1, weight='bold')
        self.f_small = tkfont.Font(family=fam, size=max(8, base.actual('size') - 1))
        st = ttk.Style(self)
        st.configure('Head.TLabel', font=self.f_head)
        st.configure('Title.TLabel', font=self.f_title)
        st.configure('Dim.TLabel', foreground=C_DIM, font=self.f_small)
        st.configure('Badge.TLabel', font=self.f_head)
        st.configure('Group.TLabel', font=self.f_head, foreground='#2563eb')
        self.f_sub = tkfont.Font(family=fam, size=max(8, base.actual('size') - 1), weight='bold')
        st.configure('Sub.TLabel', font=self.f_sub, foreground='#5b6b7d')
        st.configure('Chev.TLabel', font=self.f_head, foreground='#5b6b7d')
        if not themed:
            st.configure('Card.TFrame', relief='solid', borderwidth=1)
            st.configure('Accent.TButton', font=self.f_head, padding=8)
        return themed

    # ------------------------------------------------------------------ layout
    def build(self):
        v = self.vars
        root = ttk.Frame(self, padding=(14, 10)); root.pack(fill='both', expand=True)
        root.columnconfigure(2, weight=1); root.rowconfigure(1, weight=1)


        bg = ttk.Style(self).lookup('TFrame', 'background') or C_BG
        lc = self.left_col = ttk.Frame(root, width=int(self.cfg.get('left_w', 530))); lc.grid(row=1, column=0, sticky='nsew')
        lc.pack_propagate(False)                  # its width is what you drag it to, not what its contents ask for
        self.sash(root, 'v').grid(row=1, column=1, sticky='ns')
        self.sections, self.switches = {}, {}
        self.collapsed = set(self.cfg.get('collapsed', []))
        self.tab = 'panel'

        # always in view: the PCB, and the two halves of the job
        top = ttk.Frame(lc); top.pack(fill='x')
        s = self.section('pcb', 'Your PCB', None, parent=top, fold=False)
        row = ttk.Frame(s); row.pack(fill='x')
        self.board_name = tk.StringVar()
        cb = self.board_box = ttk.Combobox(row, textvariable=self.board_name, state='readonly')
        cb.pack(side='left', fill='x', expand=True)
        cb.bind('<<ComboboxSelected>>', self.pick_recent)
        self.board_tip = Tip(cb, 'The synth PCB with the parts on it. Save it in KiCad first.')
        ttk.Button(row, text='Browse…', command=self.browse).pack(side='left', padx=(6, 0))
        self.mode_lbl = ttk.Label(s, text='', style='Badge.TLabel'); self.mode_lbl.pack(anchor='w', pady=(6, 0))
        Tip(self.mode_lbl, 'A PCB with a Eurorack_xHP template from Eurorack.pretty on it gets a standard Eurorack panel; '
                           'any other PCB gets a panel fitted to its outline.')
        self.mode_hint = ttk.Label(s, text='', style='Dim.TLabel', wraplength=440, justify='left')
        self.mode_hint.pack(anchor='w')
        tabs = ttk.Frame(top); tabs.pack(fill='x', pady=(4, 8))
        tabs.columnconfigure(0, weight=1, uniform='t'); tabs.columnconfigure(1, weight=1, uniform='t')
        self.tab_btn = {}
        for i, (key, txt, tip) in enumerate((('panel', 'Panel', 'The board itself: its size, shape and holes.'),
                                             ('art', 'Artwork', 'Everything printed on the panel: labels, your own text and '
                                                                'pictures, scales, borders, Inkscape artwork.'))):
            bt = self.tab_btn[key] = ttk.Button(tabs, text=txt, command=lambda k=key: self.show_tab(k))
            bt.grid(row=0, column=i, sticky='ew', padx=(0, 3) if i == 0 else (3, 0), ipady=2)
            Tip(bt, tip)

        sc_ = ttk.Frame(lc); sc_.pack(fill='both', expand=True)
        cv = tk.Canvas(sc_, highlightthickness=0, width=200, bg=bg)
        lsb = ttk.Scrollbar(sc_, orient='vertical', command=cv.yview)
        cv.configure(yscrollcommand=lsb.set)
        cv.pack(side='left', fill='both', expand=True)
        left = ttk.Frame(cv, padding=(0, 0, 8, 0)); win = cv.create_window(0, 0, window=left, anchor='nw')
        def fit(_=None):
            cv.configure(scrollregion=cv.bbox('all'))
            need = left.winfo_reqheight() > cv.winfo_height() + 2
            if need and not lsb.winfo_manager():
                lsb.pack(side='right', fill='y', before=cv)
            elif not need and lsb.winfo_manager():
                lsb.pack_forget(); cv.yview_moveto(0)
            keep = getattr(self, '_keep_y', None)          # a rebuilt part of the panel mustn't move what you're looking at
            if keep is not None and need:
                cv.yview_moveto(keep / max(1, left.winfo_reqheight()))
        left.bind('<Configure>', fit)
        cv.bind('<Configure>', lambda e: (cv.itemconfigure(win, width=e.width), fit()))
        def wheel(e):
            if lsb.winfo_manager():
                cv.yview_scroll(-1 if (getattr(e, 'delta', 0) > 0 or e.num == 4) else 1, 'units')
        wheels = ('<MouseWheel>', '<Button-4>', '<Button-5>')
        cv.bind('<Enter>', lambda e: [self.bind_all(x, wheel) for x in wheels])
        cv.bind('<Leave>', lambda e: [self.unbind_all(x) for x in wheels])
        self.left = left
        for x in wheels:                         # the wheel scrolls the panel; it must never change a list it passes over
            self.unbind_class('TCombobox', x)
        field, sub, mm = self.field, self.sub, self.mm

        # ================================================================ PANEL
        # size (fit to PCB)
        s = self.section('size', 'Size and shape', 'The panel starts the same size as your PCB.')
        f = self.form(s)
        c = field(f, 'Extra round the PCB', 'Extra panel on every side, e.g. 10 mm to leave room for a case or wired jacks. '
                                            '0 = the same size as the PCB.')
        self.w_margin = mm(c, 'margin')
        c = field(f, 'Each side')
        self.w_per = ttk.Checkbutton(c, text='Set each side separately', variable=v['per_side'], command=self.refresh_states)
        self.w_per.pack(side='left')
        h2 = ttk.Frame(s); h2.pack(fill='x')                # holder for a block that comes and goes
        sides = self.sides_row = self.form(h2)
        self.w_sides = [mm(field(sides, side.capitalize()), side) for side in ('top', 'right', 'bottom', 'left')]
        f = self.form(s)
        c = field(f, 'Corner radius', 'Rounds the four corners of the panel. 0 = square corners.')
        self.w_radius = mm(c, 'radius')

        # rail holes (Eurorack)
        s = self.section('rail', 'Rail holes', '3.2 mm holes at the standard Eurorack positions. 4 holes from 10HP up.')
        f = self.form(s)
        c = field(f, 'Shape')
        ttk.Radiobutton(c, text='Round', value='round', variable=v['rail_shape'], command=self.refresh_states).pack(side='left', padx=(0, 12))
        r_ = ttk.Radiobutton(c, text='Slots', value='slot', variable=v['rail_shape'], command=self.refresh_states)
        r_.pack(side='left')
        Tip(r_, 'Horizontal slots centred on the standard hole position, so the module can slide a little along the rail.')
        c = field(f, 'Slot length', 'End to end.')
        self.w_rslot = mm(c, 'rslot')

        # case holes (fit to PCB)
        s = self.section('case', 'Case mounting holes', 'Screw holes round the panel edge, for fixing it to a case.')
        f = self.form(s)
        c = field(f, 'Where')
        for txt, val in (('None', 'none'), ('Corners', 'corners'), ('Corners + sides', 'corners+mid')):
            r_ = ttk.Radiobutton(c, text=txt, value=val, variable=v['screws'], command=self.refresh_states)
            r_.pack(side='left', padx=(0, 12))
        Tip(r_, 'A hole in each corner and one in the middle of each side.')
        h3 = ttk.Frame(s); h3.pack(fill='x')
        det = self.case_detail = ttk.Frame(h3); det.pack(fill='x')
        f = self.form(det)
        self.w_dia = mm(field(f, 'Hole size'), 'screw_dia')
        c = field(f, 'Edge to hole centre', 'Measured from the panel edge to the centre of the hole. For slots, to the centre '
                                            'of the end nearest that edge.')
        self.w_inset = mm(c, 'screw_inset')
        c = field(f, 'Shape')
        self.w_cround = ttk.Radiobutton(c, text='Round', value='round', variable=v['case_shape'], command=self.refresh_states)
        self.w_cround.pack(side='left', padx=(0, 12))
        self.w_cslot = ttk.Radiobutton(c, text='Slots', value='slot', variable=v['case_shape'], command=self.refresh_states)
        self.w_cslot.pack(side='left')
        Tip(self.w_cslot, 'Slots along the edge give the case screws some play. Corner slots run inwards from the corner position.')
        self.w_slot = mm(field(f, 'Slot length', 'End to end.'), 'slot')
        self.edge_info = tk.Label(det, text='', anchor='w', justify='left', wraplength=440, font=self.f_small)
        self.edge_info.pack(anchor='w', pady=(4, 0))

        # holes you add yourself
        s = self.section('holes', 'Extra holes', "Holes, rectangles and slots for things that aren't on the PCB "
                                                 '(a wired jack, a switch, a window).')
        f = self.form(s)
        c = field(f, 'Hole size', 'Pick a usual size or type your own in mm. These are common sizes: check them against your own parts.')
        self.hole_size = tk.StringVar(value=HOLE_SIZES[2])
        self.hole_size.trace_add('write', lambda *_: self.hole_size_changed())   # changes the selected hole, if one is
        hb = self.w_hole_size = ttk.Combobox(c, textvariable=self.hole_size, width=28); hb.pack(side='left')
        ttk.Label(c, text='mm').pack(side='left', padx=(4, 0))
        hb.bind('<<ComboboxSelected>>', lambda e: self.hole_size_picked())
        hb.bind('<Return>', lambda e: self.keep_hole_size()); hb.bind('<FocusOut>', lambda e: self.keep_hole_size())
        self.hole_list()
        ttk.Label(f, text='Pick a size, or choose "Your own size…" (or just type one in the box) - e.g. 4.5. Sizes you '
                          'type are added to the list.', style='Dim.TLabel', wraplength=420, justify='left'
                  ).grid(row=f._rows, column=0, columnspan=2, sticky='w'); f._rows += 1
        c = field(f, 'Add')
        for kind, txt in (('hole', 'Hole'), ('rect', 'Rectangle'), ('slot', 'Slot')):
            bt = ttk.Button(c, text=txt, command=lambda k=kind: self.start_add(k)); bt.pack(side='left', padx=(0, 6))
            Tip(bt, 'Click this, then click on the panel where it goes (or right-click the panel). It snaps into line with '
                    'the other holes; hold Alt to place it freely. Then set its exact place and size here.')
        sub(s, 'Selected')
        self.hole_box = ttk.Frame(s); self.hole_box.pack(fill='x')
        self.shape_sel, self.last_size = [], {'rect': (20.0, 10.0), 'slot': (10.0, 3.2)}
        self.measuring, self.measure = False, []

        # holes you removed
        s = self.section('restore', 'Holes you removed or changed', 'Delete or resize a hole in the panel in KiCad and it stays '
                                                                   'that way. Parts you said need no cutout are listed here too.')
        row = ttk.Frame(s); row.pack(fill='x')
        self.restore_list = tk.Listbox(row, height=2, selectmode='extended', activestyle='none', relief='flat',
                                       highlightthickness=1, highlightcolor='#c8ced5', highlightbackground='#c8ced5')
        self.restore_list.pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Bring back', command=self.restore).pack(side='left', padx=(6, 0), anchor='n')

        # ================================================================ ARTWORK
        # labels: the ones from the PCB, and texts of your own
        s = self.section('labels', 'Labels', "Names next to the controls, taken from the PCB, and texts you add yourself.")
        sub(s, 'From the PCB', first=True)
        f = self.form(s)
        c = field(f, 'Labels', "Each part's text comes from its Label field if it has one, otherwise its Value or Reference "
                               "(e.g. 'Cutoff', 'Play'). Change, hide or move any of them after.")
        ttk.Checkbutton(c, text='A name next to each control', variable=v['labels_on'], command=self.refresh_states).pack(side='left')
        h4 = ttk.Frame(s); h4.pack(fill='x')
        det = self.label_detail = ttk.Frame(h4); det.pack(fill='x')
        f = self.form(det)
        c = field(f, 'Position')
        ttk.Radiobutton(c, text='Above the hole', value='above', variable=v['label_pos']).pack(side='left', padx=(0, 12))
        ttk.Radiobutton(c, text='Below', value='below', variable=v['label_pos']).pack(side='left')
        c = field(f, 'Gap from the hole', 'Distance from the edge of the hole to the text. Keys in a merged switch slot follow '
                                          'their own side of the slot.')
        mm(c, 'label_gap')
        c = field(f, 'Each label')
        bt = ttk.Button(c, text='Edit labels…', command=self.edit_labels); bt.pack(side='left')
        Tip(bt, 'A list of every label: change its text, hide it, set its own gap, or choose its artwork. '
                'You can also click a label in the preview, or right-click it.')
        sub(s, 'Your own')
        f = self.form(s)
        row = self.extras_row = field(f, 'Add')
        bt = ttk.Button(row, text='Text…', command=self.start_add_text); bt.pack(side='left')
        Tip(bt, "For things that aren't on the PCB, such as what a key does. Click this, then click on the panel where the text "
                "goes. Drag any text or label to move it: it snaps into line with other labels, to the middle of holes and to "
                "the middle of gaps (hold Alt to place it freely).")
        c = field(f, 'Show', "Untick to leave your own texts off the panel (and the preview) without losing them. Handy when "
                             "you change to Inkscape artwork that already has its own text.")
        ttk.Checkbutton(c, text='My own texts on the panel', variable=v['texts_on']).pack(side='left')
        sub(s, 'Text')
        f = self.form(s)
        mm(field(f, 'Size', 'For every label and text. One of your own texts can have its own size: click it.'), 'label_size')
        c = field(f, 'Font', "KiCad's own font always works. Any other font has to be installed on the computer that opens the "
                             "panel (the gerbers carry the shapes, so the fab doesn't need it).")
        fonts = [KICAD_FONT] + sorted({x for x in tkfont.families() if not x.startswith('@')})
        ttk.Combobox(c, textvariable=v['label_font'], values=fonts, width=24, state='readonly').pack(side='left')
        c = field(f, 'Style')
        ttk.Checkbutton(c, text='Bold', variable=v['label_bold']).pack(side='left', padx=(0, 12))
        ttk.Checkbutton(c, text='ALL CAPS', variable=v['label_caps']).pack(side='left')
        sub(s, 'Selected')
        self.sel_boxes, self.sel_subs = {'labels': ttk.Frame(s)}, {}
        self.sel_boxes['labels'].pack(fill='x')

        # pictures
        s = self.section('extras', 'Pictures', 'A logo, a glider: its dark parts print.', switch='pictures_on',
                         tip="Switch off to leave your pictures off the panel (and the preview) without losing them.")
        f = self.form(s)
        bt = ttk.Button(field(f, 'Add'), text='Picture…', command=self.add_picture); bt.pack(side='left')
        Tip(bt, 'A PNG, JPG or SVG. Its dark parts print, transparent parts never do. It is copied into the Front Panel folder. '
                'Drag it into place; click it and drag a corner to resize it.')
        sub(s, 'Selected')
        self.sel_box = self.sel_boxes['extras'] = ttk.Frame(s); self.sel_box.pack(fill='x')
        self.sel = None

        # the look to start from
        s = self.section('style', 'Style', 'A look to start from. It sets the scales, rings, boxes, tabs and border below; '
                                           'change any of them after.')
        f = self.form(s)
        c = field(f, 'Style', 'None: nothing added. Minimal: ticks round the pots. Classic synth: numbered scales, rings round '
                              'buttons, boxes round rows of controls, tabs for horizontal jacks, a border. Modular: ticks, and '
                              'outputs in filled boxes. Custom: your own mix.')
        sc = self.w_style = ttk.Combobox(c, textvariable=v['art_style'], width=24, state='readonly')
        sc.pack(side='left')
        sc.bind('<<ComboboxSelected>>', lambda e: self.apply_style())
        c = field(f, 'My style', 'Remembers how this panel looks - the label size and font, scales, rings, boxes, tabs, border, '
                                 'title size and direction, maker name and line thickness - as "My style". Every new PCB you '
                                 'open then starts with it, and you can pick it from the Style list on any panel. '
                                 'It does not include the title text, the panel size or the holes.')
        ttk.Button(c, text='Save this look as my style', command=self.save_my_style).pack(side='left')
        self.w_style_note = ttk.Label(s, text='', style='Dim.TLabel', wraplength=440, justify='left')
        self.w_style_note.pack(anchor='w', pady=(2, 0))
        self.style_list()

        # title
        s = self.section('title', 'Title', "The synth's name on the panel, and yours if you like. Leave empty for none.")
        f = self.form(s)
        ttk.Entry(field(f, 'Text'), textvariable=v['art_title'], width=27).pack(side='left')
        mm(field(f, 'Size', 'Or click the title in the preview and drag one of its corners.'), 'title_size')
        c = field(f, 'Direction', 'Across, along the top. Stacked: the letters one under another, each the right way up. '
                                  'On its side: turned to read from the bottom. On its side, reading down: turned the other way. '
                                  'Drag it anywhere after.')
        ttk.Combobox(c, textvariable=v['title_dir'], values=list(TITLE_DIRS), width=24, state='readonly').pack(side='left')
        c = field(f, 'Mirror', 'The letters flipped left to right, as in a mirror. Usually for a copy of the title next to the '
                               'real one: copy the title (Ctrl+C, Ctrl+V), click the copy and tick this on it.')
        ttk.Checkbutton(c, text='Mirror image', variable=v['title_mirror']).pack(side='left')
        c = field(f, 'Maker name', 'Your name or brand, small, along the bottom. Leave empty for none.')
        ttk.Entry(c, textvariable=v['art_maker'], width=27).pack(side='left')
        self.sel_subs['title'] = sub(s, 'Selected')
        self.sel_boxes['title'] = ttk.Frame(s); self.sel_boxes['title'].pack(fill='x')

        row_tip = ('A box round 3 or more of them in a row or a column, with their scales and labels inside. Click the box in the '
                   'preview and drag its top, bottom or a side to resize it. Left out (with a note) when it would run into '
                   'another part, a label or the edge.')
        # pots
        s = self.section('pots', 'Pots', 'Scales round the pots, and a box round a row of them.')
        f = self.form(s)
        c = field(f, 'Scale', 'Marks round every pot, over a 300 degree turn. Change one pot (e.g. centre zero for a pan pot) '
                              'in Edit labels.')
        ttk.Combobox(c, textvariable=v['art_scale'], values=list(SCALES), width=24, state='readonly').pack(side='left')
        c = field(f, 'Knob size', 'Knob diameter: the scale and the label start outside it, so the knob never hides them.')
        mm(c, 'knob_size')
        ttk.Checkbutton(field(f, 'Box', row_tip), text='A box round a row of pots', variable=v['art_groups_pot']).pack(side='left')
        self.sel_subs['pots'] = sub(s, 'Selected')
        self.sel_boxes['pots'] = ttk.Frame(s); self.sel_boxes['pots'].pack(fill='x')

        # shapes round holes
        s = self.section('shapes', 'Shapes', 'A circle, box, triangle, hexagon or diamond round any hole - an outline, or filled '
                                             'with the label cut out of it.')
        sub(s, 'Shape settings', first=True)
        f = self.form(s)
        c = field(f, 'Shape')
        ttk.Combobox(c, textvariable=v['mark_kind'], values=list(MARKS), width=14, state='readonly').pack(side='left')
        ttk.Checkbutton(c, text='Filled', variable=v['mark_fill']).pack(side='left', padx=(12, 0))
        mm(field(f, 'Gap from the hole', 'From the edge of the hole to the inside of the shape.'), 'mark_gap')
        mm(field(f, 'Line thickness', 'For an outline. A filled shape has no line.'), 'mark_w')
        mm(field(f, 'Box corners', 'Corner radius of a box. 0 = square corners.'), 'mark_r', note='0 = square')
        bt = ttk.Button(field(f, 'Add'), text='Shape round a hole…', command=self.start_mark); bt.pack(side='left')
        Tip(bt, 'Click this, then click a hole - any hole, from the PCB, the panel file or one you added. Or right-click a hole and '
                'choose Add a shape round it. It gets the settings above; change the one you added below, or drag its edges.')
        self.w_mark_note = ttk.Label(s, text='', style='Dim.TLabel', wraplength=440, justify='left'); self.w_mark_note.pack(anchor='w', pady=(2, 0))
        for k in ('mark_kind', 'mark_fill', 'mark_gap', 'mark_w', 'mark_r'):     # these change the selected shape, if one is
            v[k].trace_add('write', lambda *_: self.mark_vars_changed())
        ttk.Label(s, text='Right-click any hole and choose Add a shape round it. A new shape gets these settings; click a '
                          'shape and these change it.', style='Dim.TLabel', wraplength=440,
                  justify='left').pack(anchor='w', pady=(2, 0))
        sub(s, 'Made for you')
        f = self.form(s)
        c = field(f, 'Rings')
        ttk.Checkbutton(c, text='A ring round every push button', variable=v['art_rings'], command=self.refresh_states).pack(side='left')
        self.w_ringw = mm(field(f, 'Ring thickness', 'How thick the line of the ring is.'), 'ring_width')
        self.w_ringg = mm(field(f, 'Ring gap', 'Between the edge of the button hole and the ring.'), 'ring_gap')
        c = field(f, 'Vertical outputs', "Jacks that come up through the panel and whose label says OUT get a filled box with the "
                                         "label cut out of it. If a jack isn't picked up, right-click it and add a filled box instead.")
        ttk.Checkbutton(c, text='In filled boxes', variable=v['art_outputs']).pack(side='left')
        c = field(f, 'Horizontal jacks', "Jacks lying flat on the PCB at the panel edge (no hole, the plug goes in from the side) "
                                         "get a filled tab hanging from the edge with their labels cut out. Neighbours share a tab; "
                                         "labels with the same first word (MIDI IN, MIDI OUT) become IN / OUT with MIDI underneath.")
        ttk.Checkbutton(c, text='In tabs on the edge', variable=v['art_tabs']).pack(side='left')
        c = field(f, 'Rows', row_tip)
        ttk.Checkbutton(c, text='Buttons', variable=v['art_groups_button']).pack(side='left', padx=(0, 12))
        ttk.Checkbutton(c, text='Jacks', variable=v['art_groups_jack']).pack(side='left')
        self.sel_subs['shapes'] = sub(s, 'Selected')
        self.sel_boxes['shapes'] = ttk.Frame(s); self.sel_boxes['shapes'].pack(fill='x')

        # border
        s = self.section('border', 'Border', 'A line round the panel.', switch='art_border')
        f = self.form(s)
        c = field(f, 'Gap from the edge', 'From the edge of the panel to the border. 0 = automatic: 1.5 mm, or just inside the '
                                          'case holes if there are any.')
        self.w_bgap = mm(c, 'border_gap', note='0 = automatic')
        c = field(f, 'Corner radius', '0 = the border follows the panel corners. Any other value rounds the border corners by that much.')
        self.w_bradius = mm(c, 'border_radius', note='0 = follows the panel')
        for k in STYLE_VARS:                     # changing any of these by hand makes the style 'Custom'
            v[k].trace_add('write', lambda *_: self.style_custom())

        # lines
        s = self.section('lines', 'Lines', 'A divider between sections, an arrow from one jack to the next, a bracket over two controls.')
        f = self.form(s)
        bt = ttk.Button(field(f, 'Add'), text='Line', command=self.start_line); bt.pack(side='left')
        Tip(bt, 'Click this, then click where the line starts and where it ends. It snaps to the middle and edge of holes, to '
                'the ends of other lines and to the panel edges; hold Ctrl to keep it dead level or straight up and down, Alt '
                'to place it freely. Lines are broken round holes. Click a line to change it, drag it to move it, drag an end '
                'to re-aim it.')
        mm(field(f, 'Thickness', 'For the next line you draw - or, with a line selected, that line.'), 'line_w')
        v['line_w'].trace_add('write', lambda *_: self.line_w_changed())
        self.sel_subs['lines'] = sub(s, 'Selected')
        self.sel_boxes['lines'] = ttk.Frame(s); self.sel_boxes['lines'].pack(fill='x')
        self.line_from = None

        # artwork from Inkscape
        s = self.section('art', 'Artwork from Inkscape', 'Your own graphics and text, drawn on a 1:1 copy of the panel.',
                         switch='art_on',
                         tip="Panel Generator makes an Inkscape file of the panel with the cutouts on a locked layer. Draw on its "
                             "'Artwork' layer: black prints, white cuts out of black (for white-on-black text). Inkscape renders "
                             "it, so every font and effect works.")
        h5 = ttk.Frame(s); h5.pack(fill='x')
        det = self.art_detail = ttk.Frame(h5); det.pack(fill='x')
        self.art_status = ttk.Label(det, text='', wraplength=440, justify='left'); self.art_status.pack(anchor='w', pady=(4, 0))
        row = ttk.Frame(det); row.pack(fill='x', pady=(6, 0))
        self.w_art_make = ttk.Button(row, text='Create artwork file', command=self.make_artwork)
        self.w_art_open = ttk.Button(row, text='Open in Inkscape', command=self.open_artwork)
        self.w_art_dir = ttk.Button(row, text='Show folder', command=self.open_folder)
        self.w_art_make.pack(side='left'); self.w_art_open.pack(side='left', padx=6); self.w_art_dir.pack(side='left')
        ttk.Label(det, text="Draw on the 'Artwork' layer, save in Inkscape, and the preview updates by itself.",
                  style='Dim.TLabel', wraplength=440).pack(anchor='w', pady=(4, 0))


        # how to: the tricks for what the generator can't guess, at the bottom of each tab
        for key, items in (('howto_panel', HOW_PANEL), ('howto_art', HOW_ART)):
            s = self.section(key, 'How to…', 'Tricks for what the generator can\'t guess. Click a question to see the answer.')
            for q, a in items:
                self.howto_item(s, q, a)
            row = ttk.Frame(s); row.pack(fill='x', pady=(8, 0))
            ttk.Button(row, text='The full technical guide', command=lambda: __import__('webbrowser').open(TECH_URL)).pack(side='left')

        self.show_selected()
        self.left_end = ttk.Frame(left); self.left_end.pack(fill='x')

        # right: preview + result
        right = ttk.Frame(root); right.grid(row=1, column=2, sticky='nsew')
        root.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=1); right.columnconfigure(0, weight=1)
        ph = ttk.Frame(right); ph.grid(row=0, column=0, sticky='ew')
        ttk.Label(ph, text='Preview', style='Head.TLabel').pack(side='left')
        self.chip = tk.Label(ph, text='', font=self.f_head, padx=8, pady=1); self.chip.pack(side='left', padx=10)
        rb = ttk.Button(ph, text='Refresh', command=self.update_preview); rb.pack(side='right')
        fb = ttk.Button(ph, text='Fit', command=self.fit_view, width=5); fb.pack(side='right', padx=(0, 6))
        self.snap_on = tk.BooleanVar(value=bool(self.cfg.get('snap', True)))
        sb = ttk.Checkbutton(ph, text='Snap', variable=self.snap_on, command=lambda: (self.cfg.__setitem__('snap', self.snap_on.get()), self.save_cfg()))
        sb.pack(side='right', padx=(0, 10))
        Tip(sb, 'When on, things you move or add line up with holes, the middle of parts and other labels as they come near. '
                'Untick for free placement (or hold Alt while dragging). The arrow keys nudge what is selected: 0.1 mm a press, '
                '1 mm with Shift - never snapped.')
        self.w_measure = ttk.Button(ph, text='Measure', command=self.toggle_measure, width=11)
        self.w_measure.pack(side='right', padx=(0, 6))
        Tip(self.w_measure, 'A ruler: click two points in the preview to see how far apart they are. It snaps to the middle '
                            'and edge of holes and to the panel edges (hold Alt for anywhere). Hold Ctrl to keep it dead level or straight up and '
                            'down. After the first click you can type a length instead and press Enter. The ruler then stays as a '
                            'guide: anything you drag, add or paste snaps to its ends and its middle. Press M for a new one.')
        self.w_undo = ttk.Button(ph, text='Undo', command=self.undo, width=6); self.w_undo.pack(side='right', padx=(0, 6))
        rs = ttk.Button(ph, text='Reset', command=self.reset_panel, width=6); rs.pack(side='right', padx=(0, 6))
        Tip(rs, 'Start this panel again from the PCB: the same size as the PCB, with its holes and nothing else. Clears the '
                'labels, artwork, your texts, pictures, lines and extra holes. It asks first, and Undo brings it all back.')
        self.w_undo.state(['disabled'])
        Tip(self.w_undo, 'Take back the last change (Ctrl+Z): a setting on the left, or a move, text, picture, box '
                         'or label edit in the preview. Up to 50 steps.')
        self.bind_all('<Control-z>', self.undo); self.bind_all('<Control-Z>', self.undo)

        Tip(fb, 'Show the whole panel again. Mouse wheel zooms in and out where the pointer is; drag with the right '
                '(or middle) mouse button to move around; double-click also fits.')
        self.zoom_lbl = ttk.Label(ph, text='', style='Dim.TLabel'); self.zoom_lbl.pack(side='right', padx=6)
        Tip(rb, 'The preview updates by itself when you change a setting or save the PCB in KiCad.')
        self.canvas = tk.Canvas(right, bg=C_BG, highlightthickness=1, highlightbackground='#d5dbe1')
        self.canvas.grid(row=1, column=0, sticky='nsew', pady=(6, 0))
        self.canvas.bind('<Configure>', lambda _: self.draw())
        self.view = None                 # (scale px/mm, tx, ty) once you zoom or pan; None = fit to window
        self.clicks, self.drag = {}, None
        pc = self.canvas
        pc.bind('<MouseWheel>', self.wheel_zoom)
        pc.bind('<Button-4>', self.wheel_zoom); pc.bind('<Button-5>', self.wheel_zoom)
        pc.bind('<ButtonPress-1>', self.press); pc.bind('<B1-Motion>', self.motion)
        pc.bind('<ButtonRelease-1>', self.release); pc.bind('<Double-Button-1>', lambda e: self.fit_view())
        for n in (2, 3):                 # right or middle button: drag moves the view, a click opens the menu
            pc.bind(f'<ButtonPress-{n}>', self.pan_press); pc.bind(f'<B{n}-Motion>', self.pan_motion)
            pc.bind(f'<ButtonRelease-{n}>', self.pan_release)
        pc.bind('<Motion>', self.measure_motion)
        self.pan = None
        typing = lambda: isinstance(self.focus_get(), (ttk.Entry, tk.Entry, ttk.Combobox))
        self.bind_all('<Delete>', lambda e: None if typing() else self.delete_selected())
        for key, (ax, ay) in (('Left', (-1, 0)), ('Right', (1, 0)), ('Up', (0, -1)), ('Down', (0, 1))):
            self.bind_all(f'<{key}>', lambda e, ax=ax, ay=ay: None if typing() else self.nudge(e, ax, ay))
        self.bind_all('<Control-d>', lambda e: None if typing() else self.shapes_duplicate())
        for k in ('c', 'C'):
            self.bind_all(f'<Control-{k}>', lambda e: None if typing() else self.copy_selected())
        for k in ('v', 'V'):
            self.bind_all(f'<Control-{k}>', lambda e: None if typing() else self.paste())
        self.clip, self.mouse, self.pasted_at = None, None, None
        self.multi = []                              # several texts, labels, lines or pictures picked at once
        self.bind_all('<Escape>', self.escape)
        self.bind_all('<Key>', self.ruler_key, add='+')
        self.adding = False
        self.hover = ttk.Label(right, text='Hover over a cutout to see what it is.', style='Dim.TLabel')
        self.hover.grid(row=2, column=0, sticky='w', pady=(3, 0))
        self.legend(right).grid(row=2, column=0, sticky='e', pady=(3, 0))

        self.sash(right, 'h').grid(row=3, column=0, sticky='ew', pady=(4, 0))
        go = ttk.Frame(right); go.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        self.go = ttk.Button(go, text='   Generate panel   ', style='Accent.TButton', command=self.generate)
        self.go.pack(side='right', ipady=3)
        gb = ttk.Button(go, text='Make gerbers', command=lambda: self.generate(gerbers=True)); gb.pack(side='right', padx=(0, 8), ipady=3)
        Tip(gb, "Generates the panel, then has KiCad make the gerbers and drill files, zipped ready to upload to the PCB maker, "
                "and runs KiCad's design rule check on it.")
        ttk.Button(go, text='Show folder', command=self.open_folder).pack(side='right', padx=(0, 8))
        b = ttk.Button(go, text='Open in KiCad', command=self.open_saved_panel); b.pack(side='right', padx=(0, 6))
        Tip(b, 'Open the panel as it was last generated. Close it in KiCad before you generate again.')
        st = ttk.Frame(go); st.pack(side='left', fill='x', expand=True)
        self.status = tk.Label(st, text='', anchor='w', font=self.f_head, bg=ttk.Style(self).lookup('TFrame', 'background') or C_BG)
        self.status.pack(anchor='w')
        c = ttk.Checkbutton(st, text='Open in KiCad after generating', variable=v['open']); c.pack(anchor='w')
        ttk.Label(right, text='Result', style='Head.TLabel').grid(row=5, column=0, sticky='w', pady=(8, 4))
        outf = self.result_box = ttk.Frame(right, height=int(self.cfg.get('result_h', 150))); outf.grid(row=6, column=0, sticky='nsew')
        outf.pack_propagate(False)                # its height is what you drag it to
        self.out = tk.Text(outf, height=5, wrap='word', font=('Consolas', 9), relief='flat',
                           highlightthickness=1, highlightbackground='#d5dbe1', padx=8, pady=6)
        sb = ttk.Scrollbar(outf, command=self.out.yview); self.out['yscrollcommand'] = sb.set
        sb.pack(side='right', fill='y'); self.out.pack(fill='both', expand=True)
        for tag, colour in (('ERROR', C_ERR_TXT), ('WARN', C_WARN_TXT), ('CHECK', C_WARN_TXT), ('NOTE', '#777777'),
                            ('ok', C_OK_TXT), ('head', '#000000'), ('dim', '#888888')):
            self.out.tag_configure(tag, foreground=colour)
        self.out.tag_configure('head', font=('Consolas', 9, 'bold'))
        self.out.tag_configure('fold', foreground='#2563eb', underline=True)
        self.out.tag_bind('fold', '<Button-1>', lambda e: self.toggle_notes())
        self.out.tag_bind('fold', '<Enter>', lambda e: self.out.config(cursor='hand2'))
        self.out.tag_bind('fold', '<Leave>', lambda e: self.out.config(cursor=''))
        self.notes_open, self.last_parts = False, []
        self.out.configure(state='disabled')
        self.renumber()

    def sash(self, parent, way):
        """A bar you drag to give the preview more room: 'v' between the settings and the preview, 'h' above the buttons
        and the Result box."""
        bar = tk.Frame(parent, width=10 if way == 'v' else 1, height=1 if way == 'v' else 8,
                       cursor='sb_h_double_arrow' if way == 'v' else 'sb_v_double_arrow',
                       bg=ttk.Style(self).lookup('TFrame', 'background') or C_BG)
        grip = tk.Frame(bar, bg='#c3cad3', cursor=bar['cursor'])
        grip.place(relx=0.5, rely=0.5, anchor='center', **(dict(width=3, relheight=0.12) if way == 'v' else dict(height=3, relwidth=0.08)))
        Tip(bar, 'Drag to give the preview more room, or the settings.' if way == 'v' else
                 'Drag to give the preview more room, or the Result box.')
        def start(e):
            bar._from = (e.x_root, e.y_root, self.left_col.winfo_width(), self.result_box.winfo_height())
        def move(e):
            x0, y0, w0, h0 = bar._from
            if way == 'v':
                w = max(260, min(self.winfo_width() - 320, w0 + e.x_root - x0))
                self.left_col.configure(width=w); self.cfg['left_w'] = w
            else:
                h = max(0, min(self.winfo_height() - 320, h0 - (e.y_root - y0)))
                self.result_box.configure(height=h); self.cfg['result_h'] = h
        for w in (bar, grip):
            w.bind('<ButtonPress-1>', start); w.bind('<B1-Motion>', move)
            w.bind('<ButtonRelease-1>', lambda e: self.save_cfg())
            w.bind('<Enter>', lambda e: grip.config(bg='#2563eb')); w.bind('<Leave>', lambda e: grip.config(bg='#c3cad3'))
        return bar

    LABEL_W = 150            # every setting's name sits in a column this wide, so the boxes line up

    def section(self, key, title, sub, parent=None, switch=None, tip=None, fold=True):
        """A card: a heading you can click to fold it away, an on/off switch if the whole thing is optional, and a body."""
        f = ttk.Frame(parent or self.left, style='Card.TFrame', padding=(12, 8))
        if parent is not None:
            f.pack(fill='x', pady=(0, 4))
        h = ttk.Frame(f); h.pack(fill='x')
        chev = ttk.Label(h, text='', style='Chev.TLabel', width=2)
        t = ttk.Label(h, text=title, style='Head.TLabel')
        if fold:
            chev.pack(side='left')
        t.pack(side='left')
        if switch:
            sw = ttk.Checkbutton(h, variable=self.vars[switch], command=lambda: self.switched(key, switch),
                                 style='Switch.TCheckbutton' if self.themed else 'TCheckbutton')
            sw.pack(side='right')
            self.switches[key] = switch
            if tip:
                Tip(sw, tip)
        holder = ttk.Frame(f); holder.pack(fill='x')
        body = ttk.Frame(holder); body.pack(fill='x', pady=(4, 2))
        if sub:
            ttk.Label(body, text=sub, style='Dim.TLabel', wraplength=440, justify='left').pack(anchor='w', pady=(0, 6))
        self.sections[key] = (f, chev, holder)
        if fold:
            for w in (chev, t, h):
                w.bind('<Button-1>', lambda e, k=key: self.fold(k))
                w.configure(cursor='hand2')
        return body

    def fold(self, key, to=None):
        """Fold a section away to its heading, or open it again."""
        shut = (key not in self.collapsed) if to is None else to
        (self.collapsed.add if shut else self.collapsed.discard)(key)
        self.cfg['collapsed'] = sorted(self.collapsed)
        self.save_cfg()
        self.show_folds()

    def switched(self, key, var):
        if self.vars[var].get():
            self.collapsed.discard(key)          # switching something on opens it
        self.refresh_states()

    def show_folds(self):
        for key, (f, chev, body) in self.sections.items():
            # an optional section that's switched off has nothing to show: it reads as shut
            off = key in self.switches and key != 'extras' and not self.vars[self.switches[key]].get()   # (pictures: Add stays in reach)
            shut = key in self.collapsed or off
            chev.config(text='▸' if shut else '▾')
            if shut and body.winfo_manager():          # (an empty frame keeps its old height, so the holder itself goes)
                body.pack_forget()
            elif not shut and not body.winfo_manager():
                body.pack(fill='x')

    def howto_item(self, parent, q, a):
        """A question you click to show (or hide) its answer."""
        f = ttk.Frame(parent); f.pack(fill='x', pady=(2, 0))
        head = ttk.Label(f, text='▸  ' + q, cursor='hand2', foreground='#2563eb')
        head.pack(anchor='w')
        ans = ttk.Label(f, text=a, wraplength=420, justify='left', style='Dim.TLabel')
        def flip(_=None):
            if ans.winfo_manager():
                ans.pack_forget(); head.config(text='▸  ' + q)
            else:
                ans.pack(anchor='w', padx=(18, 0), pady=(2, 6)); head.config(text='▾  ' + q)
        head.bind('<Button-1>', flip)

    def form(self, parent):
        """A block of settings: names down the left, their boxes lined up down the right."""
        f = ttk.Frame(parent); f.pack(fill='x')
        f.columnconfigure(0, minsize=self.LABEL_W)
        f._rows = 0
        return f

    def field(self, form, label, tip=None):
        l = ttk.Label(form, text=label); l.grid(row=form._rows, column=0, sticky='w', pady=3)
        cell = ttk.Frame(form); cell.grid(row=form._rows, column=1, sticky='w', pady=3)
        form._rows += 1
        if tip:
            Tip(l, tip)
        return cell

    def sub(self, parent, text, first=False):
        """A small heading inside a section."""
        f = ttk.Frame(parent); f.pack(fill='x', pady=(2 if first else 10, 2))
        ttk.Label(f, text=text.upper(), style='Sub.TLabel').pack(side='left')
        ttk.Separator(f).pack(side='left', fill='x', expand=True, padx=(8, 0))
        return f

    def mm(self, cell, key, note=None):
        e = ttk.Entry(cell, textvariable=self.vars[key], width=7); e.pack(side='left')
        ttk.Label(cell, text='mm').pack(side='left', padx=(4, 0))
        if note:
            ttk.Label(cell, text=note, style='Dim.TLabel').pack(side='left', padx=(10, 0))
        return e

    TABS = {'panel': ('size', 'rail', 'case', 'holes', 'restore', 'howto_panel'),
            'art': ('style', 'title', 'labels', 'pots', 'shapes', 'border', 'lines', 'extras', 'art', 'howto_art')}

    def show_tab(self, tab):
        if tab != self.tab:
            self.tab = tab
            self.left.master.yview_moveto(0)
        self.renumber()

    def renumber(self):
        """Show the sections of the tab you're on that apply to this kind of panel."""
        hide = {'size', 'case'} if self.mode == 'eurorack' else {'rail'}
        if getattr(self, '_laid', None) == (self.tab, self.mode):
            return self.show_folds()
        self._laid = (self.tab, self.mode)
        for k, (f, _, _) in self.sections.items():
            if k != 'pcb':
                f.pack_forget()
        for k in self.TABS[self.tab]:
            if k not in hide:
                self.sections[k][0].pack(fill='x', pady=(0, 7), before=self.left_end)
        for k, bt in self.tab_btn.items():
            bt.configure(style='Accent.TButton' if k == self.tab else 'TButton')
        self.show_folds()

    def num(self, parent, key, grid=None):
        e = ttk.Entry(parent, textvariable=self.vars[key], width=6)
        if grid:
            e.grid(row=grid[0], column=grid[1], padx=4)
        else:
            e.pack(side='left', padx=4)
        return e

    def legend(self, parent):
        f = ttk.Frame(parent)
        for colour, fill, txt, dash in ((C_PANEL_EDGE, C_PANEL, 'panel', None), (C_PCB, '', 'PCB', (4, 2)),
                                        (C_WARN, '', 'no cutout?', (3, 2)), ('#58a6ff', '', 'marker', (3, 2)),
                                        (C_WARN, C_WARN_FILL, 'too thin', None),
                                        (C_ERR, C_ERR_FILL, 'problem', None)):
            c = tk.Canvas(f, width=16, height=12, highlightthickness=0, bg=ttk.Style(self).lookup('TFrame', 'background') or C_BG)
            c.create_rectangle(2, 2, 14, 10, outline=colour, fill=fill, width=2, dash=dash)
            c.pack(side='left', padx=(10, 3))
            ttk.Label(f, text=txt, style='Dim.TLabel').pack(side='left')
        return f

    # ------------------------------------------------------------------ states
    def refresh_states(self):
        v = self.vars
        def en(w, on):
            w.state(['!disabled'] if on else ['disabled'])
        self.show(self.sides_row, v['per_side'].get(), fill='x')
        self.show(self.case_detail, v['screws'].get() != 'none', fill='x')
        self.show(self.label_detail, v['labels_on'].get(), fill='x')
        self.show(self.art_detail, v['art_on'].get(), fill='x')
        en(self.w_bradius, v['art_border'].get()); en(self.w_bgap, v['art_border'].get())
        en(self.w_ringw, v['art_rings'].get()); en(self.w_ringg, v['art_rings'].get())
        self.art_state()
        en(self.w_margin, not v['per_side'].get())
        self.show_folds()
        on = v['screws'].get() != 'none'
        for w in (self.w_dia, self.w_inset, self.w_cround, self.w_cslot):
            en(w, on)
        en(self.w_slot, on and v['case_shape'].get() == 'slot')
        en(self.w_rslot, v['rail_shape'].get() == 'slot')
        self.show_edge()

    # ------------------------------------------------------------------ artwork
    def art_file(self):
        b = self.board.get()
        return self.pg.artwork_path_for(panel_paths(b)[0]) if b else None

    def art_state(self):
        f = self.art_file()
        if not f:
            self.art_status.config(text=''); return
        ink = self.pg.find_inkscape()
        if os.path.exists(f):
            import time
            when = time.strftime('%d %b %H:%M', time.localtime(mtime(f)))
            txt = f"{os.path.basename(f)}  ·  last saved {when}"
            self.w_art_make.pack_forget()
            if not self.w_art_open.winfo_manager():
                self.w_art_open.pack(side='left', padx=(0, 6), before=self.w_art_dir)
        else:
            txt = "No artwork file yet - click Create artwork file."
            if not self.w_art_make.winfo_manager():
                self.w_art_make.pack(side='left', padx=(0, 6), before=self.w_art_dir)
            self.w_art_open.pack_forget()
        if self.guides_at and os.path.exists(f):
            txt += (f"\n⟳ Guides updated {self.guides_at} (the PCB or a setting changed). If the file is open in Inkscape: "
                    "save your artwork, then File → Revert to see them.")
        if not ink:
            txt += "\nInkscape wasn't found - install it from inkscape.org (it's needed to read the artwork)."
        self.art_status.config(text=txt)

    def make_artwork(self):
        try:
            args = self.build_args()
        except ValueError as e:
            messagebox.showerror('Panel Generator', str(e)); return
        self.config(cursor='watch'); self.update()
        try:
            code, text = self.run_engine(args + ['--make-artwork-file'], preview={})
        finally:
            self.config(cursor='')
        self.art_state()
        if os.path.exists(self.art_file() or ''):
            self.open_artwork()
        else:
            messagebox.showerror('Panel Generator', "Couldn't make the artwork file:\n\n" + text[-600:])

    def open_artwork(self):
        f = self.art_file()
        ink = self.pg.find_inkscape()
        try:
            if ink:
                gui_exe = ink[:-4] + '.exe' if ink.lower().endswith('.com') else ink
                subprocess.Popen([gui_exe, f])
            elif hasattr(os, 'startfile'):
                os.startfile(f)
        except OSError as e:
            messagebox.showerror('Panel Generator', f"Couldn't open Inkscape ({e}). Open {f} yourself.")

    def open_folder(self):
        d = os.path.dirname(panel_paths(self.board.get())[0]) if self.board.get() else None
        if d and os.path.isdir(d) and hasattr(os, 'startfile'):
            os.startfile(d)
        elif d:
            messagebox.showinfo('Panel Generator', f"The panel folder is:\n{d}" + ('' if os.path.isdir(d) else '\n(not made yet)'))

    def style_list(self):
        mine = self.cfg.get('my_style')
        self.w_style['values'] = list(ART_STYLES) + ([MY_STYLE] if mine else []) + ['Custom']
        self.w_style_note.config(text=('"My style" is saved: new PCBs start with it, and it is in the Style list.' if mine else
                                       'Nothing saved yet.'))

    def save_my_style(self):
        v = self.vars
        self.cfg['my_style'] = {k: v[k].get() for k in STYLE_VARS}
        self.save_cfg()
        self.loading_style = True
        v['art_style'].set(MY_STYLE)
        self.loading_style = False
        self.style_list()
        self.hover.config(text='Saved as "My style". New PCBs will start with this look.')

    def use_my_style(self):
        mine = self.cfg.get('my_style')
        if not mine:
            return False
        self.applying_style = True
        try:
            for k, x in mine.items():
                if k in self.vars and k in STYLE_VARS:
                    self.vars[k].set(x)
            self.vars['art_style'].set(MY_STYLE)
        finally:
            self.applying_style = False
        return True

    def apply_style(self):
        if self.vars['art_style'].get() == MY_STYLE:
            self.use_my_style()
            return self.refresh_states()
        st = ART_STYLES.get(self.vars['art_style'].get())
        if not st:
            return
        self.applying_style = True
        try:
            v = self.vars
            v['art_scale'].set(st['scale']); v['art_rings'].set(st['rings'])
            v['art_outputs'].set(st['outputs']); v['art_border'].set(st['border'])
            for k in GROUP_KINDS:
                v['art_groups_' + k].set(st['groups'])
            v['art_tabs'].set(st['tabs'])
        finally:
            self.applying_style = False
        self.refresh_states()

    def style_custom(self):
        """Changing a single item by hand makes the style 'Custom'."""
        if getattr(self, 'applying_style', False) or self.loading:
            return
        v = self.vars
        if v['art_style'].get() == MY_STYLE:           # changed away from what was saved
            mine = self.cfg.get('my_style') or {}
            if any(k in mine and v[k].get() != mine[k] for k in STYLE_VARS):
                v['art_style'].set('Custom')
            return
        st = ART_STYLES.get(self.vars['art_style'].get())
        now = tuple(v['art_' + k].get() for k in STYLE_KEYS) + tuple(v['art_groups_' + k].get() for k in GROUP_KINDS)
        if st and now != tuple(st[k] for k in STYLE_KEYS) + (st['groups'],) * len(GROUP_KINDS):
            v['art_style'].set('Custom')

    def show(self, w, on, **pack):
        if on and not w.winfo_manager():
            w.pack(**pack)
        elif not on:
            w.pack_forget()

    def show_edge(self):
        """Live readout of how much panel is left between a case hole and the edge."""
        v = self.vars
        if v['screws'].get() == 'none':
            self.edge_info.config(text=''); return
        try:
            d, i = float(v['screw_dia'].get()), float(v['screw_inset'].get())
            L = float(v['slot'].get()) if v['case_shape'].get() == 'slot' else 0.0
        except ValueError:
            self.edge_info.config(text=''); return
        if v['case_shape'].get() == 'slot' and L <= d:
            self.edge_info.config(text=f'Slot length must be longer than the {d:g} mm hole', fg=C_ERR_TXT); return
        edge = i - d / 2
        if edge < 0:
            txt, col = 'The hole would cut through the panel edge', C_ERR_TXT
        elif edge < d - 1e-6:
            txt, col = (f'{edge:.2f} mm of panel between hole and edge - thin, may crack. '
                        f'Aim for {d:g} mm (edge to centre {1.5 * d:g}+)'), C_WARN_TXT
        else:
            txt, col = f'{edge:.2f} mm of panel between hole and edge', C_DIM
        self.edge_info.config(text=txt, fg=col)

    def settings_changed(self):
        if self.loading:
            return
        self.result_is_preview = True
        if self.after_id:
            self.after_cancel(self.after_id)
        self.after_id = self.after(350, self.update_preview)

    # ------------------------------------------------------------------ board + saved settings
    def browse(self):
        start = os.path.dirname(self.board.get()) if self.board.get() else os.path.expanduser('~')
        f = filedialog.askopenfilename(title='Choose the synth PCB', initialdir=start,
                                       filetypes=[('KiCad PCB', '*.kicad_pcb')])
        if f:
            if f.endswith('_panel.kicad_pcb'):
                messagebox.showwarning('Panel Generator', 'That looks like a panel. Choose the PCB it was made from.')
                return
            self.board.set(os.path.normpath(f))
            self.board_changed()

    def recent(self):
        return [b for b in self.cfg.get('recent', []) if os.path.exists(b)]

    @staticmethod
    def board_label(path):
        d = os.path.dirname(path)
        return f"{os.path.splitext(os.path.basename(path))[0]}   ({os.path.basename(d)})"

    def show_boards(self):
        b = self.board.get()
        if b and os.path.exists(b):
            rec = [os.path.normpath(b)] + [r for r in self.recent() if os.path.normpath(r) != os.path.normpath(b)]
            self.cfg['recent'] = rec[:10]
            self.save_cfg()
        self.board_box['values'] = [self.board_label(r) for r in self.recent()]
        self.board_name.set(self.board_label(b) if b else 'Choose your PCB with Browse…')
        self.board_tip.text = b or ''

    def pick_recent(self, _=None):
        i = self.board_box.current()
        rec = self.recent()
        if 0 <= i < len(rec) and rec[i] != self.board.get():
            self.board.set(rec[i]); self.board_changed()

    def set_vars(self, s):
        """Every setting on the left, from a panel's saved settings (or the bare defaults)."""
        v = self.vars
        sides = [s['margin_top'], s['margin_right'], s['margin_bottom'], s['margin_left']]
        v['per_side'].set(len(set(sides)) > 1)
        v['margin'].set(f"{max(sides):g}")
        for name, val in zip(('top', 'right', 'bottom', 'left'), sides):
            v[name].set(f"{val:g}")
        v['screws'].set(s['screws'])
        v['screw_dia'].set(f"{s['screw_dia']:g}"); v['screw_inset'].set(f"{s['screw_inset']:g}")
        v['case_shape'].set('slot' if s['screw_slot'] > 0 else 'round')
        if s['screw_slot'] > 0:
            v['slot'].set(f"{s['screw_slot']:g}")
        v['rail_shape'].set('slot' if s['rail_slot'] > 0 else 'round')
        if s['rail_slot'] > 0:
            v['rslot'].set(f"{s['rail_slot']:g}")
        v['radius'].set(f"{s['corner_radius']:g}")
        v['svg'].set(bool(s['svg']))
        v['art_on'].set(s['artwork'] == 'on')
        v['labels_on'].set(s['labels'] == 'on')
        v['texts_on'].set(s.get('extras', 'on') in ('on', 'texts')); v['pictures_on'].set(s.get('extras', 'on') in ('on', 'pictures'))
        v['art_style'].set(s.get('art_style') or 'Custom')
        v['art_scale'].set(next((k for k, x in SCALES.items() if x == s['art_scale']), 'Ticks'))
        v['art_rings'].set(s['art_rings'] == 'on'); v['art_outputs'].set(s['art_outputs'] == 'on')
        v['art_border'].set(s['art_border'] == 'on')
        kinds = GROUP_KINDS if s['art_groups'] == 'on' else [k for k in str(s['art_groups']).split(',')]
        for k in GROUP_KINDS:
            v['art_groups_' + k].set(k in kinds)
        v['art_tabs'].set(s['art_tabs'] == 'on')
        v['border_radius'].set(f"{s['art_border_radius']:g}"); v['border_gap'].set(f"{s['art_border_gap']:g}")
        v['ring_width'].set(f"{s['ring_width']:g}"); v['ring_gap'].set(f"{s['ring_gap']:g}")
        v['art_title'].set(s['art_title']); v['art_maker'].set(s['art_maker'])
        v['title_size'].set(f"{s['title_size']:g}"); v['knob_size'].set(f"{s['knob_size']:g}")
        v['title_dir'].set(next((k for k, x in TITLE_DIRS.items() if x == s.get('title_vertical', 'off')), 'Across'))
        v['title_mirror'].set(s.get('title_mirror', 'off') == 'on')
        if s['auto_art'] != 'on':            # made artwork was switched off as a whole: that's every part of it off now
            v['art_style'].set('None'); self.apply_style()
            v['art_title'].set(''); v['art_maker'].set('')
        v['label_pos'].set(s['label_pos']); v['label_gap'].set(f"{s['label_gap']:g}"); v['label_size'].set(f"{s['label_size']:g}")
        v['label_font'].set(s['label_font'] or KICAD_FONT)
        v['label_bold'].set(s['label_bold'] == 'on'); v['label_caps'].set(s['label_caps'] == 'on')

    def reset_panel(self):
        """Back to the bare panel: the PCB's own shape and holes, nothing added. Undo brings it all back."""
        b = self.board.get()
        if not b or not os.path.exists(b) or not self.pv:
            return
        if not messagebox.askyesno('Start this panel again?',
                                   "This takes the panel back to how it comes from your PCB: the same size as the PCB, with its "
                                   "holes and nothing else.\n\n"
                                   "It clears the extra size, corners and case holes, the labels and changes to them, your texts, "
                                   "pictures, lines, shapes and extra holes, the title, scales, rings, boxes and border, and switches "
                                   "Inkscape artwork off (your Inkscape file is not deleted).\n\n"
                                   "It also leaves out everything you placed or changed in the panel file in KiCad: jacks, screws "
                                   "and other panel parts, cutouts drawn on Edge.Cuts, and holes you moved, resized or deleted.\n\n"
                                   "Your PCB is not touched. Nothing changes in KiCad until you click Generate panel, and then the "
                                   "old panel file is kept as a backup. Undo brings everything back.\n\nStart again?", icon='warning', parent=self):
            return
        self.record_state()
        self.end_measure()
        self.loading = True
        try:
            self.set_vars(dict(DEFAULTS))
            self.ui = {'ignore': self.ui.get('ignore', {}), 'label_edits': {}, 'texts': [], 'art_pos': {}, 'images': [],
                       'shapes': [], 'lines': [], 'titles': [], 'marks': [], 'bodies': [],   # parts you said need no hole stay that way
                       'fresh': True}       # and the panel file in KiCad is left out: its hand-placed parts, drawn cutouts, edits
        finally:
            self.loading = False
        self.sel, self.shape_sel, self.view = None, [], None
        self.persist_ui()
        self.refresh_states()
        self.update_preview()
        self.hover.config(text='Started again from the PCB. Undo brings everything back.')

    def board_changed(self):
        board = self.board.get()
        self.guides_at = None
        if getattr(self, 'measure', None) or getattr(self, 'measuring', False):
            self.end_measure()                 # a ruler belongs to the board it was drawn on
        self.show_boards()
        if not board or not os.path.exists(board):
            self.mode = None; self.renumber(); self.update_preview(); return
        _, mem_path = panel_paths(board)
        mem = load_json(mem_path)
        s = dict(DEFAULTS, **mem.get('settings', {}))
        v = self.vars
        self.loading = True
        try:
            self.set_vars(s)
            if not mem.get('settings'):          # a PCB you haven't made a panel for yet starts with your own look
                self.use_my_style()
            self.ui = {'ignore': dict(mem.get('ignore_uncut', {})), 'label_edits': dict(mem.get('label_edits', {})),
                       'texts': [dict(t) for t in mem.get('texts', [])], 'art_pos': dict(mem.get('art_pos', {})),
                       'images': [dict(i) for i in mem.get('images', [])],
                       'shapes': [dict(i) for i in mem.get('shapes', [])],
                       'lines': [dict(i) for i in mem.get('lines', [])],
                       'marks': [dict(i) for i in mem.get('marks', [])],
                       'bodies': [dict(i) for i in mem.get('bodies', [])],
                       'titles': [dict(i) for i in mem.get('titles', [])]}
            self.reset_undo()
        finally:
            self.loading = False
        self.refresh_states()
        self.fill_restore(mem)
        self.result_is_preview = True
        self.view = None
        self.update_preview()

    def fill_restore(self, mem=None):
        if mem is None:
            mem = load_json(panel_paths(self.board.get())[1]) if self.board.get() else {}
        self.restore_list.delete(0, 'end')
        self.restore_refs = []
        if self.ui.get('fresh'):                       # started again: nothing from the old panel file to bring back
            return
        for v in mem.get('suppressed', {}).values():
            self.restore_list.insert('end', f"{v['ref']}  - deleted"); self.restore_refs.append(('hole', v['ref']))
        for v in mem.get('kept', {}).values():
            self.restore_list.insert('end', f"{v['ref']}  - resized/moved by you"); self.restore_refs.append(('hole', v['ref']))
        for fid, ref in self.ui.get('ignore', {}).items():
            self.restore_list.insert('end', f"{ref}  - no cutout needed (not warned about)"); self.restore_refs.append(('ignore', fid))
        if not self.restore_refs:
            self.restore_list.insert('end', '(none)')
        self.restore_list.config(height=min(max(len(self.restore_refs), 2), 6))

    def watch_files(self):
        """Refresh the preview when the PCB is saved in KiCad, or the panel changes."""
        b = self.board.get()
        if b and os.path.exists(b):
            stamp = (mtime(b), mtime(panel_paths(b)[0]), mtime(self.art_file()))
            if self.stamp is not None and stamp != self.stamp:
                self.fill_restore()
                self.art_state()
                self.update_preview()
            self.stamp = stamp
        self.after(1500, self.watch_files)

    # ------------------------------------------------------------------ run
    def number(self, key, label):
        try:
            x = float(self.vars[key].get().strip())
        except ValueError:
            raise ValueError(f"'{self.vars[key].get()}' isn't a number ({label})")
        if x < 0:
            raise ValueError(f"{label} can't be negative")
        return x

    def build_args(self, restore=()):
        v = self.vars
        board = self.board.get().strip().strip('"')
        if not board:
            raise ValueError('Choose your PCB first (Browse…)')
        if not os.path.exists(board):
            raise ValueError(f"Can't find {board}")
        args = [board]
        if self.mode == 'eurorack':      # size and holes are standard
            args += ['--margin', '0', '--screws', 'none',
                     '--rail-slot', f"{self.number('rslot', 'rail slot length'):g}" if v['rail_shape'].get() == 'slot' else '0']
        else:
            if v['per_side'].get():
                for s in ('top', 'right', 'bottom', 'left'):
                    args += [f'--margin-{s}', f"{self.number(s, s + ' margin'):g}"]
                args += ['--margin', '0']
            else:
                args += ['--margin', f"{self.number('margin', 'extra round the PCB'):g}"]
            if v['screws'].get() != 'none':
                args += ['--screws', v['screws'].get(),
                         '--screw-dia', f"{self.number('screw_dia', 'case hole size'):g}",
                         '--screw-inset', f"{self.number('screw_inset', 'edge to hole centre'):g}",
                         '--screw-slot', f"{self.number('slot', 'slot length'):g}" if v['case_shape'].get() == 'slot' else '0']
            else:
                args += ['--screws', 'none']
            args += ['--corner-radius', f"{self.number('radius', 'corner radius'):g}"]
        args += ['--grow', '0']
        size = self.number('label_size', 'label text size')          # your own texts use these too
        if size < 0.5:
            raise ValueError('Label text size must be at least 0.5 mm (1 mm or more is safer for silkscreen)')
        font = v['label_font'].get()
        args += ['--labels', 'on' if v['labels_on'].get() else 'off', '--label-size', f'{size:g}',
                 '--label-gap', f"{self.number('label_gap', 'label gap'):g}",
                 '--label-pos', v['label_pos'].get(), '--label-font', '' if font == KICAD_FONT else font,
                 '--label-bold', 'on' if v['label_bold'].get() else 'off', '--label-caps', 'on' if v['label_caps'].get() else 'off']
        args += ['--extras', {(True, True): 'on', (True, False): 'texts', (False, True): 'pictures',
                              (False, False): 'off'}[(v['texts_on'].get(), v['pictures_on'].get())]]
        groups = [k for k in GROUP_KINDS if v['art_groups_' + k].get()]
        if (v['art_title'].get().strip() or v['art_maker'].get().strip() or SCALES[v['art_scale'].get()] != 'none' or groups
                or any(v[k].get() for k in ('art_rings', 'art_outputs', 'art_border', 'art_tabs'))):
            ts, ks = self.number('title_size', 'title size'), self.number('knob_size', 'knob size')
            if ts < 1:
                raise ValueError('Title size must be at least 1 mm')
            if ks < 3:
                raise ValueError('Knob size is the knob diameter in mm (13 is typical for small synth knobs)')
            args += ['--auto-art', 'on', '--art-style', v['art_style'].get(), '--art-scale', SCALES[v['art_scale'].get()],
                     '--art-rings', 'on' if v['art_rings'].get() else 'off',
                     '--art-outputs', 'on' if v['art_outputs'].get() else 'off',
                     '--art-border', 'on' if v['art_border'].get() else 'off',
                     '--art-border-radius', f"{self.number('border_radius', 'border corner radius'):g}" if v['art_border'].get() else '0',
                     '--art-border-gap', f"{self.number('border_gap', 'border gap from the edge'):g}" if v['art_border'].get() else '0',
                     '--ring-width', f"{max(0.15, self.number('ring_width', 'ring thickness')):g}",
                     '--ring-gap', f"{self.number('ring_gap', 'ring gap'):g}",
                     '--art-groups', ','.join(groups) or 'off', '--art-tabs', 'on' if v['art_tabs'].get() else 'off',
                     '--art-title', v['art_title'].get(), '--art-maker', v['art_maker'].get(),
                     '--title-size', f'{ts:g}', '--knob-size', f'{ks:g}',
                     '--title-vertical', TITLE_DIRS.get(v['title_dir'].get(), 'off'),
                     '--title-mirror', 'on' if v['title_mirror'].get() else 'off']
        else:
            args += ['--auto-art', 'off']
        args += ['--artwork', 'on' if v['art_on'].get() else 'off']
        args += ['--ui-state', json.dumps(self.ui)]
        for r in restore:
            args += ['--restore', r]
        return args

    def run_engine(self, args, preview=None):
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                code = self.pg.main(args, preview=preview)
        except ImportError as e:
            code = 2
            buf.write(f"ERROR panelgen needs the 'shapely' package. In Command Prompt run:\n    py -m pip install shapely\n({e})\n")
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 2
            if not isinstance(e.code, int) and e.code:
                buf.write(f"ERROR {e.code}\n")
        except Exception:
            code = 2
            buf.write('ERROR panelgen crashed - please send this to whoever looks after it:\n' + traceback.format_exc())
        return code, buf.getvalue()

    def update_preview(self):
        self.after_id = None
        self.record_state()
        try:
            args = self.build_args()
        except ValueError as e:
            self.pv = {'message': str(e)}
            self.draw(); self.set_chip(None); return
        pv = {}
        self.config(cursor='watch'); self.update_idletasks()
        try:
            code, text = self.run_engine(args, preview=pv)
        finally:
            self.config(cursor='')
        if not pv:
            self.pv = {'message': (text.strip().splitlines() or ["Couldn't read the PCB"])[-1]}
            self.draw(); self.set_chip(None)
            if self.result_is_preview:
                self.show_result(text, [], 2, preview=True)
            return
        self.pv = pv
        self.save_settings(pv.get('settings'))
        self.note_guides(pv['log'])
        if 'label_edits' in pv:
            self.ui['label_edits'] = dict(pv['label_edits'])
        new_mode = 'eurorack' if pv['eurorack'] else 'fit'
        if new_mode != self.mode:
            self.mode = new_mode
            self.renumber()
            return self.update_preview()    # the settings that apply differ per mode: build the args again
        x1, y1, x2, y2 = pv['panel_box']
        if pv['eurorack']:
            self.mode_lbl.config(text=f"Eurorack {pv['eurorack']}HP panel  ·  {x2 - x1:g} × {y2 - y1:g} mm")
            self.mode_hint.config(text='Found a Eurorack template on the PCB, so the panel size and rail holes are standard.')
        else:
            p = pv['pcb_box']
            self.mode_lbl.config(text=f"Panel fitted to your PCB  ·  {x2 - x1:.1f} × {y2 - y1:.1f} mm")
            self.mode_hint.config(text=f"PCB {p[2] - p[0]:.1f} × {p[3] - p[1]:.1f} mm")
        self.set_chip(pv)
        self.show_status()
        self.draw()
        self.show_selected(); self.show_shapes()
        if self.editor and self.editor.winfo_exists():
            self.editor.refresh()
        if self.result_is_preview:
            self.show_result('\n'.join(pv['log']), [], code, preview=True)

    def note_guides(self, lines):
        """The engine updated the guide layers in the artwork file: say so, and don't treat that save as a change."""
        if any(l.strip().startswith('art   updated') for l in lines):
            import time
            self.guides_at = time.strftime('%H:%M')
            b = self.board.get()
            if b:
                self.stamp = (mtime(b), mtime(panel_paths(b)[0]), mtime(self.art_file()))
            self.art_state()

    def set_chip(self, pv):
        if not pv:
            self.chip.config(text='', bg=self.cget('bg')); return
        errs = sum(1 for l in pv['log'] if l.startswith('ERROR'))
        warns = sum(1 for l in pv['log'] if l.startswith('WARN'))
        uncut = len(pv.get('uncut', []))
        if errs:
            self.chip.config(text=f" {errs} problem{'s' if errs > 1 else ''} ", bg=C_ERR_FILL, fg=C_ERR_TXT)
        elif warns or uncut:
            bits = ([f"{warns} warning{'s' if warns > 1 else ''}"] if warns else []) + \
                   ([f"{uncut} part{'s' if uncut > 1 else ''} with no cutout"] if uncut else [])
            self.chip.config(text=' ' + ' · '.join(bits) + ' ', bg=C_WARN_FILL, fg=C_WARN_TXT)
        else:
            self.chip.config(text=' No problems ', bg='#d4f0dc', fg=C_OK_TXT)

    # ------------------------------------------------------------------ preview drawing
    def draw(self):
        c = self.canvas
        c.delete('all')
        W, H = c.winfo_width(), c.winfo_height()
        pv = self.pv
        if not pv or 'message' in pv:
            msg = pv['message'] if pv else 'Choose your PCB to see the panel here.'
            c.create_text(W / 2, H / 2, text=msg, fill=C_DIM, width=W - 60, font=self.f_head)
            return
        x1, y1, x2, y2 = pv['panel_box']
        m = 40
        fit = min((W - 2 * m) / max(x2 - x1, 1), (H - 2 * m - 16) / max(y2 - y1, 1))
        self.fit_scale = fit
        if self.view:
            sc, ox, oy = self.view
        else:
            sc = fit
            ox, oy = (W - (x2 - x1) * sc) / 2 - x1 * sc, (H - 16 - (y2 - y1) * sc) / 2 - y1 * sc
        self.cur_view = (sc, ox, oy)
        self.zoom_lbl.config(text=f'{sc / fit * 100:.0f}%' if self.view else '')
        self.clicks = {}
        X = lambda x: ox + x * sc
        Y = lambda y: oy + y * sc
        def poly(geom, **kw):
            ids = []
            for p in (geom.geoms if hasattr(geom, 'geoms') else [geom]):
                pts = [v for x, y in p.exterior.coords for v in (X(x), Y(y))]
                if len(pts) >= 6:
                    ids.append(c.create_polygon(pts, **kw))
            return ids
        poly(pv['outline'], fill=C_PANEL, outline=C_PANEL_EDGE, width=2)
        if pv['eurorack']:
            r = pv['rail']
            for a, b in ((y1, y1 + r), (y2 - r, y2)):
                c.create_rectangle(X(x1), Y(a), X(x2), Y(b), fill=C_RAIL, stipple='gray25', outline='')
            c.create_text(X((x1 + x2) / 2), Y(y1 + r / 2), text='RAIL', fill='#dfe5ea', font=self.f_small)
            c.create_text(X((x1 + x2) / 2), Y(y2 - r / 2), text='RAIL', fill='#dfe5ea', font=self.f_small)
        for g in pv.get('artwork', []):
            pts = [v for x, y in g.exterior.coords for v in (X(x), Y(y))]
            if len(pts) >= 6:
                c.create_polygon(pts, fill='#ffffff', outline='')
        for mk in pv.get('markers', []):          # parts with no cutout (edge jacks...) and User.2 drawings: guides only
            for p in (mk['geom'].geoms if hasattr(mk['geom'], 'geoms') else [mk['geom']]):
                pts = [v for x, y in p.exterior.coords for v in (X(x), Y(y))]
                if len(pts) >= 6:
                    i = c.create_polygon(pts, fill='', outline='#58a6ff', dash=(3, 2))
                    c.tag_bind(i, '<Enter>', lambda e, t=mk['text']: self.hover.config(
                        text=f"{t or 'User.2 marker'}  ·  marker only - not cut or printed, it's a guide in the artwork file"))
                    c.tag_bind(i, '<Leave>', lambda e: self.hover.config(text='Hover over a cutout to see what it is.'))
            if mk['text'] and mk['text'].split(' ')[0] not in {L['ref'] for L in pv.get('labels', [])}:
                b = mk['geom'].bounds
                c.create_text(X((b[0] + b[2]) / 2), Y(b[3]) + 2, text=mk['text'].split(' ')[0], anchor='n',
                              fill='#58a6ff', font=self.f_small)
        px1, py1, px2, py2 = pv['pcb_box']
        c.create_rectangle(X(px1), Y(py1), X(px2), Y(py2), outline=C_PCB, dash=(5, 3), width=1)
        self.hover_items = {}
        for s in pv['shapes']:
            fill, outline, w = {'ok': (C_HOLE, C_PANEL_EDGE, 1), 'warn': (C_WARN_FILL, C_WARN, 2),
                                'error': (C_ERR_FILL, C_ERR, 2)}[s['status']]
            for i in poly(s['geom'], fill=fill, outline=outline, width=w):
                self.hover_items[i] = s
                c.tag_bind(i, '<Enter>', lambda e, s=s: self.show_hover(s))
                c.tag_bind(i, '<Leave>', lambda e: self.hover.config(text='Hover over a cutout to see what it is.'))
        for ref, (bx1, by1, bx2, by2), fid in pv.get('uncut', []):
            i = c.create_rectangle(X(bx1), Y(by1), X(bx2), Y(by2), outline=C_WARN, width=2, dash=(3, 3), fill=C_PANEL)
            self.clicks[i] = lambda r=ref, f=fid: self.ignore_part(r, f)
            wide = X(bx2) - X(bx1) > 70
            c.create_text(X((bx1 + bx2) / 2), Y((by1 + by2) / 2), text=f'{ref}\nno cutout?' if wide else ref, fill='#ffd28a',
                          font=self.f_small, justify='center')
            c.tag_bind(i, '<Enter>', lambda e, r=ref: self.hover.config(
                text=f"{r}  ·  no cutout - click if it doesn't need one, or see Result for how to add one"))
            c.tag_bind(i, '<Leave>', lambda e: self.hover.config(text='Hover over a cutout to see what it is.'))
        fam = pv.get('label_font') or tkfont.nametofont('TkDefaultFont').actual('family')
        self.targets = [(tuple(a['box']), 'shape', a) for a in pv.get('added', [])]       # things you can drag, topmost last
        self.targets += [(tuple(tb['box']), 'tab', tb) for tb in pv.get('tab_boxes', [])]
        self.targets += [(tuple(ln['box']), 'line', ln) for ln in pv.get('lines', [])]
        for L in pv.get('labels', []):
            self.targets.append(((L['x'] - L['w'] / 2, L['y'] - L['h'] / 2, L['x'] + L['w'] / 2, L['y'] + L['h'] / 2),
                                 'text' if L.get('own') else 'label', L))
        for it in pv.get('art_items', []):
            self.targets.append((it['box'], 'art', it))
        for k in pv.get('knocked', []):            # labels cut out of an output box, edge tab or bar: the box follows them
            self.targets.append((k['box'], 'text' if k['fid'].startswith('text:') else 'label', k))
        for im in pv.get('images', []):
            self.targets.append((im['box'], 'image', im))
        for L in pv.get('labels', []):
            px = -max(5, round(L['h'] * self.pg.KICAD_EM * sc))     # KiCad's em square is 1.4 x the text size
            i = c.create_text(X(L['x']), Y(L['y']), text=L['text'], fill='#ffffff' if L['status'] == 'ok' else '#ffb347',
                              font=(fam, px, 'bold' if pv.get('label_bold') else 'normal'))
            c.tag_bind(i, '<Enter>', lambda e, L=L: self.hover.config(
                text=f"{L['ref']}  ·  label '{L['text']}'" + ('  ·  runs into something (see Result)' if L['status'] != 'ok' else '')
                     + ('  ·  drag to move, right-click to change or delete' if L.get('own') else '  ·  drag to move, click to edit')))
            c.tag_bind(i, '<Leave>', lambda e: self.hover.config(text='Hover over a cutout to see what it is.'))
        for g in self.group_targets():             # several picked at once
            if g[1] != 'shape':
                b = g[0]
                c.create_rectangle(X(b[0]) - 3, Y(b[1]) - 3, X(b[2]) + 3, Y(b[3]) + 3, outline='#2563eb', width=2, dash=(5, 2))
        sel = self.selected_target()
        if sel:                                    # what's selected: its box, so you can see what the left panel is changing
            b = sel[0]
            if sel[1] == 'line':                   # a line: shown along itself, with a square on each end to drag
                d = sel[2]
                c.create_line(X(d['x1']), Y(d['y1']), X(d['x2']), Y(d['y2']), fill='#2563eb', width=2, dash=(5, 2))
                for hx, hy in ((X(d['x1']), Y(d['y1'])), (X(d['x2']), Y(d['y2']))):
                    c.create_rectangle(hx - 4, hy - 4, hx + 4, hy + 4, fill='#ffffff', outline='#2563eb', width=2)
            else:
                c.create_rectangle(X(b[0]) - 3, Y(b[1]) - 3, X(b[2]) + 3, Y(b[3]) + 3, outline='#2563eb', width=2, dash=(5, 2))
            if self.resizable(sel):                # corner handles: drag one to make it bigger or smaller
                for hx in (X(b[0]) - 3, X(b[2]) + 3):
                    for hy in (Y(b[1]) - 3, Y(b[3]) + 3):
                        c.create_rectangle(hx - 4, hy - 4, hx + 4, hy + 4, fill='#ffffff', outline='#2563eb', width=2)
        for a in pv.get('added', []):
            if a['id'] in self.shape_sel:
                b = a['box']
                c.create_rectangle(X(b[0]) - 3, Y(b[1]) - 3, X(b[2]) + 3, Y(b[3]) + 3, outline='#2563eb', width=2, dash=(5, 2))
                if len(self.shape_sel) == 1:           # one on its own: a square on each corner to drag it bigger or smaller
                    for hx in (X(b[0]) - 3, X(b[2]) + 3):
                        for hy in (Y(b[1]) - 3, Y(b[3]) + 3):
                            c.create_rectangle(hx - 4, hy - 4, hx + 4, hy + 4, fill='#ffffff', outline='#2563eb', width=2)
        self.draw_bodies()
        self.draw_measure()
        for sh in pv.get('shapes', []):               # the parts you see through a cutout (keys under a window): where
            for ref, (px, py), pb in sh.get('points', []):    # each one is, so labels can be lined up over them
                c.create_rectangle(X(pb[0]), Y(pb[1]), X(pb[2]), Y(pb[3]), outline=C_PCB, dash=(2, 3), width=1)
                c.create_line(X(px) - 5, Y(py), X(px) + 5, Y(py), fill=C_PCB)
                c.create_line(X(px), Y(py) - 5, X(px), Y(py) + 5, fill=C_PCB)
        for ref, (bx1, by1, bx2, by2) in pv.get('rail_bad', []):
            c.create_rectangle(X(bx1), Y(by1), X(bx2), Y(by2), outline=C_ERR, width=2, dash=(4, 2))
            c.create_text(X(bx2) + 10, Y(by1) - 2, text=f'{ref} hits the rail', anchor='nw', fill=C_ERR_TXT, font=self.f_small)
        c.create_text(X((x1 + x2) / 2), Y(y2) + 14, text=f'{x2 - x1:.1f} mm', fill=C_DIM, font=self.f_small)
        c.create_text(X(x1) - 6, Y((y1 + y2) / 2), text=f'{y2 - y1:.1f}\nmm', fill=C_DIM, font=self.f_small, anchor='e', justify='right')

    # ------------------------------------------------------------------ zoom and pan
    def fit_view(self):
        self.view = None; self.draw()

    def wheel_zoom(self, e):
        if not getattr(self, 'cur_view', None) or not self.pv or 'message' in self.pv:
            return
        up = getattr(e, 'delta', 0) > 0 or e.num == 4
        sc, ox, oy = self.cur_view
        f = 1.25 if up else 0.8
        new = max(self.fit_scale * 0.5, min(self.fit_scale * 40, sc * f))
        f = new / sc
        # keep the point under the pointer where it is
        self.view = (new, e.x - (e.x - ox) * f, e.y - (e.y - oy) * f)
        self.draw()

    def to_mm(self, e):
        sc, ox, oy = self.cur_view
        return (e.x - ox) / sc, (e.y - oy) / sc

    def target_at(self, e):
        if not getattr(self, 'cur_view', None) or not getattr(self, 'targets', None):
            return None
        x, y = self.to_mm(e)
        pad = 4 / self.cur_view[0]                    # a few pixels of slack round small text
        for b, kind, data in reversed(self.targets):
            if b[0] - pad <= x <= b[2] + pad and b[1] - pad <= y <= b[3] + pad:
                if kind == 'tab' and data.get('kind') == 'mark':     # the hole inside a shape is the hole, not the shape
                    h = data['hole']
                    if h[0] <= x <= h[2] and h[1] <= y <= h[3]:
                        continue
                if kind == 'line':                    # a sloping line's box is mostly empty: it has to be near the line itself
                    ax, ay, bx, by = data['x1'], data['y1'], data['x2'], data['y2']
                    L2 = (bx - ax) ** 2 + (by - ay) ** 2
                    u = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2)) if L2 > 1e-9 else 0.0
                    if math.hypot(x - ax - u * (bx - ax), y - ay - u * (by - ay)) > pad * 1.5 + float(data.get('w', 0.5)) / 2:
                        continue
                return b, kind, data
        return None

    def press(self, e):
        if self.measuring:
            self.drag = None
            return
        hit = None if self.adding else self.body_at(e)
        if hit:                                        # the edge of a part-size guide: drag it bigger or smaller
            self.body_sel = hit[0]['id']
            self.drag = ('body', e.x, e.y, hit, False, None)
            self.draw()
            return
        if getattr(self, 'body_sel', None):
            self.body_sel = None; self.draw()
        t = None if self.adding else self.target_at(e)
        sel = None if self.adding else self.selected_target()
        if not self.adding and len(self.shape_sel) == 1 and self.pv and getattr(self, 'cur_view', None):
            sc, ox, oy = self.cur_view                     # a corner of the one hole, rectangle or slot that's selected
            a = next((a for a in self.pv.get('added', []) if a['id'] == self.shape_sel[0]), None)
            if a:
                b = a['box']
                for i, hx in enumerate((ox + b[0] * sc - 3, ox + b[2] * sc + 3)):
                    for j, hy in enumerate((oy + b[1] * sc - 3, oy + b[3] * sc + 3)):
                        if abs(e.x - hx) <= 8 and abs(e.y - hy) <= 8:
                            self.drag = ('shapesize', e.x, e.y, a, False, (i, j), None)
                            return
        if sel and sel[1] == 'line' and getattr(self, 'cur_view', None):          # an end of the selected line: re-aim it
            sc, ox, oy = self.cur_view
            d = sel[2]
            for n, (px, py) in enumerate(((d['x1'], d['y1']), (d['x2'], d['y2']))):
                if abs(e.x - (ox + px * sc)) <= 8 and abs(e.y - (oy + py * sc)) <= 8:
                    self.drag = ('lineend', e.x, e.y, sel, False, n, None)
                    return
        if sel and self.resizable(sel) and getattr(self, 'cur_view', None):      # a corner of what's selected: resize it
            sc, ox, oy = self.cur_view
            b = sel[0]
            for hx in (ox + b[0] * sc - 3, ox + b[2] * sc + 3):
                for hy in (oy + b[1] * sc - 3, oy + b[3] * sc + 3):
                    if abs(e.x - hx) <= 8 and abs(e.y - hy) <= 8:
                        self.drag = ('resize', e.x, e.y, sel, False, 1.0)
                        return
        if not self.adding and getattr(self, 'cur_view', None):     # near the edge of a tab or box: grab the edge, not the text
            x, y = self.to_mm(e)
            grab = 6 / self.cur_view[0]
            for tt in getattr(self, 'targets', []):
                if tt[1] != 'tab':
                    continue
                b = tt[0]
                if not (b[0] - grab <= x <= b[2] + grab and b[1] - grab <= y <= b[3] + grab):
                    continue
                d_ = {'l': abs(x - b[0]), 'r': abs(x - b[2]), 't': abs(y - b[1]), 'b': abs(y - b[3])}
                if min(d_[k] for k in tt[2]['edges']) <= grab:
                    t = tt
                    break
        if t and t[1] == 'tab':
            x, y = self.to_mm(e)
            b = t[0]
            dist = {'l': abs(x - b[0]), 'r': abs(x - b[2]), 't': abs(y - b[1]), 'b': abs(y - b[3])}
            edge = min(t[2]['edges'], key=lambda k: dist[k])
            if t[2]['kind'] in ('textbox', 'mark') and dist[edge] > 6 / self.cur_view[0]:
                self.drag = ('item', e.x, e.y, t, False)        # the middle of a box round text: move it, texts and all
                return
            self.drag = ('item', e.x, e.y, t, False, 0, 0, edge)
            return
        if t and t[1] == 'shape':                       # one of several selected holes: they all move together
            i = t[2]['id']
            if getattr(e, 'state', 0) & 0x0001:         # Shift: add to or take from the selection
                self.shape_sel = [k for k in self.shape_sel if k != i] if i in self.shape_sel else self.shape_sel + [i]
                self.sel = None; self.drag = None
                self.draw(); self.show_selected(); self.show_shapes()
                return
            if i not in self.shape_sel:
                self.shape_sel, self.multi = [i], []; self.sel = None
                self.draw(); self.show_selected(); self.show_shapes()
        if t and t[1] in MULTI:
            k = self.sel_key(t)
            if getattr(e, 'state', 0) & 0x0001:         # Shift: add to or take from the selection
                if self.sel and self.sel[0] in MULTI and self.sel not in self.multi:
                    self.multi.append(self.sel)        # what was selected on its own joins in
                self.multi = [x for x in self.multi if x != k] if k in self.multi else self.multi + [k]
                self.sel, self.drag = None, None
                self.draw(); self.show_selected(); self.show_shapes(); self.say_group()
                return
            if k not in self.multi and (self.multi or self.shape_sel):
                self.multi, self.shape_sel = [], []    # something else: the group is let go
        self.drag = ('item', e.x, e.y, t, False) if t else ('band', e.x, e.y, False)

    def mirrored(self, d, edge, e):
        """Pulling this edge also moves the opposite one: the sides of a box round controls, the top and bottom of a box
        round text, and the ends of a bar shared by several labels. Hold Shift to move just the one edge."""
        if getattr(e, 'state', 0) & 0x0001:
            return False
        if d['kind'] == 'group':
            return edge in 'lr'
        if d['kind'] == 'mark':                   # a box round a hole: its sides stay even, its top or bottom reaches for a label
            return edge in 'lr' or d.get('shape') != 'box'
        return d['kind'] == 'textbox' and (edge in 'tb' or len(d.get('members', [])) > 1)

    def shape_size_drag(self, e):
        """Dragging a corner of a hole, rectangle or slot you added. A rectangle or slot keeps its opposite corner where it
        is, and its width and height change separately; a hole grows about its middle. Sizes go in 0.1 mm steps (Alt: finer)."""
        _, x0, y0, a, moved, (i, j), _ = self.drag
        if not moved and abs(e.x - x0) + abs(e.y - y0) < 3:
            return
        sc, ox, oy = self.cur_view
        x, y = self.to_mm(e)
        b = a['box']
        step = 0.01 if getattr(e, 'state', 0) & ALT_MASK else 0.1
        rnd = lambda v: max(0.5, round(v / step) * step)
        if a['kind'] == 'hole':
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            d = rnd(2 * max(abs(x - cx), abs(y - cy)))
            new, nb, txt = dict(d=round(d, 3)), (cx - d / 2, cy - d / 2, cx + d / 2, cy + d / 2), f'{d:g} mm across'
        else:
            fx, fy = b[2] if i == 0 else b[0], b[3] if j == 0 else b[1]         # the corner that stays put
            w, h = rnd(abs(x - fx)), rnd(abs(y - fy))
            nx, ny = (fx - w if i == 0 else fx + w), (fy - h if j == 0 else fy + h)
            nb = (min(fx, nx), min(fy, ny), max(fx, nx), max(fy, ny))
            new = dict(w=round(w, 3), h=round(h, 3), x=round((nb[0] + nb[2]) / 2, 3), y=round((nb[1] + nb[3]) / 2, 3))
            txt = f'{w:g} × {h:g} mm'
        c = self.canvas
        c.delete('dragbox')
        c.create_rectangle(ox + nb[0] * sc, oy + nb[1] * sc, ox + nb[2] * sc, oy + nb[3] * sc, outline='#ffd28a', dash=(4, 2),
                           width=2, tags='dragbox')
        ti = c.create_text(ox + (nb[0] + nb[2]) / 2 * sc, oy + nb[1] * sc - 14, text=txt, fill='#ffffff', font=self.f_head, tags='dragbox')
        r = c.create_rectangle(*[v + o_ for v, o_ in zip(c.bbox(ti), (-4, -2, 4, 2))], fill='#1f3a7a', outline='#ffd28a', tags='dragbox')
        c.tag_raise(ti, r)
        self.hover.config(text=('Hole: ' if a['kind'] == 'hole' else 'Width × height: ') + txt)
        self.drag = ('shapesize', x0, y0, a, True, (i, j), new)

    def resizable(self, t):
        return t[1] in ('image', 'text') or (t[1] == 'art' and str(t[2].get('key')).startswith('title'))

    def resize_drag(self, e):
        """Dragging a corner: the thing grows or shrinks about its middle, keeping its shape."""
        _, x0, y0, t, moved, f = self.drag
        if not moved and abs(e.x - x0) + abs(e.y - y0) < 3:
            return
        sc, ox, oy = self.cur_view
        b = t[0]
        cx, cy = ox + (b[0] + b[2]) / 2 * sc, oy + (b[1] + b[3]) / 2 * sc
        d0 = max(1.0, ((x0 - cx) ** 2 + (y0 - cy) ** 2) ** 0.5)
        f = max(0.15, min(8.0, ((e.x - cx) ** 2 + (e.y - cy) ** 2) ** 0.5 / d0))
        hw, hh = (b[2] - b[0]) / 2 * sc * f, (b[3] - b[1]) / 2 * sc * f
        c = self.canvas
        c.delete('dragbox')
        c.create_rectangle(cx - hw, cy - hh, cx + hw, cy + hh, outline='#ffd28a', dash=(4, 2), width=2, tags='dragbox')
        self.hover.config(text=self.resize_apply(t, f, dry=True))
        self.drag = ('resize', x0, y0, t, True, f)

    def resize_apply(self, t, f, dry=False):
        _, kind, d = t
        if kind == 'image':
            o = self.own_image(d['id'])
            new = round(max(1.0, min(500.0, float(d['w']) * f)), 1)
            if not dry and o:
                o['w'] = new
            return f'Picture: {new:g} mm wide'
        if kind == 'text':
            o = self.own_text(d['fid'])
            new = round(max(0.8, min(30.0, float(d['h']) * f)), 1)
            if not dry and o:
                o['size'] = new
            return f'Text: {new:g} mm'
        if str(d.get('key')).startswith('title:'):          # a copy of the title has its own size
            new = round(max(1.5, min(60.0, float(d.get('h', 5)) * f)), 1)
            o = self.own_title(d['key'])
            if not dry and o is not None:
                o['size'] = new
            return f'Title copy: {new:g} mm'
        try:
            cur = float(self.vars['title_size'].get())
        except ValueError:
            cur = 5.0
        new = round(max(1.5, min(60.0, cur * f)), 1)
        if not dry:
            self.vars['title_size'].set(f'{new:g}')
        return f'Title: {new:g} mm'

    def motion(self, e):
        if self.drag and self.drag[0] == 'body':
            return self.body_drag(e)
        if self.drag and self.drag[0] == 'resize':
            return self.resize_drag(e)
        if self.drag and self.drag[0] == 'shapesize':
            return self.shape_size_drag(e)
        if self.drag and self.drag[0] == 'lineend':
            _, x0, y0, t, moved, n, _ = self.drag
            if not moved and abs(e.x - x0) + abs(e.y - y0) < 3:
                return
            d = t[2]
            other = (d['x2'], d['y2']) if n == 0 else (d['x1'], d['y1'])
            p = self.line_point(e, other, skip=d['id'])
            self.rubber(other, p)
            self.drag = ('lineend', x0, y0, t, True, n, p)
            return
        if not self.drag or not getattr(self, 'cur_view', None):
            return
        if self.drag[0] == 'item':
            _, x0, y0, t, moved = self.drag[:5]
            if not moved and abs(e.x - x0) + abs(e.y - y0) < 4:
                return
            sc, ox, oy = self.cur_view
            b = t[0]
            if t[1] == 'tab' and len(self.drag) > 7:   # pull one edge of a tab: it snaps to the edges of the other tabs
                edge = self.drag[7]
                dx, dy = (e.x - x0) / sc, (e.y - y0) / sc
                axis = 0 if edge in 'lr' else 1
                pos = b[{'l': 0, 't': 1, 'r': 2, 'b': 3}[edge]] + (dx if axis == 0 else dy)
                g = None
                if not getattr(e, 'state', 0) & ALT_MASK:
                    cands = [ob[i] for tb in self.pv.get('tab_boxes', []) if tb is not t[2]
                             for ob in [tb['box']] for i in ((0, 2) if axis == 0 else (1, 3))]
                    if axis == 0:                      # a bar over two keys: snap its ends to key labels and hole edges
                        cands += [L['x'] for L in self.pv.get('labels', [])]
                        cands += [v for sh in self.pv.get('shapes', []) for v in (sh['geom'].bounds[0], sh['geom'].bounds[2])]
                    near = min(cands, key=lambda v: abs(v - pos), default=None)
                    if near is not None and abs(near - pos) <= 8 / sc:
                        pos, g = near, near
                nb = list(b); nb[{'l': 0, 't': 1, 'r': 2, 'b': 3}[edge]] = pos
                mirror = self.mirrored(t[2], edge, e) and not (len(self.drag) > 9 and self.drag[9])
                reach = False
                if mirror and t[2]['kind'] == 'textbox' and axis == 0:
                    # pulling an end past another label (or back off one) is reaching for it: only that end moves.
                    # A small change to the margin moves both ends.
                    pts = [(L['x'], L['y']) for L in self.pv.get('labels', [])] + \
                          [((k['box'][0] + k['box'][2]) / 2, (k['box'][1] + k['box'][3]) / 2) for k in self.pv.get('knocked', [])]
                    inside = lambda q: sum(1 for x, y in pts if q[0] <= x <= q[2] and q[1] <= y <= q[3])
                    reach = inside(nb) != inside(b) or abs(pos - b[0 if edge == 'l' else 2]) > 6
                    mirror = not reach
                if mirror:                                     # the opposite side follows, so what's inside stays centred
                    i, j = {'l': (0, 2), 'r': (2, 0), 't': (1, 3), 'b': (3, 1)}[edge]
                    nb[j] = b[j] - (pos - b[i])
                c = self.canvas
                c.delete('dragbox')
                if g is not None:
                    if axis == 0:
                        c.create_line(ox + g * sc, 0, ox + g * sc, c.winfo_height(), fill='#ff4fd8', dash=(3, 3), tags='dragbox')
                    else:
                        c.create_line(0, oy + g * sc, c.winfo_width(), oy + g * sc, fill='#ff4fd8', dash=(3, 3), tags='dragbox')
                c.create_rectangle(ox + nb[0] * sc, oy + nb[1] * sc, ox + nb[2] * sc, oy + nb[3] * sc,
                                   outline='#ffd28a', dash=(4, 2), width=2, tags='dragbox')
                self.drag = ('item', x0, y0, t, True, pos - b[{'l': 0, 't': 1, 'r': 2, 'b': 3}[edge]], 0, edge, mirror,
                             reach or (len(self.drag) > 9 and self.drag[9]))      # once it's a reach, it stays one
                c.config(cursor='sb_h_double_arrow' if axis == 0 else 'sb_v_double_arrow')
                return
            dx, dy, gx, gy = self.snap(t, (e.x - x0) / sc, (e.y - y0) / sc, free=bool(getattr(e, 'state', 0) & ALT_MASK))
            c = self.canvas
            c.delete('dragbox')
            if gx is not None:
                c.create_line(ox + gx * sc, 0, ox + gx * sc, c.winfo_height(), fill='#ff4fd8', dash=(3, 3), tags='dragbox')
            if gy is not None:
                c.create_line(0, oy + gy * sc, c.winfo_width(), oy + gy * sc, fill='#ff4fd8', dash=(3, 3), tags='dragbox')
            for b in ([g[0] for g in self.group_targets()] if self.in_group(t) and self.group_size() > 1 else
                      [a['box'] for a in self.pv.get('added', []) if a['id'] in self.shape_sel] if t[1] == 'shape' else [b]):
                c.create_rectangle(ox + (b[0] + dx) * sc, oy + (b[1] + dy) * sc, ox + (b[2] + dx) * sc, oy + (b[3] + dy) * sc,
                                   outline='#ffd28a', dash=(4, 2), width=2, tags='dragbox')
            if t[1] == 'shape':
                px1, py1 = self.pv['panel_box'][:2]
                b = t[0]
                self.hover.config(text=f"{(b[0] + b[2]) / 2 + dx - px1:.2f} mm from the left edge, "
                                       f"{(b[1] + b[3]) / 2 + dy - py1:.2f} mm from the top edge (to its middle)")
            self.drag = ('item', x0, y0, t, True, dx, dy)
            c.config(cursor='fleur')
            return
        _, x0, y0, moved = self.drag                    # a box round the holes you added, to select them
        if not moved and abs(e.x - x0) + abs(e.y - y0) < 4:
            return
        self.canvas.delete('dragbox')
        self.canvas.create_rectangle(x0, y0, e.x, e.y, outline='#2563eb', dash=(4, 2), tags='dragbox')
        self.drag = ('band', x0, y0, True)

    def release(self, e):
        if self.drag and self.drag[0] == 'body':
            _, _, _, (b, _), moved, new = self.drag
            self.drag = None
            self.canvas.delete('dragbox')
            if moved and new:
                o = next((o for o in self.ui.get('bodies', []) if o['id'] == b['id']), None)
                if o is not None:
                    o.update(new)
                    self.cfg['body_' + o['kind']] = {k: v for k, v in new.items()}   # the next one starts this size
                    self.persist_ui()
            self.draw()
            return
        if self.drag and self.drag[0] == 'shapesize':
            _, _, _, a, moved, _, new = self.drag
            self.drag = None
            self.canvas.delete('dragbox')
            o = next((o for o in self.ui.get('shapes', []) if o['id'] == a['id']), None)
            if moved and new and o:
                o.update(new)
                if o['kind'] != 'hole':
                    self.last_size[o['kind']] = (o['w'], o['h'])
                self.persist_ui(); self.update_preview()
            return
        if self.drag and self.drag[0] == 'lineend':
            _, _, _, t, moved, n, p = self.drag
            self.drag = None
            self.canvas.delete('dragbox')
            o = self.own_line(t[2]['id'])
            if moved and p and o:
                o['x1' if n == 0 else 'x2'], o['y1' if n == 0 else 'y2'] = round(p[0], 3), round(p[1], 3)
                self.persist_ui(); self.update_preview()
            return
        if self.drag and self.drag[0] == 'resize':
            _, _, _, t, moved, f = self.drag
            self.drag = None
            self.canvas.delete('dragbox')
            if moved:
                self.resize_apply(t, f)
                self.persist_ui(); self.update_preview()
            return
        if self.drag and self.drag[0] == 'item':
            _, x0, y0, t, moved = self.drag[:5]
            dx, dy = self.drag[5:7] if len(self.drag) > 5 else (0, 0)
            edge = self.drag[7] if len(self.drag) > 7 else None
            mirror = self.drag[8] if len(self.drag) > 8 else False
            self.drag = None
            self.canvas.config(cursor='')
            self.canvas.delete('dragbox')
            if moved and t[1] == 'tab' and edge:
                g = self.ui['label_edits'].setdefault(t[2]['key'], {})
                group = t[2]['kind'] == 'group'
                if group:                                          # start from the size it's shown at (it may have been held back)
                    g.clear(); g.update({k: v for k, v in t[2].get('grow', {}).items() if abs(v) > 0.01})
                grow = g.get(edge, 0.0) + (dx if edge in 'rb' else -dx)
                grow = max(-1.2, grow) if group else grow          # a box round controls can also come in a little
                mk = self.own_mark(t[2]['key']) if t[2]['kind'] == 'mark' else None
                if mk is not None and t[2]['shape'] != 'box':      # a round shape: dragging it changes its gap from the hole
                    mk['gap'] = round(max(0.0, float(mk.get('gap', 1.0)) + grow - g.get(edge, 0.0)), 2)
                    g.clear()
                elif mk is not None:                               # a box round a hole: can also come in, down to the hole
                    grow = round(max(-float(mk.get('gap', 1.0)) + 0.2, grow), 3)
                    sides = 'lrtb' if t[2]['shape'] != 'box' else (edge + {'l': 'r', 'r': 'l', 't': 'b', 'b': 't'}[edge] if mirror else edge)
                    for k in sides:
                        if abs(grow) > 0.01:
                            g[k] = grow
                        else:
                            g.pop(k, None)
                elif group:
                    for k in ('lr' if edge in 'lr' else edge):
                        if abs(grow) > 0.01:
                            g[k] = round(grow, 3)
                        else:
                            g.pop(k, None)
                else:                                              # a tab or a box round text; its opposite side may follow
                    delta = grow - g.get(edge, 0.0)
                    for k in (edge + {'l': 'r', 'r': 'l', 't': 'b', 'b': 't'}[edge] if mirror else edge):
                        x = g.get(k, 0.0) + delta
                        if x > 0.01:
                            g[k] = round(x, 3)
                        else:
                            g.pop(k, None)
                if not g:
                    self.ui['label_edits'].pop(t[2]['key'], None)
                self.select(t); self.persist_ui(); self.update_preview()
                return
            if moved:
                if self.in_group(t) and self.group_size() > 1:
                    return self.move_group(round(dx, 3), round(dy, 3))
                if t[1] != 'shape':
                    self.select(t)
                self.move_target(t, round(dx, 3), round(dy, 3))
                return
            if t[1] != 'shape':
                self.select(t)
            else:                                      # a click on one of several: just that one
                self.shape_sel = [t[2]['id']]
                self.draw(); self.show_shapes(reveal=True)
            return
        if self.measuring:
            if getattr(self, 'cur_view', None) and self.pv and 'message' not in self.pv:
                p = self.measure_point(e)
                if len(self.measure) != 1:
                    self.measure, self.len_buf = [p], ''
                    self.draw()
                    self.hover.config(text='Ruler: now click where to measure to - or type a length in mm and press Enter. '
                                           'Hold Ctrl to keep it straight.')
                else:
                    self.set_ruler(p)
            return
        band = self.drag if self.drag and self.drag[0] == 'band' and self.drag[3] else None
        self.drag = None
        self.canvas.config(cursor='')
        self.canvas.delete('dragbox')
        if band and getattr(self, 'cur_view', None):
            sc, ox, oy = self.cur_view
            ax, bx = sorted(((band[1] - ox) / sc, (e.x - ox) / sc))
            ay, by = sorted(((band[2] - oy) / sc, (e.y - oy) / sc))
            inb = lambda b: ax <= (b[0] + b[2]) / 2 <= bx and ay <= (b[1] + b[3]) / 2 <= by
            self.shape_sel = [a['id'] for a in (self.pv or {}).get('added', []) if inb(a['box'])]
            self.multi = []
            for t in self.targets:
                k = self.sel_key(t)
                if t[1] in MULTI and inb(t[0]) and k not in self.multi and not str(k[1]).startswith('tabword:'):
                    self.multi.append(k)
            self.sel = None
            if self.group_size() == 1 and self.multi:  # just one thing: select it the usual way
                self.sel, self.multi = self.multi[0], []
            self.draw(); self.show_selected(); self.show_shapes(reveal=bool(self.shape_sel))
            if not self.group_size() and not self.sel:
                self.hover.config(text='The box picks up labels, texts, lines, pictures and holes you added. To move around '
                                       'the panel, drag with the right mouse button.')
            else:
                self.say_group()
            return
        if self.adding:
            kind, self.adding = self.adding, False
            self.canvas.config(cursor='')
            x, y = self.to_mm(e)
            if kind == 'text':
                dx, dy, _, _ = self.snap(((x, y, x, y), 'new', None), 0, 0)
                self.add_text_at(x + dx, y + dy)
            elif kind == 'mark':
                sh = self.hole_at(x, y)
                if sh:
                    self.add_mark(sh)
                else:
                    self.hover.config(text="That isn't a hole - click Shape round a hole… again and click on a hole.")
            elif kind == 'line':
                if self.line_from is None:              # first click: where it starts
                    self.line_from = self.line_point(e)
                    self.adding = 'line'
                    self.canvas.config(cursor='crosshair')
                    self.hover.config(text='Now click where the line ends. Hold Ctrl to keep it dead level or straight up and down.')
                else:
                    self.add_line(self.line_from, self.line_point(e, self.line_from))
            else:
                self.add_shape_at(kind, x, y, free=bool(getattr(e, 'state', 0) & ALT_MASK))
            return
        for i in reversed(self.canvas.find_overlapping(e.x, e.y, e.x, e.y)):
            if i in self.clicks:
                self.clicks[i](); return
        if self.sel or self.shape_sel or self.multi:   # a click on nothing: nothing selected
            self.select(None)

    # ------------------------------------------------------------------ texts you add, and moving things
    def start_add_text(self):
        if not self.pv or 'message' in self.pv:
            return
        self.end_measure()
        self.adding = 'text'
        self.canvas.config(cursor='crosshair')
        self.hover.config(text='Click on the panel where the text should go.')

    def add_text_at(self, x, y):
        from tkinter import simpledialog
        txt = simpledialog.askstring('Add text', 'Text:', parent=self)
        if not txt or not txt.strip():
            return
        import uuid
        new = dict(id=uuid.uuid4().hex[:8], text=txt.strip(), x=round(x, 2), y=round(y, 2))
        self.ui.setdefault('texts', []).append(new)
        self.vars['texts_on'].set(True)                 # something you just added should show
        self.sel, self.shape_sel, self.multi = ('text', 'text:' + new['id']), [], []   # and is selected, ready to adjust
        self.persist_ui(); self.update_preview()

    def snap(self, t, dx, dy, free=False):
        """Line a moved text up: its middle with the middle of a hole, and its height with other labels.
        Returns the (snapped) move and the guide lines to draw. Hold Alt to place it freely."""
        b, kind, d = t
        cx, cy = (b[0] + b[2]) / 2 + dx, (b[1] + b[3]) / 2 + dy
        if free or not self.pv or not self.snap_on.get():
            return dx, dy, None, None
        # how close counts is measured on screen, as in drawing programs: zoom in for fine moves and the pull gets smaller.
        # Lining up with a row of labels or a part's middle reaches a little further.
        thr = 6 / self.cur_view[0]
        strong = 12 / self.cur_view[0]
        xs, ys, sxs, sys_ = [], [], [], []
        moving = {'add:' + i for i in self.shape_sel} if kind == 'shape' else set()
        holes = [sh for sh in self.pv.get('shapes', []) if sh.get('key') not in moving]
        if kind in ('shape', 'newshape'):
            ys.append((self.pv['panel_box'][1] + self.pv['panel_box'][3]) / 2)
        for rx, ry in self.ruler_points():             # a ruler left on the panel: its ends and middle
            xs.append(rx); ys.append(ry)
        texty = kind not in ('shape', 'newshape')
        for sh in holes:
            g = sh['geom'].bounds
            xs.append((g[0] + g[2]) / 2); ys.append((g[1] + g[3]) / 2)
            if texty:
                sxs.append(((g[0] + g[2]) / 2, (g[1] + g[3]) / 2))
            for _, (px, py), _b in sh.get('points', []):   # each key in a merged slot, each part under a window
                xs.append(px)
                if texty:
                    sxs.append((px, py))
        for L in self.pv.get('labels', []):
            if d is not None and (L is d or (L.get('fid') is not None and L.get('fid') == d.get('fid'))):
                continue
            xs.append(L['x']); ys.append(L['y'])
            if texty:
                sys_.append(L['y'])                    # level with the labels already there
        boxes = []                                     # other things on the panel, as boxes
        for key in ('art_items', 'knocked', 'images'):
            for it in self.pv.get(key, []):
                if d is not None and it is d:
                    continue
                boxes.append(it['box'])
        for mk in self.pv.get('markers', []):
            boxes.append(mk['geom'].bounds)
        boxes += [tuple(tb['box']) for tb in self.pv.get('tab_boxes', []) if not (d is not None and tb is d)]
        for ib in boxes:
            xs.append((ib[0] + ib[2]) / 2); ys.append((ib[1] + ib[3]) / 2)
        x1, y1, x2, y2 = self.pv['panel_box']
        xs.append((x1 + x2) / 2)
        # half way between two neighbouring holes in a row or a column (MIDI over its IN and OUT jacks)
        cs = sorted(((sh['geom'].bounds[0] + sh['geom'].bounds[2]) / 2, (sh['geom'].bounds[1] + sh['geom'].bounds[3]) / 2)
                    for sh in holes)
        for i, (ax, ay) in enumerate(cs):
            for bx_, by_ in cs[i + 1:]:
                if abs(ay - by_) < 1.0 and 0 < bx_ - ax < 40:
                    if not any(ax < qx < bx_ and abs(qy - ay) < 1.0 for qx, qy in cs):
                        xs.append((ax + bx_) / 2)
                if abs(ax - bx_) < 1.0 and 0 < abs(by_ - ay) < 40:
                    lo, hi = sorted((ay, by_))
                    if not any(lo < qy < hi and abs(qx - ax) < 1.0 for qx, qy in cs):
                        ys.append((ay + by_) / 2)
        # the middle of the gap between whatever is either side of it (e.g. between a screen and an edge tab)
        w2, h2 = (b[2] - b[0]) / 2, (b[3] - b[1]) / 2
        obst = [sh['geom'].bounds for sh in holes] + boxes + \
               [(L['x'] - L['w'] / 2, L['y'] - L['h'] / 2, L['x'] + L['w'] / 2, L['y'] + L['h'] / 2)
                for L in self.pv.get('labels', []) if not (d is not None and L is d)]
        row = [o for o in obst if o[1] < cy + h2 and o[3] > cy - h2]
        left = max([o[2] for o in row if o[2] <= cx - w2 + 0.01] + [x1])
        right = min([o[0] for o in row if o[0] >= cx + w2 - 0.01] + [x2])
        xs.append((left + right) / 2)
        col = [o for o in obst if o[0] < cx + w2 and o[2] > cx - w2]
        top = max([o[3] for o in col if o[3] <= cy - h2 + 0.01] + [y1])
        bot = min([o[1] for o in col if o[1] >= cy + h2 - 0.01] + [y2])
        ys.append((top + bot) / 2)
        def pick(cands, strong_cands, at):
            sb = min(strong_cands, key=lambda v: abs(v - at), default=None)
            if sb is not None and abs(sb - at) <= strong:
                return sb
            b_ = min(cands, key=lambda v: abs(v - at), default=None)
            return b_ if b_ is not None and abs(b_ - at) <= thr else None
        # over a part: of the holes and parts within reach across, the one nearest the text (the switch just above it,
        # not a pot further up that happens to be a little closer across)
        near = [p for p in sxs if abs(p[0] - cx) <= strong]
        sx = [min(near, key=lambda p: math.hypot(p[0] - cx, p[1] - cy))[0]] if near else []
        gx, gy = pick(xs, sx, cx), pick(ys, sys_, cy)
        if kind in ('shape', 'newshape'):              # not lined up with anything: whole half millimetres from the panel corner
            if gx is None:
                dx += round((cx - x1) * 2) / 2 + x1 - cx
            if gy is None:
                dy += round((cy - y1) * 2) / 2 + y1 - cy
        return dx + (gx - cx if gx is not None else 0), dy + (gy - cy if gy is not None else 0), gx, gy

    # ------------------------------------------------------------------ what's selected, changed in the left panel
    def sel_key(self, t):
        _, kind, d = t
        return kind, {'image': d.get('id'), 'art': d.get('key'), 'tab': d.get('key'), 'line': d.get('id')}.get(kind, d.get('fid'))

    def say_group(self):
        n = self.group_size()
        if n > 1:
            self.hover.config(text=f'{n} picked - drag one to move them all, Ctrl+C to copy, Delete to remove '
                                   '(PCB labels are hidden). Shift-click adds or takes one away.')

    def select(self, t):
        self.sel = self.sel_key(t) if t else None
        self.shape_sel, self.multi = [], []
        self.draw(); self.show_selected(); self.show_shapes()
        if self.sel:
            self.reveal(self.sel_home, self.sel_boxes[self.sel_home])

    def reveal(self, section, widget):
        """Bring a section of the left panel into view, if the part that matters isn't."""
        f = self.sections[section][0]
        cv = self.left.master
        try:
            tab = next(t for t, keys in self.TABS.items() if section in keys)
            if tab != self.tab or section in self.collapsed:
                self.collapsed.discard(section)
                self.show_tab(tab)
            cv.update_idletasks()
            total = max(1, self.left.winfo_height())
            top, bot = cv.yview()
            total = max(1, self.left.winfo_height())
            top, bot = cv.yview()
            y0 = widget.winfo_rooty() - self.left.winfo_rooty()
            y1 = y0 + max(60, widget.winfo_height())
            if y0 / total < top or y1 / total > bot:
                fits = y1 - f.winfo_y() + 20 < cv.winfo_height()       # show the whole section if it fits, else just the thing
                cv.yview_moveto(max(0.0, ((f.winfo_y() - 10) if fits else (y0 - 40)) / total))
            self._keep_y = None
        except tk.TclError:
            pass

    def selected_target(self):
        if not self.sel or not getattr(self, 'targets', None):
            return None
        return next((t for t in self.targets if self.sel_key(t) == self.sel), None)

    def show_selected(self):
        boxes = getattr(self, 'sel_boxes', None)
        if not boxes or 'lines' not in boxes:
            return
        cv = self.left.master                        # rebuilding these mustn't move the panel under your hand
        self._keep_y = cv.canvasy(0)
        self.after(150, lambda: setattr(self, '_keep_y', None))
        t = self.selected_target()
        if not t:
            self.sel = None
        # a label and its box live under Labels; your own text and pictures under theirs; the title, tabs and boxes under made artwork
        home = None
        if t:
            _, kind, d = t
            own_box = kind == 'tab' and d['kind'] == 'textbox' and str(d['key']).startswith('box:text:')
            home = ('lines' if kind == 'line' else 'extras' if kind == 'image' else
                    'labels' if kind in ('label', 'text') or (kind == 'tab' and d['kind'] == 'textbox') else
                    'title' if kind == 'art' else
                    'pots' if d['kind'] == 'group' and d.get('of') == 'pot' else 'shapes')
        self.sel_home = home
        if hasattr(self, 'w_mark_note'):
            on_mark = bool(t and t[1] == 'tab' and t[2].get('kind') == 'mark')
            self.w_mark_note.config(text=f"Changing the shape round {t[2].get('ref')}." if on_mark else
                                    'For the next shape you add.', style='Head.TLabel' if on_mark else 'Dim.TLabel')
        hints = {'labels': 'Click a label or one of your texts in the preview, or the box round one, to change it here.',
                 'extras': 'Click a picture in the preview to change it here.',
                 'lines': '',
                 'title': 'Click the title or the maker name in the preview to change it here.',
                 'pots': 'Click the box round the pots in the preview to change it here.',
                 'shapes': 'Click a shape in the preview to change it here.'}
        for k, b in boxes.items():
            for w in b.winfo_children():
                w.destroy()
            if k in self.sel_subs:                    # these only appear while something of theirs is selected
                for w in (self.sel_subs[k], b):
                    if k == home and not w.winfo_manager():
                        w.pack(fill='x', pady=(10, 2) if w is self.sel_subs[k] else 0)
                    elif k != home and w.winfo_manager():
                        w.pack_forget()
            elif k != home:
                ttk.Label(b, text=hints[k], style='Dim.TLabel', wraplength=440, justify='left').pack(anchor='w')
        if not t:
            return
        box = boxes[home]
        def entry(row, value, apply, width=7):
            var = tk.StringVar(value=value)
            e = ttk.Entry(row, textvariable=var, width=width); e.pack(side='left', padx=(0, 4))
            done = lambda _=None: apply(var.get())
            e.bind('<Return>', done); e.bind('<FocusOut>', done)
            return e
        def num(v, lo, hi):
            try:
                x = float(str(v).replace('mm', '').strip())
            except ValueError:
                return None
            return max(lo, min(hi, x))
        head = ttk.Label(box, text='', style='Head.TLabel'); head.pack(anchor='w', pady=(0, 2))
        form = self.form(box)
        fld = lambda label, tip=None: self.field(form, label, tip)
        if kind == 'line':
            o = self.own_line(d['id'])
            length = math.hypot(d['x2'] - d['x1'], d['y2'] - d['y1'])
            head.config(text='Line')
            def change(key, x):
                if o is not None and x is not None and x != o.get(key):
                    o[key] = x; self.persist_ui(); self.update_preview()
            if o is not None:                          # Thickness above shows this line's; changing it changes the line
                self._line_sync, was = True, self.loading
                self.loading = True
                self.vars['line_w'].set(f"{float(o.get('w', 0.5)):g}")
                self.loading, self._line_sync = was, False
            ttk.Label(box, text='Change its thickness with Thickness, above.').pack(anchor='w')
            row = fld('Ends')
            ends = self._sel_ends = tk.StringVar(value=next((k for k, x in LINE_ENDS.items() if x == d.get('arrow', 'none')), 'Plain'))
            cb = ttk.Combobox(row, textvariable=ends, values=list(LINE_ENDS), width=24, state='readonly'); cb.pack(side='left')
            cb.bind('<<ComboboxSelected>>', lambda e: change('arrow', LINE_ENDS[ends.get()]))
            row = fld('Length', 'Type a length to make the line exactly that long. Its first end stays where it is.')
            def setlen(v):
                x = num(v, 0.2, 1000)
                if o is not None and x and abs(x - length) > 0.005 and length > 1e-6:
                    o['x2'] = round(o['x1'] + (o['x2'] - o['x1']) * x / length, 3)
                    o['y2'] = round(o['y1'] + (o['y2'] - o['y1']) * x / length, 3)
                    self.persist_ui(); self.update_preview()
            entry(row, f"{length:.2f}".rstrip('0').rstrip('.'), setlen); ttk.Label(row, text='mm').pack(side='left')
            ttk.Label(box, text='Drag the line to move it; drag one of its ends to re-aim it.', style='Dim.TLabel').pack(anchor='w', pady=(4, 0))
            ttk.Button(box, text='Delete line', command=lambda: self.line_delete(d['id'])).pack(anchor='w', pady=(6, 0))
        elif kind == 'image':
            o = self.own_image(d['id'])
            head.config(text=f"Picture: {o['file'] if o else ''}")
            row = fld('Width')
            def setw(v):
                x = num(v, 1, 500)
                if o and x and abs(x - o['w']) > 1e-6:
                    o['w'] = round(x, 2); self.persist_ui(); self.update_preview()
            entry(row, f"{d['w']:g}", setw); ttk.Label(row, text='mm  (the height follows)').pack(side='left')
            row = fld('Turn')
            def setr(v):
                x = num(v, -360, 360)
                if o is not None and x is not None and abs(x - float(o.get('rot', 0))) > 1e-6:
                    o['rot'] = round(x % 360, 2); self.persist_ui(); self.update_preview()
            entry(row, f"{float(d.get('rot', 0)):g}", setr, width=5); ttk.Label(row, text='degrees').pack(side='left')
            ttk.Button(row, text='↺ 90', width=5, command=lambda: setr(str(float(o.get('rot', 0)) - 90))).pack(side='left', padx=(8, 4))
            ttk.Button(row, text='↻ 90', width=5, command=lambda: setr(str(float(o.get('rot', 0)) + 90))).pack(side='left')
            inv = self._sel_inv = tk.BooleanVar(value=bool(d.get('invert')))     # kept, or Tk forgets it
            ttk.Checkbutton(fld('Print'), text='The light parts instead of the dark', variable=inv,
                            command=lambda: self.image_invert(d['id'])).pack(side='left')
            ttk.Button(box, text='Delete picture', command=lambda: (self.image_delete(d['id']), self.select(None))).pack(anchor='w', pady=(6, 0))
        elif kind == 'text':
            o = self.own_text(d['fid'])
            head.config(text='Your text')
            row = fld('Text')
            def sett(v):
                if o and v.strip() and v.strip() != o['text']:
                    o['text'] = v.strip(); self.persist_ui(); self.update_preview()
            entry(row, o['text'] if o else '', sett, width=27)
            row = fld('Size')
            def sets(v):
                x = num(v, 0.8, 30)
                if o and x and abs(x - float(o.get('size') or 0)) > 1e-6:
                    o['size'] = round(x, 2); self.persist_ui(); self.update_preview()
            entry(row, f"{d['h']:g}", sets); ttk.Label(row, text='mm').pack(side='left')
            self.box_choice(fld('Box'), o.get('box') if o else None, lambda v: (o.__setitem__('box', v) if v else o.pop('box', None),
                                                                         self.persist_ui(), self.update_preview()))
            ttk.Button(box, text='Delete text', command=lambda: (self.text_delete(d['fid']), self.select(None))).pack(anchor='w', pady=(6, 0))
        elif kind == 'label':
            head.config(text=f"Label: {d.get('ref', '')}")
            fid = d['fid']
            if not fid.startswith('tabword:'):
                row = fld('Text')
                def setl(v):
                    if v.strip() and v != d.get('text'):
                        self.ui['label_edits'].setdefault(fid, {})['text'] = v; self.persist_ui(); self.update_preview()
                entry(row, d.get('text', ''), setl, width=27)
            if not fid.startswith('tabword:'):
                def setbox(v, fid=fid):
                    e = self.ui['label_edits'].setdefault(fid, {})
                    if v:
                        e['box'] = v
                    else:
                        e.pop('box', None)
                    self.persist_ui(); self.update_preview()
                self.box_choice(fld('Box'), self.ui['label_edits'].get(fid, {}).get('box'), setbox)
            row = ttk.Frame(box); row.pack(fill='x', pady=(6, 0))
            ttk.Button(row, text='Put back where it was', command=lambda: self.label_reset(fid)).pack(side='left')
            if not fid.startswith('tabword:'):
                ttk.Button(row, text='Hide', command=lambda: (self.label_hide(fid), self.select(None))).pack(side='left', padx=6)
                ttk.Button(row, text='Edit labels…', command=lambda: (self.edit_labels(), self.editor.focus_row(fid))).pack(side='left')
        elif kind == 'art' and str(d['key']).startswith('title:'):
            o = self.own_title(d['key'])
            head.config(text='Copy of the title')
            row = fld('Size')
            def setts(v):
                x = num(v, 1.5, 60)
                if o is not None and x is not None and x != o.get('size'):
                    o['size'] = x; self.persist_ui(); self.update_preview()
            entry(row, f"{float(d.get('h', 5)):g}", setts); ttk.Label(row, text='mm').pack(side='left')
            row = fld('Direction')
            tdir = self._sel_tdir = tk.StringVar(value=next((k for k, x in TITLE_DIRS.items() if x == d.get('vert')), 'Across'))
            cb = ttk.Combobox(row, textvariable=tdir, values=list(TITLE_DIRS), width=24, state='readonly'); cb.pack(side='left')
            def setdir(_=None):
                if o is not None:
                    o['dir'] = TITLE_DIRS[tdir.get()]; o['mirror'] = bool(tmir.get()); self.persist_ui(); self.update_preview()
            cb.bind('<<ComboboxSelected>>', setdir)
            tmir = self._sel_tmir = tk.BooleanVar(value=bool(d.get('mirror')))
            ttk.Checkbutton(fld('Mirror'), text='Mirror image', variable=tmir, command=setdir).pack(side='left')
            ttk.Label(box, text='It says what the title says. Drag it to move it; drag a corner to resize it.',
                      style='Dim.TLabel', wraplength=440, justify='left').pack(anchor='w', pady=(4, 0))
            ttk.Button(box, text='Delete this copy', command=lambda: self.title_delete(d['key'])).pack(anchor='w', pady=(6, 0))
        elif kind == 'art':
            head.config(text='Title' if d['key'] == 'title' else 'Maker name')
            ttk.Label(box, text=('Its text and size are just above. Or drag a corner of it in the preview to resize it.'
                                 if d['key'] == 'title' else 'Its text is just above.'),
                      style='Dim.TLabel', wraplength=440, justify='left').pack(anchor='w')
            b = ttk.Button(box, text='Put it back in its automatic place',
                           command=lambda: (self.ui['art_pos'].pop(d['key'], None), self.persist_ui(), self.update_preview()))
            b.pack(anchor='w', pady=(6, 0))
            if not d.get('pinned'):
                b.state(['disabled'])
        elif kind == 'tab' and d['kind'] == 'mark':
            o = self.own_mark(d['key'])
            head.config(text=f"Shape round {d.get('ref', 'a hole')}")
            if o is not None:
                self.remember_mark(o)
            ttk.Label(box, text='Change it with the Shape settings above: shape, filled, gap, line thickness and corners.',
                      wraplength=440, justify='left').pack(anchor='w')
            ttk.Label(box, text='Drag an edge in the preview to make it bigger or smaller. A box keeps its sides even (hold Shift to move '
                                'just one); pull its top or bottom over the label and a filled box cuts the label out.', style='Dim.TLabel', wraplength=440, justify='left').pack(anchor='w', pady=(4, 0))
            row = ttk.Frame(box); row.pack(anchor='w', pady=(6, 0))
            ttk.Button(row, text='Back to its own size', command=lambda: (self.ui['label_edits'].pop(d['key'], None), self.persist_ui(),
                                                                      self.update_preview())).pack(side='left')
            ttk.Button(row, text='Delete shape', command=lambda: self.mark_delete(d['key'])).pack(side='left', padx=6)
        elif kind == 'tab':
            head.config(text={'edge': 'Horizontal jack tab: ', 'output': 'Vertical output box: ', 'textbox': 'Box round ',
                              'group': 'Box round '}.get(d['kind'], '') + d.get('ref', ''))
            g = self.ui['label_edits'].get(d['key'], {})
            group = d['kind'] == 'group'
            for edge in ('ltb' if group else d['edges']):
                row = fld('Bigger on ' + ('both sides' if group and edge == 'l' else
                                          'the ' + {'l': 'left', 'r': 'right', 't': 'top', 'b': 'bottom'}[edge]))
                def setg(v, edge=edge):
                    x = num(v, -1.2 if group else 0, 50)
                    if x is None:
                        return
                    gg = self.ui['label_edits'].setdefault(d['key'], {})
                    if abs(x - gg.get(edge, 0.0)) > 1e-6:
                        for k in ('lr' if group and edge == 'l' else edge):
                            if x != 0:
                                gg[k] = round(x, 2)
                            else:
                                gg.pop(k, None)
                        if not gg:
                            self.ui['label_edits'].pop(d['key'], None)
                        self.persist_ui(); self.update_preview()
                entry(row, f"{g.get(edge, 0.0):g}", setg); ttk.Label(row, text='mm').pack(side='left')
            ttk.Label(box, text='Or drag an edge of it in the preview: it snaps to the edges of the other tabs and boxes'
                               + (', and to key labels and hole edges - stretch a bar over two keys. Drag the middle of the box '
                                  'to move it with everything in it; drag a text inside it to move just that text. Its top and bottom move together, and so '
                                  'do the ends of a bar with several labels in it when you nudge them (up to 6 mm). Pull an end further, or past '
                                  'another label, and only that end moves. Shift always moves just one edge.' if d['kind'] == 'textbox' else
                                  '. Pull a side and the other side follows, so the box stays centred on the controls.' if group else '.'),
                      style='Dim.TLabel', wraplength=390, justify='left').pack(anchor='w', pady=(4, 0))
            ttk.Button(box, text='Back to its own size', command=lambda: (self.ui['label_edits'].pop(d['key'], None),
                                                                          self.persist_ui(), self.update_preview())).pack(anchor='w', pady=(6, 0))

    # ------------------------------------------------------------------ holes, rectangles and slots you add
    def hole_dia(self):
        import re
        m = re.match(r'\s*(\d+(?:[.,]\d+)?)', self.hole_size.get())
        if not m or not 0.3 <= float(m.group(1).replace(',', '.')) <= 200:
            raise ValueError('Hole size: pick one from the list, or type a size in mm (e.g. 4.5)')
        return float(m.group(1).replace(',', '.'))

    OWN_SIZE = 'Your own size…'

    def hole_list(self):
        """The sizes in the list: your own (the ones you've typed before) first, then the usual ones."""
        mine = [f"{d:g}  ·  your size" for d in self.cfg.get('hole_sizes', [])]
        self.w_hole_size['values'] = mine + list(HOLE_SIZES) + [self.OWN_SIZE]

    def hole_size_picked(self):
        if self.hole_size.get() == self.OWN_SIZE:      # an empty box to type into
            self.hole_size.set('')
            self.w_hole_size.focus_set(); self.w_hole_size.icursor('end')
            self.hover.config(text='Type the hole size in mm (e.g. 4.5) and press Enter.')

    def keep_hole_size(self):
        """A size you typed that isn't in the list goes into it, so it's there next time."""
        try:
            d = round(self.hole_dia(), 3)
        except ValueError:
            return
        if any(abs(float(h.split()[0]) - d) < 1e-6 for h in HOLE_SIZES):
            return
        mine = [x for x in self.cfg.get('hole_sizes', []) if abs(x - d) > 1e-6]
        self.cfg['hole_sizes'] = ([d] + mine)[:6]
        self.save_cfg()
        self.hole_list()

    def hole_size_changed(self):
        """Hole size picked or typed: with one hole you added selected, it changes to that size."""
        if getattr(self, '_hole_sync', False) or len(getattr(self, 'shape_sel', [])) != 1:
            return
        o = next((o for o in self.ui.get('shapes', []) if o['id'] == self.shape_sel[0] and o['kind'] == 'hole'), None)
        try:
            d = self.hole_dia()
        except ValueError:
            return                                     # half-typed
        if o is not None and abs(d - o['d']) > 1e-6:
            o['d'] = d
            self.persist_ui(); self.update_preview()

    def start_add(self, kind):
        if not self.pv or 'message' in self.pv:
            return
        if kind == 'hole':
            try:
                self.hole_dia()
            except ValueError as e:
                messagebox.showinfo('Panel Generator', str(e)); return
        self.end_measure()
        self.adding = kind
        self.canvas.config(cursor='crosshair')
        self.hover.config(text=f'Click on the panel where the middle of the {SHAPE_NAMES[kind]} goes. Esc to cancel.')

    def add_shape_at(self, kind, x, y, free=False):
        import uuid
        if kind == 'hole':
            try:
                d = self.hole_dia()
            except ValueError as e:
                messagebox.showinfo('Panel Generator', str(e)); return
            new, w, h = dict(d=d), d, d
        else:
            w, h = self.last_size[kind]
            new = dict(w=w, h=h)
        dx, dy, _, _ = self.snap(((x - w / 2, y - h / 2, x + w / 2, y + h / 2), 'newshape', None), 0, 0, free=free)
        new.update(id=uuid.uuid4().hex[:8], kind=kind, x=round(x + dx, 3), y=round(y + dy, 3))
        self.ui.setdefault('shapes', []).append(new)
        self.shape_sel, self.sel = [new['id']], None
        self.persist_ui(); self.update_preview()
        self.show_shapes(reveal=True)

    def own_shapes(self):
        return [o for o in self.ui.get('shapes', []) if o['id'] in self.shape_sel]

    def shapes_delete(self):
        if not self.shape_sel:
            return
        self.ui['shapes'] = [o for o in self.ui.get('shapes', []) if o['id'] not in self.shape_sel]
        self.shape_sel = []
        self.persist_ui(); self.update_preview()

    def shapes_duplicate(self):
        """Copy the selected holes, keeping their sizes and spacing: the copy goes alongside, selected, ready to drag."""
        sel = self.own_shapes()
        if not sel or not self.pv or 'message' in self.pv:
            return
        import uuid
        boxes = {a['id']: a['box'] for a in self.pv.get('added', [])}
        bs = [boxes[o['id']] for o in sel if o['id'] in boxes]
        if not bs:
            return
        x1, y1, x2, y2 = min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)
        px1, py1, px2, py2 = self.pv['panel_box']
        cxs, cys = sorted(o['x'] for o in sel), sorted(o['y'] for o in sel)
        # carry the pattern on: two holes in a row are copied one more step along the row
        row = len(sel) > 1 and cys[-1] - cys[0] < 0.01
        col = len(sel) > 1 and cxs[-1] - cxs[0] < 0.01
        gap = 4.0
        if row:
            step = (cxs[-1] - cxs[0]) / (len(sel) - 1)
            dx, dy = cxs[-1] - cxs[0] + step, 0.0
        elif col:
            step = (cys[-1] - cys[0]) / (len(sel) - 1)
            dx, dy = 0.0, cys[-1] - cys[0] + step
        else:
            dx, dy = x2 - x1 + gap, 0.0
        if x2 + dx > px2 - 1 and not col:               # no room to the right: go underneath instead
            dx, dy = 0.0, y2 - y1 + gap
        if y2 + dy > py2 - 1:
            dx, dy = (-(x2 - x1 + gap), 0.0) if x1 - (x2 - x1 + gap) > px1 else (gap, gap)
        new = [dict(o, id=uuid.uuid4().hex[:8], x=round(o['x'] + dx, 3), y=round(o['y'] + dy, 3)) for o in sel]
        self.ui['shapes'] += new
        self.shape_sel = [o['id'] for o in new]
        self.persist_ui(); self.update_preview()
        self.hover.config(text='Copied - drag the copy where it goes; it snaps into line with the other holes.')

    def shapes_line_up(self, axis):
        sel = self.own_shapes()
        if len(sel) < 2:
            return
        first = min(sel, key=lambda o: (o['x'], o['y']) if axis == 'y' else (o['y'], o['x']))
        for o in sel:
            o[axis] = first[axis]
        self.persist_ui(); self.update_preview()

    def shapes_spacing(self):
        """(axis, spacing or None): the way the selected holes run, and their centre-to-centre spacing if it's even."""
        sel = self.own_shapes()
        if len(sel) < 2:
            return None, None
        axis = 'x' if max(o['x'] for o in sel) - min(o['x'] for o in sel) >= max(o['y'] for o in sel) - min(o['y'] for o in sel) else 'y'
        v = sorted(o[axis] for o in sel)
        steps = [b - a for a, b in zip(v, v[1:])]
        return axis, (steps[0] if max(steps) - min(steps) < 0.006 else None)

    def shapes_set_spacing(self, pitch):
        axis, _ = self.shapes_spacing()
        if axis is None:
            return
        sel = sorted(self.own_shapes(), key=lambda o: o[axis])
        for n, o in enumerate(sel):
            o[axis] = round(sel[0][axis] + n * pitch, 3)
        self.persist_ui(); self.update_preview()

    def show_shapes(self, reveal=False):
        box = getattr(self, 'hole_box', None)
        if box is None:
            return
        for w in box.winfo_children():
            w.destroy()
        added = {a['id']: a for a in (self.pv or {}).get('added', [])} if self.pv and 'message' not in self.pv else {}
        self.shape_sel = [i for i in self.shape_sel if i in added]
        sel = self.own_shapes()
        if not sel:
            n = len(added)
            ttk.Label(box, text=(f"{n} added. Click one in the preview to change it." if n else 'None added yet.'),
                      style='Dim.TLabel', wraplength=390, justify='left').pack(anchor='w')
            return
        px1, py1 = self.pv['panel_box'][:2]
        def entry(form, label, value, apply, note=None, tip=None):
            cell = self.field(form, label, tip)
            var = tk.StringVar(value=value)
            e = ttk.Entry(cell, textvariable=var, width=7); e.pack(side='left')
            def done(_=None):
                try:
                    x = float(var.get().replace('mm', '').replace(',', '.').strip())
                except ValueError:
                    return
                apply(x)
            e.bind('<Return>', done); e.bind('<FocusOut>', done)
            ttk.Label(cell, text='mm').pack(side='left', padx=(4, 0))
            if note:
                ttk.Label(cell, text=note, style='Dim.TLabel').pack(side='left', padx=(10, 0))
            return cell
        def change(o, key, x, lo=0.3, hi=500):
            x = round(max(lo, min(hi, x)), 3)
            if abs(x - float(o.get(key, 0) or 0)) > 1e-6:
                o[key] = x
                if o['kind'] != 'hole':
                    self.last_size[o['kind']] = (o['w'], o['h'])
                self.persist_ui(); self.update_preview()
        nice = lambda x: f"{x:.2f}".rstrip('0').rstrip('.')
        if len(sel) == 1:
            o = sel[0]
            ttk.Label(box, text=added[o['id']]['ref'], style='Head.TLabel').pack(anchor='w', pady=(0, 2))
            f = self.form(box)
            tip = 'Measured from the edge of the panel to the middle of it.'
            entry(f, 'From the left edge', nice(o['x'] - px1), lambda x: change(o, 'x', x + px1, -1e4, 1e4), 'to its middle', tip)
            entry(f, 'From the top edge', nice(o['y'] - py1), lambda x: change(o, 'y', x + py1, -1e4, 1e4), 'to its middle', tip)
            if o['kind'] == 'hole':
                self._hole_sync = True                 # Hole size above shows this hole's size; picking one changes it
                self.hole_size.set(next((h for h in HOLE_SIZES if abs(float(h.split()[0]) - o['d']) < 1e-6), f"{o['d']:g}"))
                self._hole_sync = False
                ttk.Label(f, text='Change its size with Hole size, above.').grid(row=f._rows, column=0, columnspan=2,
                                                                                  sticky='w', pady=3)
                f._rows += 1
            elif o['kind'] == 'rect':
                entry(f, 'Width', f"{o['w']:g}", lambda x: change(o, 'w', x))
                entry(f, 'Height', f"{o['h']:g}", lambda x: change(o, 'h', x))
                entry(f, 'Corner radius', f"{float(o.get('r', 0) or 0):g}", lambda x: change(o, 'r', x, 0, 100), '0 = square')
            else:
                entry(f, 'Length', f"{max(o['w'], o['h']):g}", lambda x: change(o, 'w' if o['w'] >= o['h'] else 'h', x), 'end to end')
                entry(f, 'Width', f"{min(o['w'], o['h']):g}", lambda x: change(o, 'h' if o['w'] >= o['h'] else 'w', x))
                def turn():
                    o['w'], o['h'] = o['h'], o['w']
                    self.last_size['slot'] = (o['w'], o['h'])
                    self.persist_ui(); self.update_preview()
                ttk.Button(self.field(f, 'Direction'), text='Turn 90°', command=turn).pack(side='left')
        else:
            ttk.Label(box, text=f'{len(sel)} selected', style='Head.TLabel').pack(anchor='w', pady=(0, 2))
            f = self.form(box)
            row = self.field(f, 'Line up')
            b = ttk.Button(row, text='In a row', command=lambda: self.shapes_line_up('y')); b.pack(side='left')
            Tip(b, 'Puts them all at the same height as the one furthest left.')
            b = ttk.Button(row, text='In a column', command=lambda: self.shapes_line_up('x')); b.pack(side='left', padx=6)
            Tip(b, 'Puts them all under the top one.')
            axis, pitch = self.shapes_spacing()
            entry(f, 'Spacing', '' if pitch is None else nice(pitch), lambda x: self.shapes_set_spacing(max(0.0, min(500.0, x))),
                  'middle to middle, ' + ('across' if axis == 'x' else 'down'),
                  'Empty = they are not evenly spaced. Type a spacing and the first one stays where it is.')
        f = self.form(box)
        row = self.field(f, 'This' if len(sel) == 1 else 'These')
        b = ttk.Button(row, text='Copy', command=self.shapes_duplicate); b.pack(side='left')
        Tip(b, 'Makes a copy alongside with the same sizes and spacing (Ctrl+D). Holes in a row are carried on along the row. '
               'Then drag the copy where it goes.')
        ttk.Button(row, text='Delete', command=self.shapes_delete).pack(side='left', padx=6)
        if reveal:
            self.reveal('holes', box)

    # ------------------------------------------------------------------ moving the view, and the ruler
    def pan_press(self, e):
        self.pan = (e.x, e.y, False)

    def pan_motion(self, e):
        if not self.pan or not getattr(self, 'cur_view', None):
            return
        x0, y0, moved = self.pan
        if not moved and abs(e.x - x0) + abs(e.y - y0) < 4:
            return
        sc, ox, oy = self.cur_view
        self.view = (sc, ox + e.x - x0, oy + e.y - y0)
        self.pan = (e.x, e.y, True)
        self.canvas.config(cursor='fleur')
        self.draw()

    def pan_release(self, e):
        moved = self.pan and self.pan[2]
        self.pan = None
        self.canvas.config(cursor='crosshair' if (self.measuring or self.adding) else '')
        if not moved:
            if self.adding or self.measuring:
                self.escape()
            else:
                self.context_menu(e)

    def escape(self, _=None):
        if self.adding:
            self.adding, self.line_from = False, None
            self.canvas.delete('dragbox')
            self.canvas.config(cursor='')
            self.hover.config(text='Hover over a cutout to see what it is.')
        elif self.measuring:
            self.end_measure()
        elif self.shape_sel or self.sel or self.multi:
            self.select(None)
        elif self.measure:
            self.end_measure()

    def toggle_measure(self):
        if self.measuring or self.measure:
            return self.end_measure()
        self.start_measure()

    def start_measure(self):
        if not self.pv or 'message' in self.pv:
            return
        self.adding = False
        self.measuring, self.measure, self.len_buf = True, [], ''
        self.w_measure.config(text='Cancel')
        self.canvas.config(cursor='crosshair')
        self.draw()
        self.hover.config(text='Ruler: click where to measure from, then where to (or type a length). Hold Ctrl to keep it straight.')

    def set_ruler(self, p):
        """The second point is down: the ruler stays on the panel as a guide. Its ends and its middle are snap points for
        anything you drag, add or paste, until you clear it."""
        self.measure = [self.measure[0], (round(p[0], 4), round(p[1], 4))]
        self.measuring, self.len_buf = False, ''
        self.w_measure.config(text='Clear ruler')
        self.canvas.config(cursor='')
        self.draw()

    def ruler_points(self):
        """Where things snap to on a ruler that's been set: both ends and the middle."""
        if self.measuring or len(self.measure) != 2:
            return []
        (ax, ay), (bx, by) = self.measure
        return [(ax, ay), (bx, by), ((ax + bx) / 2, (ay + by) / 2)]

    def ruler_key(self, e):
        """Typing a length: after the first point it sets the second that far away (towards the pointer, dead level or
        straight up if it's nearly so); on a ruler that's already set it changes its length."""
        if isinstance(self.focus_get(), (ttk.Entry, tk.Entry, ttk.Combobox)) or (e.state & 0x0004):
            return
        if e.keysym in ('m', 'M') and not self.adding:
            return self.start_measure()
        picking = self.measuring and len(self.measure) == 1
        if not picking and not (not self.measuring and len(self.measure) == 2):
            return
        buf = getattr(self, 'len_buf', '')
        ch = {'period': '.', 'comma': '.', 'KP_Decimal': '.'}.get(e.keysym, e.char if e.char and e.char in '0123456789.' else '')
        if e.keysym.startswith('KP_') and e.keysym[3:].isdigit():
            ch = e.keysym[3:]
        if ch:
            if ch != '.' or '.' not in buf:
                buf += ch
        elif e.keysym == 'BackSpace':
            buf = buf[:-1]
        elif e.keysym in ('Return', 'KP_Enter') and buf:
            try:
                length = float(buf)
            except ValueError:
                length = 0
            if length > 0:
                ax, ay = self.measure[0]
                if picking:
                    sc, ox, oy = self.cur_view
                    mx, my = ((self.mouse[0] - ox) / sc, (self.mouse[1] - oy) / sc) if self.mouse else (ax + 1, ay)
                else:
                    mx, my = self.measure[1]
                dx, dy = mx - ax, my - ay
                d = (dx * dx + dy * dy) ** 0.5
                dx, dy = (dx / d, dy / d) if d > 1e-6 else (1.0, 0.0)
                if picking and abs(dy) < 0.26:           # within 15 degrees of level: dead level
                    dx, dy = (1.0 if dx >= 0 else -1.0), 0.0
                elif picking and abs(dx) < 0.26:
                    dx, dy = 0.0, (1.0 if dy >= 0 else -1.0)
                self.set_ruler((ax + dx * length, ay + dy * length))
            return
        else:
            return
        self.len_buf = buf
        if picking:
            self.draw_measure(self.measure_point(E_(self.mouse)) if self.mouse else None)
        self.hover.config(text=f"Ruler length: {buf or '…'} mm  ·  Enter to set it")

    def end_measure(self):
        if not self.measuring and not self.measure:
            return
        self.measuring, self.measure, self.len_buf = False, [], ''
        self.w_measure.config(text='Measure')
        self.canvas.config(cursor='')
        self.hover.config(text='Hover over a cutout to see what it is.')
        self.draw()

    def measure_point(self, e):
        """Where the ruler lands. Ctrl (or Shift) keeps the second point dead level with, or straight above, the first."""
        p = self.measure_snap(e)
        if getattr(e, 'state', 0) & 0x0005 and len(self.measure) == 1:
            ax, ay = self.measure[0]
            p = (p[0], ay) if abs(p[0] - ax) >= abs(p[1] - ay) else (ax, p[1])
        return p

    def measure_snap(self, e):
        """The middle of a hole, the edge of a hole, a panel edge or corner - else just where the pointer is."""
        x, y = self.to_mm(e)
        if getattr(e, 'state', 0) & ALT_MASK:
            return x, y
        thr = 8 / self.cur_view[0]
        x1, y1, x2, y2 = self.pv['panel_box']
        pts = [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]
        for sh in self.pv.get('shapes', []):
            b = sh['geom'].bounds
            pts.append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
        near = min(pts, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
        if (near[0] - x) ** 2 + (near[1] - y) ** 2 <= thr ** 2:
            return near
        try:
            from shapely.geometry import Point
            best = None
            for sh in self.pv.get('shapes', []):
                for g in (sh['geom'].geoms if hasattr(sh['geom'], 'geoms') else [sh['geom']]):
                    ring = g.exterior
                    q = ring.interpolate(ring.project(Point(x, y)))
                    d = (q.x - x) ** 2 + (q.y - y) ** 2
                    if d <= (thr * 0.75) ** 2 and (best is None or d < best[0]):
                        best = (d, (q.x, q.y))
            if best:
                return best[1]
        except ImportError:
            pass
        for edge in (x1, x2):
            if abs(x - edge) <= thr:
                x = edge
        for edge in (y1, y2):
            if abs(y - edge) <= thr:
                y = edge
        return x, y

    def measure_motion(self, e):
        self.mouse = (e.x, e.y)
        if self.adding == 'line' and self.line_from is not None and getattr(self, 'cur_view', None):
            return self.rubber(self.line_from, self.line_point(e, self.line_from))
        if not self.measuring or len(self.measure) != 1 or not getattr(self, 'cur_view', None) or not self.pv or 'message' in self.pv:
            return
        self.draw_measure(self.measure_point(e))

    def draw_measure(self, live=None):
        c = self.canvas
        c.delete('ruler')
        pts = list(self.measure) + ([live] if live and len(self.measure) == 1 else [])
        if not pts or not getattr(self, 'cur_view', None) or not self.pv or 'message' in self.pv:
            return
        fixed = not self.measuring and len(self.measure) == 2
        sc, ox, oy = self.cur_view
        X = lambda v: ox + v * sc
        Y = lambda v: oy + v * sc
        col = '#ff4fd8'
        for px, py in pts:
            c.create_line(X(px) - 6, Y(py), X(px) + 6, Y(py), fill=col, tags='ruler')
            c.create_line(X(px), Y(py) - 6, X(px), Y(py) + 6, fill=col, tags='ruler')
        if len(pts) < 2:
            return
        (ax, ay), (bx, by) = pts
        dx, dy = bx - ax, by - ay
        dist = (dx * dx + dy * dy) ** 0.5
        c.create_line(X(ax), Y(ay), X(bx), Y(by), fill=col, width=2, tags='ruler')
        if fixed and dist > 1e-6:                      # the middle is a snap point too: a tick across the line
            mx, my, nx, ny = (X(ax) + X(bx)) / 2, (Y(ay) + Y(by)) / 2, -dy / dist * 6, dx / dist * 6
            c.create_line(mx - nx, my - ny, mx + nx, my + ny, fill=col, width=2, tags='ruler')
        txt = f'{dist:.2f} mm'
        if abs(dx) > 0.005 and abs(dy) > 0.005:
            txt += f'   ({abs(dx):.2f} across, {abs(dy):.2f} down)'
            c.create_line(X(ax), Y(ay), X(bx), Y(ay), X(bx), Y(by), fill=col, dash=(2, 3), tags='ruler')
        tx, ty = (X(ax) + X(bx)) / 2, (Y(ay) + Y(by)) / 2
        upright = abs(dy) > abs(dx)                    # keep the figure off the line and off what's being measured
        i = c.create_text(tx + (10 if upright else 0), ty - (0 if upright else 14), text=txt, fill='#ffffff',
                          font=self.f_head, tags='ruler', anchor='w' if upright else 'center')
        r = c.create_rectangle(*[v + o for v, o in zip(c.bbox(i), (-4, -2, 4, 2))], fill='#7a1f6b', outline=col, tags='ruler')
        c.tag_raise(i, r)
        if getattr(self, 'len_buf', ''):
            return
        if fixed:
            if getattr(self, '_ruler_said', None) != self.measure:      # say it once, not on every redraw
                self._ruler_said = list(self.measure)
                self.hover.config(text='Ruler: ' + txt + '  ·  it stays as a guide: things snap to its ends and middle. '
                                                         'Type a length + Enter to change it; Clear ruler (or M for a new one).')
        else:
            self.hover.config(text='Ruler: ' + txt + '  ·  click to set it, or type a length in mm and press Enter')

    def own_title(self, key):
        return next((o for o in self.ui.get('titles', []) if 'title:' + o['id'] == key), None)

    def title_delete(self, key):
        self.ui['titles'] = [o for o in self.ui.get('titles', []) if 'title:' + o['id'] != key]
        self.ui.get('art_pos', {}).pop(key, None)
        self.sel = None
        self.persist_ui(); self.update_preview()

    # ------------------------------------------------------------------ shapes round holes
    def own_mark(self, key):
        return next((o for o in self.ui.get('marks', []) if 'mark:' + o['id'] == key), None)

    def hole_at(self, x, y):
        """The cutout under a point in the preview, if any."""
        from shapely.geometry import Point
        p = Point(x, y)
        pad = 3 / self.cur_view[0]
        return next((sh for sh in reversed((self.pv or {}).get('shapes', [])) if sh['geom'].buffer(pad).contains(p)), None)

    def start_mark(self):
        if not self.pv or 'message' in self.pv:
            return
        self.end_measure()
        self.adding = 'mark'
        self.canvas.config(cursor='crosshair')
        self.hover.config(text='Click the hole the shape goes round (or right-click any hole). Esc to cancel.')

    def add_mark(self, sh, kind=None, fill=None):
        import uuid
        v = self.vars
        num = lambda k, d: float(v[k].get()) if v[k].get().strip() else d
        try:
            gap, w, r = num('mark_gap', 1.0), num('mark_w', 0.6), num('mark_r', 1.0)
        except ValueError:
            gap, w, r = 1.0, 0.6, 1.0
        new = dict(id=uuid.uuid4().hex[:8], on=sh['anchor'], kind=kind or MARKS.get(v['mark_kind'].get(), 'circle'),
                   fill=bool(v['mark_fill'].get()) if fill is None else fill, gap=max(0.0, gap), w=max(0.15, w), r=max(0.0, r))
        self.ui.setdefault('marks', []).append(new)
        self.shape_sel, self.sel = [], ('tab', 'mark:' + new['id'])
        self.persist_ui(); self.update_preview()
        self.hover.config(text='Shape added with the settings under Shapes - change it there, or drag its edges. '
                               'The next one you add gets the same.')
        self.reveal('shapes', self.sel_boxes['shapes'])

    def mark_vars_changed(self):
        """The Shape settings changed: if a shape is selected, it changes with them."""
        if self.loading or getattr(self, '_mark_sync', False):
            return
        t = self.selected_target() if self.pv else None
        if not (t and t[1] == 'tab' and t[2].get('kind') == 'mark'):
            return
        o = self.own_mark(t[2]['key'])
        if o is None:
            return
        v = self.vars
        o['kind'] = MARKS.get(v['mark_kind'].get(), o.get('kind', 'circle'))
        o['fill'] = bool(v['mark_fill'].get())
        for key, var, lo in (('gap', 'mark_gap', 0.0), ('w', 'mark_w', 0.15), ('r', 'mark_r', 0.0)):
            try:
                o[key] = max(lo, float(v[var].get().replace(',', '.')))
            except ValueError:
                pass                                   # half-typed: keep what it was
        self.persist_ui(record=False)

    def remember_mark(self, o):
        """Show a shape's own values in the Shape settings (without changing anything)."""
        v = self.vars
        self._mark_sync, was = True, self.loading
        self.loading = True
        v['mark_kind'].set(next((k for k, x in MARKS.items() if x == o.get('kind')), 'Circle'))
        v['mark_fill'].set(bool(o.get('fill')))
        for key, var in (('gap', 'mark_gap'), ('w', 'mark_w'), ('r', 'mark_r')):
            if key in o:
                v[var].set(f"{float(o[key]):g}")
        self.loading, self._mark_sync = was, False

    def mark_delete(self, key):
        self.ui['marks'] = [o for o in self.ui.get('marks', []) if 'mark:' + o['id'] != key]
        self.ui['label_edits'].pop(key, None)
        self.sel = None
        self.persist_ui(); self.update_preview()

    def mark_menu(self, m, sh):
        """'Add a shape round it', for the right-click menu of a hole: it uses what's set under Shapes, and opens it there."""
        m.add_command(label=f"Add a shape round {sh['label']}", command=lambda: self.add_mark(sh))

    # ------------------------------------------------------------------ lines you draw
    def line_w_changed(self):
        """Thickness changed: with a line selected, that line changes too."""
        if self.loading or getattr(self, '_line_sync', False):
            return
        t = self.selected_target() if self.pv else None
        o = self.own_line(t[2]['id']) if t and t[1] == 'line' else None
        try:
            w = max(0.15, min(10.0, float(self.vars['line_w'].get().replace(',', '.'))))
        except ValueError:
            return                                     # half-typed
        if o is not None and abs(w - float(o.get('w', 0.5))) > 1e-6:
            o['w'] = w
            self.persist_ui(record=False)

    def own_line(self, lid):
        return next((o for o in self.ui.get('lines', []) if o['id'] == lid), None)

    def start_line(self):
        if not self.pv or 'message' in self.pv:
            return
        self.end_measure()
        self.adding, self.line_from = 'line', None
        self.canvas.config(cursor='crosshair')
        self.hover.config(text='Click on the panel where the line starts. Esc to cancel.')

    def line_point(self, e, anchor=None, skip=None):
        """Where an end of a line lands: on another line's end or a ruler point if one is near, else as the ruler snaps.
        Ctrl (or Shift) keeps it dead level with, or straight above, its other end."""
        x, y = self.to_mm(e)
        p = None
        if not getattr(e, 'state', 0) & ALT_MASK:
            thr = 8 / self.cur_view[0]
            pts = [q for ln in self.pv.get('lines', []) if ln['id'] != skip for q in ((ln['x1'], ln['y1']), (ln['x2'], ln['y2']))]
            pts += self.ruler_points()
            near = min(pts, key=lambda q: (q[0] - x) ** 2 + (q[1] - y) ** 2, default=None)
            if near and (near[0] - x) ** 2 + (near[1] - y) ** 2 <= thr ** 2:
                p = near
        p = p or self.measure_snap(e)
        if anchor and getattr(e, 'state', 0) & 0x0005:
            p = (p[0], anchor[1]) if abs(p[0] - anchor[0]) >= abs(p[1] - anchor[1]) else (anchor[0], p[1])
        return p

    def rubber(self, a, b):
        sc, ox, oy = self.cur_view
        c = self.canvas
        c.delete('dragbox')
        c.create_line(ox + a[0] * sc, oy + a[1] * sc, ox + b[0] * sc, oy + b[1] * sc, fill='#ffd28a', width=2, dash=(4, 2), tags='dragbox')
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        self.hover.config(text=f'Line: {d:.2f} mm long')

    def add_line(self, a, b):
        import uuid
        self.adding, self.line_from = False, None
        self.canvas.config(cursor=''); self.canvas.delete('dragbox')
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 0.2:
            return
        try:
            w = max(0.15, min(10.0, float(self.vars['line_w'].get())))
        except ValueError:
            w = 0.5
        new = dict(id=uuid.uuid4().hex[:8], x1=round(a[0], 3), y1=round(a[1], 3), x2=round(b[0], 3), y2=round(b[1], 3), w=w, arrow='none')
        self.ui.setdefault('lines', []).append(new)
        self.shape_sel, self.sel = [], ('line', new['id'])
        self.persist_ui(); self.update_preview()

    def line_delete(self, lid):
        self.ui['lines'] = [o for o in self.ui.get('lines', []) if o['id'] != lid]
        self.sel = None
        self.persist_ui(); self.update_preview()

    # ------------------------------------------------------------------ part-size guides
    def body_menu(self, m, sh):
        """Right-click on a hole: show the size of the part that goes through it (a nut, a knob, a jack's body) as a dashed
        blue line, to judge the spacing by. Never cut or printed."""
        mine = [o for o in self.ui.get('bodies', []) if o['on'] == sh['anchor']]
        if mine:
            m.add_command(label="Remove the part's size", command=lambda: self.body_delete(mine[0]['id']))
            return
        sm = tk.Menu(m, tearoff=0)
        sm.add_command(label='Circle', command=lambda: self.add_body(sh, 'circle'))
        sm.add_command(label='Rectangle', command=lambda: self.add_body(sh, 'rect'))
        b = sh['geom'].bounds
        same = [x for x in self.pv.get('shapes', []) if x is not sh and abs((x['geom'].bounds[2] - x['geom'].bounds[0]) - (b[2] - b[0])) < 0.05
                and abs((x['geom'].bounds[3] - x['geom'].bounds[1]) - (b[3] - b[1])) < 0.05]
        if same:
            sm.add_separator()
            sm.add_command(label=f'Circle on every hole this size ({len(same) + 1})', command=lambda: self.add_body(sh, 'circle', same))
            sm.add_command(label=f'Rectangle on every hole this size ({len(same) + 1})', command=lambda: self.add_body(sh, 'rect', same))
        m.add_cascade(label="Show the part's size round it", menu=sm)

    def add_body(self, sh, kind, others=()):
        import uuid
        b = sh['geom'].bounds
        last = self.cfg.get('body_' + kind)
        if kind == 'circle':
            size = dict(d=float(last['d'])) if last and 'd' in last else dict(d=round(max(b[2] - b[0], b[3] - b[1]) + 1.3, 1))
        else:
            size = dict(w=float(last['w']), h=float(last['h'])) if last and 'w' in last else \
                dict(w=round(b[2] - b[0] + 2, 1), h=round(b[3] - b[1] + 2, 1))
        have = {o['on'] for o in self.ui.get('bodies', [])}
        for x in [sh] + list(others):
            if x['anchor'] not in have:
                self.ui.setdefault('bodies', []).append(dict(id=uuid.uuid4().hex[:8], on=x['anchor'], kind=kind, **size))
        self.persist_ui(); self.draw()
        self.hover.config(text="Part size shown (dashed blue - never cut or printed). Drag its edge to set the size; the gap to "
                               "the nearest part shows as you drag. Right-click the hole to remove it.")

    def body_delete(self, bid):
        self.ui['bodies'] = [o for o in self.ui.get('bodies', []) if o['id'] != bid]
        self.body_sel = None
        self.persist_ui(); self.draw()

    def body_shapes(self):
        """[(guide, shapely shape)] for every part-size guide whose hole is on the panel."""
        from shapely.geometry import Point, box
        holes = {sh.get('anchor'): sh for sh in (self.pv or {}).get('shapes', [])}
        out = []
        for o in self.ui.get('bodies', []):
            sh = holes.get(o['on'])
            if not sh:
                continue
            b = sh['geom'].bounds
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            g = Point(cx, cy).buffer(float(o.get('d', 7.5)) / 2, quad_segs=48) if o['kind'] == 'circle' else \
                box(cx - float(o['w']) / 2, cy - float(o['h']) / 2, cx + float(o['w']) / 2, cy + float(o['h']) / 2)
            out.append((o, g, sh))
        return out

    def body_at(self, e):
        """The part-size guide whose outline is under the pointer, if any."""
        if not self.pv or 'message' in self.pv or not getattr(self, 'cur_view', None) or not self.ui.get('bodies'):
            return None
        from shapely.geometry import Point
        x, y = self.to_mm(e)
        pad = 5 / self.cur_view[0]
        for o, g, sh in self.body_shapes():
            if g.exterior.distance(Point(x, y)) <= pad:
                return o, sh
        return None

    def body_gap(self, g, own):
        """The gap from a part-size guide to the nearest other guide, or hole if that's nearer."""
        others = [x for o, x, sh in self.body_shapes() if o['id'] != own['id']]
        ref = next((sh for o, x, sh in self.body_shapes() if o['id'] == own['id']), None)
        others += [sh['geom'] for sh in self.pv.get('shapes', []) if sh is not ref and
                   not any(oo['on'] == sh.get('anchor') for oo in self.ui.get('bodies', []))]
        return min((g.distance(x) for x in others), default=None)

    def body_drag(self, e):
        _, x0, y0, (o, sh), moved, _ = self.drag
        if not moved and abs(e.x - x0) + abs(e.y - y0) < 3:
            return
        from shapely.geometry import Point, box
        sc, ox, oy = self.cur_view
        x, y = self.to_mm(e)
        b = sh['geom'].bounds
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        step = 0.01 if getattr(e, 'state', 0) & ALT_MASK else 0.1
        rnd = lambda v: max(0.5, round(v / step) * step)
        if o['kind'] == 'circle':
            d = rnd(2 * math.hypot(x - cx, y - cy))
            new, g, txt = dict(d=round(d, 3)), Point(cx, cy).buffer(d / 2, quad_segs=48), f'{d:g} mm across'
        else:                                          # a rectangle grows evenly round the hole; the side you pull sets its size
            w, h = float(o['w']), float(o['h'])
            dx, dy = abs(x - cx), abs(y - cy)
            if dx / max(w, 0.1) >= dy / max(h, 0.1) - 0.15:
                w = rnd(2 * dx)
            if dy / max(h, 0.1) >= dx / max(w, 0.1) - 0.15:
                h = rnd(2 * dy)
            new, g, txt = dict(w=round(w, 3), h=round(h, 3)), box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), f'{w:g} × {h:g} mm'
        gap = self.body_gap(g, o)
        if gap is not None:
            txt += f'   ·   {gap:.1f} mm to the nearest' if gap > 0.005 else '   ·   touching or overlapping'
        c = self.canvas
        c.delete('dragbox')
        gb = g.bounds
        if o['kind'] == 'circle':
            c.create_oval(ox + gb[0] * sc, oy + gb[1] * sc, ox + gb[2] * sc, oy + gb[3] * sc, outline='#0284c7', dash=(4, 3), width=2, tags='dragbox')
        else:
            c.create_rectangle(ox + gb[0] * sc, oy + gb[1] * sc, ox + gb[2] * sc, oy + gb[3] * sc, outline='#0284c7', dash=(4, 3), width=2, tags='dragbox')
        ti = c.create_text(ox + cx * sc, oy + gb[1] * sc - 14, text=txt, fill='#ffffff', font=self.f_head, tags='dragbox')
        r = c.create_rectangle(*[v + o_ for v, o_ in zip(c.bbox(ti), (-4, -2, 4, 2))], fill='#075985', outline='#38bdf8', tags='dragbox')
        c.tag_raise(ti, r)
        self.hover.config(text="Part size: " + txt + '  (Alt for finer steps)')
        self.drag = ('body', x0, y0, (o, sh), True, new)

    def draw_bodies(self):
        if not self.ui.get('bodies') or not getattr(self, 'cur_view', None):
            return
        sc, ox, oy = self.cur_view
        c = self.canvas
        for o, g, sh in self.body_shapes():
            gb = g.bounds
            sel = o['id'] == getattr(self, 'body_sel', None)
            kw = dict(outline='#38bdf8', dash=(4, 3), width=2 if sel else 1)
            if o['kind'] == 'circle':
                c.create_oval(ox + gb[0] * sc, oy + gb[1] * sc, ox + gb[2] * sc, oy + gb[3] * sc, **kw)
            else:
                c.create_rectangle(ox + gb[0] * sc, oy + gb[1] * sc, ox + gb[2] * sc, oy + gb[3] * sc, **kw)

    def delete_selected(self):
        """The Delete key: whatever is selected - holes you added, lines, your texts, pictures, shapes, title copies. A
        label from the PCB can't be deleted (it belongs to its part), so it's hidden: Edit labels brings it back."""
        if getattr(self, 'body_sel', None):
            return self.body_delete(self.body_sel)
        if self.multi:
            gone = {k for k in self.multi}
            ids = lambda kind: {k[1] for k in gone if k[0] == kind}
            self.ui['texts'] = [o for o in self.ui.get('texts', []) if 'text:' + o['id'] not in ids('text')]
            self.ui['lines'] = [o for o in self.ui.get('lines', []) if o['id'] not in ids('line')]
            self.ui['images'] = [o for o in self.ui.get('images', []) if o['id'] not in ids('image')]
            for fid in ids('label'):
                self.ui['label_edits'].setdefault(fid, {})['hide'] = True
            self.ui['shapes'] = [o for o in self.ui.get('shapes', []) if o['id'] not in self.shape_sel]
            hidden = len(ids('label'))
            self.multi, self.shape_sel, self.sel = [], [], None
            self.persist_ui(); self.update_preview()
            if hidden:
                self.hover.config(text=f'Deleted. {hidden} PCB label(s) hidden - Edit labels brings them back.')
            return
        if self.shape_sel:
            return self.shapes_delete()
        t = self.selected_target()
        if not t:
            return
        _, kind, d = t
        if kind == 'label' and not str(d['fid']).startswith('tabword:'):
            self.ui['label_edits'].setdefault(d['fid'], {})['hide'] = True
            self.sel = None
            self.persist_ui(); self.update_preview()
            self.hover.config(text='Label hidden - Edit labels (or Undo) brings it back.')
            return
        if kind == 'line':
            self.line_delete(d['id'])
        elif kind == 'tab' and d['kind'] == 'mark':
            self.mark_delete(d['key'])
        elif kind == 'art' and str(d['key']).startswith('title:'):
            self.title_delete(d['key'])
        elif kind == 'text':
            self.text_delete(d['fid']); self.select(None)
        elif kind == 'image':
            self.image_delete(d['id']); self.select(None)

    # ------------------------------------------------------------------ copy and paste
    def clip_item(self, t):
        """One thing, ready to paste: (kind, its data with x, y as its middle), or None if it can't be copied."""
        _, kind, d = t
        if kind == 'text' and self.own_text(d['fid']):
            return 'text', dict(self.own_text(d['fid']))
        if kind == 'image' and self.own_image(d['id']):
            return 'image', dict(self.own_image(d['id']))
        if kind == 'line' and self.own_line(d['id']):
            o = self.own_line(d['id'])
            return 'line', dict(o, x=(o['x1'] + o['x2']) / 2, y=(o['y1'] + o['y2']) / 2)
        if kind == 'label' and not str(d['fid']).startswith('tabword:'):
            return 'text', dict(text=d.get('text', ''), x=d['x'], y=d['y'])       # a PCB label pastes as a text of yours
        if kind == 'art' and str(d['key']).startswith('title'):
            b = t[0]                                   # the title: the copy says the same, with its own place, size and direction
            return 'title', dict(dir=d.get('vert') or 'off', size=d.get('h'), mirror=bool(d.get('mirror')),
                                 x=(b[0] + b[2]) / 2, y=(b[1] + b[3]) / 2, ax=d['at'][0], ay=d['at'][1])
        return None

    def copy_selected(self):
        """Ctrl+C: remember what's selected - one thing or several: holes you added, texts, labels (as texts), lines,
        pictures, the title."""
        say = lambda t: self.hover.config(text=t)
        items = [('shape', dict(o)) for o in self.own_shapes()]
        picked = [t for t in self.group_targets() if t[1] != 'shape'] if self.multi else \
                 ([self.selected_target()] if self.selected_target() else [])
        items += [x for x in (self.clip_item(t) for t in picked) if x]
        if not items:
            if picked:
                return say("That can't be copied: it's drawn from the panel. Copy works on holes you added, texts, labels, "
                           "lines, pictures and the title.")
            return say('Nothing selected to copy. Click something, or drag a box round several, first.')
        self.clip = items
        say(f"Copied {len(items) if len(items) > 1 else ''} - Ctrl+V pastes at the pointer.".replace('Copied  -', 'Copied -'))

    def paste(self, at=None):
        if not self.clip or not self.pv or 'message' in self.pv or not getattr(self, 'cur_view', None):
            return
        import uuid
        items = self.clip
        cx = (min(o['x'] for _, o in items) + max(o['x'] for _, o in items)) / 2
        cy = (min(o['y'] for _, o in items) + max(o['y'] for _, o in items)) / 2
        c = self.canvas
        over = self.mouse and 0 <= self.mouse[0] <= c.winfo_width() and 0 <= self.mouse[1] <= c.winfo_height() \
            and c.winfo_containing(*self.winfo_pointerxy()) is c
        if at:
            tx, ty = at
            self.pasted_at, self.paste_n = None, 0
        elif over and self.mouse != self.pasted_at:        # at the pointer - or, pasting again without moving, a step along
            sc, ox, oy = self.cur_view
            tx, ty = (self.mouse[0] - ox) / sc, (self.mouse[1] - oy) / sc
            self.pasted_at, self.paste_n = self.mouse, 0
        else:
            self.paste_n = getattr(self, 'paste_n', 0) + 1
            base = getattr(self, 'paste_base', (cx, cy)) if self.mouse == self.pasted_at and over else (cx, cy)
            tx, ty = base[0] + 5 * self.paste_n, base[1] + 5 * self.paste_n
        if getattr(self, 'paste_n', 0) == 0:
            self.paste_base = (tx, ty)
        only_shapes = all(k == 'shape' for k, _ in items)
        dx, dy, _, _ = self.snap(((tx, ty, tx, ty), 'newshape' if only_shapes else 'new', None), 0, 0)
        mx, my = tx + dx - cx, ty + dy - cy
        shapes, keys = [], []
        for kind, o in items:
            o = dict(o, id=uuid.uuid4().hex[:8], x=round(o['x'] + mx, 3), y=round(o['y'] + my, 3))
            if kind == 'shape':
                self.ui.setdefault('shapes', []).append(o); shapes.append(o['id'])
            elif kind == 'title':
                self.ui.setdefault('titles', []).append(dict(id=o['id'], dir=o['dir'], size=o['size'], mirror=o.get('mirror', False)))
                self.ui.setdefault('art_pos', {})['title:' + o['id']] = [round(o['ax'] + mx, 2), round(o['ay'] + my, 2)]
                keys.append(('art', 'title:' + o['id']))
            elif kind == 'line':
                for k, m in (('x1', mx), ('y1', my), ('x2', mx), ('y2', my)):
                    o[k] = round(o[k] + m, 3)
                o.pop('x'); o.pop('y')
                self.ui.setdefault('lines', []).append(o); keys.append(('line', o['id']))
            elif kind == 'text':
                self.ui.setdefault('texts', []).append(o); keys.append(('text', 'text:' + o['id']))
                self.vars['texts_on'].set(True)
            else:
                self.ui.setdefault('images', []).append(o); keys.append(('image', o['id']))
                self.vars['pictures_on'].set(True)
        if len(keys) == 1 and not shapes:              # one thing: selected the usual way, its settings on the left
            self.sel, self.multi, self.shape_sel = keys[0], [], []
        else:
            self.sel, self.multi, self.shape_sel = None, [k for k in keys if k[0] in MULTI], shapes
        self.persist_ui(); self.update_preview()
        self.hover.config(text='Pasted - drag it into place.')

    def box_choice(self, parent, current, apply):
        """Box round a text or label: none, a line round it, or a filled bar with the text cut out."""
        names = {'No box': None, 'A line round it': 'outline', 'A filled bar, text cut out': 'filled'}
        row = parent
        var = self._sel_box = tk.StringVar(value=next((k for k, v in names.items() if v == current), 'No box'))
        cb = ttk.Combobox(row, textvariable=var, values=list(names), state='readonly', width=24)
        cb.pack(side='left')
        cb.bind('<<ComboboxSelected>>', lambda e: apply(names[var.get()]))
        Tip(cb, 'For a key with two jobs, or one that needs two keys pressed: put the text in a box, then click the box and '
                'drag its ends to stretch it over the keys. It snaps to key labels and to other boxes. Any text it reaches over goes into it too (one long bar under a row of keys).')

    def own_image(self, iid):
        return next((i for i in self.ui.get('images', []) if i['id'] == iid), None)

    def add_picture(self, at=None):
        b = self.board.get()
        if not b or not self.pv or 'message' in self.pv:
            messagebox.showinfo('Panel Generator', 'Choose your PCB first.'); return
        f = filedialog.askopenfilename(title='Add a picture', filetypes=[('Pictures', '*.png *.jpg *.jpeg *.gif *.bmp *.svg'),
                                                                         ('All files', '*.*')])
        if not f:
            return
        import shutil, uuid
        folder = os.path.join(os.path.dirname(panel_paths(b)[0]), 'images')
        try:
            os.makedirs(folder, exist_ok=True)
            name = os.path.basename(f)
            dest = os.path.join(folder, name)
            if os.path.exists(dest) and os.path.abspath(dest) != os.path.abspath(f):
                stem, ext = os.path.splitext(name)
                n = 2
                while os.path.exists(os.path.join(folder, f'{stem} {n}{ext}')):
                    n += 1
                name = f'{stem} {n}{ext}'; dest = os.path.join(folder, name)
            if os.path.abspath(dest) != os.path.abspath(f):
                shutil.copyfile(f, dest)
        except OSError as e:
            messagebox.showerror('Panel Generator', f"Couldn't copy the picture into the Front Panel folder ({e})"); return
        x1, y1, x2, y2 = self.pv['panel_box']
        cx, cy = at or ((x1 + x2) / 2, (y1 + y2) / 2)
        self.vars['pictures_on'].set(True)
        self.ui.setdefault('images', []).append(dict(id=uuid.uuid4().hex[:8], file=name, x=round(cx, 2),
                                                     y=round(cy, 2), w=round(min(20.0, (x2 - x1) / 4), 1)))
        self.persist_ui(); self.update_preview()
        self.hover.config(text='Picture added - drag it into place; change its size and turn it on the left.')

    def image_size(self, iid):
        from tkinter import simpledialog
        o = self.own_image(iid)
        if not o:
            return
        v = simpledialog.askfloat('Picture size', 'Width in mm (the height follows):', initialvalue=float(o['w']),
                                  minvalue=1, maxvalue=500, parent=self)
        if v:
            o['w'] = round(v, 2); self.persist_ui(); self.update_preview()

    def image_turn(self, iid, deg):
        o = self.own_image(iid)
        if o:
            o['rot'] = round((float(o.get('rot', 0)) + deg) % 360, 2); self.persist_ui(); self.update_preview()

    def image_invert(self, iid):
        o = self.own_image(iid)
        if o:
            o['invert'] = not o.get('invert', False); self.persist_ui(); self.update_preview()

    def image_delete(self, iid):
        self.ui['images'] = [i for i in self.ui.get('images', []) if i['id'] != iid]
        self.persist_ui(); self.update_preview()

    def own_text(self, fid):
        return next((t for t in self.ui.get('texts', []) if 'text:' + t['id'] == fid), None)

    def move_target(self, t, dx, dy, save=True):
        _, kind, d = t
        if kind == 'text':
            o = self.own_text(d['fid'])
            if o:
                o['x'] = round(o['x'] + dx, 2); o['y'] = round(o['y'] + dy, 2)
        elif kind == 'art':
            self.ui.setdefault('art_pos', {})[d['key']] = [round(d['at'][0] + dx, 2), round(d['at'][1] + dy, 2)]
        elif kind == 'image':
            o = self.own_image(d['id'])
            if o:
                o['x'] = round(o['x'] + dx, 2); o['y'] = round(o['y'] + dy, 2)
        elif kind == 'shape':
            for o in self.ui.get('shapes', []):
                if o['id'] in self.shape_sel:
                    o['x'] = round(o['x'] + dx, 3); o['y'] = round(o['y'] + dy, 3)
        elif kind == 'line':
            o = self.own_line(d['id'])
            if o:
                for k, m in (('x1', dx), ('y1', dy), ('x2', dx), ('y2', dy)):
                    o[k] = round(o[k] + m, 3)
        elif kind == 'tab' and d['kind'] == 'mark':
            pass                                       # a shape stays round its hole
        elif kind == 'tab':                            # a box round text: everything in it moves with it
            for fid in d.get('members', []):
                o = self.own_text(fid)
                if o:
                    o['x'] = round(o['x'] + dx, 2); o['y'] = round(o['y'] + dy, 2)
                else:
                    e = self.ui['label_edits'].setdefault(fid, {})
                    e['dx'] = round(e.get('dx', 0.0) + dx, 3); e['dy'] = round(e.get('dy', 0.0) + dy, 3)
            if d.get('anchor') == 'auto':
                g = self.ui['label_edits'].setdefault(d['key'], {})
                g['ox'] = round(g.get('ox', 0.0) + dx, 3); g['oy'] = round(g.get('oy', 0.0) + dy, 3)
        else:
            e = self.ui['label_edits'].setdefault(d['fid'], {})
            e['dx'] = round(e.get('dx', 0.0) + dx, 3); e['dy'] = round(e.get('dy', 0.0) + dy, 3)
        if save:
            self.persist_ui(); self.update_preview()

    # ------------------------------------------------------------------ several things at once
    def in_group(self, t):
        return (t[1] == 'shape' and t[2]['id'] in self.shape_sel) or (t[1] in MULTI and self.sel_key(t) in self.multi)

    def group_size(self):
        return len(self.multi) + len(self.shape_sel)

    def group_targets(self):
        """Everything picked: each hole you added, and each text, label, line or picture in the multi-selection."""
        keys = set(self.multi)
        return [t for t in getattr(self, 'targets', []) if (t[1] in MULTI and self.sel_key(t) in keys)
                or (t[1] == 'shape' and t[2]['id'] in self.shape_sel)]

    def nudge(self, e, ax, ay):
        """Arrow keys: move what's selected 0.1 mm (1 mm with Shift), with no snapping."""
        if not self.pv or 'message' in self.pv:
            return
        step = 1.0 if getattr(e, 'state', 0) & 0x0001 else 0.1
        dx, dy = round(ax * step, 3), round(ay * step, 3)
        if self.group_size() > 1:
            self.move_group(dx, dy)
        elif self.shape_sel:
            t = next((t for t in self.targets if t[1] == 'shape' and t[2]['id'] in self.shape_sel), None)
            if t:
                self.move_target(t, dx, dy)
        else:
            t = self.selected_target()
            if not t or (t[1] == 'tab' and t[2].get('kind') == 'mark'):
                return
            self.move_target(t, dx, dy)
        self.hover.config(text=f"Moved {step:g} mm  ·  arrow keys: 0.1 mm, with Shift 1 mm")
        return 'break'

    def move_group(self, dx, dy):
        moved_shapes = False
        for t in self.group_targets():
            if t[1] == 'shape':
                if not moved_shapes:                   # (one call moves every hole you picked)
                    self.move_target(t, dx, dy, save=False); moved_shapes = True
            else:
                self.move_target(t, dx, dy, save=False)
        self.persist_ui(); self.update_preview()

    def context_menu(self, e):
        t = self.target_at(e)
        if not t:
            if not self.pv or 'message' in self.pv or not getattr(self, 'cur_view', None):
                return
            x, y = self.to_mm(e)
            m = tk.Menu(self, tearoff=0)
            sh = self.hole_at(x, y)
            if sh:                                     # on a hole: shapes round it, and the part's size
                self.mark_menu(m, sh)
                self.body_menu(m, sh)
                m.tk_popup(e.x_root, e.y_root)
                return
            def here_text():
                dx, dy, _, _ = self.snap(((x, y, x, y), 'new', None), 0, 0)
                self.add_text_at(x + dx, y + dy)
            if self.clip:
                m.add_command(label='Paste here', command=lambda: self.paste(at=(x, y)))
                m.add_separator()
            m.add_command(label='Add text here…', command=here_text)
            m.add_command(label='Add picture here…', command=lambda: self.add_picture(at=(x, y)))
            m.add_separator()
            try:
                m.add_command(label=f'Add {self.hole_dia():g} mm hole here', command=lambda: self.add_shape_at('hole', x, y))
            except ValueError:
                pass
            m.add_command(label='Add rectangle here', command=lambda: self.add_shape_at('rect', x, y))
            m.add_command(label='Add slot here', command=lambda: self.add_shape_at('slot', x, y))
            if self.undo_stack:
                m.add_separator(); m.add_command(label='Undo', command=self.undo)
            m.tk_popup(e.x_root, e.y_root)
            return
        _, kind, d = t
        m = tk.Menu(self, tearoff=0)
        if kind == 'shape':
            if d['id'] not in self.shape_sel:
                self.shape_sel = [d['id']]; self.sel = None
                self.draw(); self.show_selected(); self.show_shapes()
            n = len(self.shape_sel)
            sh = next((x for x in self.pv.get('shapes', []) if x.get('anchor') == 'add:' + d['id']), None)
            if sh and n == 1:
                self.mark_menu(m, sh); self.body_menu(m, sh); m.add_separator()
            m.add_command(label='Copy alongside' if n == 1 else f'Copy these {n} alongside', command=self.shapes_duplicate)
            m.add_command(label='Delete' if n == 1 else f'Delete these {n}', command=self.shapes_delete)
        elif kind == 'text':
            m.add_command(label='Change text…', command=lambda: self.text_change(d['fid']))
            m.add_command(label='Text size…', command=lambda: self.text_size(d['fid']))
            m.add_command(label='Delete', command=lambda: self.text_delete(d['fid']))
        elif kind == 'image':
            m.add_command(label='Size…', command=lambda: self.image_size(d['id']))
            m.add_command(label='Turn 90° clockwise', command=lambda: self.image_turn(d['id'], 90))
            m.add_command(label='Print the light parts instead' if not d.get('invert') else 'Print the dark parts',
                          command=lambda: self.image_invert(d['id']))
            m.add_command(label='Delete', command=lambda: self.image_delete(d['id']))
        elif kind == 'art' and str(d['key']).startswith('title:'):
            m.add_command(label='Delete this copy of the title', command=lambda: self.title_delete(d['key']))
        elif kind == 'art':
            m.add_command(label=f"Put the {d['what']} back in its automatic place", state='normal' if d.get('pinned') else 'disabled',
                          command=lambda: (self.ui['art_pos'].pop(d['key'], None), self.persist_ui(), self.update_preview()))
        elif kind == 'line':
            m.add_command(label='Delete line', command=lambda: self.line_delete(d['id']))
        elif kind == 'tab' and d['kind'] == 'mark':
            m.add_command(label='Back to its own size', command=lambda: (self.ui['label_edits'].pop(d['key'], None),
                                                                         self.persist_ui(), self.update_preview()))
            m.add_command(label='Delete shape', command=lambda: self.mark_delete(d['key']))
        elif kind == 'tab':
            m.add_command(label='Back to its own size', command=lambda: (self.ui['label_edits'].pop(d['key'], None),
                                                                         self.persist_ui(), self.update_preview()))
        else:
            if not str(d['fid']).startswith('tabword:'):
                m.add_command(label='Change text…', command=lambda: self.label_change(d))
            m.add_command(label='Edit labels…', command=lambda: (self.edit_labels(), self.editor.focus_row(d['fid'])))
            m.add_command(label='Put it back where it was', command=lambda: self.label_reset(d['fid']))
            m.add_command(label='Hide this label', command=lambda: self.label_hide(d['fid']))
        m.tk_popup(e.x_root, e.y_root)

    def label_change(self, d):
        """A label that came from the PCB: type what the panel should say instead (the PCB isn't changed)."""
        from tkinter import simpledialog
        txt = simpledialog.askstring('Change text', f"Text for {d.get('ref', 'this label')}:", initialvalue=d.get('text', ''), parent=self)
        if txt is not None and txt.strip() and txt.strip() != d.get('text'):
            self.ui['label_edits'].setdefault(d['fid'], {})['text'] = txt.strip()
            self.persist_ui(); self.update_preview()

    def text_change(self, fid):
        from tkinter import simpledialog
        o = self.own_text(fid)
        if not o:
            return
        txt = simpledialog.askstring('Change text', 'Text:', initialvalue=o['text'], parent=self)
        if txt is not None and txt.strip():
            o['text'] = txt.strip(); self.persist_ui(); self.update_preview()

    def text_size(self, fid):
        from tkinter import simpledialog
        o = self.own_text(fid)
        if not o:
            return
        cur = o.get('size') or self.vars['label_size'].get()
        v = simpledialog.askfloat('Text size', 'Height in mm (blank = the label size):', initialvalue=float(cur),
                                  minvalue=0.8, maxvalue=30, parent=self)
        if v:
            o['size'] = round(v, 2); self.persist_ui(); self.update_preview()

    def text_delete(self, fid):
        self.ui['texts'] = [t for t in self.ui.get('texts', []) if 'text:' + t['id'] != fid]
        self.persist_ui(); self.update_preview()

    def label_reset(self, fid):
        e = self.ui['label_edits'].get(fid, {})
        e.pop('dx', None); e.pop('dy', None)
        if not e:
            self.ui['label_edits'].pop(fid, None)
        self.persist_ui(); self.update_preview()

    def label_hide(self, fid):
        self.ui['label_edits'].setdefault(fid, {})['hide'] = True
        self.persist_ui(); self.update_preview()

    def show_hover(self, s):
        b = s['geom'].bounds
        w, h = b[2] - b[0], b[3] - b[1]
        size = f'⌀{w:.2f} mm' if abs(w - h) < 0.01 and s['rule'] not in ('slot',) and 'slot' not in s['rule'] else f'{w:.2f} × {h:.2f} mm'
        state = {'ok': '', 'warn': '  ·  too close to something (see Result)', 'error': '  ·  problem (see Result)'}[s['status']]
        who = 'your own cutout in the panel' if s['manual'] else s['rule']
        parts = [s['label']] + ([who] if who.lower() not in s['label'].lower() else []) + [size]
        if str(s.get('key') or '').startswith('add:'):
            parts.append('drag to move, click to change it on the left')
        self.hover.config(text='  ·  '.join(parts) + state)

    # ------------------------------------------------------------------ generate
    def generate(self, restore=(), gerbers=False, open_after=None):
        try:
            args = self.build_args(restore) + (['--gerbers'] if gerbers else [])
        except ValueError as e:
            messagebox.showerror('Panel Generator', str(e))
            return
        board = args[0]
        panel, _ = panel_paths(board)
        if os.path.exists(lock_file(panel)):
            if not messagebox.askyesno('Panel Generator',
                                       f"{os.path.basename(panel)} is open in KiCad.\n\n"
                                       "Close it there first - otherwise saving it in KiCad later will undo this.\n\n"
                                       "Generate anyway?"):
                return
        notes = []
        if os.path.exists(lock_file(board)):
            notes.append(('WARN', "The PCB is open in KiCad - only what's SAVED is used. If you changed it, save it and generate again.\n"))
        self.config(cursor='watch'); self.update()
        try:
            code, text = self.run_engine(args)
        finally:
            self.config(cursor='')
        self.result_is_preview = False
        self.show_result(text, notes, code)
        self.note_guides(text.splitlines())
        errs = [l.strip()[5:].strip() for l in text.splitlines() if l.strip().startswith('ERROR')]
        if errs:
            messagebox.showwarning('Panel Generator',
                                   f"{len(errs)} problem(s) to fix before sending this panel to the fab:\n\n"
                                   + '\n\n'.join('- ' + e for e in errs[:6]) + ('\n\n…and more, see Result.' if len(errs) > 6 else ''))
        mem = load_json(panel_paths(board)[1])
        if mem:
            self.ui = {'ignore': dict(mem.get('ignore_uncut', {})), 'label_edits': dict(mem.get('label_edits', {})),
                       'texts': [dict(t) for t in mem.get('texts', [])], 'art_pos': dict(mem.get('art_pos', {})),
                       'images': [dict(i) for i in mem.get('images', [])],
                       'shapes': [dict(i) for i in mem.get('shapes', [])],
                       'lines': [dict(i) for i in mem.get('lines', [])],
                       'marks': [dict(i) for i in mem.get('marks', [])],
                       'bodies': [dict(i) for i in mem.get('bodies', [])],
                       'titles': [dict(i) for i in mem.get('titles', [])]}
            self.state_prev = self.snapshot()          # keep the history; changes made in KiCad become the new start
        self.fill_restore()
        panel, _ = panel_paths(board)
        self.stamp = (mtime(board), mtime(panel), mtime(self.art_file()))
        if code in (0, 1):
            self.cfg.setdefault('generated', {})[os.path.normpath(board)] = self.fingerprint()
        self.cfg['last_board'] = board
        self.cfg['open_after'] = self.vars['open'].get()
        self.save_cfg()
        keep = self.result_is_preview
        self.update_preview()
        self.result_is_preview = keep
        zipped = next((l.split('->', 1)[1].strip() for l in text.splitlines() if l.strip().startswith('gerb ')), None)
        if gerbers and zipped:
            if messagebox.askyesno('Panel Generator', f"Gerbers are ready:\n\n{os.path.basename(zipped)}\n\n"
                                                      "Upload that zip to your PCB maker. Show the folder now?"):
                self.open_folder()
            return
        if code in (0, 1) and (self.vars['open'].get() if open_after is None else open_after) and os.path.exists(panel):
            self.open_panel(panel)

    def show_result(self, text, notes, code, preview=False):
        lines = []
        for line in text.splitlines():
            line = re.sub(r'(?:[A-Za-z]:)?[\\/].*[\\/]([^\\/]+?\.(?:kicad_pcb|svg))', r'\1', line)
            s = line.strip()
            if preview and not s.startswith(('ERROR', 'WARN', 'CHECK', 'NOTE')):
                continue
            tag = next((t for t in ('ERROR', 'WARN', 'CHECK', 'NOTE') if s.startswith(t)), None)
            if s.startswith('panelgen '):
                tag = 'head'
            elif s.startswith(('gone', 'edit', 'restore', 'drawn', 'slot', 'eurorack', 'gerb', 'drc')):
                tag = 'ok'
            lines.append((tag, line.strip() + '\n' if preview else line + '\n'))
        warned = any(t == 'WARN' for t, _ in lines)
        unc = any(l.strip().startswith('CHECK no cutout') for _, l in lines)
        if preview:
            head = ('dim', 'Checks on the preview (the panel file only changes when you click Generate panel):\n\n')
            tail = [] if lines else [('ok', 'No problems.\n')]
            self.write([head] + lines + tail, clear=True)
            return
        summary = ('WARN', 'Done, with warnings above - check them, but the panel can still be made.\n') if code == 0 and warned else \
                  ('WARN', 'Done - but some parts have no cutout (CHECK above). Make sure none of them go through the panel.\n') if code == 0 and unc else \
                  ('ok', 'Done. No problems.\n') if code == 0 else \
                  ('ERROR', 'Done, but there are ERRORs above - fix those before sending the panel to the fab.\n') if code == 1 else \
                  ('ERROR', 'Could not generate the panel.\n')
        self.write(notes + lines + [(None, '\n'), summary], clear=True)

    def toggle_notes(self):
        self.notes_open = not self.notes_open
        self.write(self.last_parts, clear=True)

    def write(self, parts, clear=False):
        if clear:
            self.last_parts = list(parts)
        else:
            self.last_parts += list(parts)
        notes = [p for p in self.last_parts if p[0] == 'NOTE']
        self.out.configure(state='normal')
        self.out.delete('1.0', 'end')
        shown_fold = False
        for tag, text in self.last_parts:
            if tag == 'NOTE':
                if not shown_fold:
                    shown_fold = True
                    label = (f"▾ hide {len(notes)} note{'s' if len(notes) > 1 else ''}" if self.notes_open
                             else f"▸ {len(notes)} note{'s' if len(notes) > 1 else ''} (nothing to fix - click to read)")
                    self.out.insert('end', label + '\n', 'fold')
                if self.notes_open:
                    self.out.insert('end', text, 'NOTE')
                continue
            self.out.insert('end', text, tag or ())
        self.out.see('1.0' if clear else 'end')
        self.out.configure(state='disabled')

    def restore(self):
        sel = [self.restore_refs[i] for i in self.restore_list.curselection() if i < len(self.restore_refs)]
        if not sel:
            messagebox.showinfo('Panel Generator', 'Select one or more items in the list first.')
            return
        for kind, fid in sel:
            if kind == 'ignore':
                self.ui['ignore'].pop(fid, None)
        self.persist_ui()
        holes = [ref for kind, ref in sel if kind == 'hole']
        if holes:
            self.generate(restore=holes)
        else:
            self.fill_restore(); self.update_preview()

    # ------------------------------------------------------------------ undo: settings on the left and changes in the preview
    def snapshot(self):
        import copy
        return copy.deepcopy(self.ui), {k: v.get() for k, v in self.vars.items()}

    def reset_undo(self):
        self.undo_stack, self.state_prev, self.restoring = [], self.snapshot(), False
        if hasattr(self, 'w_undo'):
            self.w_undo.state(['disabled'])

    def record_state(self):
        """Remember how things were before this change, so Undo can put them back."""
        if getattr(self, 'restoring', False) or self.loading or getattr(self, 'state_prev', None) is None:
            return
        cur = self.snapshot()
        if cur != self.state_prev:
            self.undo_stack.append(self.state_prev)
            del self.undo_stack[:-50]
            if hasattr(self, 'w_undo'):
                self.w_undo.state(['!disabled'])
        self.state_prev = cur

    def undo(self, _=None):
        """Take back the last change: a setting on the left, or a move, text, picture, box or label edit in the preview."""
        if _ is not None and isinstance(self.focus_get(), (ttk.Entry, tk.Entry, ttk.Combobox)):
            return                                     # Ctrl+Z in a text box undoes the typing, not this
        self.record_state()                            # a change still waiting for the preview counts too
        if not getattr(self, 'undo_stack', None):
            return
        import copy
        ui, vals = self.undo_stack.pop()
        self.restoring, self.loading = True, True
        try:
            for k, val in vals.items():
                if k in self.vars and self.vars[k].get() != val:
                    self.vars[k].set(val)
            self.ui = copy.deepcopy(ui)
        finally:
            self.loading = False
        self.state_prev = self.snapshot()
        self.persist_ui(record=False)
        if not self.undo_stack:
            self.w_undo.state(['disabled'])
        self.sel = None; self.shape_sel = []; self.body_sel = None
        if self.after_id:
            self.after_cancel(self.after_id); self.after_id = None
        self.refresh_states()
        self.update_preview()
        self.restoring = False

    def save_settings(self, settings):
        """The settings on the left, saved into the panel's memory file as you change them - not only when you generate -
        so closing the window never loses them."""
        b = self.board.get()
        if not settings or not b:
            return
        mem_path = panel_paths(b)[1]
        mem = load_json(mem_path)
        if not mem or mem.get('settings') == settings:
            return               # no panel yet (saved with the first Generate), or nothing changed
        mem['settings'] = settings
        try:
            with open(mem_path, 'w', encoding='utf-8') as f:
                json.dump(mem, f, indent=1)
        except OSError:
            pass

    def persist_ui(self, record=True):
        """Save ignored parts and label edits into the panel's memory file straight away (if there is one yet)."""
        if record:
            self.record_state()
        b = self.board.get()
        if not b:
            return
        mem_path = panel_paths(b)[1]
        mem = load_json(mem_path)
        if not mem:
            return               # no panel yet: saved with the first Generate
        mem['ignore_uncut'] = self.ui['ignore']; mem['label_edits'] = self.ui['label_edits']
        mem['texts'] = self.ui.get('texts', []); mem['art_pos'] = self.ui.get('art_pos', {}); mem['images'] = self.ui.get('images', [])
        mem['shapes'] = self.ui.get('shapes', [])
        mem['lines'] = self.ui.get('lines', [])
        mem['titles'] = self.ui.get('titles', [])
        mem['marks'] = self.ui.get('marks', [])
        mem['bodies'] = self.ui.get('bodies', [])
        mem['fresh'] = bool(self.ui.get('fresh'))
        try:
            with open(mem_path, 'w', encoding='utf-8') as f:
                json.dump(mem, f, indent=1)
        except OSError:
            pass

    def ignore_part(self, ref, fid):
        if messagebox.askyesno('Panel Generator',
                               f"{ref} has no cutout.\n\nIs that right - it stays behind the panel?\n\n"
                               "Yes stops the warning for this part. It's listed under 'Holes you removed or changed', "
                               "so you can bring the warning back."):
            self.ui['ignore'][fid] = ref
            self.persist_ui(); self.fill_restore(); self.update_preview()

    def edit_labels(self):
        if not self.vars['labels_on'].get():
            self.vars['labels_on'].set(True); self.refresh_states(); self.update_preview()
        if self.editor and self.editor.winfo_exists():
            self.editor.lift(); self.editor.refresh(); return
        self.editor = LabelEditor(self)

    def open_saved_panel(self):
        b = self.board.get()
        panel = panel_paths(b)[0] if b else None
        if not (panel and os.path.exists(panel)):
            if messagebox.askyesno('Panel Generator', 'There is no panel yet. Generate it now and open it in KiCad?'):
                self.generate(open_after=True)
            return
        if self.out_of_date():
            ans = messagebox.askyesnocancel(
                'Panel Generator',
                "The panel is out of date - a setting, the PCB or the artwork has changed since it was generated.\n\n"
                "Generate it first?\n\n"
                "Yes - generate the panel, then open it\n"
                "No - open the old panel as it is\n"
                "Cancel - do nothing")
            if ans is None:
                return
            if ans:
                self.generate(open_after=True)
                return
        self.open_panel(panel)

    def out_of_date(self):
        """True when the saved panel was made from different settings, PCB or artwork than now."""
        b = self.board.get()
        rec = self.cfg.get('generated', {}).get(os.path.normpath(b)) if b else None
        return bool(rec) and rec != self.fingerprint()

    def open_panel(self, panel):
        try:
            kicad = find_kicad()
            if kicad:
                subprocess.Popen([kicad, panel])
            elif hasattr(os, 'startfile'):
                os.startfile(panel)
        except OSError as e:
            self.write([('WARN', f"Couldn't open KiCad automatically ({e}). Open {panel} yourself.\n")])

    def fingerprint(self):
        """What the panel depends on: the settings, and the saved PCB and artwork files."""
        try:
            args = self.build_args()
        except ValueError:
            return None
        return json.dumps([args[1:], mtime(args[0]), mtime(self.art_file()) if self.vars['art_on'].get() else None])

    def show_status(self):
        b = self.board.get()
        if not b or not os.path.exists(b):
            self.status.config(text=''); return
        panel = panel_paths(b)[0]
        if not os.path.exists(panel):
            self.status.config(text='No panel yet', fg=C_DIM); return
        import time
        rec = self.cfg.get('generated', {}).get(os.path.normpath(b))
        when = time.strftime('%H:%M', time.localtime(mtime(panel)))
        if time.strftime('%d%m%y', time.localtime(mtime(panel))) != time.strftime('%d%m%y'):
            when += time.strftime(' %d %b', time.localtime(mtime(panel)))
        if not rec:
            self.status.config(text=f'Panel saved {when}', fg=C_DIM)
        elif rec == self.fingerprint():
            self.status.config(text=f'✓ Up to date  ·  {when}', fg=C_OK_TXT)
        else:
            self.status.config(text='● Changed - generate again', fg=C_WARN_TXT)

    def save_cfg(self):
        try:
            os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
            with open(CONFIG, 'w', encoding='utf-8') as f:
                json.dump(self.cfg, f, indent=1)
        except OSError:
            pass


class LabelEditor(tk.Toplevel):
    """Table of every label: show/hide, change the text, put it above or below, undo a move."""
    COLS = ('show', 'part', 'text', 'pos', 'gap', 'art', 'moved', 'src')

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title('Edit labels'); self.geometry('1150x520'); self.transient(app)
        f = ttk.Frame(self, padding=12); f.pack(fill='both', expand=True)
        ttk.Label(f, text='Labels', style='Head.TLabel').pack(anchor='w')
        ttk.Label(f, text='Click the tick to show or hide a label  ·  double-click the text to change it  ·  click Position to '
                          'switch above/below  ·  double-click Gap to set the gap for one label (blank = the main setting)  ·  click Artwork to change the scale of a pot or mark a jack as output or input  ·  labels you move in KiCad keep their place: click Moved to put one back',
                  style='Dim.TLabel', wraplength=1120, justify='left').pack(anchor='w', pady=(2, 8))
        tf = ttk.Frame(f); tf.pack(fill='both', expand=True)
        t = self.tree = ttk.Treeview(tf, columns=self.COLS, show='headings', selectmode='browse')
        for col, txt, w, anchor in (('show', 'Show', 50, 'center'), ('part', 'Part', 120, 'w'), ('text', 'Label text', 220, 'w'),
                                    ('pos', 'Position', 90, 'center'), ('gap', 'Gap', 80, 'center'), ('art', 'Artwork', 110, 'center'), ('moved', 'Moved', 90, 'center'), ('src', 'Text came from', 330, 'w')):
            t.heading(col, text=txt); t.column(col, width=w, anchor=anchor, stretch=(col == 'text'))
        sb = ttk.Scrollbar(tf, command=t.yview); t.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y'); t.pack(fill='both', expand=True)
        t.bind('<Button-1>', self.click); t.bind('<Double-1>', self.dclick)
        b = ttk.Frame(f); b.pack(fill='x', pady=(10, 0))
        ttk.Button(b, text='Undo all my label changes', command=self.reset_all).pack(side='left')
        ttk.Button(b, text='Close', command=self.destroy).pack(side='right')
        self.refresh()

    def rows(self):
        return {r['fid']: r for r in (self.app.pv or {}).get('label_rows', [])}

    def refresh(self):
        t = self.tree
        sel = t.selection()
        t.delete(*t.get_children())
        for r in sorted(self.rows().values(), key=lambda r: self.app.pg.natkey(r['ref'])):
            moved = 'moved ↺' if (r['dx'] or r['dy']) else ''
            pos = {'': 'auto', 'above': 'above', 'below': 'below'}[r['pos'] or '']
            text = r['text'] if r['text'].strip() else '(no text - double-click to add)'
            src = 'you' if r['text'] != r['guess'] else (r['source'] or '-')
            sk = r.get('skipped') or ('', '')
            if src == '-' and sk[0]:
                src = f'not used: "{sk[0]}" {sk[1]}'
            gap = f"{r['gap']:g} mm" if r.get('gap') is not None else 'auto'
            art = ''
            if r.get('kind') == 'pot':
                art = {None: 'scale: auto', 'none': 'no scale', 'ticks': 'ticks', 'numbers': '0-10',
                       'bipolar': '- 0 +'}.get(r.get('scale'), 'scale: auto')
            elif r.get('kind') == 'jack':
                art = {None: 'auto', 'out': 'output', 'in': 'input'}.get(r.get('io'), 'auto')
            t.insert('', 'end', iid=r['fid'], values=('☐' if r['hide'] else '☑', r['ref'], text, pos, gap, art, moved, src))
        if sel and t.exists(sel[0]):
            t.selection_set(sel[0])

    def focus_row(self, fid):
        self.refresh()
        if self.tree.exists(fid):
            self.tree.selection_set(fid); self.tree.see(fid)

    def edit(self, fid, **changes):
        e = dict(self.app.ui['label_edits'].get(fid, {}))
        for k, val in changes.items():
            if k in ('gap', 'scale', 'io'):
                if val is None:
                    e.pop(k, None)
                else:
                    e[k] = val
            elif val in (None, '', False, 0, 0.0) and k != 'text':
                e.pop(k, None)
            elif k == 'text' and val is None:
                e.pop('text', None)
            else:
                e[k] = val
        if e:
            self.app.ui['label_edits'][fid] = e
        else:
            self.app.ui['label_edits'].pop(fid, None)
        self.app.persist_ui(); self.app.update_preview()

    def click(self, ev):
        t = self.tree
        fid, col = t.identify_row(ev.y), t.identify_column(ev.x)
        if not fid:
            return
        r = self.rows()[fid]
        if col == '#1':
            self.edit(fid, hide=not r['hide'])
        elif col == '#4':
            nxt = {'': 'above', 'above': 'below', 'below': ''}[r['pos'] or '']
            self.edit(fid, pos=nxt)
        elif col == '#6' and r.get('kind') == 'pot':
            seq = [None, 'ticks', 'numbers', 'bipolar', 'none']
            self.edit(fid, scale=seq[(seq.index(r.get('scale')) + 1) % len(seq)] if r.get('scale') in seq else 'ticks')
        elif col == '#6' and r.get('kind') == 'jack':
            seq = [None, 'out', 'in']
            self.edit(fid, io=seq[(seq.index(r.get('io')) + 1) % len(seq)] if r.get('io') in seq else 'out')
        elif col == '#7' and (r['dx'] or r['dy']):
            self.edit(fid, dx=0, dy=0)

    def dclick(self, ev):
        t = self.tree
        fid, col = t.identify_row(ev.y), t.identify_column(ev.x)
        if not fid or col not in ('#3', '#5'):
            return
        r = self.rows()[fid]
        x, y, w, h = t.bbox(fid, col)
        e = ttk.Entry(t); e.place(x=x, y=y, width=w, height=h)
        e.insert(0, r['text'] if col == '#3' else ('' if r.get('gap') is None else f"{r['gap']:g}"))
        e.select_range(0, 'end'); e.focus_set()
        def done(_=None, save=True):
            if save and col == '#3':
                new = e.get()
                self.edit(fid, text=None if new == r['guess'] else new)
            elif save:
                v = e.get().strip().replace('mm', '').strip()
                try:
                    self.edit(fid, gap=None if v in ('', 'auto') else max(-20.0, min(50.0, float(v))))
                except ValueError:
                    messagebox.showerror('Edit labels', f"'{v}' isn't a number. Type a gap in mm, or leave it blank "
                                         "to use the main Gap setting.", parent=self)
            e.destroy()
        e.bind('<Return>', done); e.bind('<FocusOut>', done); e.bind('<Escape>', lambda _: done(save=False))

    def reset_all(self):
        if messagebox.askyesno('Edit labels', 'Undo every label change - text, hidden, position, gap, artwork and moves - for this board?', parent=self):
            self.app.ui['label_edits'] = {}
            self.app.persist_ui(); self.app.update_preview()


if __name__ == '__main__':
    if '--selftest' in sys.argv:         # used by the build: does the packaged app start, with its proper look?
        os.environ['APPDATA'] = os.path.abspath('selftest_appdata')
        CONFIG = os.path.join(os.environ['APPDATA'], 'panelgen', 'gui.json')
        try:
            app = App(None); app.update()
            ok, why = app.themed, getattr(app, 'theme_error', '')
            app.destroy()
        except Exception:
            ok, why = False, traceback.format_exc()
        open('selftest.txt', 'w', encoding='utf-8').write(('ok' if ok else 'FAIL') + '\n' + why)
        sys.exit(0 if ok else 3)
    App(sys.argv[1] if len(sys.argv) > 1 else None).mainloop()
