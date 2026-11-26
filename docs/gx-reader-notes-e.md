# Reader (fc/gx/model.py) issues found by precision shard e (2026-11-26)

Found while narrowing GB01, G03, G01, GA01, GC08 on the noise corpus. The rules now work around these; fixing them
in the reader would let the rules drop the workarounds. model.py was not edited (shard rules).

1. **Unit guess prefers inches over cm.** `load()` tries `mm?`, then `in?`, then `cm?` and keeps the first plausible
   reading (longest part 100-3200 mm). Unitless files whose mm reading is too small are read as inches even when that
   gives 2-3 m chair sides and 2.3 m "table" parts, while the cm reading gives normal furniture sizes (12 noise
   files: parametric chairs, decor tables, wave bench, cafe set, yin-yang table...). G03 now skips oversize parts in
   `in?` files that fit a sheet at the cm reading. Suggestion: when both in and cm are plausible, pick the one whose
   biggest part lands nearer typical furniture sizes (300-1500 mm), or record the ambiguity in `g.notes`.

2. **1:10 / cm drawings pass as mm.** `_plausible()` accepts a longest part of 100 mm, so a whole desk, bunk bed or
   rocking chair drawn at 1:10 (its "250 x 125" sheet is a 2500 x 1250 sheet) is read at mm scale and every absolute
   mm limit (webs, gaps, holes) misfires 10x. GB01 and GC08 now skip unitless files whose biggest part is under
   300 mm. Suggestion: a `g.scale_unknown` flag for unitless files whose biggest part is under ~300 mm.

3. **Drawing frames / layout borders not recognised.** The sheet-border test needs >= 3 children of >= 0.3 % of the
   frame's area. A plain rectangle drawn around a nest of small parts (Kadushin: Bird Table, Fold Table base,
   Square Dance table, Italic shelf; twist shelving template) fails it and becomes one huge part whose real parts
   are "openings" and whose parts' own holes / logos become "parts". G03 and GC08 now skip a 4-corner rectangle
   with 20+ openings and 5+ parts inside them. Suggestion: treat a 4-corner rectangle with many (e.g. >= 20) children
   as a border regardless of child size.

4. **Join tolerance is tight.** `_chain` joins ends within 0.03 mm, so export rounding gaps of 0.03-0.2 mm leave
   open chains (chair, shelf, crib, oven rack, curved dining chair...). G01 now ignores gaps under 0.11 mm.
   Suggestion: join ends within ~0.1 mm (well under any kerf), keeping G01 for real gaps.

5. **'Info' layers are read as cut layers.** Kadushin files keep notes / sketches on a layer named `Info`; `SKIP`
   does not match it, so its geometry becomes open "cut" chains. G01 skips layers matching `\binfo`. Suggestion:
   add `info` to `SKIP`.

6. **Only the last sheet border is kept.** Files that draw several sheets (oven-rack shelf: 3 borders, reading table:
   2) get `g.sheet` = one of them, so GC07 / G12 judge only the parts on that sheet. Suggestion: `g.sheets` list.

7. **No process hint.** Laser / waterjet files (openings a 3 mm disc does not fit, 900 x 600 laser-bed sheets) are
   detected separately inside G10, GC08 and now GB01. Suggestion: one `g.process_hint` ('laser' / 'router' / None)
   computed in the reader.

8. **Logos read as parts.** The 29 mm Creative Commons mark (disc + two 'C' openings) on Kadushin sheets is a
   closed loop on the cut layer and becomes a part; GC08 now ignores parts under 2500 mm2 like GB01 / G10 do.

**Fixed in reader v9 (2026-11-26):** 1 (inch vs cm: the reading nearest 300-1500 mm wins), 3 (a plain rectangle with
20+ loops inside is a border), 4 (ends within ~0.1 mm join), 5 (`info` layers skipped); 2 partly: `g.scale_uncertain`
is set on unitless files whose biggest part is under 300 mm (rules can use it instead of their own 250/300 mm tests).
Still open: 6 (several sheets), 7 (process hint), 8 (logos).
