# Changelog

## 0.27.0

- **New licence:** from this version Panel Generator is free for non-commercial use under the PolyForm Noncommercial License 1.0.0, with an extra permission: you may sell the panels you make with it (for your own synths, kits and modules, even as a business). Selling the tool, or charging to use it on other people's designs, needs a commercial licence. See LICENSING.md. Versions up to 0.26.0 stay MIT.
- **Open Panel Generator from KiCad:** a small plugin adds a button to the PCB editor that opens Panel Generator with the board you're working on. Install it from this project's own list in KiCad's Plugin and Content Manager (the address is in the README), or from `KiCad-button-plugin.zip` in the download. Panel Generator notes where it is each time it starts, so the button finds it.
- **Faster preview:** a change on the left, a move, or adding or deleting something now takes about a fifth of the time it did (on the Sampler board, about 0.5 s down to 0.1 s). The PCB is read once and kept until you save it again, text and footprints are worked out once, and the checks for holes too close together skip pairs that are far apart. The preview also starts sooner after you stop typing. What it makes is the same: the panel files are byte-for-byte as before.
- **A title or maker name with no free space is still shown** (where it overlaps something, with a warning) so you can drag it somewhere clear. Before, it vanished, and the warning told you to drag something you couldn't see.
- **Delete on the maker name works** (it did nothing before).
- **Two parts with the same ID in the PCB file** (a footprint copied by hand or by a script) no longer share their labels, shapes and saved changes: each gets its own, and Result says which.
- **Clearer left side:** two tabs, *Panel* and *Artwork*, with your PCB always in view above them. Every setting has its name on the left and its box on the right, in one line, with small headings inside each section (Place, Text, Title, Pots, Buttons, Border...).
- **Sections fold away** when you click their heading, and optional ones (Labels, Your text and pictures, Artwork made for you, Artwork from Inkscape) have an on/off switch in the heading instead of a tick box.
- **The Artwork tab follows the order you work in:** Style, Title, Labels, Pots, Buttons, Jacks, Border, Pictures, Artwork from Inkscape. "Artwork made for you" is no longer one big section with a master switch: each part is switched on where it lives, and Style *None* turns the made parts off.
- **Your own texts are under Labels** (Add → Text…, and the text you click shows there), with the size and font that both kinds share. Pictures have their own section. Each can be left off the panel separately.
- **Box round a row of pots is under Pots** (and the same for Buttons and Jacks, each with its own tick box).
- **Fewer tick boxes:** *Extra round the PCB* and *Corner radius* are just numbers now (0 = none).
- **Border: gap from the edge and thickness.** Gap 0 keeps it automatic (just inside the case holes); thickness is 0.6 mm unless you change it.
- **Rings round buttons:** set the ring thickness and its gap from the hole.
- **Boxes round rows of controls can be resized:** click the box, then drag its top, bottom or a side. Pull a side and the other side follows, so the box stays centred. It stops at the biggest size that fits.
- **Drag a corner to resize** the title, a picture or one of your texts: click it, then pull one of the white corner squares.
- **What you click shows where it belongs:** a label (or the box round it) under Labels, your own text and pictures under theirs, the title, tabs and boxes under Artwork made for you.
- **Fixed: lists changing by themselves.** Scrolling the left side with the mouse wheel over a list (font, title direction, pot scale) changed its value. The wheel now only scrolls.
- **Fixed: the left side jumping to the top** when a setting changed.
- **A bar round several labels stays put when you move one label inside it,** so you can centre a label in it. Drag the middle of the bar to move it with every label in it. The box round a row of controls no longer shifts when you nudge a label.
- **Right-click any label, Change text:** also for labels that came from the PCB (the PCB itself isn't changed).
- **Fixed: a filled bar stretched over labels that had their own box hid one of them.** The longest bar now takes in every label it covers.
- **A box round text resizes evenly:** pull its top or bottom and the other follows; nudge an end of a bar that holds several labels (up to 6 mm) and the other end follows. Pull an end further, or past another label, and only that end moves, so you can still stretch a bar over more labels. Once a bar's ends sit unevenly (one lined up with a cutout, say), or an end snaps to an edge, only the end you pull moves. Shift always moves just the one edge.
- **Copy and paste:** Ctrl+C on what's selected (holes you added, one of your texts, a picture, or a label), Ctrl+V to paste it at the pointer. Right-click the panel for *Paste here*.
- **Lines:** draw a divider, a bracket or a signal-flow arrow (Artwork → Lines → Line, then two clicks). They snap to holes, other line ends and the ruler; Ctrl keeps them straight; they run right up to the edge of a hole. Click one and Thickness changes it; set its arrowheads or exact length under Selected; drag it to move it, drag an end to re-aim it.
- **My style:** *Save this look as my style* remembers the label size and font, scales, rings, boxes, tabs, border, title size and direction, maker name and line thickness. Every new PCB starts with it, and it is in the Style list for any panel.
- **Delete key** removes the selected line, text or picture, as well as holes you added.
- **Fixed: no output boxes on jacks that aren't on the PCB.** A round hole you added under Extra holes, or a jack placed by hand in the panel file, now gets its filled box when a text next to it says OUT. If the option is ticked and nothing qualifies, the Result box says why.
- **Drag a corner of a hole, rectangle or slot you added** to resize it. A rectangle's width and height change separately, with both shown as you drag.
- **Copy the title** (Ctrl+C, Ctrl+V): the copy says what the title says, with its own place, size and direction. Tick **Mirror image** on the title or on a copy to flip its letters left to right, for a mirrored pair. New direction *On its side, reading down* turns it the other way.
- **A bigger preview when you want one:** drag the bar between the settings and the preview, or the bar above the buttons and the Result box. The sizes are remembered.
- **Reset** (next to Undo) starts the panel again from the PCB: the PCB's own size and holes, nothing added. That includes anything placed or changed in the panel file in KiCad (panel jacks, screws, drawn cutouts, edited holes); when you next generate, the old panel file is kept as `<board>_panel.before-reset.kicad_pcb`. It asks first, and Undo brings everything back.
- **Shapes round any hole:** set the shape, filled or not, gap, line thickness and corners in the new **Shapes** section, then right-click any hole (from the PCB, the panel file or one you added) and choose *Add a shape round it*. Each new shape gets those settings. Click a shape and the same settings change it (the line above them says which shape you're changing). Click a shape to set its gap, line thickness and corners; drag its edges to resize it. Pull a filled box over a label and the label is cut out of it. On an outline, the gap is from the hole to the inside of the line, and a thicker line grows outwards (so gap 1 and thickness 5 leave 1 mm clear round the hole).
- **Buttons and Jacks are now one Shapes section,** with the automatic rings, output boxes, edge tabs and row boxes under *Made for you*.
- **Pick several things at once:** drag a box round them, or Shift-click. Labels, your texts, lines, pictures and holes you added can be picked together, then dragged together, copied (Ctrl+C / Ctrl+V keeps their spacing) or deleted.
- **Delete key** works on whatever is selected. A label from the PCB is hidden rather than deleted (Edit labels or Undo brings it back).
- **Parts under a window show in the preview:** keys under one big opening (or merged into one slot) are drawn as blue dotted outlines with a cross at their middle.
- **Texts line up in rows by themselves:** a text you add or drag snaps over the middle of each of those keys (the nearest one to it), and level with the labels already there, from up to 2 mm away at any zoom.
- **Settings save as you go.** The settings on the left are saved with the panel as soon as you change them, like your work in the preview, so closing the window without generating no longer loses them. (Generate panel is still what updates the panel file in KiCad.)
- **Tactile switches get a hole:** 6×6 mm tact switches (KiCad's SW_PUSH_6mm, PTS645, B3S-1000 and similar) get a 4.0 mm hole for the button, 12×12 mm ones 7.5 mm, centred on the button rather than on pin 1. New panel part `Panel_Tact_4.0mm`, and *4 · 6x6 tactile switch* in the Hole size list.
- **How to… at the bottom of each tab:** short answers for what the generator can't guess, such as changing one part's hole with a Panel field, a hole for an unknown part, stopping a hole, holes for things not on the PCB, labels, shapes, measuring. Click a question to open it.
- **Part-size guides:** right-click a hole and choose *Show the part's size round it* (circle or rectangle, or on every hole that size). A dashed blue outline shows the part's real body, nut or knob. Drag its edge to size it; the size and the gap to the nearest part show as you drag. A rectangle's sides move one at a time (Shift keeps it even round the hole), so it can show a board that sits off to one side of its hole. Never cut or printed.
- **Delete, arrows and Ctrl+C always act on the preview after you click in it,** even if you'd just typed in a box on the left (before, the key went to that box and nothing was deleted).
- **Delete key works on boxes too:** click a box round a label or text and press Delete - the box goes, the text stays. A box the artwork made (round an output, an edge tab, a row of pots) can be deleted the same way, or with right-click → Delete box; right-click the panel → *Bring back deleted boxes* restores them. Delete on the title or maker clears it. Undo brings any of it back.
- **Screw heads:** every screw hole (PCB mounting holes, case holes, screw holes of screens and the like) shows a dotted circle the size of the screw's head, and labels or artwork under it are flagged. Set the head size in the Panel tab (Auto = twice the hole, a screw from the list, your own size, or Off), or drag the edge of any of the dotted circles: it lights up when you're on it, the size shows as you drag, and every head changes to it. The list works like Hole size: "Your own size…", and sizes you type or drag are kept in the list.
- **Fine moves:** the arrow keys nudge whatever is selected 0.1 mm a press (1 mm with Shift), never snapped. A **Snap** tick box above the preview turns lining-up off altogether (Alt while dragging still does it for one move). The snap's reach is now measured on screen again, so zooming in makes it smaller. A text you add is selected straight away.
- **Measure:** hold Ctrl (or Shift) to keep the ruler dead level or straight up and down.
- **The ruler is also a guide.** After the first click, type a length (say 16) and press Enter to set the other end exactly that far away. The ruler then stays on the panel, and anything you drag, add or paste snaps to its ends and its middle. Type a new length to change it; *Clear ruler* removes it; M starts a new one.
- **Openings section removed.** "Make every opening bigger" is no longer in the window (still on the command line as `--grow`), and parts that look like they need a cutout are always flagged.

## 0.26.0

- **Extra holes:** add round holes (usual sizes in a list, or your own), rectangles and slots in the window, for things that aren't on the PCB. Click to place, or right-click the panel. They snap into line with the other holes.
- **Click a hole you added and pick a Hole size** from the list (or type one): the hole changes to that size.
- **Your own hole sizes:** choose *Your own size…* at the bottom of the Hole size list (or type straight into the box). Sizes you type are kept at the top of the list for next time.
- **Exact place and size** on the left, measured from the panel's left and top edges to the middle of the hole.
- **Select several** by dragging a box round them (or Shift-click), then move them together, line them up in a row or column, or type their spacing.
- **Copy** (Ctrl+D) repeats the selection with the same sizes and spacing; **Delete** removes it.
- **Measure:** a ruler in the preview that snaps to hole middles, hole edges and panel edges.
- **Moving around the preview is now a drag with the right (or middle) mouse button.** A left drag on an empty spot draws the selection box.

## 0.25.4

- **Stacked title:** the letters one under another, each the right way up. *Standing up* is now called *On its side*.

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
