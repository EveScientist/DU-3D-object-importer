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

---

## RESULT (2026-07-19) — SOLVED. Exports 3824/3826/3829/3831/3833/3835 (+ 3259, 3240).

Decoded LOD chunk sets (all cubes at the standard position, content in h3 chunk (8,8,8);
M-core octree h3..h7, root h7=(0,0,0)):

| N  | export | h3 | h4 | h5 | h6 | h7 |
|----|--------|----|----|----|----|----|
| 1  | 3824   | 1  | 1  | **1** | 1  | 1  |
| 2  | 3826   | 1  | 1  | 8  | 1  | 1  |
| 3  | 3259   | 1  | 1  | 8  | **1** | 1  |
| 4  | 3240   | 1  | 1  | 8  | **8** | 1  |
| 5  | 3829   | 1  | 1  | 8  | 8  | 1  |
| 6  | 3831   | 1  | 1  | 8  | 8  | 1  |
| 8  | 3833   | 1  | 1  | 8  | 8  | 1  |
| 16 | 3835   | 1  | 1  | 8  | 8  | 1  |

The 8-chunk sets are always the 2×2×2 block {a_L−1, a_L}³ where a_L = chunk_h3 >> (L−3) is
the content's ancestor chunk at level L (h5: a=2 → {1,2}³; h6: a=1 → {0,1}³). I.e. the
content ancestor PLUS its lower-corner neighbour shell (content hugs the low corner of each
coarse chunk at the standard local-8 placement).

**RULE (matches all 8 data points):**
- h3 (content) and h4 (immediate parent): always MINIMAL — the single ancestor chunk.
- Level L ≥ 5: expand to the {a_L−1, a_L}³ block **iff N ≥ 2^(L−4)** (h5→N≥2, h6→N≥4).
  The N=3 (3259, h6=1) vs N=4 (3240, h6=8) pair pins the h6 threshold exactly at 4.
- h7 is the octree root (single chunk) — never expands.

Predicts h7 would expand at N≥8 on a LARGER core (L core, where h7 isn't root) — untested.
Neighbour DIRECTION (lower vs upper) is position-dependent: all probes hug the low corner, so
they only show the lower neighbour. A centred/arbitrary shape (build_blueprint_sem centres
content) needs the neighbour picked per-axis by which side the content hugs — one more probe
set (content shifted to the HIGH corner of a coarse chunk) would confirm the mirror.

NOTE: the current emitter (octree_from_cells) emits only the MINIMAL ancestor tree and
deploys fine (DU regenerates LOD content from h3 on import), so this shell is what DU
*writes on export*, not what it *requires on import*. compute_lod_set can now reproduce DU's
exact export set for QA/byte-matching if wanted.
