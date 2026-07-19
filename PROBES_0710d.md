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

**PROVISIONAL RULE (low-corner only):** h3/h4 minimal; level L≥5 expands to {a_L−1, a_L}³
iff N ≥ 2^(L−4). *** SUPERSEDED — see HIGH-CORNER MIRROR below. The 2^(L−4) threshold was an
artifact of the low-corner placement; it does NOT hold in general. ***

Invariant that DID hold: h3 (content) and h4 (immediate parent) are ALWAYS minimal (the
single ancestor chunk); h7 (M-core octree root) never expands. The expansion, when it
happens, is always the 2×2×2 block {a_L−1, a_L}³ (lower neighbour) at the low corner.

---

## HIGH-CORNER MIRROR (2026-07-19) — Exports 3837/3839/3841/3843.

Same cubes shifted +96 on every axis → content in h3 chunk (11,11,11) = the HIGH corner of
the SAME h5 ancestor chunk (a_5 = 11>>2 = 2), opposite corner from the chunk-8 sweep.

| Hn | export | N | h3 | h4 | h5 | h6 | h7 |
|----|--------|---|----|----|----|----|----|
| H1 | 3837   | 1 | (11,11,11) | (5,5,5) | **1** (2,2,2) | 1 | 1 |
| H2 | 3839   | 2 | (11,11,11) | (5,5,5) | **1** (2,2,2) | 1 | 1 |
| H5 | 3841   | 5 | (11,11,11) | (5,5,5) | **1** (2,2,2) | 1 | 1 |
| H8 | 3843   | 8 | (11,11,11) | (5,5,5) | **8** {2,3}³   | 1 | 1 |

**Two findings:**

1. **DIRECTION is position-dependent — CONFIRMED.** At the high corner the h5 block is
   {2,3}³ (a_5 plus the UPPER neighbour 3), the mirror of the low-corner {1,2}³ (a_5 plus the
   LOWER neighbour 1). So the neighbour is on the side the content HUGS. A general
   compute_lod_set must pick the neighbour per-axis by which side of each coarse chunk the
   content's extent sits toward. (h6 stayed minimal here because chunk 11 is in the LOWER
   half of its h6 chunk 1 and N was too small to trigger — an h6 mirror needs an L core with
   an in-bounds upper h6 neighbour.)

2. **THRESHOLD is asymmetric — the 2^(L−4) rule is REFUTED.** Low corner: h5 expands at N≥2.
   High corner: h5 stays minimal through N=5 and only expands at N=8. Same ancestor chunk,
   same level, opposite corner → wildly different N threshold. Note N=1 vs N=2 at the low
   corner have IDENTICAL h5-cell footprints ({66}) yet different h5 neighbour sets, so the
   decision uses finer-than-level detail (h3/h4 border cells), and the material +1 offset
   breaks the low/high symmetry. The exact threshold is NOT yet pinned — it needs either the
   DU create_lods source or a denser N×position sweep. DO NOT ship a compute_lod_set based on
   2^(L−4).

NOTE (unchanged): the emitter (octree_from_cells) emits only the MINIMAL ancestor tree and
deploys fine — DU regenerates LOD content from h3 on import. So this whole neighbour shell is
what DU *writes on export*, not what it *requires on import*; reproducing it is QA/byte-match
only, hence low priority. The confirmed direction-mirror is the durable finding.
