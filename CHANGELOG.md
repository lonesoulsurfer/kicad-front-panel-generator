# Changelog

## 0.18.2

- **Labels for parts with no hole.** Edge jacks, a reset button behind the panel and anything else marked "no cutout needed" now get a label too, on the side of the part that's inside the panel (or on the part itself if neither side fits). They're listed as "(no hole)" in Edit labels, so you can hide any you don't want.
- **Better label text from references.** A part named in its reference, such as `AMT1` or `FX1`, is now labelled `AMT` / `FX`. Standard references (`RV1`, `SW3`, `J2`...) still aren't used as labels.
- **Says why a part has no label.** When a part's name is passed over (`TFT_3.5_ST7796S_SPI` looks like a part name, `10K` is a component value), Edit labels shows what was skipped and why, and Result has a CHECK line for it. Hide the label to clear the CHECK.
- **A gap for each label.** Double-click Gap in Edit labels to set one label's distance from its hole (blank = the main Gap setting), e.g. pot labels further down so knobs don't cover them.
- **Edge jacks: Above / Below puts the label inside the panel edge.** For a part that runs off the panel (a jack on the top edge), choosing the off-panel side puts the label just inside that edge; the gap is then measured from the edge.
- **3.5" ST7796S screen window is now 85.8 × 56.5 mm** (was 87 × 58). The glass is 85.00 × 55.26 mm, so this leaves about 0.4 mm of play at each end, 0.6 mm at each side, and 1.0 mm of panel between the screen screws and the window (was 0.41 mm).
- **Artwork guides follow the PCB.** Saving the PCB or changing a setting updates the red cutouts, label guides and part markers in the artwork file straight away, not only on Generate (and also when artwork is switched off). The window says *Guides updated* and to use File → Revert in Inkscape.
- **Drawings on a guide layer are no longer lost.** Anything you drew or pasted on the red cutout, labels or markers layer is moved to a new *Moved off the guide layers* layer before the guides are rebuilt, with a CHECK in Result. The new layer goes on top of your own layers (where it was), so white that cuts out of black stays above the black. Guide shapes are now tagged so they can be told apart from yours.
- Refreshing the guides no longer makes Inkscape render the artwork again (the cache ignores the guide layers).

## 0.18.1

- **Open in KiCad** checks the panel is up to date first. If a setting, the PCB or the artwork changed since the panel was generated, it asks whether to generate first, open the old panel, or cancel. With no panel yet, it offers to generate one.

## 0.18.0 (first packaged release)

- Panels from any KiCad 9/10 PCB: cutouts from rules, the Panel field, or shapes drawn on User.1
- Eurorack templates and panels, 2-42HP
- Live preview with zoom, warnings for thin webs, rail clashes and parts with no cutout
- Labels from the PCB, artwork from Inkscape, part markers for lining artwork up
- Deleted and resized holes remembered between runs
- Gerbers, drill files and KiCad DRC in one click
