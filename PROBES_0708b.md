# Opener-CV Probe P4 — non-monotonic profile (2026-07-08)

Locks the two remaining ambiguities in the now-cracked marker formulas:
- **interior opener = (235 − 35·ncols − h_yHI) % 256**   (is it h_yHI or h_MAX?)
- **continuation val = (34 − h + G) % 256**, G = gradient   (is G one per-plane
  constant, or is each column actually local?)

Every earlier probe used a **monotonic** height profile, so y_hi was always the
max or the min — can't separate the cases. P4 uses a profile where the +Y-edge
column is neither the tallest nor the shortest.

hcCarbon, single chunk (8,8,8). Axis convention: **X = plane, Y = column-in-plane
(y_lo..y_hi), Z = height.**

---

## Probe P4 — non-monotonic Y-profile
**2 identical planes**, each a row of **5 Y-columns, heights [2, 10, 4, 8, 6]**,
flat bottoms all on the floor at z = 8.
- X (planes): voxels **x = 8..9** (2 identical planes)
- Y=8 -> h2, Y=9 -> h10, Y=10 -> h4, Y=11 -> h8, Y=12 -> h6
- Floor: bottom of every column at **z = 8**.

Note the ends: y_lo (y8) = 2, y_hi (y12) = 6. Max = 10 (at y9), min = 2 (at y8).
So y_hi (6) is neither max nor min — that's the whole point.

Easiest build = box-fills, tallest-first so each fill is a clean rectangle.
Fill order (each spans both planes x8..9):
1. `x8..9  y8..12  z8..9`    (all 5 cols -> h>=2)
2. `x8..9  y9..12  z10..11`  (cols y9,y10,y11,y12 -> h>=4)   [y8 stops at 2]
3. `x8..9  y9,y11,y12  z12..13`  (cols y9,y11,y12 -> h>=6)   [y10 stops at 4]
4. `x8..9  y9,y11  z14..15`  (cols y9,y11 -> h>=8)           [y12 stops at 6]
5. `x8..9  y9  z16..17`      (col y9 -> h=10)                [y11 stops at 8]

Resulting heights by column:  y8=2, y9=10, y10=4, y11=8, y12=6.  ✅

(If non-contiguous fills like step 3/4 are awkward, build each column as its own
z-stack instead — the end state just needs to be heights [2,10,4,8,6] on a flat
z=8 floor, 2 identical planes. The order/method doesn't matter, only the final
occupancy.)

---

## What P4 decides
Interior-plane opener (planes are identical, so both interior; there's also the
x=8 boundary plane — ignore its opener, that's the separate unsolved one):

- **opener = 235 − 35·5 − 6 = 59**  → the formula uses **h_yHI** (the +Y-edge col).
- **opener = 235 − 35·5 − 10 = 50** → it actually uses **h_MAX**.
- anything else → the term is more complex (I'll refit).

Continuation vals (cols y8..y11 as they appear after the opener, or however DU
orders them — I'll read positions from the bytes):

- if every column reads **34 − h + G** with a **single G** = (h_yHI−h_yLO)/(nc−1)
  = (6−2)/4 = **+1**, i.e. vals y-mapped {h2->33, h10->25, h4->31, h8->27, h6->29}
  → the per-plane linear-gradient model holds.
- if the vals don't match a single G → continuation is **per-column-local** and I'll
  derive the true per-column term from the deviations.

Build it, export, give me the number.
