# Deferred-work donor batch — 2026-07-09

All remaining deferred items need real donors. Listed in GOAL priority. All
hcCarbon, chunk (8,8,8), standard position, plain solids unless noted. Give me
each export number (any order, any subset).

Axis: X = plane (slow), Y = column-in-plane (fast), Z = height.

---

## PRIORITY 1 — X1: per-X-plane occupancy (gate to curved-in-X shapes)
X-ramp: 3 planes stepping UP in height along X, flat floor z=8, Y-uniform.
- **X=8** (h4): Y=8,9,10,11 · Z=8..11
- **X=9** (h6): Y=8,9,10,11 · Z=8..13
- **X=10** (h8): Y=8,9,10,11 · Z=8..15
Build via 3 box-fills: `x8..10 y8..11 z8..11` -> `x9..10 y8..11 z12..13` -> `x10 y8..11 z14..15`.
Unlocks spheres/hulls (heights that vary along X, not just Y).

## PRIORITY 2 — wide-pad boxes (nc>=6 pad formula, for shapes wider than 5 cols)
Two uniform solid boxes, vary nx at wide nc:
- **W1 (nx4 nc6):** X=8..11, Y=8..13, Z=8..11   (4x6x4 box)
- **W2 (nx5 nc7):** X=8..12, Y=8..14, Z=8..11   (5x7x4 box)
With existing 3197/3209/3211 these pin pad(nx,nc) for the gap-6 regime.

## PRIORITY 3 — U5: nc5 uniform box (nail the "Reading too far" crash)
- **U5:** X=8,9,10 · Y=8,9,10,11,12 · Z=8..15   (3x5x8 uniform box)
I diff byte-for-byte vs du_synth's nc5-uniform output to find the crash cause.

## PRIORITY 4 — x/y position sweep (arbitrary placement CV)
Six 4x4x4 solid boxes, each shifting ONE axis (others at 8), to fit the x/y
floor-division terms for `lead`/`bnd_op` (z already solved):
- X-sweep (Y=8..11, Z=8..11): x=12..15 · x=16..19 · x=24..27
- Y-sweep (X=8..11, Z=8..11): y=12..15 · y=16..19 · y=24..27

---

Build as many as convenient; I'll process each as it arrives. X1 + the two
wide-pad boxes are the highest-value for actually making curved, wide shapes.
