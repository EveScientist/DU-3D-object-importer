# Octree LOD decode — CUBE SWEEP (LODSW) — 2026-07-10

GOAL: map how the LOD-chunk SET (h4/h5/h6/h7 counts + octant coords) depends on shape
SIZE, so build_blueprint_own can auto-generate the exact set for any shape. The set =
base pyramid + neighbor chunks; neighbor count tracks size/position vs fixed octree cell
boundaries. Anchors already in hand: 3x3x3 (3259) -> h6x1; ~4x4x4 (3240) -> h6x8.

All hcCarbon, chunk (8,8,8), corner at x8,y8,z8 (standard). Solid cubes NxNxN.
Build each as ONE box-fill: x8..(7+N) y8..(7+N) z8..(7+N).

- **C1  (1x1x1):** x8      y8      z8
- **C2  (2x2x2):** x8..9   y8..9   z8..9
- **C5  (5x5x5):** x8..12  y8..12  z8..12
- **C6  (6x6x6):** x8..13  y8..13  z8..13
- **C8  (8x8x8):** x8..15  y8..15  z8..15
- **C16 (16x16x16):** x8..23 y8..23 z8..23   (optional, spans a full h3 32-chunk half)

(1,2,5,6,8 are the priority; C16 only if convenient. I already have 3x3x3=3259 and
~4x4x4=3240.)

## What it settles
Plotting (h5,h6,h7 chunk counts + coords) vs N reveals the octree cell size and the
neighbor-inclusion rule (how far from a cell boundary a shape must reach to add the
neighbor chunk). That yields compute_lod_set(voxels) -> exact chunk coords, which
build_blueprint_own uses to emit a correct envelope for ANY shape (no template hunt).

Give me each export number as built; even a subset (say C1, C2, C5, C8) pins most of it.
