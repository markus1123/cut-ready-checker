# Furniture checker – self-improving DFM checker for flat-pack furniture

Started 2026-11-21 as the plan for the **Recursive Self Improvement Hack** (Sun 2026-11-22,
10:00–20:00, European Startup Embassy, 461 Bryant St, SF – https://luma.com/ktv3iwd9, registered: "You're In").

Builds on the kommode generator in `~/Downloads/kommode-bestilling/generator`
(`kommode.py` + `params.json` → sheet DXFs, `ut/rapport.txt` "KLAR TIL FRESING", `--selvtest`).

## Pitch (30 s)
"Describe a piece of furniture, get files you can cut and trust. The checker teaches itself
what breaks in real workshops." Kommode is test case #1.

## Why
- Furniture business: the hard problem is cost + "will it work in practice". Machine time is
  expensive, so catch problems before cutting. (Landing pages / demand discovery: not now.)

## The four parts
1. **Fault library (the scoreboard).** Deliberately broken kommode variants, each labelled with what is
   wrong (hole near edge, drawer 0.5 mm too wide, groove crossing a hole, short screws,
   wide drawer + thin bottom, ...). Metric = share of seeded faults the checker catches.
   Target: baseline about 40% → 85%+ by the demo.
2. **Rule writer.** For each missed fault, an agent writes rule + test, runs `--selvtest`; keep the rule only if
   it catches the new fault and does not flag known-good designs.
3. **Rule miner.** An agent reads real sources (Blum/Hettich mounting instructions, ShopBot forum, r/CNC,
   woodworking design guides) → candidate faults + rules. Stops the agent-vs-agent fault library
   drifting from reality; say this openly in the demo.
4. **Text → furniture** (if time). "Bookshelf 180x80x30, 5 shelves" → params → generator → checker →
   agent adjusts until it is ready to cut → DXF + CAMotics simulation.

Rules must be plain code with tests, never an LLM's opinion of a drawing.

## Day plan
| Time | Goal |
|---|---|
| Night before | Starter repo: generator as package, ~15 seeded faults, catch-rate metric, first 3 rules |
| 10:30 | Pitch, team of 2–3 (want: frontend/demo + agent-loop person) |
| 11–14 | Rule writer loop working, score going up; rule miner reading sources |
| 14:00 | Check-in #1 with score graph |
| 14–18 | Mined faults in, text → furniture, demo page (3D preview + score over time) |
| 18:00 | Demo: graph, a fault missed this morning now caught, bookshelf from one sentence |

Commitment point is 10:30 team formation. Leaving after the intros is fine; leaving a team mid-day is not.

## Status (2026-11-22)
- [x] Starter repo: `fc/` (design loader runs the real generator, DXF reader, 3D frames), fault library, scoreboard
- [x] 11 rules R01-R11 (DXF sanity, DXF vs cut list, 3D joint continuity, handedness, slide holes, banding,
      drawer box fit + sag + Monte Carlo tolerance, front gaps after banding, screw lengths, hold-down, bit reach)
- [x] Held-out set (25 faults) written by an independent red-team agent that never saw the rules
- [x] `loop.py`: miner + rule writer + acceptance gate (catches target, no regression, 0 false alarms)
- [ ] Run the loop live (needs permission to run headless `claude -p` agents)

Score history: `score_history.jsonl`. Baseline generator alone: train 24 %, held-out 4 %.
Now: train 100 %, held-out 64 %, 0/7 false alarms.

Real bugs found in the kommode by the checker and fixed in the generator:
1. Right side, right drawer sides and middle wall cut as identical copies of handed parts -> slide holes/marks
   front<->back on one side, band on the back edge (R04). Now C/CH and S/SH, D face label fixed.
2. Handle screws M4x40 left 2.4 mm in the handle (R09) -> M4x45 in params.json.
3. Small through holes (handle Ø5, plinth Ø4.5, slide pilots) deeper than a 1/8" bit's flute (R11) ->
   CNC spots 3 mm, drill through by hand (listed in manuelle-operasjoner.csv). Flute lengths are ESTIMATES: ask the workshop.

    python3 -m fc.score            # scoreboard
    python3 -m fc.score --show t07 # what each layer says about one fault
    python3 loop.py --mine 6 --iters 6
