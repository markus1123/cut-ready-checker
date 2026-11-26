# Reader (fc/gx/model.py) issues seen by precision shard d (round 2)

Found while reading why rules flag the anonymous noise corpus. Shard d may not change model.py, so these are notes
for whoever owns the reader. Each line: what the reader does, what it should probably do, which rule it misleads.

1. **Loops that poke a sliver past a part outline stay separate parts.** Edge notches / cut-outs drawn as their own
   loop across the outline are merged only into a host at least 6x bigger (`host ... area > pt.outer.area * 6`).
   A cut-out 5x smaller than its panel, or a second version of a part overlaid on the first, stays a "part" that
   overlaps its host. G02 now ignores loops >= 95 % inside another outline; the reader could merge (or drop) loops
   that lie >= 95 % inside a part regardless of the size ratio.
2. **Registration dots read as parts.** 3x3 - 9x9 mm closed squares (alignment / hand-drill marks) become Parts.
   Rules and seeded faults then treat them as furniture parts (gt02 moves a panel onto a dot and counts it as a
   caught overlap, so G02 cannot ignore dots without "losing" catches). Suggest: closed loops under ~100 mm2 that
   contain nothing and are far smaller than the file's parts -> marks (like circles under r 0.5 mm already are).
3. **Open chains that over-trace a closed outline.** A file can carry a closed outline AND an open copy of most of
   it on top (bar-stool file: a 2894 mm open chain lying entirely on/inside a closed part). The open copy shows up in
   `open_chains` and GC02 reports a part with a missing side although the part is closed. Suggest: drop open chains
   that lie (>= 95 %) within 0.5 mm of an existing closed outline.
4. **A line drawn double becomes a part.** A 261 x 5 mm closed strip with a 2 x 258 mm inner loop (a stroke with
   width, or a line and its offset) is read as a part with a sub-bit opening (GA03). GA03 now ignores parts under
   2500 mm2; a reader rule for "closed strip whose inner loop is its own offset" would be cleaner.
5. **Scale-model / unit ambiguity.** Many free-site files read as `mm?` have their largest part under 250 mm (doll's
   house furniture, cake toppers, desk toys) - or are really cm files. G05, GB03 and GA03 now skip such drawings
   when no >= 9 mm sheet is stated; a `scale_model` / `units_uncertain` flag on GDesign would let every rule share
   one decision instead of each repeating the 250 mm test.
6. **Assembly / elevation views in cut files.** Free-site files often contain the parts AND an assembled view of
   them; the reader turns the view's outlines into parts that overlap everything (G02 now ignores files with 10+
   overlapping pairs). A reader-level "view cluster" detector (many mutually overlapping outlines away from the
   nested parts) would also stop G01/G03/GB01 reading those views as parts.
