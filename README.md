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

## Status
- [x] Plan written (this file + docs/)
- [ ] Starter repo (package, fault library, metric, loop script)
- [ ] First 3 rules: tolerance Monte Carlo, drawer-bottom sag, edge-banding deduction

See `docs/kommode-gaps.md` (what the current checker misses) and `docs/tools-and-rules.md`
(how professional software verifies designs, free alternatives, which rules to write ourselves).
