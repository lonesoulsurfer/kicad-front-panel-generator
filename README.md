# KiCad Front Panel Generator

Turn your KiCad PCB into a matching front panel in one click.

Every pot, jack, switch, LED and screen on the board gets a hole in the right place and the right size. Add labels or your own Inkscape artwork, check it all in a live preview, and get gerbers ready to send to the fab. It does standard Eurorack panels (2-42HP) too.

You don't need to trace parts onto a User layer, export to Fusion or Inkscape and back, or redraw the panel by hand.

**▶ Watch the video: [Front Panel Design - Made Easy!](https://youtu.be/l9CzSfH8hN0)**

[![Front Panel Design - Made Easy! on YouTube](https://img.youtube.com/vi/l9CzSfH8hN0/hqdefault.jpg)](https://youtu.be/l9CzSfH8hN0)

![A finished panel in KiCad's 3D viewer](docs/images/finished_3d.png)

*The front panel for my Game of Life synth: holes, labels, pot scales, boxed key functions and the glider all made in Panel Generator, no Inkscape. Shown in KiCad's 3D viewer.*

## What you need

- **Windows** (to run from source on macOS or Linux, see the [technical guide](docs/TECHNICAL.md#run-from-source-windows-macos-linux))
- **KiCad 9 or 10**
- **[Inkscape](https://inkscape.org)** 1.2 or later, only if you want to add your own artwork

## Install

1. Download **`PanelGenerator-…-windows.zip`** from [Releases](../../releases) and unzip it anywhere.
2. Run **`PanelGenerator.exe`**. The first time, Windows may show *"Windows protected your PC"*. That's because the app isn't signed with a paid certificate. Click **More info → Run anyway**.
3. *(Optional)* In KiCad, add the two footprint libraries from the unzipped folder: **Preferences → Manage Footprint Libraries → Global Libraries → folder icon**. Add `PanelParts.pretty` (extra panel holes such as jacks and screws) and `Eurorack.pretty` (Eurorack templates).

## How to use it

### 1. Pick your PCB

Save your KiCad board, then open Panel Generator, click **Browse…** and choose the `.kicad_pcb` file you just saved. Once it's loaded, the preview shows a front panel the exact shape of your PCB, with holes cut out for all the parts that need them, such as pots, LEDs, audio sockets, switches and screens.

![The preview after loading a PCB](docs/images/step1_preview.png)

Panel Generator only reads the saved 'kicad_pcb' file, so save in KiCad again whenever you move a part. The preview updates by itself when you do. Boards you've used before are in the dropdown, so next time you can pick one from there instead of browsing.

### 2. Set the size, corners and case holes

By default the panel is the same size as your PCB. Use the settings on the left to change it:

- **Make the panel bigger than the PCB by**: increases the panel size around each edge, good for when you are adding a case (tick *Different amount on each side* to set each side separately).
- **Rounded corners**: sets the corner radius.
- **Case mounting holes**: screw holes to fix the panel to your case, in the corners or in the corners and the middle of each side. Set the hole size and how far its centre sits from the edge. The line underneath tells you how much panel is left between the hole and the edge. Pick **Slots** instead of round holes if you want some play to line the panel up.

Every change shows in the preview straight away. Use the **mouse wheel** to zoom in, **drag** to move around, and **Fit** to see the whole panel again. Hover over any hole to see which part it's for and how big it is.

The colours in the preview tell you what to check:

- **Orange outline:** a hole is very close to the panel edge or to another hole, so the panel there may be too thin.
- **Red outline:** a real problem, such as two holes overlapping.
- **Orange dashed box:** a part that looks like it might need a hole but doesn't have one. If it really doesn't (a tactile switch hidden behind the panel, say), click it in the preview and it won't be flagged again. If it does, see the [technical guide](docs/TECHNICAL.md) for how to add one.

The **Result** box under the preview lists anything that needs your attention.

### 3. Add labels (optional)

Tick **Add labels from the PCB** and a label section opens. Each pot, jack and switch gets a name printed next to its hole on the panel's silkscreen. The name comes from the PCB: a `Label` field if you've added one to the part, otherwise its Value (for example, a pot with the Value `Cutoff` is labelled CUTOFF).

- Choose whether labels go **above** or **below** the holes, and the **gap** between label and hole.
- Set the **text size** and **font**, and turn **bold** and **ALL CAPS** on or off.
- Click **Edit labels…** to see every label in a list, where you can change the text or remove any you don't want.

![Labels added from the PCB, in a custom font](docs/images/step3_labels.png)

### 4. Let it make the artwork (optional)

Don't want to open Inkscape? Tick **Make artwork for me** and Panel Generator draws the artwork from your panel:

- **Pot scales:** tick marks, 0–10 numbers or centre-zero (− 0 +) round each pot, over a 300° turn. Set the **Knob** size so the scale and the label start outside the knob.
- **Rings** round push buttons.
- **Outputs in filled boxes:** any jack whose label says OUT gets a solid box with the label cut out of it, the usual way modular panels show outputs. A text you add saying OUT right next to a jack counts too.
- **Boxes round rows of controls:** a box round 3 or more of the same control in a row or column, scales and labels inside.
- **Tabs for edge jacks:** jacks on the panel edge (the plug goes in from the side) get a filled tab hanging from the edge with their labels cut out. Labels like MIDI IN and MIDI OUT become IN / OUT with MIDI underneath. Drag an edge of a tab or output box to make it bigger; it snaps to the edges of the others, so you can make them all the same size.
- **Border** (square, following the panel, or with its own rounded corners) and a **title**, across the top, stacked down a side (letters one under another) or turned on its side (plus your name or brand, small, along the bottom). They go in the first free spot; drag them anywhere.

Pick a **Style** to start from (*Minimal*, *Classic synth* or *Modular*) and change anything after. To change one part (a centre-zero scale for a pan pot, or a jack that's an output but isn't labelled OUT), click its **Artwork** cell in **Edit labels**. Anything that would hit a hole, a label or the edge is left out, and you get a note.

![Artwork made for you](docs/images/auto_artwork.png)

You can use this and Inkscape together: the made artwork appears in the Inkscape file on its own layer, so you can draw more on top.

### 5. Add your own text, pictures and boxes (optional)

Everything here is done in the preview, with the settings under **Your text and pictures** on the left. Untick **Put my text and pictures on the panel** to leave them all off (for example when you switch to Inkscape artwork that has its own text); tick it again and they're back.

- **Move anything by dragging it:** a label, your text, a picture or the title. It snaps into line with the other labels, to the middle of holes, half way between two holes (a MIDI label over its IN and OUT jacks), and to the middle of the gap between two things. Hold **Alt** to place it freely.
- **Click anything to change it.** Its settings appear on the left: text, size, put it back, hide or delete.
- **Add text** for things that aren't on the PCB, such as what each key does: click **Add text…** (or right-click the panel and choose *Add text here*), then click where it goes and type it.
- **Boxes round text:** for a key with two jobs, or a function that needs two keys pressed, click the text and set **Box** to *Line round it* or *Filled bar* (text cut out). Then drag the box's ends to stretch it over the keys. It snaps to the key labels and to other boxes. Stretch it over other texts and they go into the box too, where they are: one long bar under a row of keys. A box round just one text keeps it in the middle.
- **Pictures:** click **Add picture…** and pick a PNG, JPG or SVG (a glider, a logo). Its dark parts print. Drag it into place, then click it to set its width, turn it, print its light parts instead, or delete it.
- **Undo** (or Ctrl+Z) takes back the last change, whether it's a setting on the left (panel size, labels, artwork options…) or something you did in the preview, up to 50 steps.

![Your own text, pictures and boxes](docs/images/text_pictures.png)

### 6. Draw your own artwork in Inkscape (optional)

Labels only do text. For anything else (borders, logos, boxes, white-on-black text, your own fonts), tick **Add my artwork to the silkscreen** and click **Create artwork file**.

This saves an Inkscape file in the `Front Panel` folder and opens it. The Inkscape page is an exact 1:1 copy of your panel, and every hole is drawn in red so you can see where things go. You can also line your designs up with the red holes using Inkscape's **Align and Distribute**.

![The artwork file when it first opens in Inkscape](docs/images/step4_inkscape.png)

- Draw on the **Artwork** layer. Don't move or resize the page.
- **Black** prints on the panel as silkscreen.
- **White** cuts out of black, so white text on a black bar comes out as text cut into the bar.
- **Save** in Inkscape. Panel Generator picks the file up automatically and the preview updates with your artwork. Change it and save again as often as you like.
- **Moved something on the PCB?** The red holes in the artwork file update by themselves when you save the PCB. Inkscape doesn't notice, so when Panel Generator says *Guides updated*, save your artwork in Inkscape and then use **File → Revert** to see the new positions.
- Draw on the **Artwork** layer, not the red one. Clicking a red hole to line something up can switch Inkscape to the red layer; anything you draw there is moved onto the top of your Artwork layer before the red holes are redrawn, and you'll get a note about it (File → Revert in Inkscape to see it there). To put one thing on top of another, use Home or Page Up, not a new layer.

The red holes aren't printed. They're redrawn from the PCB every time you generate, so they always match the board.

![Inkscape artwork in the preview](docs/images/step4_artwork.png)

### 7. Generate the panel

When the preview looks right, click **Generate panel**. This makes the panel file (`<your board>_panel.kicad_pcb`) in a `Front Panel` folder next to your PCB, and opens it in KiCad so you can check it, including in the 3D viewer.

Your settings are saved with each board. If you change the PCB, the settings or the artwork later, the status line next to the buttons tells you the panel is out of date. Click **Generate panel** again to update it.

Close the panel in KiCad before you generate again, so the file can be replaced.

![The generated panel open in KiCad](docs/images/step5_kicad.png)

### 8. Make gerbers

Click **Make gerbers**. Panel Generator uses KiCad to make the gerber and drill files, checks the panel, and puts everything in one zip in the `Front Panel` folder. Upload that zip to JLCPCB, PCBWay or a similar fab.

Order it as a normal 1.6 mm PCB. Black solder mask with white silkscreen is the classic synth panel look.

## Eurorack

1. Start a new PCB in KiCad. Press **A**, search for the size you want from `Eurorack.pretty` (for example `Eurorack_8HP`), and place it at 0 degrees.
2. The template draws the PCB outline for you, plus the panel outline and the top and bottom rail areas, so you can see where parts can't go. Lay out your pots, jacks and LEDs inside the PCB outline.
3. Save, and open the PCB in Panel Generator. It finds the template and builds a standard 128.5 mm tall Eurorack panel of the right width for that HP, with the rail holes in the standard places (2 holes up to 9HP, 4 holes from 10HP up). You can make the rail holes slots instead.
4. If any part runs into a rail area, it's shown in red so you can move it before you order.

![A Eurorack panel](docs/images/eurorack.png)

## Try it

[`examples/demo_synth`](examples/demo_synth) is a small synth board (4 pots, 2 jacks, an LED and 8 keys) made with KiCad's standard footprints. Open it in Panel Generator to try everything out before using your own board.

## Want more detail?

The **[technical guide](docs/TECHNICAL.md)** covers everything else: the command line, how cutout sizes are worked out (and how to add your own parts in `panel_rules.json`), custom cutouts drawn on User.1, panel-only parts, part markers, removing or resizing holes, and all the checks.

## Licence

MIT. See [LICENSE](LICENSE).
