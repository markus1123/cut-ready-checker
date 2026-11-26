# Reader (fc/gx/model.py) issues seen by precision shard q (round 3, 2026-11-26)

Found while narrowing GB04, GC07, GF09 (and trying G01, GA01, G05, GB01) on the anonymous noise corpus. model.py was
not edited (shard rules); each line says what the reader does, what it could do, and which rule it misleads.

1. **Pocket layers in other languages read as through-cuts.** `layer_op()` knows only English words (POCKET, HOLE,
   DRILL, ENGRAV ...). A German file keeps its pockets on a layer named `Taschen` (curved dining chair, 2 files):
   the reader calls that layer a cut, so every pocket outline becomes a *part* (GB04 then read a thin stretch of a
   pocket as a neck of a panel). GB04 now skips layers matching tasche / poche / tasca / cajead / vaciad.
   Suggestion: map common CAM words for pocket in German / French / Italian / Spanish / Dutch (Tasche, poche,
   tasca, cajeado, vaciado, kamer) to 'pocket' in `layer_op()`, so all rules see them as pockets.

2. **No material / process hint: folded sheet-metal designs read as wood.** Kadushin's 'Fold Table base' is a
   folded metal sheet: tongues are freed by U-shaped slit openings and stay attached by narrow bend necks, and
   relief slots sit 3-6 mm from the edge where the folds meet it. GB04 flags those necks as weak wood (pieces of
   135k / 125k / 119k mm2 joined by < 8 mm). A geometric fold-line test (rows of equal slots) does not describe this
   file (its fold lines are not drawn), so GB04 still flags it. Suggestion: a `g.material` / `g.process_hint`
   from the manifest or file name ('fold', 'steel', 'metal', 'aluminium', 'sheet metal') that wood-strength rules
   (GB04, GB01) skip; this also covers shard e's note 7 (laser vs router).

3. **Export rounding gaps of 0.11-0.20 mm stay open chains** (spice rack, rocking crib, a Thingiverse nest: 4 long
   outlines). G01 cannot tell them from a seeded missing arc facet (a dropped 0.125 mm facet in a good design is a
   genuine gap), so raising G01's SNAP to 0.25 mm was rejected (lost a transfer catch on gt01). From the flattened
   geometry alone the two look the same; the reader would have to look at the DXF entities (a gap between the end
   points of two separate entities that should share a point = rounding; a missing entity = a real gap). Left open.
