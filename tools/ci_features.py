"""Feature test for the window, run by the build on Windows and Mac before anything is published.
Covers what changes or moves your files: designs (copy, rename, delete), back panels, the Front Panel folder layout and
the move from the old flat layout, text added in KiCad, text blocks, and the left column closing up.
Run from anywhere: python tools/ci_features.py"""
import glob, importlib.machinery, io, contextlib, json, os, re, shutil, sys, tempfile, traceback

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
work = tempfile.mkdtemp()
os.environ['APPDATA'] = work
os.makedirs(os.path.join(work, 'synth'))
board = shutil.copy(os.path.join(root, 'examples', 'demo_synth', 'Demo_Synth.kicad_pcb'), os.path.join(work, 'synth'))
FP = os.path.join(work, 'synth', 'Front Panel')
sys.path.insert(0, root)
import panelgen as P
gui = importlib.machinery.SourceFileLoader('gui', os.path.join(root, 'panelgen_gui.pyw')).load_module()
said = []
gui.messagebox.showwarning = gui.messagebox.showinfo = gui.messagebox.showerror = lambda *a, **k: said.append(a[1])
gui.messagebox.askyesno = lambda *a, **k: True               # yes to "delete this design?"
fails = []

def check(what, ok):
    print(('ok    ' if ok else 'FAIL  ') + what, flush=True)
    if not ok:
        fails.append(what)

def generate(app):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        P.main(app.build_args())
    return out.getvalue()

def centre(g):
    b = g.bounds
    return round((b[0] + b[2]) / 2, 2), round((b[1] + b[3]) / 2, 2)

def flat_layout_test():
    """Panels made before v0.32 sit straight in Front Panel: they move into a folder per design, your own files stay."""
    d = os.path.join(work, 'old')
    os.makedirs(os.path.join(d, 'Front Panel', 'images'))
    b = shutil.copy(board, d)
    with contextlib.redirect_stdout(io.StringIO()):
        P.main([b, '-o', os.path.join(d, 'Front Panel', 'Demo_Synth_panel.kicad_pcb')])
    f = os.path.join(d, 'Front Panel')
    for n in ('Demo_Synth_panel_artwork.svg', 'Demo_Synth_panel_gerbers.zip', 'Demo_Synth_panel.before-reset.kicad_pcb',
              'images/logo.png', 'my_own_drawing.svg', '~Demo_Synth_panel.kicad_pcb.lck'):
        open(os.path.join(f, n), 'w').write('x')
    moved, blocked = P.tidy_panel_folder(b)
    check('old layout: a KiCad lock file stops the move', blocked == ['Front'] and not os.path.isdir(os.path.join(f, 'Front')))
    moved, blocked = P.tidy_panel_folder(b, force=True)
    at = lambda *p: os.path.exists(os.path.join(f, *p))
    check('old layout: moved into Front, Inkscape, Gerbers, Backups and Pictures',
          not blocked and at('Front', 'Demo_Synth_panel.kicad_pcb') and at('Front', 'Demo_Synth_panel.panelgen.json')
          and at('Front', 'Inkscape', 'Demo_Synth_panel_artwork.svg') and at('Front', 'Gerbers', 'Demo_Synth_panel_gerbers.zip')
          and at('Front', 'Backups', 'Demo_Synth_panel.before-reset.kicad_pcb') and at('Pictures', 'logo.png')
          and not at('Demo_Synth_panel.kicad_pcb') and not at('~Demo_Synth_panel.kicad_pcb.lck'))
    check('old layout: a file the app did not make stays where it was', at('my_own_drawing.svg'))
    check('old layout: the panel is found in its new place',
          P.panel_path_now(b) == os.path.join(f, 'Front', 'Demo_Synth_panel.kicad_pcb'))

def run(app):
    v = app.vars
    check('demo board loads', bool(app.pv) and len(app.pv['shapes']) > 3)
    out = generate(app)
    front = os.path.join(FP, 'Front', 'Demo_Synth_panel.kicad_pcb')
    check('a new panel goes into Front Panel/Front', os.path.exists(front))

    # the left column closes up when a block is hidden (Tk keeps an emptied frame at its old size)
    holder = app.sides_row.master
    v['per_side'].set(True); app.refresh_states(); app.update()
    v['per_side'].set(False); app.refresh_states(); app.update()
    check('a hidden block leaves no empty space', holder.winfo_height() <= 2)

    # text block: lines held by their left end, one under the other
    x1, y1, x2, y2 = app.pv['panel_box']
    app.ask_text = lambda: ('FIRST LINE\nA MUCH LONGER SECOND LINE', 'left')
    app.add_text_at(x1 + 20, y1 + 8); app.update()
    blk = [t for t in app.ui['texts'] if t['text'] in ('FIRST LINE', 'A MUCH LONGER SECOND LINE')]
    check('a two-line text block, lined up on the left', len(blk) == 2 and all(t.get('align') == 'left' for t in blk)
          and blk[0]['x'] == blk[1]['x'] and blk[1]['y'] > blk[0]['y'])
    n_front_texts = len(app.ui['texts'])
    app.persist_ui(); generate(app)

    # designs: a copy has its own folder and settings
    app.ask_new_design = lambda cur: ('Dark', 'copy')
    app.new_design(); app.update()
    dark = os.path.join(FP, 'Dark', 'Demo_Synth_dark_panel.kicad_pcb')
    check('New design (copy) gets its own folder and panel file', app.design_name.get() == 'Dark' and os.path.exists(dark))
    app.ui['texts'] = []; app.persist_ui(); app.update_preview(); app.update()
    app.switch_design('Front'); app.update()
    check('each design keeps its own settings', len(app.ui['texts']) == n_front_texts)
    app.switch_design('Dark'); app.update()
    check('switching back opens the copy', app.design_name.get() == 'Dark' and len(app.ui['texts']) == 0)
    gui.simpledialog = getattr(gui, 'simpledialog', None)
    from tkinter import simpledialog
    simpledialog.askstring = lambda *a, **k: 'Dark 2'
    app.rename_design(); app.update()
    check('Rename moves the folder and renames the files',
          app.design_name.get() == 'Dark 2' and os.path.exists(os.path.join(FP, 'Dark 2', 'Demo_Synth_dark_2_panel.kicad_pcb'))
          and not os.path.exists(os.path.join(FP, 'Dark')))
    app.delete_design(); app.update()
    check('Delete moves the design into Deleted designs',
          app.design_name.get() == 'Front' and glob.glob(os.path.join(FP, 'Deleted designs', 'Dark 2 *', 'Demo_Synth_dark_2_panel.kicad_pcb'))
          and not os.path.exists(os.path.join(FP, 'Dark 2')))

    # back panel: mirrored about the PCB's middle, only the holes you keep
    front_boxes = [s['geom'].bounds for s in app.pv['shapes']]
    pc = app.pv['pcb_box']; cx = (pc[0] + pc[2]) / 2
    app.ask_new_design = lambda cur: ('Back', 'back')
    app.new_design(); app.update()
    pv = app.pv
    # each part's hole on its own (the front merges a row of switches into one slot), flipped back = inside a front hole
    back = [(round(2 * cx - x, 2), y) for x, y in (centre(h['geom']) for h in pv.get('back_hidden', []))]
    inside = lambda p, b: b[0] - 0.02 <= p[0] <= b[2] + 0.02 and b[1] - 0.02 <= p[1] <= b[3] + 0.02
    check('back panel: the other holes are guides, at mirrored positions',
          pv.get('side') == 'back' and back and all(any(inside(p, b) for b in front_boxes) for p in back)
          and all(any(inside(p, b) for p in back) for b in front_boxes))
    check('back panel: no labels or part artwork', not pv.get('labels') and v['labels_on'].get() is False)
    h = pv['back_hidden'][0]
    app.back_hole(h['key'], True); app.update()
    check('back panel: a hole added with the right-click command', len(app.pv['shapes']) == len(pv['shapes']) + 1
          and centre(app.pv['shapes'][-1]['geom']) in {centre(h['geom'])} | {centre(s['geom']) for s in app.pv['shapes']})
    generate(app)
    back = os.path.join(FP, 'Back', 'Demo_Synth_back_panel.kicad_pcb')
    mem = json.load(open(back[:-len('.kicad_pcb')] + '.panelgen.json', encoding='utf-8'))
    check('back panel: written to Front Panel/Back, and stays a back panel',
          os.path.exists(back) and mem.get('side') == 'back' and mem.get('back_on') == [h['key']])
    app.back_hole(h['key'], False); app.update()
    check('back panel: the hole taken off again', len(app.pv['shapes']) == len(pv['shapes']))

    # text and lines added in KiCad: kept, shown, checked
    app.switch_design('Front'); app.update()
    hole = app.pv['shapes'][0]['geom'].bounds
    t = open(front, encoding='utf-8').read().rstrip()
    assert t.endswith(')')
    add = (f'\t(gr_text "ADDED IN KICAD" (at {x1 + 40:.2f} {y2 - 6:.2f} 0) (layer "F.SilkS") (uuid "11111111-2222-3333-4444-555555555555")\n'
           f'\t\t(effects (font (size 1.5 1.5) (thickness 0.2))))\n'
           f'\t(gr_text "OVER A HOLE" (at {(hole[0] + hole[2]) / 2:.2f} {(hole[1] + hole[3]) / 2:.2f} 0) (layer "F.SilkS") '
           f'(uuid "11111111-2222-3333-4444-666666666666")\n\t\t(effects (font (size 1.5 1.5) (thickness 0.2))))\n'
           f'\t(gr_line (start {x1 + 40:.2f} {y2 - 4:.2f}) (end {x1 + 60:.2f} {y2 - 4:.2f}) (stroke (width 0.3) (type solid)) '
           f'(layer "F.SilkS") (uuid "11111111-2222-3333-4444-777777777777"))\n')
    open(front, 'w', encoding='utf-8').write(t[:-1] + add + ')\n')
    app.update_preview(); app.update()
    items = app.pv.get('kicad_items', [])
    st = {i.get('text') or i['what']: i.get('status') for i in items}
    check('KiCad items: shown in the preview', len(items) == 3)
    check('KiCad items: one over a hole is warned, the others are not',
          st.get('OVER A HOLE') == 'warn' and st.get('ADDED IN KICAD') == 'ok' and st.get('a line') == 'ok'
          and any('added in KiCad' in l and 'OVER A HOLE' in l for l in app.pv.get('log', [])))
    generate(app)
    t2 = open(front, encoding='utf-8').read()
    check('KiCad items: kept when the panel is generated again',
          t2.count('ADDED IN KICAD') == 1 and t2.count('OVER A HOLE') == 1 and '11111111-2222-3333-4444-777777777777' in t2)

    flat_layout_test()
    check('no error boxes', not said)

def main():
    app = gui.App(board); app.geometry('1400x900+0+0')
    def go():
        try:
            run(app)
        except Exception:
            traceback.print_exc(); fails.append('crashed')
        app.destroy()
    app.after(3000, go)
    app.mainloop()
    for s in said:
        print('said:', s)
    sys.exit(1 if fails else 0)

main()
