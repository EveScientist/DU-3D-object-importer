# DU Export Lookup Table

Precise per-export record of what was built in-game and exported, so reference
data can be re-used. **Every new export MUST be added here** with its exact XYZ.

## Conventions
- **Coords** are the in-game build coordinates in the notation used when specifying
  builds (e.g. `10.5` = a voxel centered at that game coordinate). Game coord
  `N.5` ⇒ chunk-local index `N` (chunk = 8 for the 0–31 local range on an M core),
  local index = game−0.5; a voxel at `10.5` sits in chunk 8 at local index 10.
- **z=0 seam:** the z=0 boundary separates chunk cz=7 (Z<0) from cz=8 (Z≥0).
- **Material:** default is **Orange Carbon Panel** (hcCarbon, code 31) unless noted.
- **Core:** Static **M** (Size 128) unless noted.
- Scans decoded from `/home/du/exports/NNNN_export.blueprint` (older ones under
  `exports/archive/`). See [[du-blueprint-format]] for the decode.

## Table

| Export | Shape / build | Coords (X, Y, Z) | Chunks (h3) | Purpose / result |
|--------|---------------|------------------|-------------|------------------|
| 2973 | Plain 2×2×3 solid block | X∈{10.5,11.5}, Y∈{10.5,11.5}, Z∈{10.5,11.5,12.5} (12 vox) | (8,8,8) | A2 reference (plain). scan len 765, mc 623. |
| 2975 | Same block, +X/+Y vertical corner deflected (jagged = multiple corner deflects) | as 2973 | (8,8,8) | A2 sideways displacement. 8 bytes changed IN-PLACE (8-byte form), all 0x7e→lower; disp groups (0,−48),(−28,−28),(−48,0),(−56,−56) steps. |
| 2977 | Plain single voxel | (10.5, 10.5, 10.5) | (8,8,8) | A2 single-voxel reference. scan len 706, mc 605. |
| 2979 | Single voxel, **TOP** +X/+Y corner deflected X−1,Y−1 | (10.5, 10.5, 10.5) | (8,8,8) | A2: 8→12-byte expand. V0=(0,0,0), V1=(−1,−1,0). Full-scan reconstruct byte-exact. |
| 2981 | Single voxel, **BOTTOM** +X/+Y corner deflected X−1,Y−1 | (10.5, 10.5, 10.5) | (8,8,8) | A2: V0=(−1,−1,0), V1=(0,0,0). Confirms V0=bottom / V1=top convention. |

| 2983 | Build G — z=0 straddle, 2×2, 2 layers each side (16 vox) | X∈{10.5,11.5}, Y∈{10.5,11.5}, Z∈{−1.5,−0.5,+0.5,+1.5} | (8,8,8) HIGH + (8,8,7) LOW | **Material = Military Al-Li Panel (hcAlLiPa, code 12)** — scan is material-independent so analysis valid. B1 depth-3: both chunks len 757, run=3. LOW off by 3 value-bytes (@119 −1, @353 +1, @463 −1 = ×(depth−2)); HIGH interior-transform bug (rewrote to mirror LOW). |

| 2986 | Build H — z=0 straddle, 2×2, 1 layer each side (depth-2), 8 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}, Z∈{−0.5,+0.5} | (8,8,8)+(8,8,7) | B1: true depth-2 encoding. HIGH len 765 (degenerate: extra (0,0) filler, ghost val 31, h-1=1). Both chunks byte-exact. |
| 2988 | Build I — z=0 straddle, 2×2, 3 layers each side (depth-4), 24 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}, Z∈{−2.5,−1.5,−0.5,+0.5,+1.5,+2.5} | (8,8,8)+(8,8,7) | B1: 3rd point. Confirmed HIGH nudge is CONSTANT ±1 (not ×dep); LOW nudge is ×dep. Both chunks byte-exact. z=0 seam depth-generalized (2×2, depth 2/3/4). |

## Pending (spec'd, awaiting export number)
- (none)

## Archive / earlier exports (coords to backfill as confirmed)
Older referenced exports whose exact XYZ should be added here when re-confirmed:
2494 (solid interior, chunk (2,2,2)); 2906/2910/2935/2937 (z=0 seams, base position
UNKNOWN — do not byte-match blind); 2952/2954/2956 (staircases descent/peak/valley);
2959/2961/2963/2965/2967/2969/2971 (relief profiles); 2941/2943 (x=0 / y=0 seams).
