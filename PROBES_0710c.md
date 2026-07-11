# Item #6 probe — RIDGE1: single-surface X-descending height — 2026-07-10

Deployment 5 (build_scan_2d ridge, flat bounds, correct plateau/material) crashed
"Reading too far". So build_scan_2d's group law is wrong when height DESCENDS in +X
(a peak in a middle X-plane). It was only ever validated on X-uniform staircases and
X-ascending ramps. RIDGE1 = Deployment 5's exact shape so I can byte-diff synth vs real
and pin the descending-X group/marker encoding.

hcCarbon, chunk (8,8,8), flat floor z=8, nx3, nc5 (all planes full y8..y12), Y-uniform.
Height ramps 2 -> 4 -> 2 along X (ascends x8->x9, DESCENDS x9->x10).

## Heights h(x-plane) -- uniform across all of y8..y12
```
 x=8:  h2   (z8..9)
 x=9:  h4   (z8..11)
 x=10: h2   (z8..9)
```

## Build (2 box-fills)
1. `x8..10  y8..12  z8..9`    -> h2 base, all three planes   (3x5x2 = 30 vox)
2. `x9      y8..12  z10..11`  -> raise middle plane to h4     (5x2 = 10 vox)

Total 40 voxels. Game coords: X 8.5..10.5, Y 8.5..12.5, Z 8.5..11.5.

## What it settles
Byte-diff vs build_scan_2d([[2]*5,[4]*5,[2]*5]) pinpoints the wrong byte(s) in the
X-descending vertex plane (x9|x10) and/or its marker openers. Fixes build_scan_2d ->
flat-floor curved domes/hills (single-surface). Note: real SPHERES use the two-surface
path (already working); this unlocks flat-BOTTOMED curved shapes (domes, hull bottoms).
