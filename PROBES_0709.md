# Probe — nc5 uniform box (nail the run-0-Top × nc5 crash) — 2026-07-09

The synthesizer is byte-exact for nc4 uniform boxes and for nc5 VARYING shapes,
but a synthesized nc5 UNIFORM box crashes DU's mesher ("Reading too far !").
I have no nc5-uniform donor to diff against — this build provides it.

hcCarbon, chunk (8,8,8), standard position. A plain solid box, uniform height.

## Probe U5 — uniform 3×5×8 box (nx3, nc5, h8)
- **X** = 8, 9, 10        (3 planes)
- **Y** = 8, 9, 10, 11, 12  (5 columns)
- **Z** = 8, 9, 10, 11, 12, 13, 14, 15  (h8)
- Solid fill (one box-fill). 3×5×8 = 120 voxels.

I'll diff it byte-for-byte against du_synth's nc5-uniform output. Either:
- they match  -> my scan is correct; the crash is from the template/mc/Model
  envelope for this shape (investigate the cloned Model/LOD fields), or
- they differ -> the divergent bytes are the nc5-uniform bug (likely a wall/Top
  run-0 encoding detail that only shows when nc=5 AND tops are flat).

Either way this closes the crash. (Small, quick box-fill.)
