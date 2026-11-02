# Changelog

## 0.18.2

- **Labels for parts with no hole.** Edge jacks, a reset button behind the panel and anything else marked "no cutout needed" now get a label too, on the side of the part that's inside the panel (or on the part itself if neither side fits). They're listed as "(no hole)" in Edit labels, so you can hide any you don't want.
- **Better label text from references.** A part named in its reference, such as `AMT1` or `FX1`, is now labelled `AMT` / `FX`. Standard references (`RV1`, `SW3`, `J2`...) still aren't used as labels.
- **Says why a part has no label.** When a part's name is passed over (`TFT_3.5_ST7796S_SPI` looks like a part name, `10K` is a component value), Edit labels shows what was skipped and why, and Result has a CHECK line for it. Hide the label to clear the CHECK.
- **A gap for each label.** Double-click Gap in Edit labels to set one label's distance from its hole (blank = the main Gap setting), e.g. pot labels further down so knobs don't cover them.
- **Edge jacks: Above / Below puts the label inside the panel edge.** For a part that runs off the panel (a jack on the top edge), choosing the off-panel side puts the label just inside that edge; the gap is then measured from the edge.

## 0.18.1

- **Open in KiCad** checks the panel is up to date first. If a setting, the PCB or the artwork changed since the panel was generated, it asks whether to generate first, open the old panel, or cancel. With no panel yet, it offers to generate one.

## 0.18.0 (first packaged release)

- Panels from any KiCad 9/10 PCB: cutouts from rules, the Panel field, or shapes drawn on User.1
- Eurorack templates and panels, 2-42HP
- Live preview with zoom, warnings for thin webs, rail clashes and parts with no cutout
- Labels from the PCB, artwork from Inkscape, part markers for lining artwork up
- Deleted and resized holes remembered between runs
- Gerbers, drill files and KiCad DRC in one click
