# Pyramid probe (2D per-X-plane, #4) — 2026-07-09

Decodes how the group Top token encodes tilt when height varies in BOTH X and Y.
Staircases isolated Y (X-uniform); X1 isolated X (Y-uniform). This varies both,
with a column where X-tilt != Y-tilt, so the Top run tells us which it encodes.

hcCarbon, chunk (8,8,8), floor z=8. Even heights, all <= 8 (top z<=16, avoids the
z=16 sub-cell boundary). nx3 (x=8,9,10), nc4 (y=8,9,10,11).

## Heights h(x-plane, y-col)
```
         y8   y9   y10  y11
 x=8:     4    4    4    4     (plane x8: uniform h4)
 x=9:     4    6    8    6     (plane x9: a Y-bump)
 x=10:    4    4    4    4     (plane x10: uniform h4)
```
Key diagnostic column = the interior group vertex-plane at x=9, column y10:
- X-tilt (to voxel x8,y10 = h4):  |8-4| = 4
- Y-tilt (within x9, y10 vs y9 = h6): |8-6| = 2
X-tilt (4) != Y-tilt (2) -> the Top run there reveals whether it encodes X, Y,
sum, or a multi-vertex form. Plane x10 (h4) also gives an X-DECREASE interior read.

## Build (3 box-fills)
1. `x8..10  y8..11  z8..11`     (all three planes -> base h4)
2. `x9      y9..11  z12..13`    (raise x9's y9,y10,y11 -> h6)
3. `x9      y10     z14..15`    (raise x9's y10 -> h8)

Result: x8 = h4 uniform, x9 = [4,6,8,6], x10 = h4 uniform.
Voxels: x8 & x10 each 4x4=16 (h4), x9 = 4+6+8+6 = 24. Total 16+24+16 = 56.

## What it settles
Given h(x,y) for a full 2D shape (sphere/hull blocky base), how each interior
group column's Bottom/Top tokens encode the surface tilt to X and Y neighbors
simultaneously -> then du_synth can emit arbitrary curved-in-both-directions
blocky bases (the last piece before real spheres). I'll diff vs the derived
X-only + Y-only laws and pin the 2D rule.
