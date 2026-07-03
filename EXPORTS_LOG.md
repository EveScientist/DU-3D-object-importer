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

| 2990 | Build J — z=0 straddle, 3×3, 2 layers each side (depth-3), 36 vox | X∈{10.5,11.5,12.5}, Y∈{10.5,11.5,12.5}, Z∈{−1.5,−0.5,+0.5,+1.5} | (8,8,8)+(8,8,7) | B1: both chunks byte-exact len 834 FIRST TRY. ny=3 interior-row + nx=3 at depth>2 generalize. |

| 2992 | Build K — asym z=0 straddle, 2×2, 3 up / 1 down, 16 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}, Z∈{−0.5,+0.5,+1.5,+2.5} | (8,8,8) HIGH d4 + (8,8,7) LOW d2 | B1 COUPLING found: HIGH form depends on LOW's real-layer count. HIGH len 765 DEGENERATE (low_real==1) despite own depth-4; filler val=inner=depth−2=2, h-1=3. Fixed via opp_depth param. Both byte-exact. LOW unchanged. |

| 2994 | Build L — mirror asym z=0 straddle, 2×2, 1 up / 3 down, 16 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}, Z∈{−2.5,−1.5,−0.5,+0.5} | (8,8,8) HIGH d2 + (8,8,7) LOW d4 | B1: both byte-exact FIRST TRY. HIGH d2 opp4 = CLEAN form (len 757, ≠ 765 degenerate) — confirms HIGH clean-branch at depth-2. LOW d4 matched w/ NO opp param → LOW does NOT couple to high side. Asymmetry confirmed. |

| 2996 | Build M — z=0 straddle, 5×2, 2 layers each side (depth-3), 40 vox | X∈{10.5,11.5,12.5,13.5,14.5}, Y∈{10.5,11.5}, Z∈{−1.5,−0.5,+0.5,+1.5} | (8,8,8)+(8,8,7) | B1: FG groups byte-identical but ref +4 bytes (len 851 vs gen 847). nx=5 seam floor-step: ref has +1 [0,255] decl-pad pair (@~200) + +1 [255,0] tail pair vs plain heightmap. NOT YET FIXED — formula needs nx=6+ to pin ((nx−1)//4 vs +1/nx≥5). nx≤4 + 3×3 all byte-exact. |

| 2998 | Build N — z=0 straddle, 6×2, 2 layers each side (depth-3), 48 vox | X∈{10.5,11.5,12.5,13.5,14.5,15.5}, Y∈{10.5,11.5}, Z∈{−1.5,−0.5,+0.5,+1.5} | (8,8,8)+(8,8,7) | B1: BOTH chunks byte-exact len 881, ZERO correction. => nx=5 (2996) +4 is a LONE anomaly (nx=1-4,6 all exact) = suspected BUILD SLIP, not a real nx step. Rebuild of nx=5 requested. |

| 3000 | Build M-rebuild — z=0 straddle, 5×2, depth-3, 40 vox (rebuild of 2996) | X∈{10.5,11.5,12.5,13.5,14.5}, Y∈{10.5,11.5}, Z∈{−1.5,−0.5,+0.5,+1.5} | (8,8,8)+(8,8,7) | REBUILD = same +4 as 2996 → NOT a slip, nx=5 is REAL. Comparing increments: real seam applies the +4 floor-step at nx=5 (heightmap does it at nx=6) → seam follows //4 boundary, heightmap //5. Fixed via _seam_nx_step: units=(nx−1)//4−(nx−1)//5, +1 [255,0] at decl end + tail per unit. Now byte-exact. |

| 3002 | Build O — varying-depth z=0 straddle, 2×2, stepped +Z (X=10.5 up 2, X=11.5 up 1), all down 1, 10 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}; Z=−0.5 all4; Z=+0.5 all4; Z=+1.5 only X=10.5 | (8,8,8)+(8,8,7) | VARYING-DEPTH start. HIGH = per-column heightmap [[3,3],[2,2]] (runs encode per-col depth) + seam interior transform. LOW byte-exact uniform-d2 (unaffected by +Z variation). Interior filler = (0,1) here (varying) vs (inner,0) uniform — height-TRANSITION marker differs. Tangled w/ degenerate (low_real=1). |

| 3004 | Build P — CLEAN varying-depth z=0 straddle, 2×2, stepped +Z, LOW 2 deep, 14 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}; Z=−1.5 all4; Z=−0.5 all4; Z=+0.5 all4; Z=+1.5 only X=10.5 | VARYING-DEPTH clean form. HIGH REPRODUCED byte-exact (inline model): heightmap([[3,3],[2,2]]) + interior marker (33−diff, diff) [diff=1 here → (32,1)] + decls@H+1 + ±1 nudge. LOW byte-exact uniform-d3. Marker confirmed diff=1 ONLY — needs diff=2 + step-up to pin. Not yet coded into a gen_seam function. |

| 3006 | Build Q — varying-depth z=0 straddle, 2×2, +Z step of 2, LOW 2 deep, 16 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}; Z=−1.5 all4; Z=−0.5 all4; Z=+0.5 all4; Z=+1.5 X=10.5; Z=+2.5 X=10.5 | VARYING-DEPTH diff=2 CONFIRMED: interior marker = (31,2) = (33−2,2) exactly as predicted. HIGH byte-exact via gen_seam_z_high_varying([[4,4],[2,2]]). Marker (33−diff,diff) now pinned at diff 0/1/2. LOW byte-exact uniform-d3. |

| 3008 | Build R — varying-depth z=0 straddle, step-UP (right-taller), 2×2, LOW 2 deep, 14 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}; Z=−1.5 all4; Z=−0.5 all4; Z=+0.5 all4; Z=+1.5 only X=11.5 | VARYING-DEPTH step-UP: marker (32,1) = SAME as step-down → direction-INDEPENDENT (|diff|). gen_seam_z_high_varying([[2,2],[3,3]]) byte-exact FIRST TRY (fn already used abs). Direction shows only in heightmap cluster opener (127 vs 126), handled by gen_heightmap_unified. LOW byte-exact uniform-d3. |

| 3010 | Build S — nx>2 varying-depth z=0 straddle, 3-col descending +Z (4/3/2), LOW 2 deep, 24 vox | X∈{10.5,11.5,12.5}, Y∈{10.5,11.5}; Z=−1.5/−0.5/+0.5 all6; Z=+1.5 X∈{10.5,11.5}; Z=+2.5 X=10.5 | nx>2 varying SOLVED. Rebuilt gen_seam_z_high_varying to REBUILD each interior cluster (opener + (ny−1) markers + real last row), DISCARDING A1's relief filler ((val,0)+(0,diff)); pad total = len(gA)−f0−removed. Byte-exact + reduces to all prior (3004/3006/3008/2983/2990). |

| 3012 | Build T — varying-depth z=0 straddle, 3-col PEAK (2/4/2), LOW 2 deep, 22 vox | X∈{10.5,11.5,12.5}, Y∈{10.5,11.5}; Z=−1.5/−0.5/+0.5 all6; Z=+1.5 X=11.5; Z=+2.5 X=11.5 | PEAK byte-exact FIRST TRY: gen_seam_z_high_varying([[2,2],[4,4],[2,2]]), both markers (31,2) as predicted. Ascending + descending + apex all confirmed — cluster-rebuild handles arbitrary relief direction. LOW byte-exact uniform-d3. |

| 3014 | Build U — z=0 straddle, 2×2, depth varying along Y (Hdepth=[[3,2],[2,2]]), LOW 2 deep, 13 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}; Z=−1.5/−0.5/+0.5 all4; Z=+1.5 only (10.5,10.5) | Y-VARYING depth byte-exact FIRST TRY, zero code change. Heightmap encodes y-variation in cluster content ((30,2) runs); seam marker from ROW-0 diff (32,1) composes on top. LOW byte-exact uniform-d3. First per-row depth variation validated → 2D relief across z=0 basically composes. |

| 3016 | Build V — z=0 straddle, 2×2, tall column at (10.5,11.5) (Hdepth=[[2,3],[2,2]]), LOW 2 deep, 13 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}; Z=−1.5/−0.5/+0.5 all4; Z=+1.5 only (10.5,11.5) | MARKER RULE PINNED: ref marker (33,1) — BOTH prior hypotheses wrong. Marker k: value = 33−diff(row k), run = MAX diff over rows (parts key off different rows; 3014 (1,0)→(32,1), 3016 (0,1)→(33,1)). Encoded; all 9 varying/uniform cases byte-exact. LOW byte-exact uniform-d3. |

## Pending (spec'd, awaiting export number)
- (none)

## Frontier (next session)
- **nx>2 varying: peak VALIDATED (3012)** — ascending+descending+apex byte-exact.
  Valley ([[4,4],[2,2],[4,4]]) still unvalidated but same mechanism; low priority.
- ny>2 per-row varying depth; degenerate (low_real==1) varying.

## z=0 seam status: FULLY GENERALIZED (byte-exact all known builds)
depth 2/3/4 sym + asym (HIGH couples to opp real-layer count); footprints nx=2–6 / ny=2–3;
nx floor-step ((nx−1)//4−(nx−1)//5, +4 at nx=5,9,10..). Untested: nx=9/10 step recurrence
(well-motivated), varying per-column depth (relief across z=0 — the next frontier).

## Archive / earlier exports (coords to backfill as confirmed)
Older referenced exports whose exact XYZ should be added here when re-confirmed:
2494 (solid interior, chunk (2,2,2)); 2906/2910/2935/2937 (z=0 seams, base position
UNKNOWN — do not byte-match blind); 2952/2954/2956 (staircases descent/peak/valley);
2959/2961/2963/2965/2967/2969/2971 (relief profiles); 2941/2943 (x=0 / y=0 seams).
