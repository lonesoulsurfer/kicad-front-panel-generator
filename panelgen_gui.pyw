#!/usr/bin/env python3
"""Panel Generator - a window for panelgen. Double-click to run (or: py panelgen_gui.pyw [board.kicad_pcb])."""
import contextlib, glob, io, json, os, re, subprocess, sys, traceback
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
    'Minimal': dict(scale='Ticks', rings=False, outputs=False, border=False, groups=False, tabs=False),
    'Classic synth': dict(scale='Numbers 0-10', rings=True, outputs=False, border=True, groups=True, tabs=True),
    'Modular': dict(scale='Ticks', rings=False, outputs=True, border=False, groups=False, tabs=True),
}
STYLE_KEYS = ('scale', 'rings', 'outputs', 'border', 'groups', 'tabs')
TITLE_DIRS = {'Across': 'off', 'Stacked': 'stacked', 'On its side': 'on'}
SCALES = {'None': 'none', 'Ticks': 'ticks', 'Numbers 0-10': 'numbers', 'Centre zero (- 0 +)': 'bipolar'}
KICAD_FONT = "KiCad's own font"
HOLE_SIZES = ('3.2  ·  3 mm LED or M3 screw', '5.2  ·  5 mm LED or small toggle', '6.2  ·  3.5 mm jack', '6.5  ·  mini toggle switch',
              '7.5  ·  pot or encoder', '10  ·  6.35 mm jack', '2.7  ·  M2.5 screw', '2.2  ·  M2 screw')
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
        v['extras_on'] = tk.BooleanVar(value=True)
        v['auto_on'] = tk.BooleanVar(); v['art_style'] = tk.StringVar(value='Classic synth')
        v['art_scale'] = tk.StringVar(value='Ticks'); v['art_rings'] = tk.BooleanVar(value=True)
        v['art_outputs'] = tk.BooleanVar(); v['art_border'] = tk.BooleanVar()
        v['art_groups'] = tk.BooleanVar(); v['art_tabs'] = tk.BooleanVar(); v['border_radius'] = tk.StringVar(value='0')
        v['border_gap'] = tk.StringVar(value='0'); v['ring_width'] = tk.StringVar(value='0.8'); v['ring_gap'] = tk.StringVar(value='0.8')
        v['art_title'] = tk.StringVar(); v['art_maker'] = tk.StringVar()
        v['title_size'] = tk.StringVar(value='5'); v['knob_size'] = tk.StringVar(value='13')
        v['title_dir'] = tk.StringVar(value='Across')
        v['labels_on'] = tk.BooleanVar(); v['label_pos'] = tk.StringVar(value='above')
        v['label_gap'] = tk.StringVar(value='1.5'); v['label_size'] = tk.StringVar(value='2')
        v['label_font'] = tk.StringVar(value=KICAD_FONT); v['label_bold'] = tk.BooleanVar(); v['label_caps'] = tk.BooleanVar()
        self.ui = {'ignore': {}, 'label_edits': {}, 'texts': [], 'art_pos': {}, 'images': [], 'shapes': []}   # ignored parts, label changes, your texts, moved title, pictures
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
        root.columnconfigure(1, weight=1); root.columnconfigure(0, minsize=530); root.rowconfigure(1, weight=1)


        bg = ttk.Style(self).lookup('TFrame', 'background') or C_BG
        lc = ttk.Frame(root); lc.grid(row=1, column=0, sticky='nsew', padx=(0, 10))
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
        cv = tk.Canvas(sc_, highlightthickness=0, width=520, bg=bg)
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
        left.bind('<Configure>', fit)
        cv.bind('<Configure>', lambda e: (cv.itemconfigure(win, width=e.width), fit()))
        def wheel(e):
            if lsb.winfo_manager():
                cv.yview_scroll(-1 if (getattr(e, 'delta', 0) > 0 or e.num == 4) else 1, 'units')
        wheels = ('<MouseWheel>', '<Button-4>', '<Button-5>')
        cv.bind('<Enter>', lambda e: [self.bind_all(x, wheel) for x in wheels])
        cv.bind('<Leave>', lambda e: [self.unbind_all(x) for x in wheels])
        self.left = left
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
        ttk.Combobox(c, textvariable=self.hole_size, values=HOLE_SIZES, width=28).pack(side='left')
        ttk.Label(c, text='mm').pack(side='left', padx=(4, 0))
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
        # labels
        s = self.section('labels', 'Labels', "A name next to each control, taken from the PCB.", switch='labels_on',
                         tip="Each part's text comes from its Label field if it has one, otherwise its Value or Reference "
                             "(e.g. 'Cutoff', 'Play'). Change, hide or move any of them in Edit labels.")
        h4 = ttk.Frame(s); h4.pack(fill='x')
        det = self.label_detail = ttk.Frame(h4); det.pack(fill='x')
        sub(det, 'Place', first=True)
        f = self.form(det)
        c = field(f, 'Position')
        ttk.Radiobutton(c, text='Above the hole', value='above', variable=v['label_pos']).pack(side='left', padx=(0, 12))
        ttk.Radiobutton(c, text='Below', value='below', variable=v['label_pos']).pack(side='left')
        c = field(f, 'Gap from the hole', 'Distance from the edge of the hole to the text. Keys in a merged switch slot follow '
                                          'their own side of the slot.')
        mm(c, 'label_gap')
        sub(det, 'Text')
        f = self.form(det)
        mm(field(f, 'Size'), 'label_size')
        c = field(f, 'Font', "KiCad's own font always works. Any other font has to be installed on the computer that opens the "
                             "panel (the gerbers carry the shapes, so the fab doesn't need it).")
        fonts = [KICAD_FONT] + sorted({x for x in tkfont.families() if not x.startswith('@')})
        ttk.Combobox(c, textvariable=v['label_font'], values=fonts, width=24, state='readonly').pack(side='left')
        c = field(f, 'Style')
        ttk.Checkbutton(c, text='Bold', variable=v['label_bold']).pack(side='left', padx=(0, 12))
        ttk.Checkbutton(c, text='ALL CAPS', variable=v['label_caps']).pack(side='left')
        sub(det, 'One at a time')
        f = self.form(det)
        c = field(f, 'Each label')
        bt = ttk.Button(c, text='Edit labels…', command=self.edit_labels); bt.pack(side='left')
        Tip(bt, 'A list of every label: change its text, hide it, set its own gap, or choose its artwork. '
                'You can also click a label in the preview.')

        # your own text and pictures, and whatever is selected in the preview
        s = self.section('extras', 'Your text and pictures', 'Things that are not on the PCB: what a key does, a logo.',
                         switch='extras_on',
                         tip="Switch off to leave them off the panel (and the preview) without losing them - switch on and "
                             "they're back. Handy when you change to Inkscape artwork that already has its own text.")
        f = self.form(s)
        row = self.extras_row = field(f, 'Add')
        bt = ttk.Button(row, text='Text…', command=self.start_add_text); bt.pack(side='left')
        Tip(bt, 'Click this, then click on the panel where the text goes. Drag any text, label, picture or the title to move '
                'it: it snaps into line with other labels, to the middle of holes and to the middle of gaps (hold Alt to '
                'place it freely).')
        bt = ttk.Button(row, text='Picture…', command=self.add_picture); bt.pack(side='left', padx=6)
        Tip(bt, 'A PNG, JPG or SVG (a glider, a logo...). Its dark parts print, transparent parts never do. It is copied into '
                'the Front Panel folder.')
        sub(s, 'Selected')
        self.sel_box = ttk.Frame(s); self.sel_box.pack(fill='x')
        self.sel = None
        self.show_selected()

        # artwork made for you
        s = self.section('auto', 'Artwork made for you', 'Scales, rings, boxes, a border and a title, drawn from your panel. '
                                                         'No Inkscape needed.', switch='auto_on',
                         tip='Everything is placed from the holes and labels on your panel, and checked against them. It also '
                             'goes into the Inkscape file on its own layer, so you can draw more on top if you like.')
        h6 = ttk.Frame(s); h6.pack(fill='x')
        det = self.auto_detail = ttk.Frame(h6); det.pack(fill='x')
        f = self.form(det)
        c = field(f, 'Style', 'Minimal: ticks round the pots. Classic synth: numbered scales, rings round buttons, a border. '
                              'Modular: ticks, and outputs in filled boxes (any jack whose label says OUT). '
                              'Change anything below after.')
        sc = ttk.Combobox(c, textvariable=v['art_style'], values=list(ART_STYLES) + ['Custom'], width=24, state='readonly')
        sc.pack(side='left')
        sc.bind('<<ComboboxSelected>>', lambda e: self.apply_style())
        sub(det, 'Title')
        f = self.form(det)
        ttk.Entry(field(f, 'Text'), textvariable=v['art_title'], width=27).pack(side='left')
        mm(field(f, 'Size'), 'title_size')
        c = field(f, 'Direction', 'Across, along the top. Stacked: the letters one under another, each the right way up. '
                                  'On its side: turned to read from the bottom. Drag it anywhere after.')
        ttk.Combobox(c, textvariable=v['title_dir'], values=list(TITLE_DIRS), width=24, state='readonly').pack(side='left')
        c = field(f, 'Maker name', 'Your name or brand, small, along the bottom. Leave empty for none.')
        ttk.Entry(c, textvariable=v['art_maker'], width=27).pack(side='left')
        sub(det, 'Pots')
        f = self.form(det)
        c = field(f, 'Scale', 'Marks round every pot, over a 300 degree turn. Change one pot (e.g. centre zero for a pan pot) '
                              'in Edit labels.')
        ttk.Combobox(c, textvariable=v['art_scale'], values=list(SCALES), width=24, state='readonly').pack(side='left')
        c = field(f, 'Knob size', 'Knob diameter: the scale and the label start outside it, so the knob never hides them.')
        mm(c, 'knob_size')
        sub(det, 'Buttons')
        f = self.form(det)
        c = field(f, 'Rings')
        ttk.Checkbutton(c, text='A ring round each push button', variable=v['art_rings'], command=self.refresh_states).pack(side='left')
        self.w_ringw = mm(field(f, 'Ring thickness', 'How thick the line of the ring is.'), 'ring_width')
        self.w_ringg = mm(field(f, 'Gap from the hole', 'Between the edge of the button hole and the ring.'), 'ring_gap')
        sub(det, 'Jacks and groups')
        f = self.form(det)
        c = field(f, 'Outputs', "Jacks whose label says OUT get a filled box with the label cut out of it - the usual way to "
                                "tell outputs from inputs. Set any jack to output or input in Edit labels.")
        ttk.Checkbutton(c, text='In filled boxes', variable=v['art_outputs']).pack(side='left')
        c = field(f, 'Edge jacks', "Jacks on the panel edge (no hole, the plug goes in from the side) get a filled tab hanging "
                                   "from the edge with their labels cut out. Neighbours share a tab; labels with the same first "
                                   "word (MIDI IN, MIDI OUT) become IN / OUT with MIDI underneath.")
        ttk.Checkbutton(c, text='In tabs on the edge', variable=v['art_tabs']).pack(side='left')
        c = field(f, 'Rows of controls', 'A box round 3 or more of the same control in a row or a column (pots, buttons, jacks), '
                                         'with their scales and labels inside. Left out (with a note) when it would run into '
                                         'another part, a label or the edge.')
        ttk.Checkbutton(c, text='A box round them', variable=v['art_groups']).pack(side='left')
        sub(det, 'Border')
        f = self.form(det)
        c = field(f, 'Border')
        ttk.Checkbutton(c, text='A line round the panel', variable=v['art_border'], command=self.refresh_states).pack(side='left')
        c = field(f, 'Gap from the edge', 'From the edge of the panel to the border. 0 = automatic: 1.5 mm, or just inside the '
                                          'case holes if there are any.')
        self.w_bgap = mm(c, 'border_gap', note='0 = automatic')
        c = field(f, 'Corner radius', '0 = the border follows the panel corners. Any other value rounds the border corners by that much.')
        self.w_bradius = mm(c, 'border_radius', note='0 = follows the panel')
        for k in ('art_scale', 'art_rings', 'art_border', 'art_outputs', 'art_groups', 'art_tabs'):
            v[k].trace_add('write', lambda *_: self.style_custom())

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

        self.left_end = ttk.Frame(left); self.left_end.pack(fill='x')

        # right: preview + result
        right = ttk.Frame(root); right.grid(row=1, column=1, sticky='nsew')
        root.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=5); right.rowconfigure(5, weight=1); right.columnconfigure(0, weight=1)
        ph = ttk.Frame(right); ph.grid(row=0, column=0, sticky='ew')
        ttk.Label(ph, text='Preview', style='Head.TLabel').pack(side='left')
        self.chip = tk.Label(ph, text='', font=self.f_head, padx=8, pady=1); self.chip.pack(side='left', padx=10)
        rb = ttk.Button(ph, text='Refresh', command=self.update_preview); rb.pack(side='right')
        fb = ttk.Button(ph, text='Fit', command=self.fit_view, width=5); fb.pack(side='right', padx=(0, 6))
        self.w_measure = ttk.Button(ph, text='Measure', command=self.toggle_measure, width=9)
        self.w_measure.pack(side='right', padx=(0, 6))
        Tip(self.w_measure, 'A ruler: click two points in the preview to see how far apart they are. It snaps to the middle '
                            'and edge of holes and to the panel edges (hold Alt for anywhere). Hold Ctrl to keep it dead level or straight up and down. Esc or click again to finish.')
        self.w_undo = ttk.Button(ph, text='Undo', command=self.undo, width=6); self.w_undo.pack(side='right', padx=(0, 6))
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
        self.bind_all('<Delete>', lambda e: None if typing() else self.shapes_delete())
        self.bind_all('<Control-d>', lambda e: None if typing() else self.shapes_duplicate())
        self.bind_all('<Escape>', self.escape)
        self.adding = False
        self.hover = ttk.Label(right, text='Hover over a cutout to see what it is.', style='Dim.TLabel')
        self.hover.grid(row=2, column=0, sticky='w', pady=(3, 0))
        self.legend(right).grid(row=2, column=0, sticky='e', pady=(3, 0))

        go = ttk.Frame(right); go.grid(row=3, column=0, sticky='ew', pady=(12, 0))
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
        ttk.Label(right, text='Result', style='Head.TLabel').grid(row=4, column=0, sticky='w', pady=(8, 4))
        outf = ttk.Frame(right); outf.grid(row=5, column=0, sticky='nsew')
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
            off = key in self.switches and key != 'extras' and not self.vars[self.switches[key]].get()
            shut = key in self.collapsed or off
            chev.config(text='▸' if shut else '▾')
            if shut and body.winfo_manager():          # (an empty frame keeps its old height, so the holder itself goes)
                body.pack_forget()
            elif not shut and not body.winfo_manager():
                body.pack(fill='x')

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

    def mm(self, cell, key, note=None):
        e = ttk.Entry(cell, textvariable=self.vars[key], width=7); e.pack(side='left')
        ttk.Label(cell, text='mm').pack(side='left', padx=(4, 0))
        if note:
            ttk.Label(cell, text=note, style='Dim.TLabel').pack(side='left', padx=(10, 0))
        return e

    TABS = {'panel': ('size', 'rail', 'case', 'holes', 'restore'), 'art': ('labels', 'extras', 'auto', 'art')}

    def show_tab(self, tab):
        if tab != self.tab:
            self.tab = tab
            self.left.master.yview_moveto(0)
        self.renumber()

    def renumber(self):
        """Show the sections of the tab you're on that apply to this kind of panel."""
        hide = {'size', 'case'} if self.mode == 'eurorack' else {'rail'}
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
        self.show(self.auto_detail, v['auto_on'].get(), fill='x')
        for w in self.extras_row.winfo_children():
            w.state(['!disabled'] if v['extras_on'].get() else ['disabled'])
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

    def apply_style(self):
        st = ART_STYLES.get(self.vars['art_style'].get())
        if not st:
            return
        self.applying_style = True
        try:
            v = self.vars
            v['art_scale'].set(st['scale']); v['art_rings'].set(st['rings'])
            v['art_outputs'].set(st['outputs']); v['art_border'].set(st['border'])
            v['art_groups'].set(st['groups']); v['art_tabs'].set(st['tabs'])
        finally:
            self.applying_style = False

    def style_custom(self):
        """Changing a single item by hand makes the style 'Custom'."""
        if getattr(self, 'applying_style', False) or self.loading:
            return
        st = ART_STYLES.get(self.vars['art_style'].get())
        v = self.vars
        if st and tuple(v['art_' + k].get() for k in STYLE_KEYS) != tuple(st[k] for k in STYLE_KEYS):
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

    def board_changed(self):
        board = self.board.get()
        self.guides_at = None
        self.show_boards()
        if not board or not os.path.exists(board):
            self.mode = None; self.renumber(); self.update_preview(); return
        _, mem_path = panel_paths(board)
        mem = load_json(mem_path)
        s = dict(DEFAULTS, **mem.get('settings', {}))
        v = self.vars
        self.loading = True
        try:
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
            v['auto_on'].set(s['auto_art'] == 'on')
            v['extras_on'].set(s.get('extras', 'on') != 'off')
            v['art_style'].set(s.get('art_style') or 'Custom')
            v['art_scale'].set(next((k for k, x in SCALES.items() if x == s['art_scale']), 'Ticks'))
            v['art_rings'].set(s['art_rings'] == 'on'); v['art_outputs'].set(s['art_outputs'] == 'on')
            v['art_border'].set(s['art_border'] == 'on')
            v['art_groups'].set(s['art_groups'] == 'on'); v['art_tabs'].set(s['art_tabs'] == 'on')
            v['border_radius'].set(f"{s['art_border_radius']:g}"); v['border_gap'].set(f"{s['art_border_gap']:g}")
            v['ring_width'].set(f"{s['ring_width']:g}"); v['ring_gap'].set(f"{s['ring_gap']:g}")
            v['art_title'].set(s['art_title']); v['art_maker'].set(s['art_maker'])
            v['title_size'].set(f"{s['title_size']:g}"); v['knob_size'].set(f"{s['knob_size']:g}")
            v['title_dir'].set(next((k for k, x in TITLE_DIRS.items() if x == s.get('title_vertical', 'off')), 'Across'))
            v['label_pos'].set(s['label_pos']); v['label_gap'].set(f"{s['label_gap']:g}"); v['label_size'].set(f"{s['label_size']:g}")
            v['label_font'].set(s['label_font'] or KICAD_FONT)
            v['label_bold'].set(s['label_bold'] == 'on'); v['label_caps'].set(s['label_caps'] == 'on')
            self.ui = {'ignore': dict(mem.get('ignore_uncut', {})), 'label_edits': dict(mem.get('label_edits', {})),
                       'texts': [dict(t) for t in mem.get('texts', [])], 'art_pos': dict(mem.get('art_pos', {})),
                       'images': [dict(i) for i in mem.get('images', [])],
                       'shapes': [dict(i) for i in mem.get('shapes', [])]}
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
        if v['labels_on'].get():
            size = self.number('label_size', 'label text size')
            if size < 0.5:
                raise ValueError('Label text size must be at least 0.5 mm (1 mm or more is safer for silkscreen)')
            font = v['label_font'].get()
            args += ['--labels', 'on', '--label-size', f'{size:g}', '--label-gap', f"{self.number('label_gap', 'label gap'):g}",
                     '--label-pos', v['label_pos'].get(), '--label-font', '' if font == KICAD_FONT else font,
                     '--label-bold', 'on' if v['label_bold'].get() else 'off', '--label-caps', 'on' if v['label_caps'].get() else 'off']
        else:
            args += ['--labels', 'off']
        args += ['--extras', 'on' if v['extras_on'].get() else 'off']
        if v['auto_on'].get():
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
                     '--art-groups', 'on' if v['art_groups'].get() else 'off', '--art-tabs', 'on' if v['art_tabs'].get() else 'off',
                     '--art-title', v['art_title'].get(), '--art-maker', v['art_maker'].get(),
                     '--title-size', f'{ts:g}', '--knob-size', f'{ks:g}',
                     '--title-vertical', TITLE_DIRS.get(v['title_dir'].get(), 'off')]
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
        sel = self.selected_target()
        if sel:                                    # what's selected: its box, so you can see what the left panel is changing
            b = sel[0]
            c.create_rectangle(X(b[0]) - 3, Y(b[1]) - 3, X(b[2]) + 3, Y(b[3]) + 3, outline='#2563eb', width=2, dash=(5, 2))
        for a in pv.get('added', []):
            if a['id'] in self.shape_sel:
                b = a['box']
                c.create_rectangle(X(b[0]) - 3, Y(b[1]) - 3, X(b[2]) + 3, Y(b[3]) + 3, outline='#2563eb', width=2, dash=(5, 2))
        self.draw_measure()
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
                return b, kind, data
        return None

    def press(self, e):
        if self.measuring:
            self.drag = None
            return
        t = None if self.adding else self.target_at(e)
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
                self.shape_sel = [i]; self.sel = None
                self.draw(); self.show_selected(); self.show_shapes()
        self.drag = ('item', e.x, e.y, t, False) if t else ('band', e.x, e.y, False)

    def motion(self, e):
        if not self.drag or not getattr(self, 'cur_view', None):
            return
        if self.drag[0] == 'item':
            _, x0, y0, t, moved = self.drag[:5]
            if not moved and abs(e.x - x0) + abs(e.y - y0) < 4:
                return
            sc, ox, oy = self.cur_view
            b = t[0]
            if t[1] == 'tab':                          # pull one edge of a tab: it snaps to the edges of the other tabs
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
                c = self.canvas
                c.delete('dragbox')
                if g is not None:
                    if axis == 0:
                        c.create_line(ox + g * sc, 0, ox + g * sc, c.winfo_height(), fill='#ff4fd8', dash=(3, 3), tags='dragbox')
                    else:
                        c.create_line(0, oy + g * sc, c.winfo_width(), oy + g * sc, fill='#ff4fd8', dash=(3, 3), tags='dragbox')
                c.create_rectangle(ox + nb[0] * sc, oy + nb[1] * sc, ox + nb[2] * sc, oy + nb[3] * sc,
                                   outline='#ffd28a', dash=(4, 2), width=2, tags='dragbox')
                self.drag = ('item', x0, y0, t, True, pos - b[{'l': 0, 't': 1, 'r': 2, 'b': 3}[edge]], 0, edge)
                c.config(cursor='sb_h_double_arrow' if axis == 0 else 'sb_v_double_arrow')
                return
            dx, dy, gx, gy = self.snap(t, (e.x - x0) / sc, (e.y - y0) / sc, free=bool(getattr(e, 'state', 0) & ALT_MASK))
            c = self.canvas
            c.delete('dragbox')
            if gx is not None:
                c.create_line(ox + gx * sc, 0, ox + gx * sc, c.winfo_height(), fill='#ff4fd8', dash=(3, 3), tags='dragbox')
            if gy is not None:
                c.create_line(0, oy + gy * sc, c.winfo_width(), oy + gy * sc, fill='#ff4fd8', dash=(3, 3), tags='dragbox')
            for b in ([a['box'] for a in self.pv.get('added', []) if a['id'] in self.shape_sel] if t[1] == 'shape' else [b]):
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
        if self.drag and self.drag[0] == 'item':
            _, x0, y0, t, moved = self.drag[:5]
            dx, dy = self.drag[5:7] if len(self.drag) > 5 else (0, 0)
            edge = self.drag[7] if len(self.drag) > 7 else None
            self.drag = None
            self.canvas.config(cursor='')
            self.canvas.delete('dragbox')
            if moved and t[1] == 'tab':
                g = self.ui['label_edits'].setdefault(t[2]['key'], {})
                grow = g.get(edge, 0.0) + (dx if edge in 'rb' else -dx)
                if grow > 0.01:
                    g[edge] = round(grow, 3)
                else:
                    g.pop(edge, None)
                if not g:
                    self.ui['label_edits'].pop(t[2]['key'], None)
                self.select(t); self.persist_ui(); self.update_preview()
                return
            if moved:
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
                self.measure = [p] if len(self.measure) != 1 else [self.measure[0], p]
                self.draw()
            return
        band = self.drag if self.drag and self.drag[0] == 'band' and self.drag[3] else None
        self.drag = None
        self.canvas.config(cursor='')
        self.canvas.delete('dragbox')
        if band and getattr(self, 'cur_view', None):
            sc, ox, oy = self.cur_view
            ax, bx = sorted(((band[1] - ox) / sc, (e.x - ox) / sc))
            ay, by = sorted(((band[2] - oy) / sc, (e.y - oy) / sc))
            self.shape_sel = [a['id'] for a in (self.pv or {}).get('added', [])
                              if ax <= (a['box'][0] + a['box'][2]) / 2 <= bx and ay <= (a['box'][1] + a['box'][3]) / 2 <= by]
            self.sel = None
            self.draw(); self.show_selected(); self.show_shapes(reveal=True)
            if not self.shape_sel:
                self.hover.config(text='The box selects holes you added under Extra holes. To move around the panel, '
                                       'drag with the right mouse button.')
            return
        if self.adding:
            kind, self.adding = self.adding, False
            self.canvas.config(cursor='')
            x, y = self.to_mm(e)
            if kind == 'text':
                dx, dy, _, _ = self.snap(((x, y, x, y), 'new', None), 0, 0)
                self.add_text_at(x + dx, y + dy)
            else:
                self.add_shape_at(kind, x, y, free=bool(getattr(e, 'state', 0) & ALT_MASK))
            return
        for i in reversed(self.canvas.find_overlapping(e.x, e.y, e.x, e.y)):
            if i in self.clicks:
                self.clicks[i](); return
        if self.sel or self.shape_sel:                 # a click on nothing: nothing selected
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
        self.ui.setdefault('texts', []).append(dict(id=uuid.uuid4().hex[:8], text=txt.strip(), x=round(x, 2), y=round(y, 2)))
        self.vars['extras_on'].set(True)                # something you just added should show
        self.persist_ui(); self.update_preview()

    def snap(self, t, dx, dy, free=False):
        """Line a moved text up: its middle with the middle of a hole, and its height with other labels.
        Returns the (snapped) move and the guide lines to draw. Hold Alt to place it freely."""
        b, kind, d = t
        cx, cy = (b[0] + b[2]) / 2 + dx, (b[1] + b[3]) / 2 + dy
        if free or not self.pv:
            return dx, dy, None, None
        thr = 8 / self.cur_view[0]                     # 8 pixels, in mm
        xs, ys = [], []
        moving = {'add:' + i for i in self.shape_sel} if kind == 'shape' else set()
        holes = [sh for sh in self.pv.get('shapes', []) if sh.get('key') not in moving]
        if kind in ('shape', 'newshape'):
            ys.append((self.pv['panel_box'][1] + self.pv['panel_box'][3]) / 2)
        for sh in holes:
            g = sh['geom'].bounds
            xs.append((g[0] + g[2]) / 2); ys.append((g[1] + g[3]) / 2)
        for L in self.pv.get('labels', []):
            if d is not None and L is d:
                continue
            xs.append(L['x']); ys.append(L['y'])
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
        bx = min(xs, key=lambda v: abs(v - cx), default=None)
        by = min(ys, key=lambda v: abs(v - cy), default=None)
        gx = bx if bx is not None and abs(bx - cx) <= thr else None
        gy = by if by is not None and abs(by - cy) <= thr else None
        if kind in ('shape', 'newshape'):              # not lined up with anything: whole half millimetres from the panel corner
            if gx is None:
                dx += round((cx - x1) * 2) / 2 + x1 - cx
            if gy is None:
                dy += round((cy - y1) * 2) / 2 + y1 - cy
        return dx + (gx - cx if gx is not None else 0), dy + (gy - cy if gy is not None else 0), gx, gy

    # ------------------------------------------------------------------ what's selected, changed in the left panel
    def sel_key(self, t):
        _, kind, d = t
        return kind, {'image': d.get('id'), 'art': d.get('key'), 'tab': d.get('key')}.get(kind, d.get('fid'))

    def select(self, t):
        self.sel = self.sel_key(t) if t else None
        self.shape_sel = []
        self.draw(); self.show_selected(); self.show_shapes()
        if self.sel:
            self.reveal('extras', self.sel_box)

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
            y0 = widget.winfo_rooty() - self.left.winfo_rooty()
            y1 = y0 + max(60, widget.winfo_height())
            if y0 / total < top or y1 / total > bot:
                cv.yview_moveto(max(0.0, (f.winfo_y() - 10) / total))
        except tk.TclError:
            pass

    def selected_target(self):
        if not self.sel or not getattr(self, 'targets', None):
            return None
        return next((t for t in self.targets if self.sel_key(t) == self.sel), None)

    def show_selected(self):
        box = getattr(self, 'sel_box', None)
        if box is None:
            return
        for w in box.winfo_children():
            w.destroy()
        t = self.selected_target()
        if not t:
            self.sel = None
            ttk.Label(box, text='Nothing selected. Click a text, label, picture, the title or a tab in the preview.',
                      style='Dim.TLabel', wraplength=390, justify='left').pack(anchor='w')
            return
        _, kind, d = t
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
        if kind == 'image':
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
        elif kind == 'art':
            head.config(text='Title' if d['key'] == 'title' else 'Maker name')
            ttk.Label(box, text="Its text and size are set in 'Artwork made for you'.", style='Dim.TLabel').pack(anchor='w')
            b = ttk.Button(box, text='Put it back in its automatic place',
                           command=lambda: (self.ui['art_pos'].pop(d['key'], None), self.persist_ui(), self.update_preview()))
            b.pack(anchor='w', pady=(6, 0))
            if not d.get('pinned'):
                b.state(['disabled'])
        elif kind == 'tab':
            head.config(text={'edge': 'Edge tab: ', 'output': 'Output box: ', 'textbox': 'Box round '}.get(d['kind'], '') + d.get('ref', ''))
            g = self.ui['label_edits'].get(d['key'], {})
            for edge in d['edges']:
                row = fld('Bigger on the ' + {'l': 'left', 'r': 'right', 't': 'top', 'b': 'bottom'}[edge])
                def setg(v, edge=edge):
                    x = num(v, 0, 50)
                    if x is None:
                        return
                    gg = self.ui['label_edits'].setdefault(d['key'], {})
                    if abs(x - gg.get(edge, 0.0)) > 1e-6:
                        if x > 0:
                            gg[edge] = round(x, 2)
                        else:
                            gg.pop(edge, None)
                        if not gg:
                            self.ui['label_edits'].pop(d['key'], None)
                        self.persist_ui(); self.update_preview()
                entry(row, f"{g.get(edge, 0.0):g}", setg); ttk.Label(row, text='mm').pack(side='left')
            ttk.Label(box, text='Or drag an edge of it in the preview: it snaps to the edges of the other tabs and boxes'
                               + (', and to key labels and hole edges - stretch a bar over two keys.' if d['kind'] == 'textbox' else '.'),
                      style='Dim.TLabel', wraplength=390, justify='left').pack(anchor='w', pady=(4, 0))
            ttk.Button(box, text='Back to its own size', command=lambda: (self.ui['label_edits'].pop(d['key'], None),
                                                                          self.persist_ui(), self.update_preview())).pack(anchor='w', pady=(6, 0))

    # ------------------------------------------------------------------ holes, rectangles and slots you add
    def hole_dia(self):
        import re
        m = re.match(r'\s*(\d+(?:[.,]\d+)?)', self.hole_size.get())
        if not m or not 0.3 <= float(m.group(1).replace(',', '.')) <= 200:
            raise ValueError('Hole size: type a size in mm, e.g. 6.2')
        return float(m.group(1).replace(',', '.'))

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
                entry(f, 'Hole size', f"{o['d']:g}", lambda x: change(o, 'd', x))
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
            self.adding = False
            self.canvas.config(cursor='')
            self.hover.config(text='Hover over a cutout to see what it is.')
        elif self.measuring:
            self.end_measure()
        elif self.shape_sel or self.sel:
            self.select(None)

    def toggle_measure(self):
        if self.measuring:
            return self.end_measure()
        if not self.pv or 'message' in self.pv:
            return
        self.adding = False
        self.measuring, self.measure = True, []
        self.w_measure.config(text='Stop')
        self.canvas.config(cursor='crosshair')
        self.hover.config(text='Ruler: click where to measure from, then where to. Hold Ctrl to keep it straight. Esc to finish.')

    def end_measure(self):
        if not self.measuring:
            return
        self.measuring, self.measure = False, []
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
        if not self.measuring or len(self.measure) != 1 or not getattr(self, 'cur_view', None) or not self.pv or 'message' in self.pv:
            return
        self.draw_measure(self.measure_point(e))

    def draw_measure(self, live=None):
        c = self.canvas
        c.delete('ruler')
        pts = list(self.measure) + ([live] if live and len(self.measure) == 1 else [])
        if not self.measuring or not pts or not getattr(self, 'cur_view', None):
            return
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
        self.hover.config(text='Ruler: ' + txt + '  ·  click to measure something else, Esc to finish')

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
        self.vars['extras_on'].set(True)
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

    def move_target(self, t, dx, dy):
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
        else:
            e = self.ui['label_edits'].setdefault(d['fid'], {})
            e['dx'] = round(e.get('dx', 0.0) + dx, 3); e['dy'] = round(e.get('dy', 0.0) + dy, 3)
        self.persist_ui(); self.update_preview()

    def context_menu(self, e):
        t = self.target_at(e)
        if not t:
            if not self.pv or 'message' in self.pv or not getattr(self, 'cur_view', None):
                return
            x, y = self.to_mm(e)
            m = tk.Menu(self, tearoff=0)
            def here_text():
                dx, dy, _, _ = self.snap(((x, y, x, y), 'new', None), 0, 0)
                self.add_text_at(x + dx, y + dy)
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
            m.add_command(label='Copy' if n == 1 else f'Copy these {n}', command=self.shapes_duplicate)
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
        elif kind == 'art':
            m.add_command(label=f"Put the {d['what']} back in its automatic place", state='normal' if d.get('pinned') else 'disabled',
                          command=lambda: (self.ui['art_pos'].pop(d['key'], None), self.persist_ui(), self.update_preview()))
        else:
            m.add_command(label='Edit labels…', command=lambda: (self.edit_labels(), self.editor.focus_row(d['fid'])))
            m.add_command(label='Put it back where it was', command=lambda: self.label_reset(d['fid']))
            m.add_command(label='Hide this label', command=lambda: self.label_hide(d['fid']))
        m.tk_popup(e.x_root, e.y_root)

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
                       'shapes': [dict(i) for i in mem.get('shapes', [])]}
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
        self.sel = None; self.shape_sel = []
        if self.after_id:
            self.after_cancel(self.after_id); self.after_id = None
        self.refresh_states()
        self.update_preview()
        self.restoring = False

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
