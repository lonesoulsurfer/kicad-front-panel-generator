"""'Open Panel Generator' for KiCad's PCB editor.

This plugin is only a button: it opens Panel Generator (a separate app) with the PCB you have open. Panel Generator
itself is downloaded from https://github.com/lonesoulsurfer/kicad-front-panel-generator/releases.

How it finds the app:
1. Panel Generator writes where it lives into  <APPDATA>/panelgen/app.json  each time it starts, so after you've
   opened it once, the button just works.
2. Otherwise you're asked to find PanelGenerator.exe (or panelgen_gui.pyw) once; that's remembered.
"""
import json
import os
import subprocess
import sys

import pcbnew
import wx

RELEASES = 'https://github.com/lonesoulsurfer/kicad-front-panel-generator/releases'
HERE = os.path.dirname(os.path.abspath(__file__))
CONF_DIR = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'panelgen')
APP_FILE = os.path.join(CONF_DIR, 'app.json')                 # written by Panel Generator
MINE = os.path.join(CONF_DIR, 'kicad_button.json')            # what you picked here, if it came to that


def _read(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _works(cmd):
    """The command still points at something that's there."""
    return bool(cmd) and all(not os.path.isabs(p) or os.path.exists(p) for p in cmd[:2])


def app_command():
    """How to start Panel Generator: a list for subprocess, or None if it hasn't been found yet."""
    for path in (MINE, APP_FILE):
        cmd = _read(path).get('cmd')
        if isinstance(cmd, list) and _works(cmd):
            return cmd
    return None


def command_for(picked):
    """The command for a file you picked: the app itself, or the source script run by Python (not KiCad's own)."""
    if picked.lower().endswith(('.pyw', '.py')):
        if sys.platform == 'win32':
            return ['pyw', '-3', picked]                     # the Python launcher: the Python you installed shapely into
        return ['python3', picked]
    return [picked]


def remember(cmd):
    try:
        os.makedirs(CONF_DIR, exist_ok=True)
        with open(MINE, 'w', encoding='utf-8') as f:
            json.dump({'cmd': cmd}, f, indent=1)
    except OSError:
        pass


def start(cmd, board):
    kw = {}
    if sys.platform == 'win32':
        kw['creationflags'] = 0x00000008 | 0x00000200        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw['start_new_session'] = True
    subprocess.Popen(cmd + [board], close_fds=True, **kw)


class PanelGeneratorAction(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = 'Open Panel Generator'
        self.category = 'Front panel'
        self.description = 'Open this PCB in Panel Generator to make its front panel'
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(HERE, 'icon.png')
        self.dark_icon_file_name = os.path.join(HERE, 'icon.png')

    def Run(self):
        parent = wx.GetActiveWindow()
        board = pcbnew.GetBoard()
        path = board.GetFileName() if board else ''
        if not path:
            wx.MessageBox('Save the PCB first, then click Open Panel Generator again.', 'Panel Generator',
                          wx.OK | wx.ICON_INFORMATION, parent)
            return
        try:
            if board.IsModified():
                wx.MessageBox('Panel Generator reads the PCB as it is saved on disk.\n\n'
                              'Save in KiCad (Ctrl+S) to include your latest changes - Panel Generator updates '
                              'by itself when you do.', 'Panel Generator', wx.OK | wx.ICON_INFORMATION, parent)
        except Exception:
            pass                                             # older KiCad: no IsModified
        cmd = app_command()
        if cmd is None:
            ans = wx.MessageBox("Where is Panel Generator?\n\nClick OK to find PanelGenerator.exe (in the folder you "
                                "unzipped it to). If you haven't downloaded it yet, click Cancel and the download "
                                "page opens.", 'Panel Generator', wx.OK | wx.CANCEL | wx.ICON_QUESTION, parent)
            if ans != wx.OK:
                wx.LaunchDefaultBrowser(RELEASES)
                return
            wild = 'Panel Generator (PanelGenerator.exe;panelgen_gui.pyw)|PanelGenerator.exe;panelgen_gui.pyw|All files|*.*'
            with wx.FileDialog(parent, 'Find Panel Generator', wildcard=wild,
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                cmd = command_for(dlg.GetPath())
            remember(cmd)
        try:
            start(cmd, path)
        except OSError as e:
            remember([])                                     # forget it, so you're asked again next time
            wx.MessageBox(f"Panel Generator didn't start:\n{e}\n\nClick the button again to find it.",
                          'Panel Generator', wx.OK | wx.ICON_WARNING, parent)
