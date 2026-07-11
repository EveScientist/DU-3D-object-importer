# Structural-closeout probes (2026-07-08)

The dense flat-skeleton is content-100%-solved. These close the last 3 GENUINE
unknowns (everything else is either derived or mechanical bg-phase). All hcCarbon.
Give me each export number. Small simple boxes/staircases — quick box-fills.

Axis convention: X = plane (slow), Y = column-in-plane (fast), Z = height.

---

## P5 — boundary-opener (bnd_op) law   [2 builds]
bnd_op (the −X face marker opener) = 65 for h4 boxes, 73 for h8. Looks like 57+2h
for UNIFORM height, but all staircases so far read 65. Need to separate "uniform
height law" from "non-uniform default".

**P5a — uniform 4×4×6 box (h6):**
- x=8..11, y=8..11, z=8..13  (solid, h=6). Predict bnd_op = 57+2·6 = 69.

**P5b — staircase with NO height-4 column:** heights [6,8,10,12] along Y, 2 planes.
- x=8..9,  y=8..11,  floor z=8:  y8→h6, y9→h8, y10→h10, y11→h12.
- Build tallest-first: `x8..9 y8..11 z8..13`(all≥6), `y9..11 z14..15`(≥8),
  `y10..11 z16..17`(≥10), `y11 z18..19`(=12).
- If bnd_op still 65 → it's a fixed non-uniform default. If it varies → reveals the law.

---

## P6 — wide-footprint group gap (nc≥6)   [2 builds]
Group inter-plane bg gap = 8 for nc≤5, but = 6 for nc=6 (3197). Need the gap-vs-nc
rule (and the pad/scanlen it drives) for wide shapes — most real shapes are wide.

**P6a — uniform 3×7×4 box (nc=7):** x=8..10, y=8..14, z=8..11.
**P6b — uniform 3×8×4 box (nc=8):** x=8..10, y=8..15, z=8..11.
- I read the group inter-plane gap + scanlen; pins gap(nc) for nc 6,7,8.

---

## P7 — position independence   [1 build]
All donors so far sit at chunk (8,8,8) with the shape starting at voxel 8. Need to
know if the constants (leading-bg length 99, and the 34/199/235 marker/wall bases)
shift with absolute position.

**P7 — uniform 4×4×4 box, SHIFTED:** same size as the 3162 reference but moved to
x=18..21, y=18..21, z=18..21 (still inside chunk (8,8,8), just offset within it).
- I diff against 3162: if marker/wall vals + offsets are identical → constants are
  position-independent within a chunk (great, simplest case). If they shift →
  I derive the position term (like h3_generator's n1_first(lx,ly,lz)).

---

## After these
bnd_op law + nc≥6 gap + position term = the whole flat skeleton generalizes. Then
I port h3_generator's bg-phase `flip` bookkeeping (mechanical) and the flat-base
synthesizer emits any dense scan byte-exact → deflection layer → arbitrary closed
shapes with no donor.
