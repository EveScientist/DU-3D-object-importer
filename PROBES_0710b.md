# Item #5 probe — OCC3: consecutive full-width planes in a narrowing shape — 2026-07-10

Deployment 3 (synth nc[3,5,5,5,3]) crashed "Reading too far" though every sub-structure
individually matches a validated donor. The ONE un-validated element: a full-width (nc5)
plane's MARKER opener + its flush nc5|nc5 vertices when the plane sits between other
full-width planes IN A SHAPE THAT NARROWS elsewhere. OCC1/OCC2 never had two consecutive
equal-width planes, so the lvl-0 interior values are extrapolated from constant-nc boxes
and may be wrong in a narrowing context.

OCC3 = EXACTLY Deployment 3's geometry, so I can byte-diff synth vs real and pin the fix.

hcCarbon, chunk (8,8,8), flat floor z=8, height h4, nx5, nc 3->5->5->5->3.

## Footprint
```
        y8   y9   y10  y11  y12
 x=8:    .    X    X    X    .      nc3
 x=9:    X    X    X    X    X      nc5
 x=10:   X    X    X    X    X      nc5
 x=11:   X    X    X    X    X      nc5
 x=12:   .    X    X    X    .      nc3
```
All filled columns z=8..11 (h4).

## Build (3 box-fills)
1. `x8..12  y9..11  z8..11`   -> nc3 core across all five planes   (5x3x4 = 60 vox)
2. `x9..11  y8      z8..11`   -> widen middle three low edge       (12 vox)
3. `x9..11  y12     z8..11`   -> widen middle three high edge      (12 vox)

Total 84 voxels. Game coords: X 8.5..12.5, Y 8.5..12.5, Z 8.5..11.5.

## What it settles
Byte-diff vs build_scan_narrow([{1,2,3},{0..4},{0..4},{0..4},{1,2,3}],4) pinpoints the
exact wrong byte(s) for consecutive full-width planes (the lvl-0 interior marker opener
and/or the flush vertex opener in a narrowing shape). Fixes build_scan_narrow -> arbitrary
round footprints (rounded rects, discs, and the base for real spheres).
