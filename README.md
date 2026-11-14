# KiCad Front Panel Generator

Panel Generator makes a front panel PCB from your KiCad PCB.

[![Download Panel Generator for Windows](https://img.shields.io/github/v/release/lonesoulsurfer/kicad-front-panel-generator?label=%E2%AC%87%20Download%20Panel%20Generator&style=for-the-badge&color=2563eb)](https://github.com/lonesoulsurfer/kicad-front-panel-generator/releases/latest)

**[⬇ Download Panel Generator for Windows](https://github.com/lonesoulsurfer/kicad-front-panel-generator/releases/latest)**: on that page, under **Assets**, click **`PanelGenerator-v…-windows.zip`**.
⚠️ **Do not use the green *Code → Download ZIP* button.** That zip has only the source code. It does not have the app (`PanelGenerator.exe`).

[![Sponsor lonesoulsurfer](https://img.shields.io/badge/%E2%99%A5%20Sponsor-lonesoulsurfer-db61a2?style=for-the-badge)](https://github.com/sponsors/lonesoulsurfer)

Panel Generator is free. If it saves you time, you can [sponsor its work](https://github.com/sponsors/lonesoulsurfer).

Panel Generator finds each pot, jack, switch, LED and screen on your board. It cuts a hole of the correct size in the correct position for each part. You can add labels, shapes, pictures and artwork. A live preview shows the panel while you work. When the panel is correct, Panel Generator makes the gerbers for the PCB manufacturer. It also makes standard Eurorack panels (2HP to 42HP).

You do not have to copy the parts onto a User layer. You do not have to export to Fusion 360 or Inkscape and back. You do not have to draw the panel again by hand.

**▶ Watch the video: [Front Panel Design - Made Easy!](https://youtu.be/l9CzSfH8hN0)**

[![Front Panel Design - Made Easy! on YouTube](https://img.youtube.com/vi/l9CzSfH8hN0/hqdefault.jpg)](https://youtu.be/l9CzSfH8hN0)

![A finished panel in KiCad's 3D viewer](docs/images/finished_3d.png)

*The front panel for my Game of Life synth, in KiCad's 3D viewer. Panel Generator made all of it: the holes, labels, pot scales, boxes round the key functions and the glider. I did not use Inkscape.*

## What you need

- **Windows.** To use the source code on macOS or Linux, see the [technical guide](docs/TECHNICAL.md#run-from-source-windows-macos-linux).
- **KiCad 9 or 10.**
- **[Inkscape](https://inkscape.org) 1.2 or later.** You need it only if you draw your own artwork.

## Install

1. **[Download Panel Generator](https://github.com/lonesoulsurfer/kicad-front-panel-generator/releases/latest).** Under **Assets**, click **`PanelGenerator-v…-windows.zip`**. Do not click *Source code*.
2. Unzip the file into a folder of your choice.
3. Open the `PanelGenerator` folder and double-click **`PanelGenerator.exe`**.
4. Windows can show *"Windows protected your PC"* the first time. Click **More info**, then **Run anyway**. This message shows because the app does not have a paid signature certificate.
5. *(Optional)* Add the **Open Panel Generator** button to KiCad. See [Open it from KiCad](#open-it-from-kicad).
6. *(Optional)* Add the two footprint libraries to KiCad:
   1. In KiCad, click **Preferences → Manage Footprint Libraries**.
   2. Click the **Global Libraries** tab, then the folder icon.
   3. Add `PanelParts.pretty` from the Panel Generator folder. It has extra panel holes, for example jacks and screws.
   4. Add `Eurorack.pretty`. It has the Eurorack templates.

### Open it from KiCad

Panel Generator can add an **Open Panel Generator** button to the KiCad PCB editor. When you click the button, Panel Generator opens with the board that is open in KiCad. The button operates in KiCad 7, 8, 9 and 10.

1. In Panel Generator, click **＋ Add an "Open Panel Generator" button to KiCad**. This line is at the top left, below the name of your PCB.
2. Close the KiCad PCB editor.
3. Open the PCB editor again. The button is at the right end of the top toolbar. Its icon is a dark panel with a knob, a jack and an orange LED.

Panel Generator reads the PCB file that is saved on the disk. Save the board in KiCad before you click the button. Each time you save in KiCad, Panel Generator updates the panel.

If you move the Panel Generator folder, run `PanelGenerator.exe` one time from the new folder. The button then finds the app again.

<details><summary>Other ways to install the button (KiCad Plugin and Content Manager)</summary>

**From a file:**
1. In KiCad, open the **Plugin and Content Manager**.
2. Click **Install from File…**.
3. Click `KiCad-button-plugin.zip` in the Panel Generator folder one time, then click **Open**. Do not double-click the file.
4. Click **Apply Pending Changes**.

**From the list of this project:**
1. In the Plugin and Content Manager, click **Manage…**, then **+**.
2. Paste `https://raw.githubusercontent.com/lonesoulsurfer/kicad-front-panel-generator/main/pcm/repository.json` and click **Save**.
3. At the top, select *Panel Generator (lonesoulsurfer)*.
4. Click **Install** on **Panel Generator button**.
5. Click **Apply Pending Changes**.

With this method, KiCad shows new versions of the button automatically.

If you install the button with two methods, KiCad shows only one button.
</details>

## How to use it

### 1. Select your PCB

1. Save your board in KiCad.
2. In Panel Generator, click **Browse…**.
3. Select the `.kicad_pcb` file.

The preview shows a front panel with the same shape as your PCB. It has holes for all the parts that need them, for example pots, LEDs, audio jacks, switches and screens.

![The preview after loading a PCB](docs/images/step1_preview.png)

Panel Generator reads only the saved `.kicad_pcb` file. When you move a part, save the board in KiCad again. The preview then updates automatically. The list at the top keeps the boards that you used before. Select a board from this list to open it again.

### 2. Set the size, corners and holes

The settings are on two tabs:
- **Panel**: the board itself (size, shape and holes).
- **Artwork**: all that is printed on the panel.

Click the heading of a section to close it or to open it. Some sections have a switch in the heading. Use the switch to turn the section on or off.

The panel starts with the same size as your PCB. On the **Panel** tab, you can set these items:

- **Extra round the PCB**: makes the panel larger on all sides, for example to fit a case. To set a different value for each side, select *Set each side separately*.
- **Corner radius**: makes the corners round. 0 gives square corners.
- **Case mounting holes**: screw holes to attach the panel to your case. You can put them in the corners, or in the corners and at the middle of each side. Set the hole size and the distance from the hole centre to the edge. The line below shows how much panel material stays between the hole and the edge. Select **Slots** to make slots, not round holes. Slots let you adjust the position of the panel.
- **Screw heads**: a screw head is wider than its hole. Text near a mounting hole can go under the screw head. Panel Generator shows a dotted circle with the size of the head round each screw hole. This includes the mounting holes of the PCB, the case holes, and the screw holes of parts such as screens. If something printed is under a head, it shows in orange, and Result gives a warning.
   - *Auto* makes the head two times the hole size. This is approximately correct for pan-head screws.
   - Select your screw from the list, or select *Your own size…* and type the size. The list keeps the sizes that you type.
   - Or drag the edge of a dotted circle in the preview. The circle becomes bright when the pointer is on its edge. The size shows while you drag. When you release the mouse button, all the screw heads change to that size.
   - Select *Off* to remove the circles.

Each change shows in the preview immediately.

**To use the preview:**
- Turn the **mouse wheel** to zoom.
- Drag with the **right mouse button** to move the view.
- Click **Fit** to see all of the panel.
- Put the pointer on a hole to see its part and its size.
- To make the preview larger, drag the bar between the settings and the preview. You can also drag the bar above the buttons and the Result box.

**Extra holes** are for parts that are not on the PCB. Examples are a window, or a jack or a switch with wires to the board.

- **To add a hole:**
   1. Select a **Hole size** from the list. Or select *Your own size…* and type the size. The list keeps the sizes that you type.
   2. Click **Hole**.
   3. Click the panel where the hole goes.

   **Rectangle** and **Slot** operate in the same way. You can also right-click the panel and add a hole at that position.
- **Alignment:** a new hole moves into line with the other holes. If there is no hole to align with, it goes to the nearest 0.5 mm. To put it in a free position, hold **Alt**. To stop all alignment, clear the **Snap** check box above the preview.
- **Small movements:** click the hole, then push the **arrow keys**. Each push moves it 0.1 mm. With Shift, each push moves it 1 mm.
- **Exact values:** click the hole. Its settings show on the left: the distance from its centre to the **left edge** and to the **top edge** of the panel, and its size. Type exact values there. For a round hole, select a new **Hole size** from the list to change its size. You can also drag one of its white corner squares. A rectangle shows its width and height while you drag.
- **Many holes at the same time:** drag a box round the holes that you added, or Shift-click each hole. Then you can drag them together, **line them up** in a row or column, or type the **spacing** (centre to centre).
- **Copy** (Ctrl+D) adds a copy of the selected holes, with the same sizes and spacing. Two holes in a row become four holes with equal spacing. Drag the copy to a different position if necessary. Push **Delete** to remove the selected holes.
- **Part sizes:** right-click a hole and select *Show the part's size round it*. A dashed blue circle or rectangle shows the real size of the part, for example the nut of a jack or a knob. Use it to set the space between the holes.
   - Drag an edge to change the size. The size and the gap to the nearest part show while you drag.
   - A side of a rectangle moves alone. Thus the rectangle can extend to one side of its hole, for example for a USB board with the connector at one end.
   - Drag a corner to move two sides.
   - Hold **Shift** to keep the rectangle equal on all sides of the hole.
   - Panel Generator does not cut or print these guides.
- **Measure** (above the preview) is a ruler. Click two points to see the distance between them. The ruler snaps to the centres and edges of holes and to the panel edges. Hold **Ctrl** to keep it horizontal or vertical.
- **The ruler is also a guide.** After the first click, type a length (for example `16`) and push Enter. The second end goes exactly that distance away. The ruler stays on the panel until you click **Clear ruler**. All that you drag, add or paste snaps to its ends and its centre.

   *Example:* you need two holes 16 mm apart, with a slot between them.
   1. Add the first hole.
   2. Measure 16 mm from its centre.
   3. Paste a second hole on the far end of the ruler.
   4. Put the rectangle on the centre of the ruler.

Panel Generator checks the extra holes in the same way as all other holes: too near an edge, or on top of a part. If you make the panel larger later, the extra holes stay in the same position relative to the PCB.

**The colours in the preview:**

- **Orange outline:** a hole is very near the panel edge or another hole. The material there can be too thin.
- **Red outline:** a real problem, for example two holes on top of each other.
- **Orange dashed box:** a part that possibly needs a hole, but has no hole. If it does not need a hole (for example a tactile switch behind the panel), click it in the preview. Panel Generator then does not show it again. If it needs a hole, see the [technical guide](docs/TECHNICAL.md).

The **Result** box below the preview shows all the items that you must check.

### 3. Add labels (optional)

1. On the **Artwork** tab, open **Labels**.
2. Select *A name next to each control*.

Each pot, jack and switch gets a name next to its hole, in the silkscreen of the panel. The name comes from the PCB. If the part has a `Label` field, Panel Generator uses it. If not, it uses the Value of the part. For example, a pot with the Value `Cutoff` gets the label CUTOFF.

- Select **above** or **below** the holes, and set the **gap** between the label and the hole.
- Set the **text size** and the **font**. Turn **bold** and **ALL CAPS** on or off.
- Click **Edit labels…** to see all the labels in a list. In the list, you can change the text, or hide a label.
- To change one label, right-click it and select **Change text…**.

![Labels added from the PCB, in a custom font](docs/images/step3_labels.png)

### 4. Make the artwork automatically (optional)

The **Artwork** tab can draw the artwork for your panel. You do not have to use Inkscape. Select a **Style** at the top. Then change the items in the sections below it: Title, Labels, Pots, Shapes, Border, Lines and Pictures.

- **Pot scales:** tick marks, the numbers 0 to 10, or a centre-zero scale (− 0 +) round each pot, for a 300° turn. Set the **Knob** size, so that the scale and the label start outside the knob.
- **Shapes round a hole:**
   1. Under **Shapes**, set the shape (circle, box, triangle, hexagon or diamond), filled or outline, gap, line thickness and corners.
   2. Right-click a hole and select *Add a shape round it*.

   Each new shape gets these settings, so a row of shapes is quick to make. The gap is the distance from the hole to the inner side of the line. A thicker line grows outwards. To change a shape, click it. The same settings then change that shape. You can also drag its edges. If you pull a filled box over a label, the label is cut out of the box. You can put a shape round all holes, also the holes that the automatic options below do not find.
- **Rings** round push buttons. Set the thickness of the ring and its gap from the hole.
- **Vertical outputs in filled boxes:** some jacks come up through the panel and have OUT in their label. Each of these jacks gets a filled box, with the label cut out. This is the usual output marking on modular panels. These also get a box:
   - a jack with your own text OUT next to it.
   - a round extra hole with the text OUT next to it (a jack with wires that is not on the PCB).
- **Boxes round rows of controls:** select *Box* under Pots, Buttons or Jacks. Panel Generator puts a box round each row or column of 3 or more controls, with the scales and labels in the box. Drag the top, the bottom or a side of the box to change its size. The opposite side moves too, so the box stays centred.
- **Horizontal jacks in tabs:** some jacks lie flat at the panel edge, and the plug goes in from the side. These jacks get a filled tab at the edge, with the labels cut out. Labels such as MIDI IN and MIDI OUT become IN and OUT, with MIDI below them. Drag an edge of a tab or an output box to make it larger. It snaps to the edges of the other tabs and boxes, so you can make them all the same size.
- **Border:** a line round the panel. It can be square, follow the panel corners, or have its own corner radius. Set its **gap from the edge** and its **thickness**. If the gap is 0, Panel Generator sets it automatically: 1.5 mm, or just inside the case holes.
- **Title:** your title, and your name or brand in small text along the bottom. The title can go across the top, letter below letter down a side, or turned on its side (reading up or reading down). Select **Mirror image** to flip the letters left to right. The title goes in the first free position. Drag it to a different position if necessary. If there is no free position, the title shows on top of something, and Result gives a warning. Drag the title to a clear area.
- **Copies of the title:** click the title, push **Ctrl+C**, then **Ctrl+V**. Each copy has its own position, size and direction.

The styles are *None*, *Minimal*, *Classic synth* and *Modular*. If you change a setting, the style becomes *Custom*. When the panel looks correct, click **Save this look as my style**. Each new PCB then starts with the same fonts, sizes, scales, rings and border, and *My style* shows in the Style list.

To change the artwork of one part, click its **Artwork** cell in **Edit labels**. For example, use this for a centre-zero scale on a pan pot, or for an output jack that does not have OUT in its label.

If an item touches a hole, a label or the edge, Panel Generator does not include it, and Result gives a note.

![Artwork made for you](docs/images/auto_artwork.png)

You can use this artwork and Inkscape together. The artwork that Panel Generator makes shows in the Inkscape file on its own layer, and you can draw more on top of it.

### 5. Add your own text, pictures and boxes (optional)

You do this work in the preview. Your own texts are under **Labels**, and pictures are under **Pictures**. To remove them from the panel but keep them, clear *My own texts on the panel*, or turn Pictures off. For example, do this when you use Inkscape artwork that has its own text.

- **To move an item, drag it.** You can drag a label, your text, a picture, a line or the title. It snaps to:
   - the line of the other labels.
   - the centre of holes.
   - the centre of each key below a window or in a merged slot. A blue dotted outline with a cross at its centre shows each key.
   - the point half way between two holes (for example a MIDI label above its IN and OUT jacks).
   - the centre of the gap between two items.

   Hold **Alt** to put the item in a free position. For small movements, click the item and push the arrow keys (0.1 mm, or 1 mm with Shift).
- **To change an item, click it.** Its settings show on the left: text, size, position and delete. To change the size of the title, a picture or one of your texts, click it and drag one of its white corner squares.
- **To add text:** under **Labels → Your own**, click **Text…**. Or right-click the panel and select *Add text here*. Then click where the text goes, and type it. Use this for items that are not on the PCB, for example the function of each key.
- **Boxes round text:** use a box for a key with two functions, or for a function that needs two keys.
   1. Click the text.
   2. Set **Box** to *Line round it* or *Filled bar*. A filled bar has the text cut out.
   3. Drag the ends of the box to extend it over the keys. The ends snap to the key labels, to the edges of holes and to other boxes.

   If you extend the box over other texts, they go into the box at their positions. Thus you can make one long bar below a row of keys. If the two ends of the box are equal, they move together. If one end is longer, or one end snaps to an edge, only the end that you pull moves. Hold **Shift** to move only one end.
- **Lines:**
   1. Under **Lines**, click **Line**.
   2. Click where the line starts, then where it ends. Hold **Ctrl** to keep it horizontal or vertical.

   Use lines as dividers, brackets or signal-flow arrows. Click a line to change its **Thickness**, to add an arrowhead, or to type its exact length. Drag an end to move that end. A line that ends at a hole goes to the edge of the hole.
- **Pictures:** click **Picture…** and select a PNG, JPG, GIF, BMP or SVG file (for example a logo). The dark parts print. Drag the picture into position. Click it to set its width, turn it, print the light parts, or delete it.
- **Many items at the same time:** drag a box round them, or Shift-click each item. You can select labels, texts, lines, pictures and extra holes together. Then you can drag, copy or delete them together.
- **Delete:** push the **Delete** key to remove the selected item.
   - A PCB label is hidden, not deleted. **Edit labels** shows it again.
   - On a box round text, Delete removes only the box. The text stays.
   - You can also delete a box that Panel Generator made (round an output, an edge tab or a row of pots). To show these boxes again, right-click the panel and select *Bring back deleted boxes*.
   - On the title or the maker name, Delete removes the text.
- **Copy and paste:** select a text, a picture, a line, the title or extra holes. Push **Ctrl+C**, then **Ctrl+V**. The copy goes to the position of the pointer. Or right-click the panel and select *Paste here*. A copied PCB label becomes one of your own texts.
- **Reset** (next to Undo) starts the panel again from your PCB. The panel gets the size of the PCB, with its holes and nothing else. This also removes the parts and cutouts that you put into the panel file in KiCad. Panel Generator asks before it does this. When you generate again, it keeps the old panel file as a backup (`…_panel.before-reset.kicad_pcb`). Undo brings it all back.
- **Undo** (or Ctrl+Z) cancels the last change. This can be a setting on the left or an action in the preview. You can undo up to 50 changes.

![Your own text, pictures and boxes](docs/images/text_pictures.png)

### 6. Draw your own artwork in Inkscape (optional)

Use Inkscape for artwork that Panel Generator does not make, for example a complex logo or your own drawings.

1. Turn on **Artwork from Inkscape**.
2. Click **Create artwork file**.

Panel Generator saves an Inkscape file in the `Front Panel` folder and opens it. The Inkscape page is an exact 1:1 copy of your panel. Each hole shows in red, so you can see where to put the artwork. To align your artwork with the red holes, use **Align and Distribute** in Inkscape.

![The artwork file when it first opens in Inkscape](docs/images/step4_inkscape.png)

- Draw on the **Artwork** layer. Do not move the page, and do not change its size.
- **Black** prints on the panel as silkscreen.
- **White** cuts out of black. Thus white text on a black bar becomes text cut into the bar.
- **Save** in Inkscape. Panel Generator reads the file automatically, and the preview shows your artwork. You can change and save it as many times as necessary.
- **If you move a part on the PCB:** when you save the PCB, the red holes in the artwork file update automatically. Inkscape does not see this change. When Panel Generator shows *Guides updated*, save your artwork in Inkscape. Then click **File → Revert** in Inkscape to see the new positions.
- **Do not draw on the red layer.** When you click a red hole to align something, Inkscape can change to the red layer. If you draw on the red layer, Panel Generator moves that item to the top of your Artwork layer, and gives a note. (Use **File → Revert** in Inkscape to see it.) To put one item on top of another, use Home or Page Up. Do not make a new layer.

Panel Generator does not print the red holes. It draws them again from the PCB each time you generate. Thus they always agree with the board.

![Inkscape artwork in the preview](docs/images/step4_artwork.png)

### 7. Generate the panel

When the preview is correct, click **Generate panel**. Panel Generator makes the panel file (`<your board>_panel.kicad_pcb`) in a `Front Panel` folder next to your PCB. Then it opens the file in KiCad, so you can check it, also in the 3D viewer.

Panel Generator saves your settings and all your work in the preview while you work. You can close the window at any time. Later, you can change the PCB, the settings or the artwork. The status line next to the buttons then tells you that the panel is out of date. Click **Generate panel** again to update it.

Close the panel file in KiCad before you generate again. If the file is open, Panel Generator cannot replace it.

![The generated panel open in KiCad](docs/images/step5_kicad.png)

### 8. Make gerbers

Click **Make gerbers**. Panel Generator uses KiCad to make the gerber and drill files. It checks the panel and puts all the files in one zip file in the `Front Panel` folder. Upload that zip file to JLCPCB, PCBWay or a different PCB manufacturer.

Order it as a usual 1.6 mm PCB. Black solder mask with white silkscreen gives the classic synth panel appearance.

**3D printing or CNC:** the panel file is a usual KiCad PCB. To get a 3D model, open it in KiCad and use **File → Export → STEP**. To get the outline and holes for a CNC machine, click **File → Plot**, select the DXF format and the Edge.Cuts layer, and plot.

## Eurorack

1. Start a new PCB in KiCad.
2. Push **A** and find the template for your size in `Eurorack.pretty` (for example `Eurorack_8HP`).
3. Put the template on the board at 0 degrees. The template draws the PCB outline, the panel outline, and the top and bottom rail areas. The rail areas show where you cannot put parts.
4. Put your pots, jacks and LEDs inside the PCB outline.
5. Save the board, and open it in Panel Generator.

Panel Generator finds the template. It makes a standard Eurorack panel, 128.5 mm tall, with the correct width for that HP. It puts the rail holes in the standard positions: 2 holes up to 9HP, and 4 holes from 10HP. You can change the rail holes to slots. If a part goes into a rail area, it shows in red, so you can move it before you order.

![A Eurorack panel](docs/images/eurorack.png)

## Try it

[`examples/demo_synth`](examples/demo_synth) is a small synth board with 4 pots, 2 jacks, an LED and 8 keys. It uses the standard KiCad footprints. Open it in Panel Generator to try all the functions before you use your own board.

## More information

The **[technical guide](docs/TECHNICAL.md)** gives all the other information:
- the command line.
- how Panel Generator calculates the size of each cutout, and how to add your own parts in `panel_rules.json`.
- cutouts that you draw on the User.1 layer.
- parts for the panel only, and part markers.
- how to remove a hole or change its size.
- all the checks.

## Support the project

Panel Generator is free for non-commercial use. I make it in my free time. If it helps you, you can support its work:

- **[Sponsor me on GitHub](https://github.com/sponsors/lonesoulsurfer).** You can give one time or each month. GitHub takes no fee.
- **Tell other people.** Show your panels, and put a link to this page in your project.
- **Report problems.** Open an issue, and attach the PCB file if possible.

## Licence

**Panel Generator is free for non-commercial use**, under the [PolyForm Noncommercial License 1.0.0](LICENSE).

**You can sell the panels that you make with it**, for your own synths, kits and modules. This is also permitted for a business.

You must have a commercial licence to sell the tool, or to get money for its use on the designs of other persons. To ask for a commercial licence, open an issue with the title *Commercial licence*.

[LICENSING.md](LICENSING.md) gives the details in plain words.

Versions 0.26.0 and earlier have the MIT licence. The KiCad button plugin (the `kicad-plugin` folder) also has the MIT licence.
