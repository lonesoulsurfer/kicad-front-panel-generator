# Panel Generator for KiCad: a button in the PCB editor that opens Panel Generator with the board you're working on.
# It can be installed twice - from the Plugin and Content Manager, and by Panel Generator's "Add to KiCad" - and only
# one button should show: the copy from the Plugin and Content Manager wins.
import os

PCM_NAME = 'com_github_lonesoulsurfer_panel-generator-button'


def _other_copy_wins():
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(here) == PCM_NAME:
        return False
    try:
        import pcbnew
        dirs = str(getattr(pcbnew, 'PLUGIN_DIRECTORIES_SEARCH', '')).split('\n')
    except Exception:
        return False
    return any(d and os.path.isdir(os.path.join(d, PCM_NAME)) for d in dirs)


if not _other_copy_wins():
    try:
        from .panel_generator_action import PanelGeneratorAction
        PanelGeneratorAction().register()
    except Exception as e:                  # never stop KiCad from loading because of this plugin
        import logging
        logging.getLogger(__name__).warning('Panel Generator button not loaded: %s', e)
