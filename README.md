# Cut-Ready Checker

**Live demo: https://cut-ready-checker.netlify.app**

A self-improving checker that stops bad CNC cutting files for flat-pack furniture before they reach the router.
Built in one day at the Recursive Self-Improvement Hack (San Francisco, 2026-11-22).

A parametric generator turns ~30 numbers into DXF sheets, a parts list and a drilling plan for an 8-drawer chest,
cut on a ShopBot at a makerspace. One wrong hole, depth or mirrored part wastes a sheet and an hour of machine time.
This repo is the checker that reads those files and refuses to send a bad job, and the loop that improves it.

## How it works

1. **Fault library = the exam.** Realistic mistakes injected into a good design (`faults/`): a slide hole 12 mm too low,
   a pocket drilled through the face, an inch/mm mix-up in the DXF header, a right side cut as a copy of the left.
   Sets: `train` (rule writers may read), `mined` (written by the loop's miner agent), `heldout` (written by a separate
   red-team agent, never shown to rule writers), `good` (known-good variants: any error there is a false alarm).
2. **Rules are plain code** (`fc/rules/`). Each is a deterministic Python check with a threshold and a reason from a
   workshop or a manufacturer manual. No model judges a design at check time.
   The checker reads the actual DXF files and a 3D model of the assembly (frames per part, chirality, coaxial holes).
3. **The loop** (`loop.py`): a miner agent writes new faults; a writer agent writes one rule per missed fault; a fixed
   gate keeps the rule only if it catches that fault, loses nothing already caught, and raises zero false alarms.
   Every accepted rule is a git commit (`rsi-loop` author in the history).
4. **Cost optimizer** (`optimize.py`): hill climbing with random restarts over hidden board choices, column count and
   nesting order, with the full checker as a hard constraint. `--region bay_area` swaps in US 4x8 sheets and USD prices.

## Results (end of day)

| Set | Generator's own check | Generator + 26 rules |
|---|---|---|
| Training | 6/34 | 34/34 |
| Mined by the loop | 0/6 | 6/6 |
| Held-out (never seen) | 1/25 | **18/25** |
| False alarms on known-good designs | – | 0/7 |

Real bugs found in the chest before cutting: mirrored parts generated as identical copies, holes deeper than the bit's
flute, handle screws that barely bite, Minifix housings drilled for the wrong board thickness, slide screws nearly
through 16 mm drawer sides, groove feed too fast for a 1/8" bit, drawers wider than the slide maker allows.

Honest caveats: 4 of the 6 loop-written rules catch only the fault they were written for (the gate does not reward
generality yet); the held-out titles were seen once by the main agent after they were written; most prices are estimates.

## Run it

The checker drives the chest generator (a separate project, not in this repo). Point `FC_GEN` at its folder:

```
export FC_GEN=/path/to/generator      # contains kommode.py, nestlib.py, params.json
python3 -m fc.score                   # catch rate per set + false alarms
python3 -m fc.score --show t33        # what every layer says about one fault
python3 -m fc.attribution             # which rule catches which fault -> attribution.json
python3 loop.py --mine 6 --iters 6    # the self-improvement loop (needs the claude CLI)
python3 optimize.py [--region bay_area]
python3 demo/build.py && python3 demo/site.py   # rebuild the demo page into site/
```

Manufacturer sources behind rules R18–R26 are listed in `docs/rules-from-manuals.md` (the PDFs themselves are not
redistributed).
