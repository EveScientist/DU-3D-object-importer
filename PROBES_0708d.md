# Probe X1 — per-X-plane occupancy (#4 / #2) — 2026-07-08

Validates the synthesizer's group-region mapping when column heights vary ALONG X
(all donors so far are X-uniform, so this is untested). hcCarbon, chunk (8,8,8).
Axis convention: X = plane (slow), Y = column-in-plane (fast), Z = height.

## Probe X1 — X-staircase (Y-uniform, X-varying ascending ramp)
Three X-planes, each a UNIFORM-height row of 4 Y-columns, heights STEPPING UP in X.
Flat floor at z=8. A 3-step ascending ramp.

- **X=8 plane** (h4): Y = 8,9,10,11 · Z = 8,9,10,11
- **X=9 plane** (h6): Y = 8,9,10,11 · Z = 8,9,10,11,12,13
- **X=10 plane** (h8): Y = 8,9,10,11 · Z = 8,9,10,11,12,13,14,15

= a solid whose top face rises in steps along X (4 -> 6 -> 8), flat across Y.
nx3, nc4, 4+6+8 = 18 voxels/column-row × 4 = 72 voxels.

Build as 3 box-fills:
1. `x8..10  y8..11  z8..11`   (all three planes -> h>=4)
2. `x9..10  y8..11  z12..13`  (planes x9,x10 -> h>=6)
3. `x10     y8..11  z14..15`  (plane x10 -> h=8)

## What it reveals
- Which voxel-plane's heights drive each of the interior GROUP vertex-planes
  (x=9, x=10 gridlines sit between voxel planes of DIFFERENT height).
- How the -X (x=8) and +X (x=11) boundary planes encode when the profile isn't uniform.
- Whether an X-direction height jump creates X-tilts (analogous to the Y-tilts in the
  Top-cap run law) in the group tokens.

I'll diff it against du_synth's output and fix the height->vertex-plane mapping, which
unlocks shapes that curve along X (spheres, hulls) rather than X-uniform prisms.
