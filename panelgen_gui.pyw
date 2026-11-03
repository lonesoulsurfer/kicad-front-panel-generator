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
                auto_art='off', art_style='Classic synth', art_scale='ticks', art_rings='on', art_outputs='off', art_border='off',
                art_border_radius=0.0, art_groups='off', art_tabs='off',
                art_title='', art_maker='', title_size=5.0, knob_size=13.0)
ART_STYLES = {   # what each style switches on
    'Minimal': dict(scale='Ticks', rings=False, outputs=False, border=False, groups=False, tabs=False),
    'Classic synth': dict(scale='Numbers 0-10', rings=True, outputs=False, border=True, groups=True, tabs=True),
    'Modular': dict(scale='Ticks', rings=False, outputs=True, border=False, groups=False, tabs=True),
}
STYLE_KEYS = ('scale', 'rings', 'outputs', 'border', 'groups', 'tabs')
SCALES = {'None': 'none', 'Ticks': 'ticks', 'Numbers 0-10': 'numbers', 'Centre zero (- 0 +)': 'bipolar'}
KICAD_FONT = "KiCad's own font"
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
        v['expand'] = tk.BooleanVar(); v['margin'] = tk.StringVar(value='10')
        v['per_side'] = tk.BooleanVar()
        for s in ('top', 'right', 'bottom', 'left'):
            v[s] = tk.StringVar(value='10')
        v['screws'] = tk.StringVar(value='none')
        v['screw_dia'] = tk.StringVar(value='2.2'); v['screw_inset'] = tk.StringVar(value='3.5')
        v['case_shape'] = tk.StringVar(value='round'); v['slot'] = tk.StringVar(value='4')
        v['rail_shape'] = tk.StringVar(value='round'); v['rslot'] = tk.StringVar(value='5')
        v['round'] = tk.BooleanVar(); v['radius'] = tk.StringVar(value='3')
        v['grow_on'] = tk.BooleanVar(); v['grow'] = tk.StringVar(value='0.5')
        v['svg'] = tk.BooleanVar(); v['open'] = tk.BooleanVar(value=self.cfg.get('open_after', True))
        v['uncut_check'] = tk.BooleanVar(value=True)
        v['art_on'] = tk.BooleanVar()
        v['auto_on'] = tk.BooleanVar(); v['art_style'] = tk.StringVar(value='Classic synth')
        v['art_scale'] = tk.StringVar(value='Ticks'); v['art_rings'] = tk.BooleanVar(value=True)
        v['art_outputs'] = tk.BooleanVar(); v['art_border'] = tk.BooleanVar()
        v['art_groups'] = tk.BooleanVar(); v['art_tabs'] = tk.BooleanVar(); v['border_radius'] = tk.StringVar(value='0')
        v['art_title'] = tk.StringVar(); v['art_maker'] = tk.StringVar()
        v['title_size'] = tk.StringVar(value='5'); v['knob_size'] = tk.StringVar(value='13')
        v['labels_on'] = tk.BooleanVar(); v['label_pos'] = tk.StringVar(value='above')
        v['label_gap'] = tk.StringVar(value='1.5'); v['label_size'] = tk.StringVar(value='2')
        v['label_font'] = tk.StringVar(value=KICAD_FONT); v['label_bold'] = tk.BooleanVar(); v['label_caps'] = tk.BooleanVar()
        self.ui = {'ignore': {}, 'label_edits': {}, 'texts': [], 'art_pos': {}}   # ignored parts, label changes, your texts, moved title
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
        if not themed:
            st.configure('Accent.TButton', font=self.f_head, padding=8)
        return themed

    # ------------------------------------------------------------------ layout
    def build(self):
        v = self.vars
        root = ttk.Frame(self, padding=(14, 10)); root.pack(fill='both', expand=True)
        root.columnconfigure(1, weight=1); root.columnconfigure(0, minsize=480); root.rowconfigure(1, weight=1)


        bg = ttk.Style(self).lookup('TFrame', 'background') or C_BG
        lc = ttk.Frame(root); lc.grid(row=1, column=0, sticky='nsew', padx=(0, 10))
        cv = tk.Canvas(lc, highlightthickness=0, width=470, bg=bg)
        lsb = ttk.Scrollbar(lc, orient='vertical', command=cv.yview)
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
        self.sections = {}

        # 1 PCB
        s = self.section('pcb', 'Your PCB', 'The synth PCB with the parts on it. Save it in KiCad first.')
        row = ttk.Frame(s); row.pack(fill='x')
        self.board_name = tk.StringVar()
        cb = self.board_box = ttk.Combobox(row, textvariable=self.board_name, state='readonly')
        cb.pack(side='left', fill='x', expand=True)
        cb.bind('<<ComboboxSelected>>', self.pick_recent)
        self.board_tip = Tip(cb, '')
        ttk.Button(row, text='Browse…', command=self.browse).pack(side='left', padx=(6, 0))
        self.mode_lbl = ttk.Label(s, text='', style='Badge.TLabel'); self.mode_lbl.pack(anchor='w', pady=(6, 0))
        Tip(self.mode_lbl, 'A PCB with a Eurorack_xHP template from Eurorack.pretty on it gets a standard Eurorack panel; '
                           'any other PCB gets a panel fitted to its outline.')
        self.mode_hint = ttk.Label(s, text='', style='Dim.TLabel', wraplength=400, justify='left')
        self.mode_hint.pack(anchor='w')

        # 2a size (fit to PCB)
        s = self.section('size', 'Panel size and shape', 'The panel starts as your PCB outline.')
        row = ttk.Frame(s); row.pack(fill='x')
        c = ttk.Checkbutton(row, text='Make the panel bigger than the PCB by', variable=v['expand'], command=self.refresh_states)
        c.pack(side='left')
        Tip(c, 'Extra panel around the PCB on every side, e.g. 10 mm to leave room for a case or wired jacks.')
        self.w_margin = self.num(row, 'margin'); ttk.Label(row, text='mm').pack(side='left')
        h1 = ttk.Frame(s); h1.pack(fill='x'); h2 = ttk.Frame(s); h2.pack(fill='x')     # holders for rows that come and go
        self.w_per = ttk.Checkbutton(h1, text='Different amount on each side', variable=v['per_side'], command=self.refresh_states)
        self.w_per.pack(anchor='w', padx=(26, 0), pady=(4, 0))
        sides = self.sides_row = ttk.Frame(h2); sides.pack(anchor='w', padx=(26, 0), pady=(2, 0))
        self.w_sides = []
        for i, side in enumerate(('top', 'right', 'bottom', 'left')):
            ttk.Label(sides, text=side.capitalize()).grid(row=0, column=2 * i, padx=(0 if i == 0 else 10, 3))
            self.w_sides.append(self.num(sides, side, grid=(0, 2 * i + 1)))
        row = self.corner_row = ttk.Frame(s); row.pack(fill='x', pady=(8, 0))
        c = ttk.Checkbutton(row, text='Rounded corners, radius', variable=v['round'], command=self.refresh_states); c.pack(side='left')
        self.w_radius = self.num(row, 'radius'); ttk.Label(row, text='mm').pack(side='left')

        # 2b rail holes (Eurorack)
        s = self.section('rail', 'Rail holes', '3.2 mm holes at the standard Eurorack positions. 4 holes from 10HP up.')
        ttk.Radiobutton(s, text='Round holes', value='round', variable=v['rail_shape'], command=self.refresh_states).pack(anchor='w')
        row = ttk.Frame(s); row.pack(fill='x', pady=(2, 0))
        c = ttk.Radiobutton(row, text='Slots, length', value='slot', variable=v['rail_shape'], command=self.refresh_states)
        c.pack(side='left')
        Tip(c, 'Horizontal slots centred on the standard hole position, so the module can slide a little along the rail.')
        self.w_rslot = self.num(row, 'rslot'); ttk.Label(row, text='mm end to end').pack(side='left')

        # 3 case holes (fit to PCB)
        s = self.section('case', 'Case mounting holes', 'Screw holes round the panel edge, for fixing it to a case.')
        row = ttk.Frame(s); row.pack(fill='x')
        for txt, val in (('None', 'none'), ('Corners', 'corners'), ('Corners + middle of each side', 'corners+mid')):
            ttk.Radiobutton(row, text=txt, value=val, variable=v['screws'], command=self.refresh_states).pack(side='left', padx=(0, 12))
        h3 = ttk.Frame(s); h3.pack(fill='x')
        det = self.case_detail = ttk.Frame(h3); det.pack(fill='x')
        g = ttk.Frame(det); g.pack(fill='x', pady=(6, 0))
        ttk.Label(g, text='Hole size').grid(row=0, column=0, sticky='w')
        self.w_dia = self.num(g, 'screw_dia', grid=(0, 1)); ttk.Label(g, text='mm').grid(row=0, column=2, sticky='w')
        l = ttk.Label(g, text='Edge to hole centre'); l.grid(row=0, column=3, sticky='w', padx=(16, 0))
        Tip(l, 'Measured from the panel edge to the centre of the hole. For slots, to the centre of the end nearest that edge.')
        self.w_inset = self.num(g, 'screw_inset', grid=(0, 4)); ttk.Label(g, text='mm').grid(row=0, column=5, sticky='w')
        row = ttk.Frame(det); row.pack(fill='x', pady=(6, 0))
        self.w_cround = ttk.Radiobutton(row, text='Round', value='round', variable=v['case_shape'], command=self.refresh_states)
        self.w_cround.pack(side='left', padx=(0, 12))
        self.w_cslot = ttk.Radiobutton(row, text='Slots along the edge, length', value='slot', variable=v['case_shape'],
                                       command=self.refresh_states)
        self.w_cslot.pack(side='left')
        Tip(self.w_cslot, 'Give the case screws some play. Corner slots run inwards from the corner position.')
        self.w_slot = self.num(row, 'slot'); ttk.Label(row, text='mm').pack(side='left')
        self.edge_info = tk.Label(det, text='', anchor='w', justify='left', wraplength=410, font=self.f_small)
        self.edge_info.pack(anchor='w', pady=(4, 0))

        # 4 openings
        s = self.section('open', 'Openings', 'Pots, jacks, switches, screens and LEDs - sized from the PCB.')
        row = ttk.Frame(s); row.pack(fill='x')
        c = ttk.Checkbutton(row, text='Make every opening bigger by', variable=v['grow_on'], command=self.refresh_states)
        c.pack(side='left')
        Tip(c, 'Adds this much to every opening (screens, switches, pots, jacks, LEDs). Screw and mounting holes stay as they are.')
        self.w_grow = self.num(row, 'grow'); ttk.Label(row, text='mm').pack(side='left')
        c = ttk.Checkbutton(s, text='Warn about parts that seem to need a cutout but have none', variable=v['uncut_check'])
        c.pack(anchor='w', pady=(4, 0))
        Tip(c, 'Jacks, switches, pots, LEDs and screens with no rule get a dashed orange box in the preview. '
               'Click one that really sits behind the panel to stop warning about it.')

        # labels
        s = self.section('labels', 'Labels', 'Optional: text for each control, printed on the panel\'s silkscreen.')
        c = ttk.Checkbutton(s, text='Add labels from the PCB', variable=v['labels_on'], command=self.refresh_states)
        c.pack(anchor='w')
        Tip(c, "Each part's text comes from its Label field if it has one, otherwise its Value or Reference "
               "(e.g. 'Cutoff', 'Play'). Change, hide or move any of them in Edit labels.")
        h4 = ttk.Frame(s); h4.pack(fill='x')
        det = self.label_detail = ttk.Frame(h4); det.pack(fill='x')
        g = ttk.Frame(det); g.pack(fill='x', pady=(6, 0))
        ttk.Label(g, text='Position').grid(row=0, column=0, sticky='w')
        pr = ttk.Frame(g); pr.grid(row=0, column=1, columnspan=3, sticky='w', padx=4)
        ttk.Radiobutton(pr, text='Above', value='above', variable=v['label_pos']).pack(side='left', padx=(0, 8))
        ttk.Radiobutton(pr, text='Below', value='below', variable=v['label_pos']).pack(side='left')
        l = ttk.Label(g, text='Gap'); l.grid(row=0, column=4, sticky='w', padx=(14, 0))
        Tip(l, 'Distance from the edge of the hole to the text. Keys in a merged switch slot follow their own side of the slot.')
        self.num(g, 'label_gap', grid=(0, 5)); ttk.Label(g, text='mm').grid(row=0, column=6, sticky='w')
        ttk.Label(g, text='Text size').grid(row=1, column=0, sticky='w', pady=(6, 0))
        self.num(g, 'label_size', grid=(1, 1)); ttk.Label(g, text='mm').grid(row=1, column=2, sticky='w', pady=(6, 0))
        l = ttk.Label(g, text='Font'); l.grid(row=1, column=4, sticky='w', padx=(14, 0), pady=(6, 0))
        fonts = [KICAD_FONT] + sorted({f for f in tkfont.families() if not f.startswith('@')})
        fc = ttk.Combobox(g, textvariable=v['label_font'], values=fonts, width=16, state='readonly')
        fc.grid(row=1, column=5, columnspan=2, sticky='w', padx=4, pady=(6, 0))
        Tip(fc, "KiCad's own font always works. Any other font has to be installed on the computer that opens the panel "
                "(the gerbers carry the shapes, so the fab doesn't need it).")
        row = ttk.Frame(det); row.pack(fill='x', pady=(6, 0))
        ttk.Checkbutton(row, text='Bold', variable=v['label_bold']).pack(side='left', padx=(0, 12))
        ttk.Checkbutton(row, text='ALL CAPS', variable=v['label_caps']).pack(side='left')
        ttk.Button(row, text='Edit labels…', command=self.edit_labels).pack(side='right')

        # artwork made for you
        s = self.section('auto', 'Artwork made for you', 'Optional: pot scales, rings, output boxes, a border and a title, '
                                                         'drawn from your panel. No Inkscape needed.')
        c = ttk.Checkbutton(s, text='Make artwork for me', variable=v['auto_on'], command=self.refresh_states)
        c.pack(anchor='w')
        Tip(c, 'Everything is placed from the holes and labels on your panel, and checked against them. It also goes into '
               "the Inkscape file on its own layer, so you can draw more on top if you like.")
        h6 = ttk.Frame(s); h6.pack(fill='x')
        det = self.auto_detail = ttk.Frame(h6); det.pack(fill='x')
        g = ttk.Frame(det); g.pack(fill='x', pady=(6, 0))
        ttk.Label(g, text='Style').grid(row=0, column=0, sticky='w')
        sc = ttk.Combobox(g, textvariable=v['art_style'], values=list(ART_STYLES) + ['Custom'], width=14, state='readonly')
        sc.grid(row=0, column=1, columnspan=3, sticky='w', padx=4)
        sc.bind('<<ComboboxSelected>>', lambda e: self.apply_style())
        Tip(sc, 'Minimal: ticks round the pots. Classic synth: numbered scales, rings round buttons, a border. '
                "Modular: ticks, and outputs in filled boxes (any jack whose label says OUT). Change anything below after.")
        ttk.Label(g, text='Title').grid(row=1, column=0, sticky='w', pady=(6, 0))
        ttk.Entry(g, textvariable=v['art_title'], width=20).grid(row=1, column=1, columnspan=3, sticky='w', padx=4, pady=(6, 0))
        l = ttk.Label(g, text='Size'); l.grid(row=1, column=4, sticky='w', padx=(10, 0), pady=(6, 0))
        self.num(g, 'title_size', grid=(1, 5)); ttk.Label(g, text='mm').grid(row=1, column=6, sticky='w', pady=(6, 0))
        l = ttk.Label(g, text='Maker'); l.grid(row=2, column=0, sticky='w', pady=(6, 0))
        Tip(l, 'Your name or brand, small, along the bottom. Leave empty for none.')
        ttk.Entry(g, textvariable=v['art_maker'], width=20).grid(row=2, column=1, columnspan=3, sticky='w', padx=4, pady=(6, 0))
        ttk.Label(g, text='Pot scale').grid(row=3, column=0, sticky='w', pady=(6, 0))
        ps = ttk.Combobox(g, textvariable=v['art_scale'], values=list(SCALES), width=16, state='readonly')
        ps.grid(row=3, column=1, columnspan=3, sticky='w', padx=4, pady=(6, 0))
        Tip(ps, 'Marks round every pot, over a 300 degree turn. Change one pot (e.g. centre zero for a pan pot) in Edit labels.')
        l = ttk.Label(g, text='Knob'); l.grid(row=3, column=4, sticky='w', padx=(10, 0), pady=(6, 0))
        Tip(l, 'Knob diameter: the scale and the label start outside it, so the knob never hides them.')
        self.num(g, 'knob_size', grid=(3, 5)); ttk.Label(g, text='mm').grid(row=3, column=6, sticky='w', pady=(6, 0))
        row = ttk.Frame(det); row.pack(fill='x', pady=(6, 0))
        ttk.Checkbutton(row, text='Rings round buttons', variable=v['art_rings']).pack(side='left', padx=(0, 12))
        c = ttk.Checkbutton(row, text='Outputs in filled boxes', variable=v['art_outputs']); c.pack(side='left')
        Tip(c, "Jacks whose label says OUT get a filled box with the label cut out of it - the usual way to tell outputs "
               "from inputs. Set any jack to output or input in Edit labels.")
        row = ttk.Frame(det); row.pack(fill='x', pady=(4, 0))
        c = ttk.Checkbutton(row, text='Boxes round rows of controls', variable=v['art_groups']); c.pack(side='left', padx=(0, 12))
        Tip(c, 'A box round 3 or more of the same control in a row or a column (pots, buttons, jacks), with their scales '
               "and labels inside. Left out (with a note) when it would run into another part, a label or the edge.")
        c = ttk.Checkbutton(row, text='Tabs for edge jacks', variable=v['art_tabs']); c.pack(side='left')
        Tip(c, "Jacks on the panel edge (no hole, the plug goes in from the side) get a filled tab hanging from the edge "
               "with their labels cut out. Neighbours share a tab; labels with the same first word (MIDI IN, MIDI OUT) "
               "become IN / OUT with MIDI underneath.")
        row = ttk.Frame(det); row.pack(fill='x', pady=(4, 0))
        ttk.Checkbutton(row, text='Border', variable=v['art_border'], command=self.refresh_states).pack(side='left')
        l = ttk.Label(row, text='corner radius'); l.pack(side='left', padx=(10, 0))
        Tip(l, '0 = the border follows the panel corners. Any other value rounds the border corners by that much.')
        self.w_bradius = self.num(row, 'border_radius'); ttk.Label(row, text='mm').pack(side='left')
        ttk.Button(row, text='Add text…', command=self.start_add_text).pack(side='right')
        for k in ('art_scale', 'art_rings', 'art_border', 'art_outputs', 'art_groups', 'art_tabs'):
            v[k].trace_add('write', lambda *_: self.style_custom())

        # artwork
        s = self.section('art', 'Artwork from Inkscape', 'Optional: your own graphics and text, drawn on a 1:1 copy of the panel.')
        c = ttk.Checkbutton(s, text='Add my artwork to the silkscreen', variable=v['art_on'], command=self.refresh_states)
        c.pack(anchor='w')
        Tip(c, "Panel Generator makes an Inkscape file of the panel with the cutouts on a locked layer. Draw on its "
               "'Artwork' layer: black prints, white cuts out of black (for white-on-black text). Inkscape renders it, "
               "so every font and effect works.")
        h5 = ttk.Frame(s); h5.pack(fill='x')
        det = self.art_detail = ttk.Frame(h5); det.pack(fill='x')
        self.art_status = ttk.Label(det, text='', wraplength=410, justify='left'); self.art_status.pack(anchor='w', pady=(4, 0))
        row = ttk.Frame(det); row.pack(fill='x', pady=(6, 0))
        self.w_art_make = ttk.Button(row, text='Create artwork file', command=self.make_artwork)
        self.w_art_open = ttk.Button(row, text='Open in Inkscape', command=self.open_artwork)
        self.w_art_dir = ttk.Button(row, text='Show folder', command=self.open_folder)
        self.w_art_make.pack(side='left'); self.w_art_open.pack(side='left', padx=6); self.w_art_dir.pack(side='left')
        ttk.Label(det, text="Draw on the 'Artwork' layer, save in Inkscape, and the preview updates by itself.",
                  style='Dim.TLabel', wraplength=410).pack(anchor='w', pady=(4, 0))


        # 6 holes you removed
        s = self.section('restore', 'Holes you removed or changed', 'Delete or resize a hole in the panel and it stays that way. '
                                                                   'Parts you said need no cutout are listed here too.')
        row = ttk.Frame(s); row.pack(fill='x')
        self.restore_list = tk.Listbox(row, height=2, selectmode='extended', activestyle='none', relief='flat',
                                       highlightthickness=1, highlightcolor='#c8ced5', highlightbackground='#c8ced5')
        self.restore_list.pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Bring back', command=self.restore).pack(side='left', padx=(6, 0), anchor='n')

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
        tb = ttk.Button(ph, text='Add text', command=self.start_add_text); tb.pack(side='right', padx=(0, 6))
        Tip(tb, 'Click here, then click on the panel where the text goes. Drag any text, label or the title to move it: '
                'it snaps into line with other labels and to the middle of holes (hold Alt to place it freely). '
                'Right-click it for more.')
        Tip(fb, 'Show the whole panel again. Mouse wheel zooms in and out where the pointer is; drag to move around; '
                'double-click also fits.')
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
        pc.bind('<Button-3>', self.context_menu); pc.bind('<Button-2>', self.context_menu)
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

    def section(self, key, title, sub):
        f = ttk.Frame(self.left); f.pack(fill='x', pady=(0, 7))
        h = ttk.Frame(f); h.pack(fill='x')
        badge = tk.Canvas(h, width=22, height=22, highlightthickness=0, bg=ttk.Style(self).lookup('TFrame', 'background') or C_BG)
        badge.pack(side='left', padx=(0, 8))
        ttk.Label(h, text=title, style='Head.TLabel').pack(side='left')
        ttk.Label(f, text=sub, style='Dim.TLabel', wraplength=410, justify='left').pack(anchor='w', padx=(30, 0))
        body = ttk.Frame(f); body.pack(fill='x', padx=(30, 0), pady=(3, 0))
        self.sections[key] = (f, badge)
        return body

    def renumber(self):
        """Show the sections that apply to this kind of panel, numbered in order."""
        show = {'pcb', 'open', 'labels', 'auto', 'art', 'restore'} | ({'rail'} if self.mode == 'eurorack' else {'size', 'case'})
        order = ['pcb', 'size', 'rail', 'case', 'open', 'labels', 'auto', 'art', 'restore']
        n = 0
        for k in order:
            f, badge = self.sections[k]
            f.pack_forget()
        for k in order:
            f, badge = self.sections[k]
            if k in show:
                n += 1
                f.pack(fill='x', pady=(0, 7), before=self.left_end)
                badge.delete('all')
                badge.create_oval(1, 1, 21, 21, fill='#2563eb', outline='')
                badge.create_text(11, 11, text=str(n), fill='white', font=self.f_small)

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
        self.show(self.w_per, v['expand'].get(), anchor='w', padx=(26, 0), pady=(4, 0))
        self.show(self.sides_row, v['expand'].get() and v['per_side'].get(), anchor='w', padx=(26, 0), pady=(2, 0))
        self.show(self.case_detail, v['screws'].get() != 'none', fill='x')
        self.show(self.label_detail, v['labels_on'].get(), fill='x')
        self.show(self.art_detail, v['art_on'].get(), fill='x')
        self.show(self.auto_detail, v['auto_on'].get(), fill='x')
        en(self.w_bradius, v['art_border'].get())
        self.art_state()
        en(self.w_margin, v['expand'].get() and not v['per_side'].get())
        en(self.w_per, v['expand'].get())
        for w in self.w_sides:
            en(w, v['expand'].get() and v['per_side'].get())
        on = v['screws'].get() != 'none'
        for w in (self.w_dia, self.w_inset, self.w_cround, self.w_cslot):
            en(w, on)
        en(self.w_slot, on and v['case_shape'].get() == 'slot')
        en(self.w_rslot, v['rail_shape'].get() == 'slot')
        en(self.w_radius, v['round'].get())
        en(self.w_grow, v['grow_on'].get())
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
            v['expand'].set(any(x > 0 for x in sides))
            v['per_side'].set(len(set(sides)) > 1)
            if any(x > 0 for x in sides):
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
            v['round'].set(s['corner_radius'] > 0)
            if s['corner_radius'] > 0:
                v['radius'].set(f"{s['corner_radius']:g}")
            v['grow_on'].set(s['grow'] > 0)
            if s['grow'] > 0:
                v['grow'].set(f"{s['grow']:g}")
            v['svg'].set(bool(s['svg']))
            v['uncut_check'].set(s['check_uncut'] != 'off')
            v['art_on'].set(s['artwork'] == 'on')
            v['labels_on'].set(s['labels'] == 'on')
            v['auto_on'].set(s['auto_art'] == 'on')
            v['art_style'].set(s.get('art_style') or 'Custom')
            v['art_scale'].set(next((k for k, x in SCALES.items() if x == s['art_scale']), 'Ticks'))
            v['art_rings'].set(s['art_rings'] == 'on'); v['art_outputs'].set(s['art_outputs'] == 'on')
            v['art_border'].set(s['art_border'] == 'on')
            v['art_groups'].set(s['art_groups'] == 'on'); v['art_tabs'].set(s['art_tabs'] == 'on')
            v['border_radius'].set(f"{s['art_border_radius']:g}")
            v['art_title'].set(s['art_title']); v['art_maker'].set(s['art_maker'])
            v['title_size'].set(f"{s['title_size']:g}"); v['knob_size'].set(f"{s['knob_size']:g}")
            v['label_pos'].set(s['label_pos']); v['label_gap'].set(f"{s['label_gap']:g}"); v['label_size'].set(f"{s['label_size']:g}")
            v['label_font'].set(s['label_font'] or KICAD_FONT)
            v['label_bold'].set(s['label_bold'] == 'on'); v['label_caps'].set(s['label_caps'] == 'on')
            self.ui = {'ignore': dict(mem.get('ignore_uncut', {})), 'label_edits': dict(mem.get('label_edits', {})),
                       'texts': [dict(t) for t in mem.get('texts', [])], 'art_pos': dict(mem.get('art_pos', {}))}
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
            if v['expand'].get():
                if v['per_side'].get():
                    for s in ('top', 'right', 'bottom', 'left'):
                        args += [f'--margin-{s}', f"{self.number(s, s + ' margin'):g}"]
                    args += ['--margin', '0']
                else:
                    args += ['--margin', f"{self.number('margin', 'panel size'):g}"]
            else:
                args += ['--margin', '0']
            if v['screws'].get() != 'none':
                args += ['--screws', v['screws'].get(),
                         '--screw-dia', f"{self.number('screw_dia', 'case hole size'):g}",
                         '--screw-inset', f"{self.number('screw_inset', 'edge to hole centre'):g}",
                         '--screw-slot', f"{self.number('slot', 'slot length'):g}" if v['case_shape'].get() == 'slot' else '0']
            else:
                args += ['--screws', 'none']
            args += ['--corner-radius', f"{self.number('radius', 'corner radius'):g}" if v['round'].get() else '0']
        args += ['--grow', f"{self.number('grow', 'opening size increase'):g}" if v['grow_on'].get() else '0']
        if not v['uncut_check'].get():
            args.append('--no-uncut-check')
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
                     '--art-groups', 'on' if v['art_groups'].get() else 'off', '--art-tabs', 'on' if v['art_tabs'].get() else 'off',
                     '--art-title', v['art_title'].get(), '--art-maker', v['art_maker'].get(),
                     '--title-size', f'{ts:g}', '--knob-size', f'{ks:g}']
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
        self.targets = []                 # things you can drag: (box in mm, kind, data), topmost last
        for L in pv.get('labels', []):
            self.targets.append(((L['x'] - L['w'] / 2, L['y'] - L['h'] / 2, L['x'] + L['w'] / 2, L['y'] + L['h'] / 2),
                                 'text' if L.get('own') else 'label', L))
        for it in pv.get('art_items', []):
            self.targets.append((it['box'], 'art', it))
        for L in pv.get('labels', []):
            px = -max(5, round(L['h'] * self.pg.KICAD_EM * sc))     # KiCad's em square is 1.4 x the text size
            i = c.create_text(X(L['x']), Y(L['y']), text=L['text'], fill='#ffffff' if L['status'] == 'ok' else '#ffb347',
                              font=(fam, px, 'bold' if pv.get('label_bold') else 'normal'))
            c.tag_bind(i, '<Enter>', lambda e, L=L: self.hover.config(
                text=f"{L['ref']}  ·  label '{L['text']}'" + ('  ·  runs into something (see Result)' if L['status'] != 'ok' else '')
                     + ('  ·  drag to move, right-click to change or delete' if L.get('own') else '  ·  drag to move, click to edit')))
            c.tag_bind(i, '<Leave>', lambda e: self.hover.config(text='Hover over a cutout to see what it is.'))
            self.clicks[i] = lambda f=L['fid']: (self.edit_labels(), self.editor.focus_row(f))
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
        t = None if self.adding else self.target_at(e)
        self.drag = ('item', e.x, e.y, t, False) if t else (e.x, e.y, False)

    def motion(self, e):
        if not self.drag or not getattr(self, 'cur_view', None):
            return
        if self.drag[0] == 'item':
            _, x0, y0, t, moved = self.drag[:5]
            if not moved and abs(e.x - x0) + abs(e.y - y0) < 4:
                return
            sc, ox, oy = self.cur_view
            b = t[0]
            dx, dy, gx, gy = self.snap(t, (e.x - x0) / sc, (e.y - y0) / sc, free=bool(getattr(e, 'state', 0) & ALT_MASK))
            c = self.canvas
            c.delete('dragbox')
            if gx is not None:
                c.create_line(ox + gx * sc, 0, ox + gx * sc, c.winfo_height(), fill='#ff4fd8', dash=(3, 3), tags='dragbox')
            if gy is not None:
                c.create_line(0, oy + gy * sc, c.winfo_width(), oy + gy * sc, fill='#ff4fd8', dash=(3, 3), tags='dragbox')
            c.create_rectangle(ox + (b[0] + dx) * sc, oy + (b[1] + dy) * sc, ox + (b[2] + dx) * sc, oy + (b[3] + dy) * sc,
                               outline='#ffd28a', dash=(4, 2), width=2, tags='dragbox')
            self.drag = ('item', x0, y0, t, True, dx, dy)
            c.config(cursor='fleur')
            return
        x0, y0, moved = self.drag
        if not moved and abs(e.x - x0) + abs(e.y - y0) < 4:
            return
        sc, ox, oy = self.cur_view
        self.view = (sc, ox + e.x - x0, oy + e.y - y0)
        self.drag = (e.x, e.y, True)
        self.canvas.config(cursor='fleur')
        self.draw()

    def release(self, e):
        if self.drag and self.drag[0] == 'item':
            _, x0, y0, t, moved = self.drag[:5]
            dx, dy = self.drag[5:7] if len(self.drag) > 5 else (0, 0)
            self.drag = None
            self.canvas.config(cursor='')
            self.canvas.delete('dragbox')
            if moved:
                self.move_target(t, round(dx, 3), round(dy, 3))
                return
            if t[1] in ('text', 'art'):
                return
            moved = False
        else:
            moved = self.drag and self.drag[2]
            self.drag = None
            self.canvas.config(cursor='')
        if moved:
            return
        if self.adding:
            self.adding = False
            self.canvas.config(cursor='')
            x, y = self.to_mm(e)
            dx, dy, _, _ = self.snap(((x, y, x, y), 'new', None), 0, 0)
            self.add_text_at(x + dx, y + dy)
            return
        for i in reversed(self.canvas.find_overlapping(e.x, e.y, e.x, e.y)):
            if i in self.clicks:
                self.clicks[i](); return

    # ------------------------------------------------------------------ texts you add, and moving things
    def start_add_text(self):
        if not self.pv or 'message' in self.pv:
            return
        self.adding = True
        self.canvas.config(cursor='crosshair')
        self.hover.config(text='Click on the panel where the text should go.')

    def add_text_at(self, x, y):
        from tkinter import simpledialog
        txt = simpledialog.askstring('Add text', 'Text:', parent=self)
        if not txt or not txt.strip():
            return
        import uuid
        self.ui.setdefault('texts', []).append(dict(id=uuid.uuid4().hex[:8], text=txt.strip(), x=round(x, 2), y=round(y, 2)))
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
        for sh in self.pv.get('shapes', []):
            g = sh['geom'].bounds
            xs.append((g[0] + g[2]) / 2); ys.append((g[1] + g[3]) / 2)
        for L in self.pv.get('labels', []):
            if d is not None and L is d:
                continue
            xs.append(L['x']); ys.append(L['y'])
        for it in self.pv.get('art_items', []):
            if d is not None and it is d:
                continue
            ib = it['box']; xs.append((ib[0] + ib[2]) / 2); ys.append((ib[1] + ib[3]) / 2)
        x1, y1, x2, y2 = self.pv['panel_box']
        xs.append((x1 + x2) / 2)
        bx = min(xs, key=lambda v: abs(v - cx), default=None)
        by = min(ys, key=lambda v: abs(v - cy), default=None)
        gx = bx if bx is not None and abs(bx - cx) <= thr else None
        gy = by if by is not None and abs(by - cy) <= thr else None
        return dx + (gx - cx if gx is not None else 0), dy + (gy - cy if gy is not None else 0), gx, gy

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
        else:
            e = self.ui['label_edits'].setdefault(d['fid'], {})
            e['dx'] = round(e.get('dx', 0.0) + dx, 3); e['dy'] = round(e.get('dy', 0.0) + dy, 3)
        self.persist_ui(); self.update_preview()

    def context_menu(self, e):
        t = self.target_at(e)
        if not t:
            return
        _, kind, d = t
        m = tk.Menu(self, tearoff=0)
        if kind == 'text':
            m.add_command(label='Change text…', command=lambda: self.text_change(d['fid']))
            m.add_command(label='Text size…', command=lambda: self.text_size(d['fid']))
            m.add_command(label='Delete', command=lambda: self.text_delete(d['fid']))
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
                       'texts': [dict(t) for t in mem.get('texts', [])], 'art_pos': dict(mem.get('art_pos', {}))}
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

    def persist_ui(self):
        """Save ignored parts and label edits into the panel's memory file straight away (if there is one yet)."""
        b = self.board.get()
        if not b:
            return
        mem_path = panel_paths(b)[1]
        mem = load_json(mem_path)
        if not mem:
            return               # no panel yet: saved with the first Generate
        mem['ignore_uncut'] = self.ui['ignore']; mem['label_edits'] = self.ui['label_edits']
        mem['texts'] = self.ui.get('texts', []); mem['art_pos'] = self.ui.get('art_pos', {})
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
    App(sys.argv[1] if len(sys.argv) > 1 else None).mainloop()
