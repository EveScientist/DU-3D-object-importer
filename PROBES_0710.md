# Item #5 probe — OCC1: per-X-plane occupancy (column-count narrowing) — 2026-07-10

Gate to TRUE spheres/hulls: a footprint that NARROWS in X (fewer occupied Y-columns
at the ends than the middle). Every shape so far has a constant-nc (square) footprint.
E1 already proved X-varying HEIGHT works, so the ONLY remaining unknown is how DU
encodes a Y-column that exists in one X-plane but not its neighbour.

hcCarbon, chunk (8,8,8), flat floor z=8. Height constant h4 (isolates occupancy from
the two-surface z-law, which is already solved). nx3, nc varies 3->5->3.

## Footprint  (X = plane slow, Y = column fast; . = empty, X = filled)
```
        y8   y9   y10  y11  y12
 x=8:    .    X    X    X    .      nc3  (y9,y10,y11)
 x=9:    X    X    X    X    X      nc5  (y8..y12)
 x=10:   .    X    X    X    .      nc3  (y9,y10,y11)
```
All filled columns are z=8..11 (h4). Symmetric in X: nc3 -> nc5 -> nc3.

## Build (3 box-fills)
1. `x8..10  y9..11  z8..11`   -> nc3 core across all three planes   (3x3x4 = 36 vox)
2. `x9      y8      z8..11`   -> widen x9 low edge                  (4 vox)
3. `x9      y12     z8..11`   -> widen x9 high edge                 (4 vox)

Total 44 voxels.

Game coords (voxel index N = game N.5): X 8.5..10.5, Y 8.5..12.5, Z 8.5..11.5.

## What it settles
1. Does the MARKER region shrink for a narrower plane, or are absent columns still
   encoded (h0 markers)? -> tells us if nc is per-plane.
2. How the GROUP vertex-plane between an nc3 plane and an nc5 plane encodes the two
   Y-columns (y8,y12) that appear/disappear across the X-transition.
3. -X / +X boundary planes at nc3 (both ends are the narrow plane here).

Then I generalize build_scan_2surf_2d / group_interior_2surf_2d to accept per-plane
column sets -> arbitrary round footprints -> real spheres.
