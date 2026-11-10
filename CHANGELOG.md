# Changelog

## 0.25.3

- **Undo covers everything:** settings on the left (panel size, margins, holes, labels, artwork options) as well as changes in the preview. The history is kept when you generate.

## 0.25.2

- **Put my text and pictures on the panel** tick box (in *Your text and pictures*): untick to leave your own text, its boxes and your pictures off without losing them.

## 0.25.1

- A box stretched over other texts takes them in: one long bar under a row of keys, each name cut out where it is.

## 0.25.0

- **Undo** button (and Ctrl+Z) for changes made in the preview and the left panel's selection settings.
- **Right-click an empty spot** to add text or a picture there.
- **Title across or standing up** along a side.
- **Turn pictures** by any angle, or 90° at a time.
- **Snaps half way between two holes** in a row or column, e.g. MIDI over its IN and OUT jacks.
- **A text you add saying OUT next to a jack** gives that jack an output box, for jacks with no label on the PCB.
- README: new screenshots and a step for your own text, pictures and boxes.

## 0.24.0

- **Boxes round text:** a line round a text or label, or a filled bar with the text cut out. Drag the ends to stretch it over two keys (snaps to key labels and other boxes); the text stays centred.
- Grabbing near the edge of a tab or box now always resizes it, even with text right next to the edge.

## 0.23.0

- **Tidier window:** the steps are grouped under *Panel* and *Artwork*, each step in its own box. *Holes you removed or changed* moves up into Panel.
- **Click to select:** click a label, your text, a picture, the title or a tab in the preview, and its settings appear on the left under *Your text and pictures* (with Add text… and Add picture…). Right-click still works as a shortcut.
- **Bigger tabs:** drag an edge of an edge tab or output box to enlarge it; it snaps to the edges of the others. Or type the amount on the left.

## 0.22.0

- **Pictures:** Add picture… puts a PNG, JPG or SVG on the panel; drag it, size it, print its dark or light parts.
- **Snapping** also lines things up with markers, tabs and pictures, and with the middle of the gap between two things (e.g. a title between the screen and the edge).
- Edge-tab labels snap, and the shared word under an edge tab (MIDI) can be dragged.
- Add text… moved into the Artwork made for you section.

## 0.21.1

- Labels cut out of an output box or an edge tab can be dragged too; the box or tab follows the label.

## 0.21.0

- **Artwork made for you, stage 2:** boxes round rows or columns of 3+ of the same control, and filled tabs for jacks on the panel edge (labels cut out; MIDI IN / MIDI OUT become IN / OUT with MIDI underneath).
- **Border corner radius:** give the border its own rounded corners.
- **Add text…** button in the Artwork made for you section too.

## 0.20.1

- **Snapping:** a text, label or title you drag (or add) snaps into line with the other labels and to the middle of holes, with pink guide lines while you drag. Hold Alt to place it freely.

## 0.20.0

- **Drag to move** in the preview: labels, the title, the maker name and your own text. Right-click for more (put it back, hide, change, delete).
- **Add text:** your own text anywhere on the panel (e.g. what each key does), printed and checked like a label. Kept if you move, retype or delete it in KiCad.

## 0.19.0

- **Artwork made for you** (new section, or `--auto-art on`): pot scales (ticks, 0-10 or centre zero over 300°), rings round buttons, outputs in filled boxes with the label cut out, a border, a title and a maker name, placed from the panel and checked against holes, labels and the edge. Styles: Minimal, Classic synth, Modular. Per-part scale and input/output in Edit labels. No Inkscape needed; the result also appears in the Inkscape file as a guide layer.
- Pot labels start outside the knob and scale (with auto artwork on), and any label whose usual side hits a cutout or the edge moves to the other side.

## 0.18.2

- **Labels for parts with no hole.** Edge jacks, a reset button behind the panel and anything else marked "no cutout needed" now get a label too, on the side of the part that's inside the panel (or on the part itself if neither side fits). They're listed as "(no hole)" in Edit labels, so you can hide any you don't want.
- **Better label text from references.** A part named in its reference, such as `AMT1` or `FX1`, is now labelled `AMT` / `FX`. Standard references (`RV1`, `SW3`, `J2`...) still aren't used as labels.
- **Says why a part has no label.** When a part's name is passed over (`TFT_3.5_ST7796S_SPI` looks like a part name, `10K` is a component value), Edit labels shows what was skipped and why, and Result has a CHECK line for it. Hide the label to clear the CHECK.
- **A gap for each label.** Double-click Gap in Edit labels to set one label's distance from its hole (blank = the main Gap setting), e.g. pot labels further down so knobs don't cover them.
- **Edge jacks: Above / Below puts the label inside the panel edge.** For a part that runs off the panel (a jack on the top edge), choosing the off-panel side puts the label just inside that edge; the gap is then measured from the edge.
- **3.5" ST7796S screen window is now 85.8 × 56.5 mm** (was 87 × 58). The glass is 85.00 × 55.26 mm, so this leaves about 0.4 mm of play at each end, 0.6 mm at each side, and 1.0 mm of panel between the screen screws and the window (was 0.41 mm).
- **Artwork guides follow the PCB.** Saving the PCB or changing a setting updates the red cutouts, label guides and part markers in the artwork file straight away, not only on Generate (and also when artwork is switched off). The window says *Guides updated* and to use File → Revert in Inkscape.
- **Drawings on a guide layer are no longer lost.** Anything you drew or pasted on the red cutout, labels or markers layer is moved onto the top of your topmost visible layer (normally Artwork) before the guides are rebuilt, with a CHECK in Result, so white that cuts out of black stays above the black and no extra layers appear. Guide shapes are now tagged so they can be told apart from yours.
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
