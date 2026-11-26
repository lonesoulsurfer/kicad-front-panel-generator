"""A PCB saved by KiCad 10 must give a panel file that says KiCad 10 (its setup block is copied from the PCB, and KiCad
10 writes that block in a new way: a file that says KiCad 9 with KiCad 10's setup can't be opened). A KiCad 9 PCB must
still give a KiCad 9 panel. Run from the repo folder: python tools/ci_kicad10.py"""
import os, re, sys, shutil, tempfile, io, contextlib
sys.path.insert(0, os.getcwd())
import panelgen as P

SRC = os.path.join('examples', 'demo_synth', 'Demo_Synth.kicad_pcb')
K10_SETUP = ('\t\t(tenting\n\t\t\t(front yes)\n\t\t\t(back yes)\n\t\t)\n\t\t(covering\n\t\t\t(front no)\n\t\t\t(back no)\n\t\t)\n'
             '\t\t(plugging\n\t\t\t(front no)\n\t\t\t(back no)\n\t\t)\n\t\t(capping no)\n\t\t(filling no)\n')

def panel_header(board_text, d):
    pcb = os.path.join(d, 'Board.kicad_pcb')
    open(pcb, 'w', encoding='utf-8').write(board_text)
    with contextlib.redirect_stdout(io.StringIO()):
        P.main([pcb])
    out = open(P.default_panel_path(pcb), encoding='utf-8').read()
    ver = re.search(r'\(version (\d+)\)', out).group(1)
    gen = re.search(r'\(generator_version "([^"]+)"\)', out).group(1)
    return ver, gen, out

bad = 0
src = open(SRC, encoding='utf-8').read()
with tempfile.TemporaryDirectory() as d:
    ver, gen, _ = panel_header(src, d)
    ok = (ver, gen) == ('20241229', '9.0')
    print(('ok  ' if ok else 'FAIL') + f' KiCad 9 PCB -> panel version {ver}, generator {gen}')
    bad += not ok
with tempfile.TemporaryDirectory() as d:
    k10 = src.replace('(version 20241229)', '(version 20260206)', 1).replace('(generator_version "9.0")', '(generator_version "10.0")', 1)
    k10 = re.sub(r'\t\t\(tenting front back\)\n', K10_SETUP, k10, count=1)
    assert '(front yes)' in k10, 'the KiCad 10 setup block was not put in'
    ver, gen, out = panel_header(k10, d)
    ok = (ver, gen) == ('20260206', '10.0') and '(capping no)' in out
    print(('ok  ' if ok else 'FAIL') + f' KiCad 10 PCB -> panel version {ver}, generator {gen}, KiCad 10 setup kept: {"(capping no)" in out}')
    bad += not ok
sys.exit(1 if bad else 0)
