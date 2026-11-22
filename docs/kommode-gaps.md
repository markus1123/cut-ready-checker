# Kommode generator – what it checks and what it misses (reviewed 2026-11-21)

Source: `~/Downloads/kommode-bestilling/generator/kommode.py` (`check()`), `ut/rapport.txt`.
State: `--selvtest` passes; report says **KLAR TIL FRESING: NEI**, blocked on measured board
thicknesses, Fellesverkstedet bit confirmation, measured slide hole pattern.

## Already checked
- 3D collision check on all 64 parts (axis-aligned boxes)
- Drawer side clearance vs slide (13.0 mm/side = 12.7 + 0.3), drawer height vs opening, space above/below/between drawers
- Hole Ø vs smallest bit, hole distance to edge, blind-hole depth, groove width/depth, hole crossing a groove,
  screws from opposite faces meeting inside the board (mid-wall slides)
- No inside corners (all contours are outside rectangles, grooves exit both ends) → no dogbones
- Minifix depth, confirmat length, front screw, drawer bottom play in groove
- Parts fit on sheets; decor grain direction respected (no rotation when `retning` is set)
- Test kit `ut/prove/` (~13 min): carcass corner, one drawer, mini carcass with real slide row

## Gaps (candidates for rules / test cuts)
1. **Tolerance stack-up on the drawers**: ±0.3 mm margin vs board thickness variation + cutting accuracy + squareness. Classic failure.
2. **Edge banding not modelled**: cut sizes = finished sizes assuming 0.4–0.6 mm iron-on banding; gaps between fronts not re-checked.
3. **Hold-down**: tabs/onion skin left to VCarve; small parts can shift.
4. **Melamine chipping**: needs a compression bit; ask Fellesverkstedet.
5. **Drawer bottom sag**: 724 mm span of 6 mm hardboard in an 800 mm drawer; no load check.
6. **Machine time** is feed × length formula (~94 min); real is often 1.5–2× (plunges, acceleration, tool changes).
7. **Hand operations**: 24 edge holes, Minifix housings, slide holes only marked – accuracy depends on jig work.
8. **Known warning**: handle screws M4x40 through 38 mm → should be 42–48 mm.

## Next real-world steps (from the review)
1. Import sheet DXFs into VCarve (Fellesverkstedet's CAM) and run its 3D preview → real check + realistic time.
2. Book the free guidance session at Fellesverkstedet; have someone experienced review the files.
3. Cut the test kit first (~13 min ≈ 125 kr spindle time).
4. Optional: Polyboard trial with the Hettich library as a comparison.
