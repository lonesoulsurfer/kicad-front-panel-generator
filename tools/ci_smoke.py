"""Smoke test for the window, run by the build on Windows before anything is published.
Opens the demo board, drives the preview with real Tk mouse events, generates a panel, and fails loudly if anything is off."""
import importlib.machinery, os, shutil, sys, tempfile, traceback

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
work = tempfile.mkdtemp()
os.environ['APPDATA'] = work
board = shutil.copy(os.path.join(root, 'examples', 'demo_synth', 'Demo_Synth.kicad_pcb'), work)
sys.path.insert(0, root)
gui = importlib.machinery.SourceFileLoader('gui', os.path.join(root, 'panelgen_gui.pyw')).load_module()
said = []
gui.messagebox.showwarning = gui.messagebox.showinfo = gui.messagebox.showerror = lambda *a, **k: said.append(a[1])
gui.messagebox.askyesno = lambda *a, **k: False
app = gui.App(board); app.geometry('1400x900+0+0')
c, fails, menus = app.canvas, [], []
app.context_menu = lambda e: menus.append((e.x, e.y))       # a real menu would wait for a click nobody makes

def check(what, ok):
    print(('ok    ' if ok else 'FAIL  ') + what, flush=True)
    if not ok:
        fails.append(what)

def px(mx, my):
    sc, ox, oy = app.cur_view
    return int(ox + mx * sc), int(oy + my * sc)

def mouse(button, a, b=None):
    c.event_generate(f'<ButtonPress-{button}>', x=a[0], y=a[1])
    if b:
        for k in range(1, 6):
            c.event_generate(f'<B{button}-Motion>', x=int(a[0] + (b[0] - a[0]) * k / 5), y=int(a[1] + (b[1] - a[1]) * k / 5))
    c.event_generate(f'<ButtonRelease-{button}>', x=(b or a)[0], y=(b or a)[1])
    app.update()

def run():
    v = app.vars
    check('demo board loads into the preview', bool(app.pv) and 'message' not in app.pv and len(app.pv['shapes']) > 3)
    v['expand'].set(True); v['margin'].set('12'); v['labels_on'].set(True); v['auto_on'].set(True); app.refresh_states()
    app.update_preview(); app.update()
    x1, y1, x2, y2 = app.pv['panel_box']
    check('labels and made artwork', len(app.pv['labels']) > 3 and len(app.pv['artwork']) > 3)
    for y in (30, 45):                                       # two extra holes in the left margin
        app.start_add('hole'); mouse(1, px(x1 + 6, y1 + y))
    check('two extra holes added by clicking', len(app.pv['added']) == 2)
    mouse(1, px(x1 + 1, y1 + 20), px(x1 + 11, y1 + 55))
    check('left-drag box selects both', len(app.shape_sel) == 2)
    app.shapes_set_spacing(14); app.shapes_duplicate(); app.update()
    ys = sorted(o['y'] for o in app.ui['shapes'])
    check('copy carries the spacing on', len(ys) == 4 and all(abs(b - a - 14) < 0.01 for a, b in zip(ys, ys[1:])))
    app.select(None)
    mouse(3, (300, 300), (360, 330))
    check('right-drag moves the view', app.view is not None and not menus)
    mouse(3, (300, 300))
    check('right-click opens the menu', len(menus) == 1)
    app.fit_view()
    app.toggle_measure(); mouse(1, px(x1, y1)); mouse(1, px(x2, y1)); app.update()
    check('ruler measures the panel width', len(app.measure) == 2 and abs(app.measure[1][0] - app.measure[0][0] - (x2 - x1)) < 0.01)
    app.end_measure()
    n = len(app.ui['shapes']); app.undo(); app.update()
    check('undo takes the copy back', len(app.ui['shapes']) == n - 2)
    app.generate(open_after=False); app.update()
    panel = gui.panel_paths(board)[0]
    check('panel file written', os.path.exists(panel) and open(panel, encoding='utf-8').read().count('gr_circle') >= 8)
    check('no error boxes', not said)

def go():
    try:
        run()
    except Exception:
        traceback.print_exc(); fails.append('crashed')
    app.destroy()

app.after(3000, go)
app.mainloop()
for s in said:
    print('said:', s)
sys.exit(1 if fails else 0)
