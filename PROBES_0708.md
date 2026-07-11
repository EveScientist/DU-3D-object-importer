# Opener-CV Probes — build & export (2026-07-08)

Goal: crack the **marker OPENER** value (first marker of each X-plane) for tall
dense solids. Already known from donors 3162/3174:
- marker = `[val, 01, 02, h-1, 00]`, byte4 = height-1
- **continuation val = 34 - h** (non-opener columns) — position-independent
- box opener: -X boundary plane `57+2h`, interior planes `95-h` (only tested at footprint 4x4)

These probes vary the three things I still can't separate: **footprint width**,
**height**, and **profile-position weighting**. All hcCarbon, all inside chunk
(8,8,8) (single chunk, no seams). Export each; tell me the export number.

Axis convention (from decode): **X = plane / slow axis**, **Y = column-within-plane / fast axis**
(opener = the y=lowest column of each plane), **Z = height**.

---

## Probe P1 — uniform wide box  (isolates footprint dependence)
A **solid 6 x 6 x 4** block (uniform height 4).
- X (planes): voxels **x = 8..13**  (6 planes)
- Y (cols):   voxels **y = 8..13**  (6 columns)
- Z (height): voxels **z = 8..11**  (h = 4)
- One box-fill, hcCarbon. Game-coord centers = 8.5 .. 13.5 on each axis.

Tells me: does interior opener stay `95-h` (=91) and continuation stay `34-h`
(=30) when the footprint grows from 4x4 to 6x6? i.e. is the tall-solid encoding
**footprint-independent** (the hoped-for simplification) or does the opener carry
a `-35*ncols`-type term like the thin-plate regime.

---

## Probe P2 — ascending Y-staircase  (THE key probe: profile weighting)
**3 identical planes**, each a row of **5 Y-columns with heights 2,4,6,8,10**,
flat bottoms all on the same floor (z starts at 8).
- X (planes): voxels **x = 8..10** (3 planes, all identical)
- Y=8 -> h2, Y=9 -> h4, Y=10 -> h6, Y=11 -> h8, Y=12 -> h10
- Floor: bottom of every column at **z = 8**.

Easiest build = 5 stacked box-fills (each spans all 3 planes x=8..10):
1. `x8..10  y8..12  z8..9`   (base layer, all 5 cols -> h>=2)
2. `x8..10  y9..12  z10..11` (cols y9..12 -> h>=4)
3. `x8..10  y10..12 z12..13` (cols y10..12 -> h>=6)
4. `x8..10  y11..12 z14..15` (cols y11..12 -> h>=8)
5. `x8..10  y12     z16..17` (col  y12    -> h=10)

Tells me: (a) confirms continuation = 34-h across h=2,4,6,8,10 in one shot;
(b) the opener for a NON-uniform profile [2,4,6,8,10] — compare vs P3.

---

## Probe P3 — descending Y-staircase  (same multiset, reversed)
Identical to P2 but heights reversed along Y — **opener column is now the TALL one**.
- Y=8 -> h10, Y=9 -> h8, Y=10 -> h6, Y=11 -> h4, Y=12 -> h2
- Floor at z = 8, 3 identical planes x=8..10.

Box-fills (mirror of P2):
1. `x8..10  y8..12  z8..9`
2. `x8..10  y8..11  z10..11`
3. `x8..10  y8..10  z12..13`
4. `x8..10  y8..9   z14..15`
5. `x8..10  y8      z16..17`

P2 vs P3 is the discriminator:
- opener identical in P2 & P3  => opener depends only on the **multiset** of heights
- opener = f(first-column h only)  => depends on the opener column, not the profile
- opener differs by a position-weighted amount  => reveals the **weight per column**
  (i.e. the `sum k*h_k` style term) — the exact thing blocking synthesis.

---

## What I'll do with them
Read the marker openers + continuation vals of P1/P2/P3, combine with 3162/3174/3191,
and fit `opener = (base +/- 32n +/- w*profile) % 256`. If P1 shows footprint-independence
and P2/P3 pin the weighting, the marker region becomes fully synthesizable and I can
extend du_dense to emit arbitrary-occupancy skeletons (no donor needed).
