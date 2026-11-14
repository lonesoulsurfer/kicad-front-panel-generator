# Panel Generator for KiCad: a button in the PCB editor that opens Panel Generator with the board you're working on.
try:
    from .panel_generator_action import PanelGeneratorAction
    PanelGeneratorAction().register()
except Exception as e:                      # never stop KiCad from loading because of this plugin
    import logging
    logging.getLogger(__name__).warning('Panel Generator button not loaded: %s', e)
