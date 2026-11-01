# KiCad Front Panel Generator: technical guide

Everything in detail. For the short version, see the [README](../README.md).

Makes a front panel `.kicad_pcb` straight from your synth (or any) KiCad PCB: a cutout for every pot, jack, switch, LED and screen, sized and placed from the PCB itself. Add labels or your own Inkscape artwork, check it in a live preview, and get gerbers ready to order. Standard Eurorack panels (2-42HP) too.

No more marking parts on a User layer, PNG round trips, or redrawing the panel in Fusion.

## Install (Windows)

1. Download **`PanelGenerator-…-windows.zip`** from [Releases](https://github.com/lonesoulsurfer/kicad-front-panel-generator/releases) and unzip it anywhere (e.g. `Documents\PanelGenerator`).
2. Run **`PanelGenerator.exe`**. The first time, Windows may say *"Windows protected your PC"*. That's because the app isn't signed with a paid certificate: click **More info → Run anyway**.
3. You also need:
   - **KiCad 9 or 10.** Panels are KiCad 9 files, and **Make gerbers** uses KiCad's own command-line tool.
   - **[Inkscape](https://inkscape.org) 1.2 or later**, only if you want to add your own artwork.
4. In KiCad, add the two libraries from the unzipped folder: **Preferences → Manage Footprint Libraries → Global Libraries → folder icon**, then pick `PanelParts.pretty`, and again for `Eurorack.pretty`.

`panel_rules.json` next to the .exe holds the cutout sizes for each part. Edit it to add your own parts (see below).

## Run from source (Windows, macOS, Linux)

Python 3.10+.

```
pip install -r requirements.txt
python panelgen_gui.pyw
```

On Windows you can double-click **`Panel Generator.cmd`** instead. The command-line version is `panelgen.py` (see *Command line* below).

Every package is needed for the full app: `shapely` for the geometry, `sv-ttk` for the modern look (the window still works without it), and `contourpy`, `numpy` and `pillow` for reading Inkscape artwork.

## The Panel Generator window

Run **`PanelGenerator.exe`** (or from source, `Panel Generator.cmd` / `panelgen_gui.pyw`).

- **Left:** numbered steps. Pick your PCB from the dropdown of boards you've used recently (or **Browse…** for a new one), then the settings that apply to it. A PCB with a Eurorack template shows *Rail holes*; any other PCB shows *Panel size and shape* and *Case mounting holes*. Hover over an option for help.
- **Right:** a live **preview** of the panel. It updates when you change a setting, save the PCB in KiCad, or save the artwork in Inkscape. **Mouse wheel** zooms in and out where the pointer is, **drag** to move around, **Fit** (or double-click) shows the whole panel again. Cutouts that are too close to something turn **orange**, problems turn **red**, and parts that hit a Eurorack rail get a red box. Hover over a cutout to see what it is and its size. The PCB is the dashed blue outline.
- **Under the preview:** a status line says whether the saved panel is **up to date**, or has **changed since it was generated** (a setting, the PCB or the artwork). Then **Open in KiCad**, **Show folder**, **Make gerbers** and **Generate panel**, which writes the panel into the `Front Panel` folder.
- **Result** lists warnings and errors. Notes that need no action are folded into one line; click it to read them.

It remembers your settings for each board. Holes you deleted or resized in the panel, and parts you said need no cutout, are listed in the last step; select one and click **Bring back**.

Two habits that matter: **save the PCB** in KiCad before generating (only the saved file is read), and **close the panel** in KiCad before generating (the window warns you if it's still open).

## Command line

```
py panelgen.py Sampler.kicad_pcb
```

This writes `Front Panel/Sampler_panel.kicad_pcb`, in a **Front Panel** folder it creates next to the PCB: **the PCB outline**, plus a cutout for every pot, switch, screen, LED and so on, and the PCB's own mounting holes. Nothing else is added unless you ask:

```
py panelgen.py Sampler.kicad_pcb --margin 10 --screws corners
```

makes the panel 10 mm bigger all round and adds a case screw in each corner. Add `--again` to reuse the settings from the last run (from the command line or the window).

| Option | Default | Meaning |
|---|---|---|
| `--margin` | 0 | Extra panel beyond the PCB outline on every side. 0 = panel is exactly the PCB outline |
| `--margin-top/-right/-bottom/-left` | | Override one side |
| `--screws` | none | Case screw holes round the panel edge: `none`, `corners`, `corners+mid` |
| `--screw-dia` / `--screw-inset` | 2.2 / 3.5 | Case screw size, and distance from the panel edge to the hole **centre**. The window shows how much panel is left between hole and edge as you type |
| `--rail-slot` | 0 | Eurorack only: rail holes as horizontal slots this long |
| `--screw-slot` | 0 | Make the case holes slots this long, end to end (e.g. `--screw-slot 4` with a 2.5 mm hole). 0 = round |
| `--corner-radius` | 0 | Rounded panel corners |
| `--min-web` | 1.0 | Warn when material between two parts' cutouts is thinner |
| `--grow` | 0 | Make every opening (screens, switches, pots, jacks, LEDs) this much bigger, e.g. `--grow 0.5`. Screw and mounting holes stay as they are |
| `-o` | `Front Panel/<pcb>_panel.kicad_pcb` | Output file |

### Slotted case holes

Pick **Slots along the edge** in the window (or `--screw-slot 4`) to give the case screws some play. Slots run **along the edge**: top and bottom ones side to side, left and right ones up and down, corners side to side.

**Distance from edge** is measured to the centre of the slot's rounded end nearest that edge, so a slot is never closer to any edge than a round hole would be. Middle slots are centred on the middle of the side; corner slots start at the corner position and run inwards. The PCB's own mounting holes stay round.

### The Front Panel folder

Everything for the panel lives in `Front Panel` next to your PCB: the panel `.kicad_pcb`, its `.panelgen.json` memory, the SVG template, and the `.kicad_pro`/`.kicad_prl` KiCad makes when you open it. Your synth project folder stays clean.

Panels made by older versions (sitting next to the PCB) are **moved into the folder automatically** on the next run, memory included, so deleted holes stay deleted. If that old panel is still open in KiCad it can't be moved: you get an ERROR, close it and generate again.

## What it derives from the PCB (`panel_rules.json`)

| Part | Cutout | Centre taken from |
|---|---|---|
| Cherry MX | 19.05 mm square + 0.5 mm wiggle room (19.55), touching ones merge into slots | 4 mm centre hole |
| Pots (KiCad + EasyEDA R09), encoders | 7.5 mm | body circle (the shaft, not pin 1) |
| Toggle switch | 5.2 mm | footprint origin |
| LED 3 mm / 5 mm | 3.2 / 5.2 mm | body circle |
| Jack on the PCB (Thonkiconn / PJ398SM / PJ301M) | 6.2 mm | jack shaft |
| 2.8" TFT, 50 × 80 module (`MyProject:TFT_2.8in_ILI9341`) | 69.5 × 50 glass + 1 mm = 70.5 × 51 window + mounting holes at 2.2 mm | centre of the F.Fab outline |
| 2.8" TFT, smaller module (`TFT_Displays:ILI9341_TFT`) | 56 × 41 window + mounting holes at 2.2 mm | centre of the F.Fab outline |
| 2.4" ST7789V TFT | 49 × 37 + 0.5 clearance = 49.5 × 37.5 window + mounting holes | centre of the F.Fab outline |
| Alps SKRC 9 mm switch | 6.6 mm | footprint origin (the stem) |
| 3.5" ST7796S TFT | 87 × 58 window (landscape) + mounting holes at 2.2 mm | middle of the module's mounting holes |
| PJ-320D jacks (horizontal), 3×6 tactile switch | no cutout, and no "no cutout" warning | - |
| Mounting holes | 2.2 mm | footprint origin |

"Body circle" is the largest circle on F.Fab. EasyEDA footprints have no F.Fab, so the largest silkscreen circle is used instead and the run prints a CHECK line, because EasyEDA silkscreen isn't always exactly on the shaft.

Edit `panel_rules.json` to add parts. Rules match on the footprint library ID (a single glob or a list). `clearance` adds wiggle room to each dimension. `"shape": "none"` marks a part that never goes through the panel (no cutout, and no warning about it). `"centre": "npth_centre"` centres a cutout on the middle of the footprint's mounting holes, which suits screen modules.

### Drawing a cutout on the PCB (User.1)

**Anything you draw on the User.1 layer of the PCB becomes a cutout, exactly as drawn.** It's the quickest way to add a screen window, an odd-shaped hole, or anything panelgen has no rule for:

1. Pick **User.1** in the layer dropdown.
2. Draw a rectangle over the screen's visible area (KiCad snaps to the corners already drawn on the footprint), and circles over the mounting holes at the size you want in the panel.
3. Re-run. Each closed shape on User.1 becomes a cutout.

Rectangles, circles, polygons, and outlines made of lines and arcs all work. You can also put a User.1 shape **inside a footprint** in your library, and every board using that footprint then gets the cutout automatically, in the right place whatever the rotation.

- A User.1 shape that sits **entirely inside another cutout** is treated as an old centre marker and ignored (the run says how many).
- A User.1 shape that **sits on or around** a part panelgen already cuts (e.g. an old outline drawn round a screen or the switches) is treated as old markup and ignored, with a NOTE saying so. To make the drawing the cutout instead, add `Panel=skip` to the part(s) it replaces.
- Every drawn cutout is listed in the output, so a leftover marker turning into a hole is easy to spot.
- Use a different layer with `--panel-layer User.4`.

### Per-part control: the `Panel` field

Add a field named `Panel` to a footprint in KiCad:

- `skip`: leave this part off the panel (e.g. H1, H3)
- `circle:6.0`, `square:19.05`: override the cutout for this one part
- `rect:57x42`: rectangle, **width × height as you see it on the panel**, whatever way the footprint is rotated. This is the exact final size; no clearance is added.
- Add `holes` to also cut the footprint's mounting holes: `rect:74x50 holes` (2.2 mm) or `rect:74x50 holes=3` (3 mm). Use this for a screen panelgen has no rule for.

- Add `offset=X,Y` to shift the cutout from the centre, in mm as seen on the panel (+X right, +Y down). For displays whose glass isn't centred on the module, e.g. `rect:24x13 offset=0,-2.5`.

Overrides are centred on the footprint's F.Fab outline, not its origin, because many screen footprints put the origin on pin 1. If a footprint has no F.Fab outline, the origin is used and the run prints a CHECK line.

**To tweak a screen window** you can resize it in the panel (see *Changing a generated cutout*), or set the size on the PCB with `Panel` = `rect:49.8x37.6`. The PCB route also follows the screen if it moves.

## Labels (optional)

Tick **Add labels from the PCB** in the window (or `--labels on`) to print a label for each control on the panel's silkscreen (F.Silkscreen). It's off by default.

- **Where the text comes from:** a `Label` field on the part if it has one (the most reliable way: add a field called `Label` in KiCad). Otherwise its **Value**, if that reads like a name ("Play", "rec", "1"), or its **Reference**, if it isn't a plain designator ("Cutoff", or "Delay1", which becomes "Delay"). Component values (10K, 100nF), part numbers (ILI9341) and generic names (SW_SPDT, ~) are skipped.
- **Options:** above or below the hole, the gap between hole and text, text size, font (KiCad's own, or any font on your computer), bold, ALL CAPS.
- **Keys in a merged switch slot** get their label on their own side of the slot: top row above, bottom row below.
- **Edit labels…** opens a table of every label: tick to show or hide, double-click to change the text, click Position for above/below/auto. Click a label in the preview to jump to it.
- **Change labels in KiCad too:** move a label in the panel and it stays where you put it, even if the part later moves on the PCB (it keeps the same offset). Retype it and your text is kept. Delete it and it's hidden. All of these show up in Edit labels, where you can undo them.
- **Checks:** a WARN if a label runs into a cutout, goes off the panel or overlaps another label. For a font from your computer, the width is **measured from the font file**, so wide fonts (Space Madness, etc.) are checked properly. For KiCad's own font it's an estimate (about 0.8 x the text size per letter).
- **Text size and other fonts:** KiCad draws a font from your computer 1.4 x bigger than its text size (its letters fill an em square of size x 1.4). So 3.5 mm in a wide font is much bigger than 3.5 mm in KiCad's font. The preview and the SVG template both show the true size.
- Labels are also written into the SVG template, on a layer that isn't imported back (so they're never doubled up).
- **Panel-only parts** (jacks, charge port and so on, placed from PanelParts in the panel) get a label too. Add a field called `Label` to the part in the panel (e.g. `GATE IN`), or type the text in Edit labels, where they're listed as "P1 (panel)".
- A font other than KiCad's own must be installed on the computer that opens the panel file. The gerbers contain the letter shapes, so the fab doesn't need the font.

## Artwork from Inkscape (optional)

For anything labels can't do (borders, boxes, logos, white-on-black text, your own fonts), draw it in Inkscape on an exact 1:1 copy of the panel.

1. Tick **Add my artwork to the silkscreen** and click **Create artwork file**. This makes `<panel>_artwork.svg` in the Front Panel folder and opens it in Inkscape. The page *is* the panel. The cutouts are drawn in red on their own layer, so you can see exactly where everything goes, and **align to them**: click a red cutout, Shift+click your text, then use Align and Distribute with *Relative to: First selected*. Moving a red cutout by accident does no harm, because that layer is rebuilt from the PCB every time you generate.
2. Draw on the **Artwork** layer (or any layers of your own). **Every visible layer is printed**, except the red cutout layer and the labels guide. To leave a layer out (a reference picture, say), hide it with the eye icon. **Black prints** on the silkscreen. **White cuts out of black**, so a black bar with white text on it comes out as text cut into the bar. Any font installed on your computer works.
3. **Save** in Inkscape. The preview updates by itself, and Generate puts the artwork on F.Silkscreen.

How it works: Inkscape itself renders the Artwork layer (at 600 dpi), and Panel Generator traces it into silkscreen shapes, as KiCad's Image Converter does. Text, effects, clips and patterns all come out as they look in Inkscape. Edges are traced to a fraction of a pixel, and the imported shapes land within about 0.01 mm of where you drew them.

- **Don't change the page size** in Inkscape (Document Properties). The page position is what lines everything up.
- **Existing artwork** (e.g. an older Inkscape panel): select it all in the old file (hide any reference picture first), copy it, paste it into the new file's Artwork layer, group it (Ctrl+G), and drag it until your hole outlines sit on the red cutouts. Zoom in right on one hole for the last nudge (arrow keys, or Alt+arrow for fine steps). An SVG not made from the template is refused rather than imported in the wrong place.
- If the panel size changes later (margins), the artwork stays lined up with the holes. You get a NOTE to check anything near the edges.
- Artwork that runs past the panel edge is trimmed off. Over a hole, the fab removes it anyway.
- The traced shapes are cached, so Inkscape only runs again when the file changes.
- **Every time you generate**, the red cutout layer, the labels guide and the page size in your artwork file are brought up to date with the panel. Your own layers aren't touched.
- **Part markers (blue, dashed):** parts that don't get a hole (edge-mounted jacks, a reset button behind the panel, anything you clicked "no cutout needed" on) are drawn as blue outlines with their name, e.g. `J3 MIDI out`, so you can line labels up with them. Anything you draw on **User.2** on the PCB shows up as a marker too. Markers are never cut or printed, and they update every Generate like the red cutouts. (Don't use User.1 for markers: User.1 shapes are cut.)
- The file opens with a 1 mm grid (5 mm major lines) on a **light grey page**, so white artwork is visible while you draw. Toggle the grid with **#**. The page colour isn't printed.
- **If the preview doesn't match your Inkscape window** for some text (letters spaced differently, say), convert that text to shapes: select it, **Path > Object to Path**, and save. Inkscape's own command-line render, which does the work behind the scenes, can lay out some text settings (flowed text with odd line spacing) differently from the window. Keep an editable copy on a hidden layer if you like; hidden layers aren't printed.
- **White that isn't on black does nothing**, except where it crosses something black, which it cuts. Text that runs past the end of its black bar can nick the border without you seeing it on a white page. **Ctrl+5** (Outline view) shows everything as outlines.

## Eurorack panels

Add `Eurorack.pretty` as a footprint library (same way as PanelParts). It has a start-here template for 2-20HP plus 21, 22, 24, 26, 28, 32, 36 and 42HP.

1. New PCB. Press **A**, search `Eurorack_8HP` (or your size), place it. Leave it at **0 degrees**.
2. The template gives you the **PCB outline** on Edge.Cuts (0.5 mm in from each panel side, 106.5 mm tall), and the **panel outline, rail zones and rail holes** on User.Comments, so you can see the rails while placing parts.
3. Place pots, jacks, LEDs and so on as normal. Mount with the pot and jack nuts, or add mounting holes; they're picked up like any other board.
4. Generate. panelgen sees the template and makes a standard Eurorack panel lined up with it: 128.5 mm tall, the Doepfer width for that HP, rail holes 3.2 mm, 3 mm from top and bottom, 7.5 mm from the left.

- **Rail clash check:** any part whose courtyard reaches into a rail zone (top or bottom 11 mm) is an ERROR, as is a PCB outline drawn outside the area between the rails. Parts without a courtyard get a NOTE saying they weren't checked.
- **Slotted rail holes:** in *Rail holes* pick *Slots* (or `--rail-slot 5`). They run horizontally, centred on the standard position.
- Expand-panel and case-hole settings are ignored for Eurorack (NOTE), since the size and holes are standard.
- To use a different-shaped PCB, keep the template for the panel and rails, and draw your own outline on Edge.Cuts. You'll need to remove the template's Edge.Cuts rectangle, or KiCad sees two outlines.

| HP | Panel width | Rail holes (x from left) | Source |
|---|---|---|---|
| 2-3 | 9.8 / 14.9 | centred, top and bottom | narrow panels: centred |
| 4-5 | 20.0 / 25.0 | 7.5 top and bottom | 4HP drawing |
| 6-9 | Doepfer, or ~HP x 5.08 - 0.3 | top: 7.5 + (HP-3) x 5.08, bottom: 7.5 | 8HP drawing (top 32.9) |
| 10+ | Doepfer, or ~HP x 5.08 - 0.3 | 7.5 and 7.5 + (HP-4) x 5.08, top and bottom | 14HP drawing (58.3) |

Widths for 3, 5, 7, 9, 11, 13, 15, 17, 19, 24, 26, 32 and 36HP aren't in Doepfer's table and are estimated; the run prints a CHECK line for those. Rebuild the templates after changing the spec with `py make_eurorack.py`.

## Panel-only parts (jacks, charge port, extra screws)

Add `PanelParts.pretty` as a footprint library. Place its parts in the **panel** file and position them exactly using KiCad's properties (X/Y), Align and Distribute.

- `Panel_Jack_6.2mm`, `Panel_Jack_7.2mm`, `Panel_Toggle_5.2mm`, `Panel_LED_3.2mm`, `Panel_LED_5.2mm`
- `Panel_USB-C_Charge_12x4.3mm`: slot and both screw holes in one footprint, so they can't drift
- `Panel_Screw_2.2mm`, `Panel_Screw_3.2mm`

## Making your own panel parts (`panelpart.py`)

One line makes a finished panel-only footprint in `PanelParts.pretty`: centred on its origin, board-only, excluded from BOM and position files, nothing on silkscreen.

```
py panelpart.py slot 12x4.3 --name USB-C_Charge_Slot --holes 2.5@-8,0 2.5@8,0
py panelpart.py rect 74x50 --name TFT_3.5in --hole-grid 2.2 82x46
py panelpart.py rect 30x10 --radius 2 --name Rounded_Window
py panelpart.py circle 9.5 --name Big_Pot
```

| Shape | Meaning |
|---|---|
| `circle D` | round hole |
| `rect WxH` | rectangle; `--radius R` rounds the corners |
| `slot WxH` | slot with fully rounded ends (made as an oval drill, which fabs route as a slot) |
| `--holes D@X,Y …` | extra round holes, X/Y measured from the centre |
| `--hole-grid D WxH` | four holes of diameter D at the corners of a W × H rectangle (e.g. screen screws) |

Then in KiCad: press **A** in the panel, search for the name, place it, press **E** to type its X/Y. An existing name isn't overwritten unless you add `--force`. If you replace a part that's already on a panel, select it → right-click → **Update Footprint from Library**.

Anything else drawn on Edge.Cuts also counts: shapes inside your own footprints (lines, arcs, circles, rectangles, polygons, round or oval NPTH holes) and shapes drawn straight onto the panel. They're all included in the overlap and edge checks.

## Changing a generated cutout in KiCad

**Resize or move it in KiCad and panelgen keeps your version.** Double-click a hole and change its radius, or a screen window and change its size, then save, close and re-run:

```
  edit  TFT1 - changed in the panel to 56.50 x 41.50 mm, your version is kept
  yours TFT1 - edited in panel, kept as you left it (--restore TFT1 to regenerate)
```

- If that part later **moves on the PCB**, you get a WARN: your edited cutout stays where you left it. `--restore TFT1` replaces it with a fresh one in the new position.
- Deleting an edited cutout counts as deleting it.
- The **panel outline** is the exception: it's always rebuilt from the margins. Change its size with `--margin`, `--margin-top` and so on.

## Removing a generated hole

Just **delete it in the panel** (click it, press Delete), **save**, close the file, and re-run. panelgen notices it's gone and keeps it off on every later run, even if the part moves on the PCB:

```
  gone  H1 - deleted in the panel, will stay off
  off   H1 @(69.39, 33.69) - deleted in panel (--restore H1 to bring back)
```

To bring it back: `--restore H1` (or `--restore CASE-tl`, `--restore SW5` for a switch slot, `--restore all`).

This works for any generated cutout: holes, screen windows, TFT mounting holes, a switch slot, and case screws (named `CASE-tl`, `CASE-tr`, `CASE-br`, `CASE-bl`, `CASE-t`, `CASE-b`, `CASE-l`, `CASE-r`).

panelgen remembers deletions and edits in `<panel>.panelgen.json` in the Front Panel folder. **Keep it with the panel file.** Without it, panelgen can only spot deletions by matching shapes; if too much has changed it won't guess, and the hole comes back.

`Panel=skip` on the PCB still works too. Use it for parts that should never be on any panel.

## Re-running

Everything panelgen makes is in a group called `panelgen`. Re-running after changing the PCB replaces only that group. Your hand-placed parts and artwork stay, and they're included in the overlap and web checks.

- **Save and close the panel in KiCad before re-running.** Otherwise KiCad still has the old version open, and saving it later overwrites the new one.
- Don't add your own items to the `panelgen` group, or they'll be deleted on the next run.

## Gerbers

**Make gerbers** generates the panel, then has KiCad's own command-line tool (`kicad-cli`, part of KiCad 9 and 10) make everything the PCB maker needs:

- gerbers for F/B copper, F/B mask, F/B silkscreen and Edge.Cuts (Protel file names, e.g. `.gto`, `.gm1`), plus the job file
- drill files, plated and non-plated separately, with drill maps
- all of it zipped as `<panel>_gerbers.zip` in the Front Panel folder, ready to upload. The loose files are in `<panel>_gerbers` next to it.

It also runs **KiCad's DRC** on the panel and reports a summary in Result (the full report is `<panel>_drc.json`). Errors there are worth a look in KiCad (Inspect > Design Rules Checker). Warnings about silkscreen over holes or the board edge are normal for a panel with artwork: the fab trims silkscreen at cutouts.

From the command line: `py panelgen.py MyBoard.kicad_pcb --again --gerbers`.

## Checks

- **CHECK:** a part that looks like it goes through the panel (jack, switch, pot, encoder, LED, screen, MIDI socket…, judged by its footprint name) but has no rule, no Panel field and no User.1 drawing, so it got no cutout. The preview draws a dashed orange box on it. Give it a cutout, or **click its box in the preview** if it really stays behind the panel (it's then listed in the last step, to undo). You can also add `Panel=skip` to the part, or untick *Warn about parts that seem to need a cutout* to turn the check off
- **ERROR:** cutouts overlap, or a cutout crosses the panel edge (exit code 1)
- **WARN:** case holes with less than one hole-width of panel between hole and edge (e.g. a 2.5 mm hole needs 2.5 mm of material, so a distance of 3.75 mm). This is a rule of thumb, not a fab limit
- **WARN:** web thinner than `--min-web` between different parts, or to the edge. Spacing inside one footprint (e.g. the charge slot's screws) isn't checked, since that's by design.
- Messages include the position, so duplicate references (e.g. several `REF**`) can be told apart.
- **NOTE:** switches that almost touch (under 0.1 mm) are merged anyway and reported, because one is usually off-grid on the PCB
- **NOTE:** switch gaps thinner than `--min-web` (e.g. keys on a 19.3 mm pitch) are joined into one slot, since that sliver couldn't be made anyway
