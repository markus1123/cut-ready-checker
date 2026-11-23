# Corpus – real CNC furniture designs from other people

Purpose: **false-alarm tests from outside our own generator.** Today the checker's "good" set is 7 variants of
our own kommode. These are designs other people drew, and most of them have been cut and built many times
(Opendesk maker network, AtFAB, Fellesverkstedet's own workshop furniture). If a rule flags them, the rule is
probably wrong (or the rule found something real – check by hand before deciding).

Raw files live in `corpus/raw/` and are **gitignored**: many are CC-BY-NC (Opendesk), and the repo will be public.
Only the manifests and tools are committed.

## Layout
| File | What |
|---|---|
| `raw/<owner>_<repo>/` | Shallow clones of the source repos (gitignored) |
| `raw/web/<source>/<slug>/` | Files downloaded from sites outside GitHub (gitignored) |
| `designs.jsonl` | One line per design folder: repo, category, furniture type, built by others, licence, units, files + sha1, duplicates |
| `web_manifest.jsonl` | Provenance for `raw/web` (page URL, licence as stated, designer) |
| `survey.jsonl` | Per DXF: entity types, `$INSUNITS`, layers, extents |
| `profiles.jsonl` | Per unique DXF: closed cut loops vs open chains, circles, layers (is it usable for checks?) |
| `tools/` | `survey.py`, `build_manifest.py`, `profiles.py` (rebuild: see below) |

## Rebuild
    python3 corpus/tools/survey.py corpus/raw > corpus/survey.jsonl
    python3 corpus/tools/build_manifest.py corpus/raw corpus/survey.jsonl > corpus/designs.jsonl
    python3 corpus/tools/profiles.py corpus/raw corpus/designs.jsonl > corpus/profiles.jsonl

Needs `pip3 install --user ezdxf`. Downloaded files are data: never run anything from `raw/`.

## Sources (GitHub, 2026-11-22)
- Opendesk CC-BY set (`timrolls/Opendesk`, mirrored in `shulter/opendesk/cc-by-files` and
  `kemelzaidan/open-source-furniture/opendesk`) + `shulter/opendesk/all-files` (incl. NC designs)
- `opendesk/design-playground`: AtFAB designs + Digital Wood Joints library (51 joints, 2D + 3D)
- `kemelzaidan/open-source-furniture`: AtFAB (CC-BY), Ronen Kadushin (CC-BY-NC), Open Design Contest
- Fellesverkstedet: hat-systems (CC-BY 4.0), HOK workbench (CC-BY 4.0), Workshop-furniture (CC-BY-SA), BeeBar,
  makercon building blocks (CC0)
- WikiHouse Skylark (520 cut files, sparse clone), Wren, Pionierswoning, Wikished, pavilion – buildings, category `structure`
- Smaller: `indraastra/designs` (ShopBot shelves/trays), `pinkie1378/woodworking-plans`, `chousallen/AutoBookshelf_CAD`,
  `SigmazGFX` workbench, `seanperkins/ashleys-bed` (never built), `Lucactus22/CNC_cabinet_generator` golden outputs
  (generated, never built – category `generator_output`)

Not cloned: `MateenKhan/designs2` (22 GB), unrelated hits (keyboards, enclosures, CAD block libraries).

## Numbers (GitHub part)
- 1,078 DXFs → **955 unique files, 179 unique design folders** after sha1 dedupe
- Categories: 96 furniture, 64 structure, 12 non-furniture, 5 generator output, 2 joint library
- Furniture: about 80 distinct pieces; 79 folders built by others, 16 unknown, 1 never built
- Furniture licences: 41 CC-BY-NC, 36 CC-BY, 4 CC0, 1 CC-BY-SA, 13 unknown
- Usable geometry (furniture, 218 unique files): 81 fully closed, 94 mostly closed, 39 messy, 4 no loops

## Web sources (outside GitHub, harvested 2026-11-22 by an agent; scripts in `harvest_scripts/`)
743 designs, about 1,000 DXFs (+ 164 PDF, 76 SVG, 31 AI, 18 DWG). Provenance per design in `web_manifest.jsonl`.
- 3axis.co (336) and vecty.co (176): free-file sites, no designer or source → `source_tier: anonymous`.
  3axis licence forbids redistributing the files; vecty's CC BY-SA claim is unreliable (contains Opendesk designs).
- Thingiverse via Internet Archive mirror (125), Fab Academy student repos (70, built by the student →
  `built_by_others: by_designer`), Ronen Kadushin (18, CC BY-NC-SA), Opendesk archive.org 2017 mirror (15, all
  duplicates of GitHub files), OSE office desk, Talorgen chair, DAC chair.
- Blocked: AtFAB (site dead, files never archived), Obrary ($0 checkout with email), Opendesk (login), Thingiverse/
  Printables/Cults/GrabCAD (403 to scripts), Instructables (file server wants a Referer; 13 good projects listed in
  `instructables_needs_human.jsonl`).
- Not finished: Fab Academy 2018–2020 and 2025 (`harvest_scripts/fab_crawl.py`, then `fab_fetch.py`; 54 machining-week
  sets to sort by hand in `fabacademy_cnc_unclassified_candidates.txt`), about 730 Thingiverse mirror candidates left
  (`harvest_scripts/ia_thing.py`).

## Numbers (everything)
- 2,056 DXFs → **1,687 unique files, 718 unique design folders**; **635 furniture designs**
- Furniture by source tier: 96 GitHub, 143 web with known source, 396 anonymous
- Build evidence: 79 built by others (Opendesk/AtFAB/Fellesverkstedet), 71 built by the designer (Fab Academy), rest unknown
- Types: 219 seating, 155 tables, 92 shelves, 30 desks, 25 storage, 12 beds, 94 other
- Usable geometry (fully or mostly closed outlines): GitHub 175/218 files, web 199/312, anonymous 284/381

## Caveats
- Units: most files have `$INSUNITS = 0`; `build_manifest.py` guesses inches vs mm from the extents (`in?` / `mm?`).
- "Built by others" is per source, not per design: Opendesk/AtFAB/Fellesverkstedet designs are marked yes.
- These DXFs don't follow our layer convention (`01_BOR_D5_Z11`), so the current rules can't read them yet.
  Next step: a generic adapter (closed loops + circles + layer/depth guesses) and a few rules that need only
  geometry: slot width vs sheet thickness, inner corner radius vs bit, hole-to-edge distance, part fits sheet,
  minimum web width.
