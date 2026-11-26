# Reader (fc/gx/model.py) issues seen by precision shard p (round 3, 2026-11-26)

Found while reading why G02, GF04, GH01, G10, GB03, GF10, GC03 and GA03 flag the anonymous noise corpus. model.py was
not edited (shard rules); each line says what the reader does, what it could do, and which rule it misleads.

1. **A stock sheet with strips drawn as single lines is read as one 2440 x 1220 part.** A cut list that draws the
   sheet outline and separates its strips with single dividing lines (workbench "Cut List": 80 mm strips) has no
   closed strip loops, so the sheet stays a part and every dividing line that stops at another line is "an open
   line running into the part" (GF04). The empty-sheet test only fires when the rectangle has no children. Suggest:
   a stock-size rectangle (STOCK, +-2 %) is never a part; open lines inside it are cuts between strips (and could be
   polygonised into the strips).
2. **Assembly / elevation views still read as parts** (shard d note 6, still open). Most of the remaining G02 noise
   flags are a part and a second drawing of it overlaid (cat shelf, desk with drawer, chair template: 25-75 % of
   each other), thin edge-on views of panels (strips as wide as the sheet is thick laid across a top: round centre
   table, kids desk, children's stool) or two materials drawn on top of each other (cork disc over its liner).
   A reader-level view detector would remove these from G02 and G10 at once.
3. **Tiny loops become parts.** G02 had to ignore overlaps between two loops both under 2500 mm2 (dots, logo
   pieces, laser-model tabs drawn assembled) and overlaps smaller than a 1/8" bit footprint (corners drawn touching
   with snap error, 3 x 3 mm registration dots on a stool). Same as shard d note 2: a `mark` class for closed loops
   far smaller than the file's parts would let every rule share that decision.
4. **No colour / pen information.** Single-layer laser files from free-file sites separate engrave from cut by colour,
   not by layer (e.g. "table with engraving": ornament and lettering on the only layer). The reader drops entity
   colour, so GB03 / GA03 cannot tell an engrave-by-colour file from lettering left on the cut path. Suggest: keep
   the ACI / true colour on loops and treat a colour used only by sub-bit loops as an engrave pen.
