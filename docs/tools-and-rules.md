# How designs get verified – professional, free, and our own rules (2026-11-21)

## Three layers in professional software
1. **CAD – does the product work?** (NX, SolidWorks, Fusion 360): assembly collision checks, motion
   simulation (open drawers fully), tolerance stack-up analysis (NX, 3DCS, CETOL), strength simulation (FEA) for sag/load,
   manufacturability rules (NX Check-Mate, SolidWorks DFMXpress).
2. **CAM – can the machine cut it?** (NX CAM, Fusion, Mastercam, VCarve): toolpaths from the real tool
   library + material-removal simulation (uncut material, gouges, bit fits corner) + realistic run time.
3. **Machine simulation** (Vericut, NX's integrated machine simulation): simulates the real machine + controller running the G-code.
   Mainly for 5-axis metal; layer 2 is enough for a 3-axis ShopBot.

Furniture makers use cabinet software: Cabinet Vision, Microvellum, imos (pro); Polyboard,
Mozaik (affordable). Parametric cabinets + Blum/Hettich hole patterns + edge-banding deductions + nesting + CNC output.

Nothing catches material variation, hold-down, chipping, bad hardware batches, assembly order →
industry cuts a **first article**. Our equivalent: the test kit.

## Free tools
| Need | Tool |
|---|---|
| Cutting simulation | **CAMotics** (open source, material removal from G-code) |
| CAD + CAM + collisions | **Fusion 360 Personal** (free for hobby use, limited); **FreeCAD** (CAM workbench + Woodworking add-on by dprojects) |
| Hardware data | **Blum / Hettich** free CAD downloads + configurators (verify exact model; KA4532 data was contradictory) |
| Nesting / cut lists | OpenCutList (SketchUp), Kiri:Moto (browser) – generator already does this |

## Rules we can write ourselves
| Gap | Rule / model | Difficulty |
|---|---|---|
| Drawer tolerance stack-up | Monte Carlo over thickness ±0.3, cutting accuracy ±0.2, squareness, slide tolerance → % drawers that bind/rattle | Easy (~1 h) |
| Drawer bottom sag | Beam/plate formula, hardboard stiffness, 10–15 kg/drawer, limit ~2 mm | Easy (material values estimated) |
| Edge banding | Subtract banding thickness per banded edge; re-check gaps between fronts | Easy |
| Hold-down / tabs | Auto tabs below size X; small parts towards middle of sheet | Medium |
| Real cutting sim | DXF → G-code → CAMotics headless → compare to 3D model; better time | Medium–hard |
| Assembly order / tool access | Order + screwdriver reach | Hard, probably skip |
| Material behaviour | Not rule-able → test kit | – |

Cabinet software = decades of lessons written down as rules and libraries. We can write down the obvious
ones; the rest comes from test cuts and asking Fellesverkstedet.
