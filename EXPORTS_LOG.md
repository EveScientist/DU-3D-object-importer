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
| 3156 | Plain 2×2×2 solid (closed-shapes PROBE 1 reference) | X,Y,Z∈{10.5,11.5} | (8,8,8) | scan 765, mc 624. |
| 3157 | Same block, hand-displaced UNDERSIDE + TOP on same column | X,Y,Z∈{10.5,11.5} | (8,8,8) | scan 769 (+4), mc 624. **TWO-SURFACE PROVEN**: (11,11,10) bottom−42 & (11,11,12) top+42 = same column bottom+top, independent, both 8B in-place z-slot; (10,10,10) outer bottom−28 → run2 face 8B→12B tilt. See closed_shapes_kickoff PROBE 1 RESULT. |
| 3160 | Same block, 4 SIDE-face (vertical) hand-drags | X,Y,Z∈{10.5,11.5} | (8,8,8) | scan 789 (+24), mc 624. **SIDES PROVEN** (x/y slots = z mechanics): (12,11,11)+x ctr x−29 & (10,11,11)−x ctr x−46 → **16B THREE-VERTEX** (middle vertex T1); (11,10,12)−y top y+28 & (11,10,10)−y bottom y+56 → 12B two-vertex V1/V0. See closed_shapes_kickoff PROBE 2 RESULT. |
| 3162 | **4×4×4 solid**, 7 Z-drags on face-interior verts (displaced ONLY, no plain twin) | X,Y,Z∈{8.5,9.5,10.5,11.5} (spans 8..12) | (8,8,8) | scan 1009. **WALK ORDER SOLVED**: 5 X-plane sections (X slow, Y fast); interior columns = Bottom(val29)+Top(val2) run-0 z-slot pairs. Anchors: top +18/+34/+50/+70 @563/651/739/595, bottom −24/−42/−60 @555/643/731. See closed_shapes_kickoff PROBE 3 RESULT. |

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

| 3018 | Build W — z=0 straddle, 2×3, y-graded +Z (Hdepth=[[4,3,2],[2,2,2]]), LOW 2 deep, 21 vox | X∈{10.5,11.5}, Y∈{10.5,11.5,12.5}; Z=−1.5/−0.5/+0.5 all6; Z=+1.5 (10.5,10.5)+(10.5,11.5); Z=+2.5 (10.5,10.5) | ny=3 CRACKED THE FULL MARKER MODEL: ref markers (31,2),(31,1) → value = 33−FWD running max(diffs[0..k]), run = BWD running max(diffs[k..]) (mirrors A1 rInc/rDec). ALSO: last content row of every cluster = 33−BWD running max(profile[ny−2:]) (y-descending tails differ from raw heightmap: (30,2) not (29,2)); interior profile = ADJACENT-pair max, not running max from col0 (pinned by 3010 regression). All 10 refs byte-exact. LOW byte-exact uniform-d3 2×3. |

| 3020 | Build X — z=0 straddle, 2×4, y-staircase +Z (Hdepth=[[5,4,3,2],[2,2,2,2]]), LOW 2 deep, 30 vox | X∈{10.5,11.5}, Y∈{10.5,11.5,12.5,13.5}; Z=−1.5/−0.5/+0.5 all8; Z=+1.5 (10.5,{10.5,11.5,12.5}); Z=+2.5 (10.5,{10.5,11.5}); Z=+3.5 (10.5,10.5) | UNIFIED VALUE RULE PINNED: middle rows ARE rDec-shifted (row2=29), and marker k2=(31,1) broke the fwd-running-max hypothesis (fit ny≤3 coincidentally). One rule for markers AND content: value_i = 33−(seq[0] if i==0 else max(seq[i−1:])), run_i = max(seq[i:]); seq = profile (content) / row-diffs (markers). All 11 refs byte-exact. LOW byte-exact uniform-d3 2×4. |

| 3022 | Build Y — z=0 straddle, 2×2, varying −Z depth (up 2 all; down 3 X=10.5 / down 2 X=11.5), 18 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}; Z=+1.5/+0.5/−0.5/−1.5 all4; Z=−2.5 only X=10.5 pair | STRUCTURAL SURPRISE: LOW = byte-exact UNIFORM min-depth d3 (z=−2.5 layer ABSENT from LOW); the extra below-min layer folds into HIGH = gen_seam_z_high_varying([[4,4],[3,3]]) byte-exact. Only 2 h3 chunks (verified). HIGH param = up+ghost+extra-below; additive-vs-flag ambiguous at extra=1 → Build Z. |

| 3024 | Build Z — z=0 straddle, 2×2, up 2 all, down 4 X=10.5 / down 2 X=11.5 (extra=2), 20 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}; Z=+1.5/+0.5/−0.5/−1.5 all4; Z=−2.5/−3.5 only X=10.5 pair | BOTH hypotheses wrong — ROLES FLIPPED vs 3022: HIGH = byte-exact plain uniform d3; LOW carries the variation (first varying LOW ever). Decoded + coded gen_seam_z_low_varying([[5,5],[3,3]]) byte-exact: interior k0 run→diff, k≥1 value→33−diff, final opener +diff, col-c x-marker decl +diff, nudges split (first-decl/fg0−dep(col0), preval+dep(colLast)). All 8 uniform reductions == gen_seam_z_low exactly. REPRESENTATION RULE: extra=1 → folds into HIGH (3022); extra≥2 → varying LOW + min-uniform HIGH (3024). |

| 3026 | Build AA — z=0 straddle, 3×2, up 2 all; down 2/3/4 across X (extras 0/1/2), 30 vox | X∈{10.5,11.5,12.5}, Y∈{10.5,11.5}; Z=+1.5/+0.5/−0.5/−1.5 all6; Z=−2.5 X∈{11.5,12.5} pairs; Z=−3.5 X=12.5 pair | CHOICE IS WHOLE-CHUNK: HIGH byte-exact plain uniform-min d3; LOW carries ALL variation incl the extra=1 col ([[3,3],[4,4],[5,5]]). Also pinned SIGNED step rules (build was ascending, 3024 descending): x-marker decl += s(c) signed; interior opener += min(0,s); final opener += max(0,s(last)). gen_seam_z_low_varying byte-exact 3024+3026+8 uniform reductions. |

| 3028 | Build AB — z=0 straddle, 2×2, BOTH sides varying: X=10.5 up 2/down 4, X=11.5 up 1/down 2, 18 vox | X∈{10.5,11.5}, Y∈{10.5,11.5}; Z=+1.5 X=10.5 pair; Z=+0.5/−0.5/−1.5 all4; Z=−2.5/−3.5 X=10.5 pair | INDEPENDENCE PROVEN, zero new code: HIGH == gen_seam_z_high_varying([[3,3],[2,2]]) byte-exact (identical to 3004/P despite varying ground below); LOW == gen_seam_z_low_varying([[5,5],[3,3]]) byte-exact (identical to 3024/Z despite varying surface above). VARYING z=0 SEAM GENERATIVELY COMPLETE for validated envelope. |

| 3032 | Build AC — x=0 straddle plate, 4 cols × 2 rows × 1 tall, 8 vox | X∈{−1.5,−0.5,+0.5,+1.5}, Y∈{10.5,11.5}, Z=10.5 | (8,8,8)+(7,8,8) | B2: LOW SOLVED = plain 3-wide plate @lx0=30 (=32−n_real), 1 boundary ghost, NO jitter (old _x0_jitter = CV-band shim, obsolete). HIGH = plain 3w @lx0=−1 + leading ghost-decl block [0,255,0, CV(lx0=−2)=175,1,2,0,0, 33,1,2,0] + first-decl +44 (120→164). ALSO: 2941/2943 minimal builds DISQUALIFIED as oracles (unknown position + structure mismatch under current code). |

| 3034 | (AD mis-build — axes swapped) 2×1 bar, 3 up / 3 down crossing z=0, 12 vox | actual: 2 cols × 1 row × 6 tall through z=0 (intended AD plate rotated) | (8,8,8)+(8,8,7) | ACCIDENTAL FIRST ny=1 z-seam datapoint: HIGH matched unchanged; LOW off 2 bytes → at ny=1 the single row is first AND last, last-row rule wins (run kept, not zeroed). Fixed in gen_seam_z_low (ny>1 guard); all regressions + varying reductions clean. |

| 3036 | Build AD — x=0 straddle plate, 6 cols × 2 rows × 1 tall, 12 vox | X∈{−2.5,−1.5,−0.5,+0.5,+1.5,+2.5}, Y∈{10.5,11.5}, Z=10.5 | (8,8,8)+(7,8,8) | B2 x=0 WIDTH PINNED: HIGH transform WIDTH-INVARIANT (same ghost block CV(−2)=175 + first-decl +44 as 3032) — byte-exact. LOW = plain 4w@lx0=29 + CV-band layout shift (CV=6≤160: pre +2 pair before first decl absorbed after decl run, fg0 +2 absorbed at tail; 3032 CV=207>160 needs none). gen_seam_x0_high/low rewritten general — all 4 chunks (2 builds × 2) byte-exact. Band edge 160 assumed from bw band (2 CV points). |

| 3038 | Build AE — y=0 straddle plate, 2 cols × 4 rows (2/side) × 1 tall, 8 vox | X∈{10.5,11.5}, Y∈{−1.5,−0.5,+0.5,+1.5}, Z=10.5 | (8,8,8)+(8,7,8) | B2 y=0 SOLVED + UNIFIED SEAM PRINCIPLE: LOW = plain plate @ly0=30 byte-exact first try. HIGH = decl region from (rows+2)-plate @ly0=−2 (declares extra overlap row; lead=CV(−2)=119, extra 33/col) + FG region from (rows+1)-plate @ly0=−1, tail −2 — SAME principle as z=0 clean form (decls declare one extra overlap unit). Also REINTERPRETED x=0's "+44": 164 = standard x-marker value — x=0 HIGH decls are those of the (cols+2)-plate @lx0=−2. gen_seam_y0_high/low rewritten; all byte-exact. |

| 3040 | Build AF — x=0 straddle slab, 4 cols × 2 rows × 2 tall, 16 vox | X∈{−1.5,−0.5,+0.5,+1.5}, Y∈{10.5,11.5}, Z∈{10.5,11.5} | (8,8,8)+(7,8,8) | h=2: PREDICTION CONFIRMED — first-decl 163 = x-marker formula (200−h−35(ny−1)); ghost-block h−1 fields track h, block marker 33→32 (33−(h−1), h=3 would distinguish const −1). NEW: h≥2 interior-filler transform — every FG cluster EXCEPT the far-edge one takes z=0-degenerate form (first ny−1 rows → run 0 + (h−2,0) filler); HIGH far edge = last cluster, LOW = first (HIGH's c0 counts interior because decls claim an extra ghost cluster). +24B = 3 fillers ×8. Coded _seam_x0_interior_fillers; all byte-exact incl regressions. |

| 3042 | Build AG — x=0 straddle slab, 4 cols × 2 rows × 3 tall, 24 vox | X∈{−1.5,−0.5,+0.5,+1.5}, Y∈{10.5,11.5}, Z∈{10.5,11.5,12.5} | (8,8,8)+(7,8,8) | h=3: BOTH target predictions held (filler = (h−2,0)=(1,0) ✓; ghost-block marker 31 = 33−(h−1) ✓). NEW SURPRISE: ALL decl third-bytes (the "constant 2") = max(2,h)=3, both chunks — x=0-SEAM-SPECIFIC (plain heightmaps + z=0 seams keep 2 at any h). Added _seam_x0_decl_third. Byte-exact both chunks; suite 30/30. |

| 3044 | Build AH — y=0 straddle slab, 2 cols × 4 rows (2/side) × 2 tall, 16 vox | X∈{10.5,11.5}, Y∈{−1.5,−0.5,+0.5,+1.5}, Z∈{10.5,11.5} | (8,8,8)+(8,7,8) | y=0 h=2: row-flavored fillers, OWN GEOMETRY — only INTERIOR x-clusters transform (both edges plain; narrower than x=0's all-but-far-edge). HIGH: opener + rows 0..ny−2 → run0+(h−2,0) filler, LAST row survives (ghost row first). LOW: opener survives, ALL rows transform (ghost row last). +24B, decls untouched. Coded _seam_y0_interior_fillers; byte-exact both chunks; suite 31/31. |

| 3046 | Build AI — y=0 straddle slab, 2 cols × 4 rows (2/side) × 3 tall, 24 vox | X∈{10.5,11.5}, Y∈{−1.5,−0.5,+0.5,+1.5}, Z∈{10.5,11.5,12.5} | (8,8,8)+(8,7,8) | y=0 h=3: BYTE-EXACT AS-IS both chunks, zero code change. Filler h−2 confirmed for y=0; decl-third flip ABSENT (decls keep 2 at h=3) → max(2,h) rule is x=0-SPECIFIC. Suite 32/32. B2 basic height model complete for all 3 axes. |

| 3048 | Build AJ — x=0 straddle height hump (1,2|2,1 across X), 2 rows, 12 vox | Z=10.5: all 4 cols × 2 rows; Z=11.5: X=±0.5 only | (8,8,8)+(7,8,8) | NEW SUB-FORMAT DISCOVERED: 16-byte THREE-VERTEX groups [val,1,run, T0,0, T1,0, T2,0, 0] in boundary-adjacent clusters — T1 z-offsets +14 and +42 (=half voxel) steps — DU generates sub-voxel transition geometry where relief steps cross the seam. Confirmed: ghost cols take across-boundary neighbor height; head transforms unchanged; uniform fillers where expected. HIGH raw @360-432, LOW @720-815 documented. Offset formula (why 14/42, scaling with step size/direction) = NEW FRONTIER, needs dedicated builds. |

| 3050 | Build AK — x=0 straddle hump, step of 2 (heights 1,3|3,1), 2 rows, 16 vox | Z=10.5: all 4 cols × 2 rows; Z=11.5+Z=12.5: X=±0.5 only | (8,8,8)+(7,8,8) | OFFSETS ARE FIXED CONSTANTS: 3050 = 3048 + pure height-scaling (runs 2→3, values 31→30, decl fields +1, x-marker 162=200−h−35, block marker 31=33−(h−1) — ALL known rules). T1z +14/+42 UNCHANGED at step 2. 16-byte form pinned: [val,1,run, T0,0, T1,0, T2,0, h−2] (final byte was 0 at h=2, 1 at h=3 = h−2). Transition geometry shape is step-size-independent. |

| 3052 | Build AL — x=0 one-sided step AT boundary (heights 2,2|1,1), 2 rows, 12 vox | Z=10.5: all 4 cols × 2 rows; Z=11.5: X∈{−1.5,−0.5} only | (8,8,8)+(7,8,8) | STEP-AT-BOUNDARY = NO transition geometry (zero 16-byte groups) — pure flat clusters, each side own heights, ghosts copy neighbors (HIGH ghost h2, LOW ghost h1); cliff face = chunk face. 3-vertex form ONLY when step is 1 col AWAY from boundary (slope spans it). Fillers per-cluster by own height (h1 clusters none); LOW c2 (h2) unexpectedly plain — map in generator work. HIGH clusters: [h2+filler ghost],[h2 plain],[h1],[h1]; LOW: [h2 plain far],[h2+filler],[h2 plain],[h1 ghost]. |

| 3054 | Build AM — x=0 straddle, step 2 cols from boundary (heights 2,1,1|1,1,1), 2 rows, 14 vox | Z=10.5: all 6 cols × 2 rows; Z=11.5: X=−2.5 only | (8,8,8)+(7,8,8) | 3-VERTEX FORM IS STRICTLY BOUNDARY-ADJACENT: this step encodes as plain A1 heightmap composition (5 flat clusters, no 16-byte groups, no fillers even on h2 clusters). HIGH == gen_seam_x0_high(3) BYTE-EXACT — far side fully independent of the step. Filler-set rule under mixed heights = open bookkeeping (3052 had 1 filler cluster, 3054 none). |
| 3056 | Build AN — x=0 ONE-SIDED step 1 col out (heights 1,1|2,1), 2 rows, 10 vox | Z=10.5: X∈{−1.5,−0.5,+0.5,+1.5} × Y∈{10.5,11.5}; Z=11.5: X=+0.5 only | (8,8,8)+(7,8,8) | TRI TRIGGER DISAMBIGUATED — INVERTED vs own-pair hypothesis: HIGH (own pair 2→1 steps) = completely PLAIN (no 16B, ghost h1 cluster plain, gen predicted TRI = wrong side); LOW (own side flat, opp pair steps) = TRI ghost cluster in exact 3048-LOW form (opener+last row +14, middle filler'd). Rule: transition geometry lives in the chunk ACROSS the seam from the step (tri = opp[0]≠opp[1]). Gate flipped in gen_seam_x0_*_varying; both chunks byte-exact after fix; all prior refs unaffected (they stepped symmetrically or not at all). Suite 38/38. |
| 3058 | Build AO — x=0 symmetric VALLEY (heights 2,1|1,2), 2 rows, 12 vox | Z=10.5: X∈{−1.5,−0.5,+0.5,+1.5} × Y∈{10.5,11.5}; Z=11.5: X∈{−1.5,+1.5} | (8,8,8)+(7,8,8) | TWO FINDS: (1) TRI trigger is DIRECTIONAL — opp[0]>opp[1] (descends away); valley (ascends away) = ZERO transition geometry both chunks, so no negative-dz form exists to probe. (2) HIGH's ghost EDGE cluster = interior-pair cluster of the TWO across-boundary cols: height max(hB,ghost)=2 over h1 ghost (decl stays d0; next opener shifts via 129−prev_h chain); hump refs masked this (max==ghost). LOW = byte-exact PLAIN plate (outer across-boundary col fully ignored — no mirror rule). Both chunks byte-exact after fix; suite 39/39. |
| 3060 | Build AP — x=0 hump 1,2|2,1 at ny=3 (3 rows), 18 vox | Z=10.5: X∈{−1.5,−0.5,+0.5,+1.5} × Y∈{10.5,11.5,12.5}; Z=11.5: X=±0.5 × 3 rows | (8,8,8)+(7,8,8) | ny>2 VALIDATED: LOW byte-exact FIRST TRY (TRI ends + 2 filler'd middles compose); HIGH FG exact as predicted (+42 on EACH middle row — no grading); only miss = head block gains one 33-marker per extra row (full ny-entry column decl group of the hB ghost-ghost column, = (n+2)-plate concept; xmark 129=200−1−35·2 already fit). Block generalized; both chunks byte-exact; suite 40/40. Remaining x=0-varying unknowns: h≥4, n_real≥4, ny≥4. |
| 3062 | Build AQ — y=0 hump 1,2|2,1 (2 cols × 4 rows straddling y=0), 12 vox | Z=10.5: X∈{10.5,11.5} × Y∈{−1.5,−0.5,+0.5,+1.5}; Z=11.5: X∈{10.5,11.5} × Y=±0.5 | (8,8,8)+(8,7,8) | y=0 varying = TRANSPOSE of x=0 rules: seam-adjacent element per x-cluster = OPENER (HIGH) / GHOST ROW (LOW); TRI dz +14 at x-EDGE clusters, +42 at x-interior (HIGH openers); LOW ghost row +14 at edges, filler form interior; T1 offset stays in the Z slot (displacement is vertical — not the y slot). HIGH decls = varying (rows+2)-plate @ly0=−2 with [hB, ghost]+rows (hB rule transposes; vals 119/94 = −35 shift). Fillers confined to x-interior clusters; HIGH rows two-sided neighbor rule, LOW rows ONE-SIDED (+y toward seam — 3062 LOW row1 rejects two-sided; x/y asymmetry). gen_seam_y0_high/low_varying coded; byte-exact both chunks + uniform reductions h1/h2/h3. Suite 42/42. |
| 3064 | Build AR — y=0 VALLEY 2,1|1,2 (2 cols × 4 rows), 12 vox | Z=10.5: X∈{10.5,11.5} × Y∈{−1.5,−0.5,+0.5,+1.5}; Z=11.5: X∈{10.5,11.5} × Y=±1.5 | (8,8,8)+(8,7,8) | SEAM CHAIN RESET discovered: plain y-plates encode rows as val=33−fwd-running-max / run=bwd-running-max over the profile, but seam chunks reset the chain at the boundary — own rows chain over OWN rows only; ghost row group standalone: HIGH (33−max(hB,ghost), run=ghost) + opener run=max(hB,ghost) (across-boundary-pair rule transposed), LOW (33−ghost, run=ghost) (outer col ignored — LOW asymmetry transposed). Directional TRI trigger transposes (valley = zero transition geometry ✓). Hump 3062 had masked the reset (chains coincided). _y0_rebuild_fg rebuilt spec-based; both chunks byte-exact; 3062+reductions unaffected. Suite 43/43. |
| 3066 | Build AS — y=0 ONE-SIDED step (heights 1,1|2,1), 2 cols, 10 vox | Z=10.5: X∈{10.5,11.5} × Y∈{−1.5,−0.5,+0.5,+1.5}; Z=11.5: X∈{10.5,11.5} × Y=+0.5 | (8,8,8)+(8,7,8) | TRIGGER SIDE TRANSPOSES ✓ (HIGH plain, LOW carries TRI ghost rows — exactly as predicted from x=0's 3056). Residual 6 bytes/chunk pinned PAIRWISE ROW RUNS: seam-chunk row runs = max(own, next group) incl the ghost as neighbor — NOT the plain plate's bwd-running-max (3064's profiles couldn't distinguish; 3066's h1-row-before-h2-ghost does: run 2 where bwdmax-of-own gives 1; ghost row next = own row0 for HIGH). Fixed in _y0_rebuild_fg; both chunks byte-exact; all priors unaffected. Suite 44/44. y=0 VARYING = CLOSED to x=0 standard. |
| 3077 | Build AT — y=0+z=0 SURFACE corner (3×2×2 slab), 12 vox | X∈{10.5,11.5,12.5} × Y∈{−0.5,+0.5} × Z∈{−0.5,+0.5} | (8,8,8)+(8,7,8)+(8,8,7)+(8,7,7) | xz rules transpose PARTIALLY: (8,8,8) = PLAIN gen_seam_z_high@ly0=−1 byte-exact (NO jitter — x0 corner jitter is x-SPECIFIC); (8,7,8) = z_high@ly31 + y_fwd_ghost (ghost ROW → ALL content rows filler form) byte-exact first pass, no jitter; (8,8,7) +y−z = z_low@ly−1 + REVERSE jitter (+4: pad before preval + trailing); (8,7,7) double-neg = z_low@ly31 y_fwd_ghost + openers AFTER first special cluster +2 (surface echo of dense yz-edge "double-neg fill +2 after first fill") + x0-CV-band-style layout shift (pad→before first decl absorbed pre-preval; pad→after preval absorbed from tail). gen_corner_yz coded; all 4 byte-exact; suite 47/47. Single-point assumptions: opener+2 range (c≥2), layout-shift trigger, nx/depth scaling. |

| 3079 | Build AU — x=0+y=0 SURFACE corner (4×4×1 slab, h1), 16 vox | Z=10.5: X∈{−1.5,−0.5,+0.5,+1.5} × Y∈{−1.5,−0.5,+0.5,+1.5} | (8,8,8)+(7,8,8)+(8,7,8)+(7,7,8) | CLEANEST corner: (8,8,8) = gen_corner_hh(2,2) BYTE-EXACT (terrain-grid 2-axis corner form IS the octant xy corner — unified seam principle); (7,7,8) = PURE plain plate @(30,30) (x0 CV band shift ABSENT despite in-band CV); (7,8,8) = y0-high decl splice @lx0=30 WITHOUT the pure-y0 −2 tail trim; (8,7,8) = plain @(−1,30) + x0-high head in UNIFIED placement (full ghost-col decl group inserted @first_decl−10, one pad pair dropped after, first-decl→x-marker — verified byte-equivalent to existing block construction on 3048/3060). gen_corner_xy coded; all 4 byte-exact; suite 48/48. ALL THREE 2-plane surface corners now solved+coded (xz/yz/xy). |

| 3081 | Build AV — DISPLACED 3048 hump (user modified vertex points MANUALLY, not the smooth tool), 12 vox | same coords as 3048; manual vertex edits on top step edges | (8,8,8)+(7,8,8) | DISPLACEMENT-THROUGH-SEAM DECODED (opens END-GOAL arc): vertex edits change ONLY displacement slots — structure/values/runs/decls/pads byte-identical to blocky 3048. Carriers per group form: TRI groups → T2 slot (T1 keeps +14/+42); flat run>0 → 12B two-vertex [val,1,run, 7e-triple, run−1, V1, 0,0] (s-slot = run−1, retro-fits old single-chunk refs); (0,0) fillers → in-place 8B; run-0 content rows stay NEUTRAL. Displacement PER-CLUSTER uniform here: bevel clusters (±28,0,−40), hump-top interior (0,0,−16), far/h1 neutral. apply_seam_displacement coded; BOTH chunks reconstruct byte-exact from gen_seam_x0_*_varying + the map (suite 49/49). NO value function to solve (2026-07-04 user decision): the final tool computes vertex targets FROM THE .OBJ MESH per placed voxel — we choose our own displacement values; DU's smoother is irrelevant to the pipeline. |

## Pending (spec'd, awaiting export number)
- (none)

## Generated import tests
- **tests/grid_tilt_0705_1805.blueprint** (2026-07-05) — FIRST LARGE bumpy landscape: 100×100-vox
  (4×4-chunk) displaced plate, asymmetric diagonal tilt dz84=−round(0.4x+0.8y) (0..−120). First
  exercise of per-corner displacement through the GRID-INTERIOR generators (gen_middle_x/
  gen_double_middle/gen_ymid_xlow/xhigh/gen_corner_middle verts= paths, validated only tiny before).
  NEW du_solid.gen_terrain_grid(corner_z,gx,gy) routes each chunk its global-corner slice (ranges
  GENERALIZE gen_terrain's validated 2-chunk slices: x-low[0:nL+2]/x-mid_j[nL+32j−2:+33]/
  x-high[nx−Rx−1:nx+1], y sym); flat-reduction 16/16 == gen_terrain_flat_grid==3105; continuity
  automatic (shared lines sampled once). du_mesh.gen_grid_from_mesh + selftest 12/12. Donor 3105,
  mc per-chunk via _mc_from_scan (displacement-invariant), round-trip verified. EXPECTED: one
  continuous tilted plane over the whole plate, gentle downslope +x / steeper +y, deepest (+x,+y);
  NO crack/scramble at any of the 6 internal boundaries. Any localized defect names the offending
  grid-interior generator's vert ordering (middle_x/double_middle/ymid/corner_middle verts UNPROVEN
  in hardware).
  **RENDERED PERFECTLY 2026-07-05 — one continuous tilted plane across all 16 chunks, no cracks or
  scrambles. ALL grid-interior generators' vert ordering HARDWARE-PROVEN at scale. The large
  landscape displacement pipeline is complete; full M-core = same op at ~8×8 + one bigger donor.**
  OBSERVATION (design fact): displacement is RELATIVE TO THE BLOCKY TOP FACE and UNCLAMPED by DU —
  the −120 (−1.43 vox) far corner pushed the top surface BELOW the base bottom (z=0) with the h=1
  base. Harmless, but confirms: for downward relief the blocky base must be thick enough (h ≥
  ceil(max|dz|/84)+margin) or the surface passes through the underside. Ties into the >±1.5-vox
  amplitude arc (varying blocky height through grid seams).
- **tests/mesh_wave_import_0704_1434.blueprint** (2026-07-04) — FIRST MESH-DRIVEN import test:
  cosine half-pipe valley z(x)=0.75+0.25·cos(πx/2) over a 4×1 patch, generated end-to-end by the
  NEW du_mesh solver (mesh → corner z-sample → blocky H + per-corner vertex offsets →
  gen_surface_displaced). Corner offsets 0/−21/−42/−21/0 (smooth half-voxel dip). Envelope+mc 514
  from donor 2700 (same all-1 blocky H; mc displacement-invariant). Round-trip verified. Solver
  offline-validated: reproduces gen_linear_ramp (2700), the diagonal tilt, and plain flat plates
  byte-exactly from synthetic meshes. EXPECTED: 4-vox strip at the 2700 position whose top is a
  smooth cosine valley — full height at the ends, half-voxel dip center, no steps.
  **DEPLOYED PERFECTLY 2026-07-04 — the mesh→solver→encoder→assembler path is hardware-proven.**
- **tests/mesh_span_wave_0704_1439.blueprint** (2026-07-04) — increment 2: the same cosine valley
  SPANNING a chunk-grid boundary via mesh→gen_terrain_from_mesh (4×2 patch @gx=30,gy=10; the −42
  dip line sits exactly ON the boundary, forcing shared ghost-line offsets). Donor 2669 (= flat
  gen_terrain(30,10,4,2)); mcs {(8,8,8):756,(9,8,8):587}; round-trip verified. Selftest 4/4 (adds
  boundary-spanning ramp == gen_terrain byte-exact). EXPECTED: 4×2 plate, one continuous smooth
  valley across the boundary, NO crack or step.
  **RENDERED PERFECTLY 2026-07-04 — multi-chunk mesh terrain (shared ghost-line offsets) hardware-proven.**
- **tests/mesh_x0_wave_0704_1446.blueprint** (2026-07-04) — increment 3: the cosine valley across
  the x=0 OCTANT seam (dip line −42 exactly ON x=0), via gen_x0_from_mesh → gen_seam_x0_*_varying
  + apply_seam_displacement per-group vlist mode (new; fillers inherit preceding row's V, run-0
  rows neutral). Donor 3032 (uniform x0 pair); mcs {(8,8,8):587,(7,8,8):756}; round-trip verified;
  selftest 6/6 (adds 3081-vlist equivalence + flat-across-x0 reduction). EXPECTED: 4×2 plate
  straddling x=0, smooth half-voxel dip AT the octant boundary, no crack.
  **DEPLOYED 2026-07-04: rendered a HILL (center 0, edges −42) — NOT a mapping bug: the TEST MESH
  had a cosine PHASE ERROR (cos(π(x−2)/2) peaks at the seam). DU rendered the buggy mesh
  faithfully; solver + mapping were correct all along (user caught it: "check your file").**
- **tests/mesh_x0_ramp_diag_0704_1452.blueprint** (2026-07-04) — diagnostic ramp across x=0,
  distinct offset per corner line. **RENDERED PERFECTLY 2026-07-04: smooth wedge X −1.5→+1.5,
  depths exactly 0/−21/−42/−63/−84 left→right, no crack at the octant seam — the x0 MESH PATH
  (cluster→line mapping, carriers, ghost-line consistency) is HARDWARE-PROVEN. (Also falsified
  the interim "mirrored mapping" hypothesis — a symmetric hill is the value-mirror of a valley.)**
- **tests/mesh_x0_valley_fixed_0704_1500.blueprint** (2026-07-04) — the intended valley with the
  phase FIXED (0.75 − 0.25·cos): line offsets 0/−21/−42/−21/0, dip AT x=0. Donor 3032; round-trip
  verified. EXPECTED: smooth half-voxel dip at the octant boundary rising to full height at ±2.
  **RENDERED AS A VALLEY 2026-07-04 — confirmed; increment 3 (x=0 crossing) fully closed.**
- **tests/mesh_y0_ramp_0704_1503.blueprint** (2026-07-04) — increment 4: linear ramp across the
  y=0 octant seam (asymmetric probe first, per the x0 lesson): z(y)=1−(y+2)/4, line offsets
  y=−2..+2 → 0/−21/−42/−63/−84, uniform in x. gen_y0_from_mesh (new; transposed group order:
  clusters = x-lines, groups within = y-lines ascending, opener first). Donor 3038; mcs
  {(8,8,8):719,(8,7,8):658}; round-trip verified; selftest 7/7. EXPECTED: smooth wedge sloping
  down toward +y, full height at y=−2 to a voxel deep at y=+2, no crack at y=0.
  **DEPLOYED AS EXPECTED 2026-07-04 — increment 4 (y=0 crossing) hardware-proven first try.**
- **tests/x0_varying_tri_import_0704_0952.blueprint** (2026-07-04) — NOVEL asymmetric-width hump
  across x=0 (LOW [2,1] / HIGH [2,1,1] boundary-first; TRI transition clusters BOTH chunks —
  first in-game exercise of generated 16-byte three-vertex groups). (8,8,8)=gen_seam_x0_high_varying
  ([2,1,1],[2,1]) mc 642; (7,8,8)=gen_seam_x0_low_varying([2,1],[2,1]) mc 755; envelope 3054;
  round-trip verified. EXPECTED: 14 vox — Z=10.5: X∈{−1.5,−0.5,+0.5,+1.5,+2.5} × Y∈{10.5,11.5};
  Z=11.5: X∈{−0.5,+0.5} × Y∈{10.5,11.5}; smooth bevel at the seam.
  **DEPLOYED PERFECTLY 2026-07-04** — x=0 varying stack incl generated TRI groups hardware-validated.
- **tests/y0_varying_tri_import_0704_0952.blueprint** (2026-07-04) — v1, mirror of 3066 (LOW [2,1] /
  HIGH [1,1]). **FAILED TO DEPLOY (bp 3068): "Deserializing invalid vertex" on BOTH cells; client
  crash.** Post-mortem: LOW deviated from the plain oracle plate by ONE byte — the "chain-reset"
  ghost val 32 vs 31. Led to the PAIRWISE-PREV value rule (val_j=33−max(h_j,h_prev), HIGH ghost's
  prev = hB): fits every real ref byte (suite 46/46) and differs from chain-reset exactly at
  own-boundary>ghost configs like this one. Seam chunks = pairwise both directions (vals look −y,
  runs look +y); plain plates = running maxes. HIGH knobs still un-oracled → v2/v3/v4 variants.
- **tests/y0_varying_tri_import_{v2,v3,v4}_0704_1005.blueprint** (2026-07-04) — diagnostic variants
  of the failed v1, same LOW (now = plain plate) + mc; HIGH differs: v2 = pairwise vals + TRI;
  v3 = fwd-chain vals (far rows 31) + TRI; v4 = pairwise vals, NO TRI.
  **v2 (bp 3071) DEPLOYED + RENDERED PERFECTLY 2026-07-04** — arbitrates BOTH knobs: pairwise-prev
  values confirmed in hardware (far-row 32; fwd-chain/v3 moot) AND the TRI trigger fires with a
  flat own side (v4 moot). y=0 varying stack hardware-validated; current du_solid code correct
  as-is. (NB first spawn attempt accidentally pulled stale bp 3068 = v1 — check blueprint ids in
  the server log when a deploy behaves oddly.) OPTIONAL hardening (low priority): hand-build the
  same shape in-game and export → byte-oracle for the extrapolated HIGH form.
- **mc FIELD DECODED (empirically, 14 refs)**: mc = base(chunk type, plate dims) − (last-plate-
  column height − 1). Bases: x0-HIGH 587 (3-col plate, 2 rows) +55/extra col −35/extra row (last
  col = FAR col); x0-LOW 756 (last col = GHOST, width-independent); y0-HIGH 719 (last = far row);
  y0-LOW 658 (last = ghost row). Enables fully novel generated import tests (no donor chunk needed).
- **tests/z0_novel_pairing_gen.blueprint** (2026-07-03) — novel pairing: HIGH = 3014's y-varying
  surface (gen_seam_z_high_varying([[3,2],[2,2]]), mc 635) + LOW = 3024's deep varying ground
  (gen_seam_z_low_varying([[5,5],[3,3]]), mc 603); template/envelope 3028; round-trip verified.
  Expected deploy: 17 vox — 2×2 block Z=−1.5..+0.5, (10.5,10.5) up to +1.5, X=10.5 pair down to −3.5.
  **DEPLOYED PERFECTLY in-game 2026-07-03** — varying z=0 seam model hardware-validated end to end.

## Frontier (next session)
- **nx>2 varying: peak VALIDATED (3012)** — ascending+descending+apex byte-exact.
  Valley ([[4,4],[2,2],[4,4]]) still unvalidated but same mechanism; low priority.
- ny>2 per-row varying depth; degenerate (low_real==1) varying.

## z=0 seam status: FULLY GENERALIZED (byte-exact all known builds)
depth 2/3/4 sym + asym (HIGH couples to opp real-layer count); footprints nx=2–6 / ny=2–3;
nx floor-step ((nx−1)//4−(nx−1)//5, +4 at nx=5,9,10..). Untested: nx=9/10 step recurrence
(well-motivated), varying per-column depth (relief across z=0 — the next frontier).

## z=0 displacement carriers (Build AW, 2026-07-04)
- **3095** (Build AW — 2986 blocky base + user hand-dragged top vertices, asymmetric) —
  z-SEAM DISPLACEMENT CARRIERS = SAME GRAMMAR as x0/y0: flat run>0 → 12B two-vertex
  [val,1,run, 7e³, run−1, V1, 0,0]; (0,0) filler in-place carrying its row's corner value
  (run-0 row emits neutral but its V surfaces in the filler — matches apply_seam_displacement's
  walk exactly); run-0 rows neutral. LOW CHUNK MIRRORS HIGH's surface offsets (ghost layer
  includes the surface): identical value sets (−20/−68/−8/−36/−2/−43) in both chunks.
  apply_seam_displacement worked UNCHANGED. (3095 also contains a stray (7,8,8) chunk 671B —
  the hand-drag spilled a sliver across x=0; not needed for the decode.) gen_z0_from_mesh
  gained displace=True; selftest 9/9 (flat reduction exposed + fixed a chooser gap: low_real
  ≤1 requires the DEGENERATE high form; degenerate-varying still underived/asserted).
- **tests/mesh_z0_tilt_0704_2009.blueprint** — mapping probe: tilted plane z=1−(x+3y)/14 over
  the 2986 footprint, all 9 corner offsets distinct (0..−48). Donor 2986, mcs 635/603.
  EXPECTED: flat tilted top sloping down gently toward +x, strongly toward +y, deepest (−48)
  at the (+x,+y) corner.
  **DEPLOYED AS EXPECTED 2026-07-04 — z=0 crossing displacement (carriers + mapping) hardware-
  proven. ALL THREE center planes + grid seams + single chunks now render mesh-driven smooth
  surfaces correctly.**

## Build AX — 4×4-chunk flat donor (3105, 2026-07-04)
- **3105** = flat h1 plate X,Y∈[20.5,119.5], Z=10.5 (100×100 vox, 16 chunks cx/cy 8..11).
  mcs: 533 (most), 592 (cy=11 row exc corner), 550 (cx=11 col), 609 ((11,11)).
  gen_terrain_flat_grid(20,20,100,100): **6/16 byte-exact — ALL FOUR double-middles + x-low
  middles PASS**; failures = edge families at never-probed scale (ny=13 / Rx=24 / Ry=24):
  (a) (8,8,8) plain plate ny=13: 13 single pad-pair DELETIONS in FG (~1/cluster) → plate
      cluster-gap likely shrinks at large ny (cf. z-code's 4−(ny≥6); plain-plate rule unprobed
      beyond small ny);
  (b) (9/10,8,8) gen_middle_x(32,ny=13) + (11,8,8) gen_seam_high(24,ny=13): periodic per-column
      −2×2 deletions in the DECL region (period ~146) + same FG gap effect — the C1-family
      pad-count question at scale;
  (c) (11,9/10,8) gen_ymid_xhigh(Rx=24): ref +16B = one 4-pair pad run @~4550 + one at tail —
      width-step formula (pre_b10 += 2*((Rx+1)//4), validated Rx≤6) under-counts at Rx=24;
  (d) y-HIGH row (8..11,11,8) gen_seam_high_y(24,13,x_fwd_ghost)/gen_corner_middle(24)/
      gen_corner_hh(24,24): STRUCTURAL — ref inserts whole per-column decl groups
      (~129B each: val 0x5c + marker runs) got lacks + an 820B got-only block deleted +
      FG replacements — the documented-unvalidated ybfs branch / Ry=24 decl-splice truncation.
  PLAN: fix (a)→(b)→(c)→(d) one at a time against 3105 as oracle, gating each behind
  size thresholds to keep 604/604 + 50/50 green; then wire 'grid' displacement region +
  bumpy sine test (amplitude ≤±1.5 vox) using 3105 envelope/mcs.
  **SOLVED 16/16 BYTE-EXACT 2026-07-04 (commits 987f170/ef4c678/fba47d7/[a]/[b]/4aeba57).**
  All 4 failure classes closed; the "decl doubling" was a difflib artifact — real cause was gap
  shrinks + preval/length formulas at never-probed scale. Fixes:
  (a) plate FG clgap band 12≤ny<32 → 2 pairs + L term.
  (b) middle_x/seam_high: ny≥7 decl x-gap shrink + clgap band + pre −2/col (middle_x nxd−1;
      seam_high nxd, +2 tail).
  (c) ymid_xhigh T = 158−5Rx+(Rx≥6)+2·((Rx+1)//12).
  (d) NEW 14≤ny<32 band in gen_heightmap_unified (decl xgap −2 pairs, clgap −1, pre_b10 −4·nx,
      L −2/nx −4) → (8,11,8); same band in gen_middle_x + pre_nb −(4·nxd+2) + a max(Lnb,len(s))
      no-truncate guard (band was cutting the last FG group) + corner_middle Ltot −2 →
      (9/10,11,8); gen_corner_hh pre_b10 = _fg0(bd)−2 (derives from bd, inherits the band, ==
      old formula at validated sizes) + Ltot +2 band → (11,11,8).
  KEY LESSON: derive positions from the composed sub-plate (`_fg0(bd)−2`) instead of duplicate
  formulas — self-adjusts to bands, zero magic constants. Bands gated to keep the 33-row (ny≥32)
  families and all validated small-ny cases byte-identical. Single-point caveats: the exact band
  BOUNDS (11-13 lower, 32 upper) and the corner Ltot ±2 terms are pinned only at ny∈{25,26}/Rx=Ry=24.
  NEXT: wire 'grid' displacement region into du_mesh + bumpy sine test (amplitude ≤±1.5 vox)
  using 3105 envelope/mcs.

## Multi-region composition probe (2026-07-04)
- **tests/mesh_xy_tilt_0704_2019.blueprint** — displaced x=0+y=0 SURFACE CORNER: one tilted plane
  z=1−(2(x+2)+10(y+2))/84 over the 3079 footprint (all 25 corner lines distinct, 0..−48).
  gen_xy_from_mesh (new): gen_corner_hh(verts) for (8,8,8) + displaced plates through the
  y0-splice/x0-head recipes; flat-mesh reduction == gen_corner_xy blocky (selftest 10/10).
  Donor 3079, mcs 681/620/594/533. EXPECTED: ONE continuous plane, gently down toward +x,
  strongly down toward +y, deepest at (+2,+2); NO crack at x=0, y=0, or the corner. Any
  discontinuity localizes the offending chunk.
  **DEPLOYED AS EXPECTED 2026-07-04 — multi-region composition (4 octant chunks, 3 recipe
  families, one continuous displaced plane) hardware-proven.**
- **tests/mesh_xz_tilt_0704_2027.blueprint** — displaced x=0+z=0 corner (2947 shape/donor, ny=4):
  tilt dz=−(20(x+1)+4(y−10)), 15 distinct corners, 0..−56. gen_xz_from_mesh: vlist through the
  jittered/fwd-ghost z-degenerate corner chunks; −z chunks mirror +z offsets (3095 rule).
  EXPECTED: continuous plane, strong slope toward +x, gentle toward +y, deepest (+x, far-y),
  no crack at x=0. RENDERED PERFECTLY 2026-07-18.
- **tests/mesh_yz_tilt_0704_2027.blueprint** — displaced y=0+z=0 corner (3077 shape/donor, nx=3):
  tilt dz=−(6(x−10)+20(y+1)), 12 distinct corners, 0..−58. gen_yz_from_mesh. EXPECTED:
  continuous plane, gentle toward +x, strong toward +y, deepest (far-x, +y), no crack at y=0.
  (Both: flat-mesh reductions == blocky gen_corner_xz/yz; selftest 11/11.)
  **BOTH DEPLOYED AS EXPECTED 2026-07-04 — xz and yz displaced corners hardware-proven. EVERY
  probed carrier surface (plain/grid/x0/y0/z0/xy/xz/yz) now renders mesh displacement correctly.**

## 3-plane surface corner (2949 revisited 2026-07-04)
- **2949** (archive; 2×2×2 origin box, 1 vox/octant, 8 chunks) — 3-PLANE SURFACE CORNER SOLVED
  with the current toolkit (old attempt: 1/8). SIX octants = plain gen_seam_z_high/low bases at
  lx0/ly0∈{−1,31} with x_fwd_ghost/y_fwd_ghost per side. (8,7,7) = base + last-opener +2 (yz
  double-neg rule, WITHOUT 3077's layout shift — that shift is config-dependent). (7,7,7) = base
  + fg0−2 pad drop + last-opener +2. (8,8,8) = plain plate @(−1,−1,−1) with the bfs SPLIT LEAD
  UNSPLIT (pad pair moved before the opener), standard z c1-special, head−2/tail+2. NO jitters
  anywhere (x0/yz jitters are 2-plane artifacts). The "3-way y-interaction" that blocked the old
  attempt was the pre-B2 models, not DU. gen_corner_xyz coded; 8/8 byte-exact; suite 50/50.
  Minimal-box scope only (1 vox/octant); scaling unprobed.

## Archive / earlier exports (coords to backfill as confirmed)
Older referenced exports whose exact XYZ should be added here when re-confirmed:
2494 (solid interior, chunk (2,2,2)); 2906/2910/2935/2937 (z=0 seams, base position
UNKNOWN — do not byte-match blind); 2952/2954/2956 (staircases descent/peak/valley);
2959/2961/2963/2965/2967/2969/2971 (relief profiles); 2941/2943 (x=0 / y=0 seams).
- **tests/grid_centered_dome_0705.blueprint** (2026-07-05) — negative-octant bumpy landscape validation:
  centered Gaussian dome spanning ALL FOUR octants across x=0 AND y=0 (donor 3114, 23 gen_terrain_grid
  chunks + 2 flat-degenerate Rx=1 corner). **DEPLOYED CORRECTLY 2026-07-05 — negative-octant landscape
  HARDWARE-PROVEN: octant-agnostic interiors + ordinary x=0/y=0 boundaries + ny=32 edges all render as
  one continuous smooth dome. Full-M-core landscape = same op at core scale + a full-core flat donor.**
- **tests/fullcore_dome_0705.blueprint** (2026-07-05) — FULL M-CORE LANDSCAPE: 1-vox dome over the
  interior 6×6 (192×192, all 4 octants across x=0/y=0, seamless dome→0 at border) + flat border ring
  (donor 3151's real chunks). **DEPLOYED SUCCESSFULLY 2026-07-05 — full-M-core bumpy landscape
  HARDWARE-PROVEN at 8×8-chunk scale. Landscape capability COMPLETE (flat-bordered); full edge-to-edge
  bumpiness needs only the ny=31/Rx=30 border grind (mechanical).**
- **tests/fullcore_edge_dome_0705.blueprint** (2026-07-05) — EDGE-TO-EDGE bumpy full M-core: centered
  dome (sigma70) with displacement all the way to the edges; 61 bumpy chunks (all edge rows/columns
  now generate correctly) + 3 flat structural corners (NW/SE/NE, dome~0 there → seamless). Donor 3151.
  **DEPLOYED 2026-07-05 — edge-to-edge bumpy full M-core rendered correctly; the 1-voxel empty border
  is the donor's deliberate inset (3151), NOT a defect. All edge rows/columns bumpy, 3 corners flat &
  seamless. LANDSCAPE ARC FULLY DONE (edges finished; 3 extreme-corner chunks deferred, low priority).**
  Edge fixes: north row ny=31 (gen_corner_middle(30) ybfs-skip), east col Rx=30 (gen_ymid_xhigh T+1),
  ny=31 flush in gen_middle_x. 61/64 structural byte-exact (25 differ only by DU's flat bevel, which
  our displacement overwrites). RENDERED PERFECTLY 2026-07-18.
- **tests/lens_capsule_0707.blueprint** (2026-07-07) — FIRST GENERATED CLOSED SHAPE (du_dense.py):
  4×4×4 solid carved to a lens/capsule (domed top peak +72, domed bottom −64, +6 +x tilt, flat
  sides). Plain donor recovered by zeroing 3162's displacements (no extra build). **DEPLOYED &
  RENDERED CLEAN 2026-07-07 — smooth closed surface, no cracks; user read back all 25 grid points =
  byte-exact match. Two-surface dense generation hardware-proven.** NEXT: rounded sides (probe 4).
- **tests/barrel_x_0707.blueprint** (2026-07-07) — INCREMENT A: du_dense ±X faces rounded (barrel bulge),
  flat top/bottom/±Y. **DEPLOYED PERFECTLY** — generated full-form side groups accepted by DU.
- **tests/gem_0707.blueprint** (2026-07-07) — INCREMENT B: 4×4×4 inflated to a near-sphere via one
  radial field (du_dense.apply_shape) — all 6 faces + edges + corners. **DEPLOYED — smooth near-sphere,
  no cracks. COMPLETE single-chunk closed-surface generator hardware-proven (incl ±Y faces).**
| 3178 | 8x4x4 solid box crossing chunk boundary (multi-chunk probe 6) | X game 27.5-34.5, Y/Z 8.5-11.5 | (8,8,8)+(9,8,8) | Dense seam: continued face uncapped (interior BT plane), 1-plane overlap both chunks, seam opener val 67 vs 63 outer/55 interior. |
| 3179 | 3178 box + top-row arc across seam (multi-chunk probe 7) | same as 3178 | (8,8,8)+(9,8,8) | SEAM AGREEMENT: overlap planes x31/32/33 byte-identical +32/48/36 in both chunks; 3-plane overlap; surface continuous across seam. |
- **tests/mc_dome_0707.blueprint** (2026-07-07) — FIRST GENERATED MULTI-CHUNK closed surface: domed-top box spanning chunk (8,8,8)/(9,8,8) seam, one dome field across both chunks, overlap byte-identical. **DEPLOYED AS EXPECTED — continuous across seam, no crack. Multi-chunk generation proven.**
- **tests/ellipsoid_gentle_0707.blueprint** (2026-07-07) — 3172 ball gently squashed 82% in z (coord de-risk). DEPLOYED: clean oblate ellipsoid, slightly faceted. Confirms coordinate extraction sound; earlier failure was overshoot not coords.
| 3185 | ~24-vox solid ball crossing Y chunk boundary (bigger-ball donor) | ~game(32.5,16.5,16.5), crosses Y=32.5 | (8,8,8)+(8,9,8) | Parses to 25 X-planes/chunk (marker-region fix: group regions >100B). Y-seam column mapping puzzle (mirror/double-max) unresolved. |
| 3187 | 4x8x4 solid box crossing Y boundary (Y-seam probe 8) | X/Z game 8.5-11.5, Y 27.5-34.5 | (8,8,8)+(8,9,8) | Y-seam = X-seam on column axis: 3-col overlap (Y31/32/33), uncapped continued faces, col->Y=ylo+c. |
| 3189 | 24-vox sphere @ (32,16,16), crosses X | center 32,16,16 | (8,8,8)+(9,8,8) | Correct X-crossing sphere donor. |
| 3191 | 20-vox SOLID sphere @ (16,16,16), single chunk | center 16,16,16 | (8,8,8) | Clean known-solid donor. 21 X-planes, h up to ~24 center. Parser tall-column(h>17) Top-detect bug found. |
| 3197 | Opener-CV probe P1: uniform solid 6x6x4 box | x8..13 y8..13 z8..11 | (8,8,8) | Footprint probe. interior opener=21 -> pinned −35·ncols term. |
| 3199 | Opener-CV probe P2: ascending Y-staircase h=[2,4,6,8,10], 3 planes x 5 cols | x8..10 y8..12 z8+ | (8,8,8) | interior opener=50, continuation gradient +2. |
| 3201 | Opener-CV probe P3: descending Y-staircase h=[10,8,6,4,2] | x8..10 y8..12 z8+ | (8,8,8) | interior opener=58, continuation gradient −2. Cracked opener CV + gradient law. |
| 3203 | Opener-CV probe P4: non-monotonic Y-profile h=[2,10,4,8,6], 2 planes | x8..9 y8..12 z8+ | (8,8,8) | interior opener=54 -> opener uses h_yHI. SOLVED marker region = circular delta val[i]=34−h[i−1]. |
| 3205 | Closeout P5a: uniform 4×4×6 box (h6) | x8..11 y8..11 z8..13 | (8,8,8) | bnd_op=65 (NOT 69) -> 57+2h dead. interior opener=89=235−140−6 ✓. |
| 3207 | Closeout P5b: staircase [6,8,10,12] no-h4, 2 planes | x8..9 y8..11 z8+ | (8,8,8) | bnd_op=65 -> bnd_op is positional not height. |
| 3209 | Closeout P6a: uniform 3×7×4 box (nc7) | x8..10 y8..14 z8..11 | (8,8,8) | group gap=6, marker gap=6. grpspan formula exact. |
| 3211 | Closeout P6b: uniform 3×8×4 box (nc8) | x8..10 y8..15 z8..11 | (8,8,8) | group gap=6, marker gap=6. |
| 3213 | Closeout P7: 4×4×4 box SHIFTED +10 all axes | x18..21 y18..21 z18..21 | (8,8,8) | POSITION: content identical to 3162; only lead(99→197)+bnd_op(65→131) shift. |
| 3215 | Position S1: 4×4×4 shift X only +10 | x18..21 y8..11 z8..11 | (8,8,8) | lead=195 bnd_op=27. |
| 3217 | Position S2: 4×4×4 shift Y only +10 | x8..11 y18..21 z8..11 | (8,8,8) | lead=101 bnd_op=159. |
| 3219 | Position S3: 4×4×4 shift Z only +10 | x8..11 y8..11 z18..21 | (8,8,8) | lead=99 bnd_op=75. Position law additive; z solved (bnd +z, lead 0). |
- **tests/mc_lens_0707.blueprint** (2026-07-07) — multi-chunk LENS (domed top+bottom) across X-seam from box donor. **DEPLOYED AS EXPECTED — multi-chunk CLOSED-shape generation proven (two surfaces continuous across chunk seam).**
- **tests/ellipsoid2_0707.blueprint** (2026-07-07) — 3191 gentle 80%% z-squash, full parse. DEPLOYED: equator (central 8 Z) SMOOTH (core BT extraction validated), top/bottom ~5 Z-rows blocky (run>0 cap-vertex placement is the pinpointed remaining gap).
| 3353 | M2 probe B12: flat 8x12x4 box (nx8 nc12) | x8..15 y8..19 z8..11 | (8,8,8) | Pinned large-nc layout: pad=246-10*nx holds at nc12, gap band 7..14 -> 6. |
| 3355 | M2 probe B16: flat 12x16x4 box (nx12 nc16) | x8..19 y8..23 z8..11 | (8,8,8) | Gap band >=16 -> 4 confirmed; pad line holds. M2 layout generative nc4-nc16. |
| 3357 | OPD opener-discriminator: planes [2,4,6,8],[8,8,8,8],[6,6,6,6] | x8..10 y8..11 z8+ | (8,8,8) | Y-lo opener dispatch confirmed (desc off full-width = max-K). |
| 3359 | OPD2: planes [2,4,6,4],[8,8,8,8],[6,6,6,6] | x8..10 y8..11 z8+ | (8,8,8) | Equal-nc flat descent uses OWN-PAIR form. du_general 14/14. |
| 3361 | OVH1 overhang probe: 3x3 h2 base + floating bar (gap2,h2) | base x8..10 y8..10 z8..9, bar x8..10 y9 z12..13 | (8,8,8) | Two-interval column = extra marker (val igap-1) + extra group tokens (val igap-2, run h_up) in max-window walls; column t := full span. |
| 3363 | OVH2 overhang probe: same base, bar gap3 h3 | base x8..10 y8..10 z8..9, bar x8..10 y9 z13..15 | (8,8,8) | Pinned slopes of overhang val laws. CAVEAT: gap AND h_up co-varied -> igap-vs-h_up still confounded (needs OVH3 gap2/h3). du_general intervals: 16/16 byte-exact. |
- **tests/deployment11_mc_ramp.blueprint** (2026-07-11) — DEPLOYMENT 11: novel X-crossing stepped ramp from build_multichunk (M3), 3178 envelope. Voxels x27..34 y8..11, z from 8, heights per X-plane: x27-28 h2 (z8-9), x29-31 h3 (z8-10), x32-34 h4 (z8-11); height step exactly at the chunk seam x32. RENDERED PERFECTLY 2026-07-18.
- **tests/deployment11b_mc_ramp.blueprint** (2026-07-11) — Deployment 11 RETRY. 11a (bp 3364) FAILED: 'Deserializing invalid vertex' both chunks = plateau-byte/tail mismatch (ramp plateaus give marker b2=3; du_assemble MAT_TAIL said 2 — the OCC3 3325 lesson re-hit via the multi-chunk path). du_assemble.encode_voxel_b64 now derives b2 from the scan and patches the tail per chunk. Same voxels as 11: x27..34 y8..11, h2(x27-28)/h3(x29-31)/h4(x32-34) from z8, step at seam x32. AWAITING DEPLOY. If it STILL fails: suspect the b2 plateau law itself for edge-touching plateaus (chunk2's plateau 32-34 ends at the last plane; OCC3 validated interior-only).
- **tests/deployment11c_mc_ramp.blueprint** (2026-07-11) — Deployment 11 RETRY 2. 11b (bp 3365) failed identically (invalid vertex both chunks, voxels in build mode then client crash = OCC3 b2-over-read signature). Assembly path EXONERATED offline (rebuilt donor-3178 bodies BYTE-IDENTICAL). Root cause: b2 plateau law over-generalized — plateau counts FOOTPRINT (column-set) runs only; height plateaus don't count (all constant-footprint donors have b2=2 incl E1/stairs; OCC3's 3 was a footprint plateau). Ramp b2 now 2. Same voxels: x27..34 y8..11, h2(x27-28)/h3(x29-31)/h4(x32-34) from z8. AWAITING DEPLOY.
| 3367 | PLT-MC donor: in-game stepped ramp = exact Deployment 11 shape | x27..34 y8..11 base z8, h2(x27-28)/h3(x29-31)/h4(x32-34) | (8,8,8)+(9,8,8) | ONE byte off per chunk vs generation -> flat vol-tie Y-lo opener = 35*mean + MAX bottom-interval col top - zfirst (owner-by-half branch was wrong; coincidental on 3252). b2=2 confirmed for height plateaus (footprint-only law). |
- **tests/deployment11d_mc_ramp.blueprint** (2026-07-11) — Deployment 11 RETRY 3: tie-dispatch fix; voxel bodies now BYTE-IDENTICAL to donor 3367's. Same voxels: x27..34 y8..11, h2/h3/h4 steps from z8. AWAITING DEPLOY (should render identically to 3367's construct).
- **Deployment 11d DEPLOYED & RENDERED PERFECTLY (2026-07-11)** — X-crossing stepped ramp across the chunk seam. M3 MULTI-CHUNK PIPELINE HARDWARE-PROVEN END-TO-END: global occupancy -> build_multichunk (split + seam forms + position laws) -> du_assemble -> deploy.
| 3372 | OVH3 probe: 3x3 h2 base + bar gap2/h3 | base x8..10 y8..10 z8..9, bar x8..10 y9 z12..14 | (8,8,8) | GAP LAW CONFIRMED: extra marker val=igap-1 (1, not h_up-1=2); group extra val=igap-2 (0). Implemented readings correct, no code change. |
| 3374 | OVH4 probe: 3x3 h2 base + 2-wide slab | base x8..10 y8..10 z8..9, slab x8..10 y8..9 z12..13 | (8,8,8) | LAYERED WALL MODEL: every wall = [lower tokens][upper-layer tokens]; both-sides uppers PAIR into (B_up,T_up) with spread runs (second two-surface deck); one-side = single (igap-2,h_up); boundary planes keep single all-wall upper tokens; opener run = bottom h (not span). Window model was byte-equivalent for single doubled cols only. Layout fully standard. |
| 3376 | ZC1 probe: 4x4x8 box crossing z=32 | x8..11 y8..11 z27..34 | (8,8,8)+(8,8,9) | Z-SPLIT RULES: markers carry to S / from S-2 like X/Y; LOW-side GROUP region uses z from S-1 (h-runs 4, final 33-4, opener F w/ zfirst=-1, -X grp opener = bnd law @ z=-1 +19). bnd_op law holds in z incl negative local. OPEN: z-cut interior walls collapse pairs to (33,0) tokens + one 27 outlier -- uniform box can't discriminate; needs ZC2. |
| 3378 | ZC2 probe: mixed closed/crossing z-columns | x8..10 y8..11, z27 base, tops y8:30 y9:33 y10:35 y11:30 | (8,8,8)+(8,8,9) | Z-CUT GRAMMAR SOLVED: B/T are SURFACE tokens (B unless both cols bottom-cut, T unless both top-cut); B/Y-hi val -> 33 when lag-window all present-and-top-cut; T val -> 33 when both bottom-cut; group-absent cols (below S-1) = zero heights/edge collapse/anchors -1. Everything else standard. build_multichunk now splits X, Y AND Z. Reg 28/28. Also pinned: identical-plane vol ties = own-pair form (maxT only for non-identical ties, 3252). |
| 3380 | XY1 probe: box crossing X=32 AND Y=32 (4 chunks) | x27..34 y27..34 z8..11 | (8,8,8)+(9,8,8)+(8,9,8)+(9,9,8) | MULTI-AXIS COMPOSITION PROVEN: corner seam-line opener = bnd_law-36+35 (adjustments ADD); marker opener = bnd law at (-2,-2); layout hooks DON'T stack (+10 only); new hook xseam+yopen grp_off-2; lead law x<8 nonzero-yterm +2. |
| 3382 | X3 probe: 40-voxel beam crossing x=32 AND x=64 (3 chunks) | x27..66 y8..11 z8..11 | (8,8,8)+(9,8,8)+(10,8,8) | Middle chunk xseam_lo+xopen_hi composes as coded (35 marker + 35 group planes, no caps). premat = pad-(lead-99) exact (incl 0); negative formula lands at 4 (provisional). Reg 35/35. |
- **tests/deployment12_mc_dome.blueprint** (2026-07-11) — DEPLOYMENT 12 (item 3: smoothing across seams): base box x27..34 y8..11 z8..10 (h3), ALL top-surface vertices (z=11) deflected onto the parabola Z = 11 - (x-31)^2/22 via build_multichunk smooth_fn (global-coords wrapper added), 3178 envelope. Expect a smooth ridge peaking at x=31, CONTINUOUS across the x=32 seam. AWAITING DEPLOY.
- **tests/deployment12b_mc_dome.blueprint** (2026-07-11) — Deployment 12 RETRY. 12a (bp 3383) failed 'Reading too far' both chunks. Offline shakedown via NEW smooth round-trip suite (test_smooth_roundtrip.py: 3191 + BOTH 3189 seam chunks now regenerate BYTE-EXACT from extracted donor displacement fields) found & fixed: (1) b2 plateau law final form = fully-identical-plane runs bounded by strictly narrower planes (3191's six nc20 planes differ in heights -> b2=2); (2) GROUP gap bands sit LOWER than marker bands (<=10:8, <=24:6, <=40:4, else 2); (3) pad kink re-keyed nx>=20 (+6); (4) ROOT CAUSE of 12a: smooth nominals passed the group-line INDEX as the x coord (dome evaluated at x=0..8 instead of 27..35 -> all top vertices clamped to -100 junk). Same shape as 12: x27..34 y8..11 z8..10 + top parabola Z=11-(x-31)^2/22. AWAITING DEPLOY.
- **tests/deployment12c_mc_dome_inplace.blueprint** (2026-07-12) — BISECT after 12b (bp 3388) failed same as 12a ('Reading too far' both chunks; coordinate fix was real but not the structural cause). 12c = SAME plain du_general base (x27..34 y8..11 z8..10) + dome applied ONLY as IN-PLACE run-0 T z-slot writes (du_dense mechanism, mc_dome-proven; ZERO expanded tokens; 18+12 writes, dome only on interior top vertices so edges stay flat). If 12c renders -> expanded-token emission (or its interplay with layout) is the killer; if 12c fails -> plain-base or in-place at this shape/position. AWAITING DEPLOY.
| 3396 | PLT-H3 donor: uniform h3 box (in-game built) | x27..34 y8..11 z8..10 | (8,8,8)+(9,8,8) | **MY GENERATION BYTE-EXACT vs donor — content was never wrong. Donor mcs = 756/642 vs 3178's 755/641: THE ENTIRE 12-FAMILY FAILURE WAS BORROWED WRONG mc ('mc is moot' is FALSE — shape-dependent CV; 11d survived because ramp mc == h4-box mc coincidentally). 'Reading too far' = parser sizes a read from the mat byte.** |
- **tests/deployment12e_mc_dome.blueprint** (2026-07-12) — smoothed dome rebuilt with TRUE mcs 756/642. Same shape: x27..34 y8..11 z8..10, top parabola Z=11-(x-31)^2/22 across the seam. AWAITING DEPLOY. If it fails (mc law may depend on smoothing/groups, not just occupancy): fallback 12f = plain h3 box w/ 756/642 (byte-identical to 3396) must work.
- **Deployment 12e DEPLOYED & RENDERED PERFECTLY (2026-07-12)** — smoothed parabolic dome continuous across the x=32 seam (x27..34 y8..11 z8..10 + top deflection). SMOOTHING-ACROSS-SEAMS HARDWARE-PROVEN. Root cause of 12a-12d: borrowed mc (must match shape).
| 3400 | P1/CYS: stepped dome crossing y=32 | x8..10 y27..36 z8+, tops 9,10,11,12,13,13,12,11,10,9 | (8,8,8)+(8,9,8) | Curved-Y-seam donor; DECODE IN PROGRESS (real law diffs both chunks). **2026-07-17: item 14 SOLVED -- STRUCT-EXACT (stale dy+42 opener segs + reversed tail counts = build-state; 3446 same shape is byte-exact).** |
| 3402 | P2/ZC3: closed col in high z-chunk | x8..10; y8:27..30, y9:27..35, y10:33..36, y11:27..30 | (8,8,8)+(8,8,9) | DECODED (partial): above-S cols in LOW chunk = absent-in-markers (+35 on next continuation, F counts y-SPAN, group edge-walls around them); in HIGH chunk = overhang grammar (zero-height base at S-1 anchor + interval as upper layer; wall windows use span-from-anchor; upper tokens igap-2 form). One val TBD: mixed-wall T=1 vs law 2. mc law held both chunks. |
| 3404 | P3/ZOV: cut column + overhang | x8..10; y8,y10: z28..30; y9: [z28..33, z36..38] | pending decode | |
| 3406 | P4/OVH5: slab gap2/h3 | base x8..10 y8..10 z8..9 + slab y8..9 z12..14 | (8,8,8) | **BYTE-EXACT first shot: paired-form vals (B_up=igap-2, T_up=h_up-2) CONFIRMED. Item 7 CLOSED, no code change.** |
| 3408-3426 | P5-P14 sweeps (boxes; see spec) | x/y/nc/nx sweep | (8,8,8) | ALL BYTE-EXACT after law updates: mc slopes are INTEGER +55x/-35y (ownership bonuses + //5 slopes were aliasing artifacts — law now dead simple); lead x-term = period-9 table 86*(x//9)+base[x%9] (resolves (20,13)->215 exactly; base cells 2,5,6,7 interpolated); y-term +4-shifted for positives; nc5-nx4 pad kink REMOVED (was a y-position effect: nx4 pad -2 at y'%15 in {4,5}); pad cells (nx4,nc9)=204, (nx3,nc15)=212; nc15 band edges confirmed. Reg = 49 chunk-tests byte-exact. |
| 3428 | CYS-A curved Y-seam nx4 | x8..11 y27..36 z8+, tops 9,10,11,12,13,13,12,11,10,9 | (8,8,8)+(8,9,8) | Curved-Y-seam nx-sweep (with 3400 nx3, 3430 nx2). **2026-07-17: STRUCT-EXACT (stale payload, 3400 family).** |
| 3430 | CYS-B curved Y-seam nx2 | x8..9 y27..36 z8+ (same profile) | (8,8,8)+(8,9,8) | nx2 curved: yseam boundary MERGES (like flat); reveals nx-dependent boundary content. **2026-07-17: BYTE-EXACT.** |
| 3432 | CYS-RAMP: monotonic curved Y-crossing (deconfounds phantom vs neighbour) | x8..10 y27..36 z8+, heights 2,3,4,5,6,7,8,9,10,11 (tops z9..z18) | (8,8,8)+(8,9,8) | Deconfounded yopen -X closing wall: it's a +Y CONTINUATION token (run=h(seam col)), present unless seam==prev-col (plateau merge, 3400); +X ALWAYS emits it. Token COUNT law solved; continuation VALUE law still open (1a ramp vs 1b plateau); yseam boundary still open. **2026-07-17: BYTE-EXACT (item 14 solved).** |
| 3434 | CYS-P1 plateau grid | x8..10 y27..36 z8+, heights 2,5,5,5,6,7,9,9,9,11 | (8,8,8)+(8,9,8) | 5-donor yopen grid (2026-07-12; rows backfilled 2026-07-17). BYTE-EXACT 2026-07-17. |
| 3436 | CYS-D1 descending | x8..10 y27..36 z8+, heights 2,4,6,8,10,9,7,5,3,2 | (8,8,8)+(8,9,8) | Descending-into-high-chunk variant. STRUCT-EXACT 2026-07-17 (stale +X dy payload + doubled +14 tail = build-state). |
| 3438 | CYS-A4 ramp nx4 | x8..11 y27..36 z8+, heights 2,3,4,5,6,7,8,9,10,11 | (8,8,8)+(8,9,8) | 3432's shape at nx4. BYTE-EXACT 2026-07-17 with yseam_payload=False (exported PLAIN opener/interior-T -- proves payload nondeterminism). |
| 3442 | CYS-A2 ramp nx2 | x8..9 y27..36 z8+, heights 2,3,4,5,6,7,8,9,10,11 | (8,8,8)+(8,9,8) | 3432's shape at nx2. BYTE-EXACT 2026-07-17 (incl nx2 yopen pad cell). |
| 3444 | CYS-POS | x18..20 y27..36 z8+, tops 9,10,11,12,13,13,12,11,10,9 | (8,8,8)+(8,9,8) | 3400's shape at x18. BYTE-EXACT 2026-07-17 (pinned the x-PERIODIC yseam grp hook: absent at x18). |
| 3446 | DROP1 | x8..10 y27..36 z8+, heights 2,3,4,5,6,6,5,4,3,2 (== 3400's SHAPE) | (8,8,8)+(8,9,8) | ★ SAME SHAPE as 3400, DIFFERENT payload bytes -> proved displacement payload = BUILD STATE, not shape law. BYTE-EXACT 2026-07-17 (canonical fresh form). |
| 3447 | DROP2 | x8..10 y27..36 z8+, heights 2,3,4,5,6,6,4,3,2,2 | (8,8,8)+(8,9,8) | DROP chain (incremental edits -> stale low tails). HIGH byte-exact; LOW struct-exact 2026-07-17. |
| 3448 | DROP3 | x8..10 y27..36 z8+, heights 2,3,4,5,6,6,3,2,2,2 | (8,8,8)+(8,9,8) | Same: HIGH byte-exact; LOW struct-exact (stale tail). |
| 3450 | STEP | x8..10 y27..36 z8+, heights 2,4,6,8,8,7,6,4,2,1 | (8,8,8)+(8,9,8) | BYTE-EXACT 2026-07-17 with yseam_payload=False (plain opener/interior-T; tail expanded +14@hs-1 canonical). |
| 3452 | TAIL-POS | x18..20 y27..36 z8+, tops 9,10,11,12,13,13,12,11,10,9 | (8,8,8)+(8,9,8) | 3444's twin. BYTE-EXACT 2026-07-17. |
| 3454 | DROP4 | x8..10 y27..36 z8+, heights 2,3,4,5,6,6,2,2,2,2 | (8,8,8)+(8,9,8) | HIGH byte-exact; LOW struct-exact (stale tail). |
| 3455 | DROP5 h1-tail | x8..10 y27..36 z8+, heights 2,3,4,5,6,6,1,1,1,1 | (8,8,8)+(8,9,8) | h=1 cols beyond the seam. Pinned: yseam chunks count h1 cols FULL in marker gaps (h1-exclusion is non-seam). HIGH byte-exact; LOW struct-exact. |
| 3457 | HSEAM8 3-plateau | x8..10 y27..36 z8+, heights 2,4,6,8,8,8,7,4,2,1 | (8,8,8)+(8,9,8) | Flat seam-triple -> plain opener law confirmed. HIGH byte-exact; LOW struct-exact (tail = 3450's + count-extension: PROOF of incremental-edit staleness). |
| 3459 | DEEP | x8..10 y27..36 z8+, heights 2,3,4,5,6,6,5,2,2,2 | (8,8,8)+(8,9,8) | y34-locality check. BYTE-EXACT 2026-07-17. |
- **tests/deployment13_dome.blueprint** (2026-07-12) — DEPLOYMENT 13 (ARC #13 first pipeline shape): NOVEL solid dome (circular footprint radius 8, domed top h0..6) built entirely through the obj_pipeline back-half: voxel occupancy {(x,y,z)} -> to_columns -> build_multichunk(mc=None, law) -> build_blueprint_own (3191 envelope, compute_lod_set 19-chunk). Single chunk (8,8,8), voxels x9..25 y9..25 z8..14, 1007 voxels/197 cols. mc=675 (law). Combines NARROWING footprint + CURVED top (novel combo). Pipeline byte-exact vs 5 donors (X/Y/Z boxes + E1). AWAITING DEPLOY.
- **DEPLOYMENT 13 (bp 3463) FAILED** 'Deserializing invalid vertex' — ROOT CAUSE: HEIGHT-1 columns (dome edge) -> Top token = min(corners)-2 = -1 = 0xff = invalid vertex. Donors are all h>=2 so untested. FIX: obj_pipeline.to_columns(min_thickness=2) grows every column to >=2 voxels (legit for a deflection base). 'smooth sphere briefly appeared' = stale 3191-template LOD showing through the failed h3.
- **tests/deployment13c_dome_r5.blueprint** (2026-07-13) — DEPLOYMENT 13c: radius-5 dome (nc<=11, height<=4, min-thick 2), SAFE opener regime (no group vals >=0xe0). Novel curved+narrowing shape via full pipeline. mc from law. AWAITING DEPLOY (proves h=1 fix + pipeline).
- **tests/deployment13b_dome_r8.blueprint** (2026-07-13) — radius-8 dome (nc13); min-thick 2 removes h=1, BUT large-nc varying-height openers wrap to 0xfe/0xfc (else-branch 35*mean(nc) term, untested regime; no donor for nc>11 varying-height). Deploy only after 13c confirms base pipeline.
| 3466 | NCV1 narrowing+curved probe | x8..10 diamond dome | (8,8,8) | BYTE-EXACT (narrowing+curved law correct). |
| 3468 | NCV2 nc1 tips + curved | x8..10 | (8,8,8) | BYTE-EXACT (nc1+curved ok). |
| 3470 | NCV3 nc7 curved | x8..10 | (8,8,8) | BYTE-EXACT (nc7 + 0xf3 opener valid). |
| 3473 | NCV4 col-set run + narrowing | x8..11 | (8,8,8) | BYTE-EXACT (isolated col-set run ok). |
| 3475 | DOMER3 radius-3 dome (the failing shape) | x13..19 y13..19 | (8,8,8) | ONE BYTE OFF -> cracked the bug: DESCENDING equal-nc col-set run OFF A WIDER PEAK uses shifted-pair F=_F(L), not own-pair. G5 opener f3 not 15. Gated on ncp(L-1)>ncp(L) (OPD2 descends w/o peak -> own-pair). |
- **tests/deployment13e_dome_r5.blueprint** (2026-07-13) — DEPLOYMENT 13e: radius-5 dome rebuilt with the descending-col-set-run fix. No invalid tokens. mc=745. Deployments 13/13c/13d all failed on this exact bug (x16 nc11 peak -> descending run x17-19). AWAITING DEPLOY.
| 3483 | DOMER4 radius-4 dome (the large-nc test) | x12..20 y12..20 | (8,8,8) | GROUP CONTENT ALL BYTE-EXACT (col-set-run + mc fixes work!). Only diff was PAD: maxnc9 uses 239-9*nx (slope-9 band nc7-11), not 246-10*nx. mc nc-term=(nc_last+max)/2 confirmed. Dome group encoding SOLVED; remaining = pad extrapolation nc10/11. |
- **tests/deployment13g_dome_r4.blueprint** — radius-4 dome, BYTE-EXACT to DOMER4 donor (will render). AWAITING DEPLOY (confirms novel curved+narrowing dome end-to-end).
- **tests/deployment13h_dome_r5.blueprint** — radius-5 dome, maxnc11 pad EXTRAPOLATED (base 237). Group content correct; pad is a guess. Deploy after 13g.
- **DEPLOYMENT 13g + 13h RENDERED PERFECTLY (2026-07-13)** — radius-4 (maxnc9) AND radius-5 (maxnc11) domes both import+render clean. ARC #13 CORE PROVEN: voxel occupancy -> to_columns -> build_multichunk -> deploy renders novel curved+narrowing domes. maxnc11 extrapolated pad (base 237) CONFIRMED correct by 13h. The 8-deploy dome saga is CLOSED.

## 2026-07-14 session — multi-chunk verification, layout laws, cavity/window/sealed arcs

| BP | What | Coords (game .5 = voxel index) | Chunks | Result |
|----|------|-------------------------------|--------|--------|
| 3493 | X-seam nc8 box (Deployment-14 shape hand-built) | x28.5-39.5 y10.5-17.5 z8.5-11.5 | (8,8,8)+(9,8,8) | Cracked 2 laws: _LEAD cell +1 (→ closed-form lead x-law later) + pad flat/curved split maxnc7/8. BYTE-EXACT after. |
| 3497 | A: lead cell2 @x0=19 (nx6 nc4) | x19.5-24.5 y8.5-11.5 z20.5-23.5 | (8,8,8) | Lead 203 (killed cell2=20 table) + exposed grp_off+2 anomaly (nx6 pocket, UNRESOLVED). |
| 3500 | B: flat nx8 nc8 | x12.5-19.5 y13.5-20.5 z8.5-11.5 | (8,8,8) | BYTE-EXACT — pad flat/curved split CONFIRMED. |
| 3502/3504/3506 | S1-S3 lead sweep x0=16/17/18 (nx4 nc4 z8) | x{16,17,18}.5+3 y8.5-11.5 z8.5-11.5 | (8,8,8) | Consecutive run 16-21 → LEAD X-LAW xt=10xp-2·ceil(xp/5) (+2 xp1,2). All 11 pts exact. |
| 3508/3510 | C/D grp_off gap probes (nx8/nx5) | x20.5+8 y24.5-27.5 z12.5-15.5 / x9.5+5 y18.5-21.5 z24.5-27.5 | (8,8,8) | Both resid 0 → killed max(0,nx-maxnc) rule. |
| 3512/3514/3516/3518 | E/F/G/H nx6 isolation grid (x9/x19 × z8/z20) | nx6 nc4 boxes | (8,8,8) | Grid: x9→pad+2 (z-indep); x19,z20→grp_off+2; x19,z8 CLEAN. Tangled nx6×x0×z pocket — DEFERRED, guarded (nx==6 flag). |
| 3520-3534 | YA-YC + Y1-Y5 lead y-sweep (nx3! boxes) | x8.5-10.5 y varies z8.5-11.5 | (8,8,8) | Sweep was nx3-CONTAMINATED (nx3 has own y-transitions). Old y-law 2*((yp+4)//9) CONFIRMED for nx>=4. |
| 3536 | A: square tube 5x5, 1x1 hole | x8.5-12.5 y8.5-12.5 z8.5-11.5, hole (10,10) | (8,8,8) | Cracked SPAN principle (holes counted in y-span; +35/absent marker). BYTE-EXACT. |
| 3538/3540/3542 | CB/CC/CD: 2x2 hole, off-center, 1x2 slot | 4x4 & 5x5 tubes z8.5-11.5 | (8,8,8) | All BYTE-EXACT (+X-boundary span + void-exit wall + both-absent skip). |
| 3544/3546 | VE1 (2x3 hole) / VE2 (2x2 h5) | x8.5-11.5 y8.5-13.5 / 4x4 z8.5-12.5 | (8,8,8) | void-exit = 33-h+35*(w-1); ncg gap-band uses span. BYTE-EXACT. |
| 3548 | SB: sealed hollow 5^3 shell (1-THICK walls) | x/y/z 8.5-12.5, core 3^3 hollow | (8,8,8) | h=1 GOLDMINE: markers fine (h-1=0, ig-1 law); group = all-singles edge mode (h=1 arc, OPEN). Shape unsupported (1-thick). |
| 3550/3552/3554/3556 | PW1/W2/W4/W5 windows (1x2, 1x3, 2-wide, 3-deep wall) | walls y8.5-9.5(-10.5) x8.5-12.5 | (8,8,8) | WINDOW grammar: WVOID + interval-chain + interior overhang. All BYTE-EXACT. |
| 3559/3561/3563/3565 | MW1-MW4': two windows / stacked / 3-wide / diff-z | walls x8.5-12.5 | (8,8,8) | Region-based WVOID + chain VALUE law (h_k-2, void_h). All BYTE-EXACT. |
| 3567/3569 | SC1 solid 5^3 / SC2 sealed 7^3 shell 2-thick | x/y/z 8.5-12.5 / 8.5-14.5 core 10.5-12.5 | (8,8,8) | SEALED CAVITY = window chain DIRECTION-SYMMETRIC (Y-face rule). Both BYTE-EXACT. |
| 3571/3573 | SC3 non-cubic cavity / SC4 two cavities | 8x7x6 box core 4x2x2 / 10x6x6 box 2 cores | (8,8,8) | SC3 exact; SC4 → pad nx-kink discovery. |
| 3575/3577 | SC5 solid nx10 / SC6 one cavity | x8.5-17.5 y8.5-13.5 z8.5-13.5 | (8,8,8) | PAD NX-KINK: +2*((nx-5)//5) when nx>=10 & nx>=maxnc & no seam (B16 exempt nx<nc; subsumes old nx>=20+6). All BYTE-EXACT. Reg=76. |
| 3579/3581/3583 | H1 plate / H2 x-step / H3 y-step (h=1 isolation) | 4x4 @z8: h1 plate; x8-9 h2+x10-11 h1; y8-9 h2+y10-11 h1 | (8,8,8) | h=1 GROUP MODE: wall touching h=1 col = single edge-form (bval, max h); markers/openers/closes unchanged. All BYTE-EXACT. |
| 3585 | H4 wedge staircase h3/h2/h1 | x8-9 z8-10, x10-11 z8-9, x12-13 z8 (y8-11) | (8,8,8) | SHADOW-OPENER generalization: identical pair after taller plane = _F(L). BYTE-EXACT. |
| 3586 | H5 far plate | x14.5-17.5 y14.5-17.5 z20.5 | (8,8,8) | h=1 content ALL correct; pad -2 = deferred single-chunk ±2 pocket (y'6/z20). Not in reg. |
| 3588 | H6 1-tall gap (PW2 shape) | wall x8.5-12.5 y8.5-9.5 z8.5-13.5, remove (10.5, z11.5) | (8,8,8) | DU emits VAL-0x00 MARKER for ig=1 (legal!); parser fixed, encoder was right. BYTE-EXACT. |
| 3548 | (revisited) 1-thick sealed shell | 5^3 shell | (8,8,8) | h=1+cavity integration: 4-corner deck rule. BYTE-EXACT. Reg=82. |
| 3590/3592 | C1 diamond / C2 round dome with h=1 RIMS (curved-h1 probes) | C1: 3x5 diamond h1-3 @x8-10; C2: DOMER3-1 @x13-19 y13-19 h1-3 | (8,8,8) | BOTH BYTE-EXACT FIRST DIFF — h=1 mode composes with curved laws, no new rules. |
| 3594 | C3 opener-wrap probe (flat widening 13->15 cols) | x8.5-9.5 y9.5-21.5 h2 + x10.5-11.5 y8.5-22.5 h2 | (8,8,8) | val-0xff markers LEGAL; mkband edge 28->4 (<=26:6); pad maxnc15 -4 nx-independent. BYTE-EXACT. Reg=85. |
| 3646/3648 | NC15/NC17 nx3 diamonds (curved big-nc pad) | x8.5-10.5; NC15 ncs 11/15/11 y8.5-22.5 h2-5; NC17 ncs 13/17/13 y8.5-24.5 h2-5 | (8,8,8) | Pads 214/212. First read "cyclic band" (WRONG — single-point slope degeneracy). Both BYTE-EXACT after slope-10 fix. |
| 3653 | WNC15 run [13,13,15,15,15,13,13] | x8.5-14.5, y per plane (9.5/8.5 starts), h2-5 dome profiles | (8,8,8) | RUN GRAMMAR at width>=13 CONFIRMED (markers identical). Pad 174 -> nc15 = 244-10nx SLOPE -10 (with 3646). BYTE-EXACT. |
| 3657 | WNC15B shoulders [11,11,13,13,15,15,15,13,13,11,11] | x8.5-18.5 (as-built: x9/x17 cols7-9 h3 variance) | (8,8,8) | 11<->13 transition CONFIRMED. Pad 136 -> CURVED KINK fires nx>=10 even nx<maxnc. BYTE-EXACT (as-built). |
| 3691 | WWIDE [7,11,11,7] widening probe | x8.5-11.5, nc7 y12.5-18.5 / nc11 y10.5-20.5, h2-4 | (8,8,8) | +4 WIDENING OPENER CORRECT. Pad 204 -> maxnc11 curved = slope-10 base246 (13h re-confirms +kink). BYTE-EXACT. |
| 3693 | WWIDE3 [3,7,11,7,3] nc3-tip probe | x8.5-12.5, nc3 y14.5-16.5 h2 tips | (8,8,8) | BYTE-EXACT first diff — nc3 tip + 3->7 widening + yp6 lead all correct. Dome content 100% proven. |
| 3696 | FULL-DOME nc15 donor (= Deployment 15d shape) | x8.5-22.5, 15 planes nc[3,7,11,11,13,13,15,15,15,13,13,11,11,7,3], 161 cols (x20.5 y14-16 h3 build variance) | (8,8,8) | THE CLOSER: pad 102 -> CURVED KINK = 2*q^2 QUADRATIC (q=(nx-5)//5; 4-point fit 0/0/+2/+8). mc CONFIRMED (mat 32). BYTE-EXACT. Reg=93. |
| 3700 | FULL-DOME nc15 CORRECTED (plane-12 slip fixed to intended h4) | same as 3696, x20.5 y14.5-16.5 now h4 | (8,8,8) | **BYTE-EXACT to our generation** -> scan fully proven. 1-byte blueprint diff vs our 3697 exposed the _scan_mc 0xff-opener bug (mc 513 vs 544). |
| (3702) | Deployment 15d import | nc15 dome x8.5-22.5 | (8,8,8) | ★ **RENDERED PERFECTLY — nc15 curved dome deploy-proven.** |
| (3703/3704) | Deployment 15a / 15 imports (nc17 mt2/h1) | nc17 dome x8.5-24.5 | (8,8,8) | Both invalid-vertex WITH correct mc -> genuine nc17 gap (base 242 single-point). WNC17 donor requested. |
| 3707 | WNC17 run [15,15,17,17,17,15,15] | x8.5-14.5, h2-6, y-starts 10.5/10.5/9.5x3/10.5/10.5 | (8,8,8) | b2 FLAT-TOP GATE (curved identical planes keep b2=2; item 13) + nc17 pad 242-10nx+2*idrun. BYTE-EXACT. |
| 3712 | FULL 15a donor (nx17 maxnc17 dome, 213 cols) | x9.5-25.5, 17 planes nc[3,9,11,13,15,15,15,17,17,17,15,15,15,13,11,9,3], h3-edge planes x15.5/x19.5 | (8,8,8) | ONE-BYTE diff -> SHADOW-rule gate = MAX-TOP not Tlast (h3-edge plane doesn't shadow). BYTE-EXACT. Reg=95. |
| 3718 | H1-RIM donor (= 3712 with 20 rim cols at h1) | x9.5-25.5 nc17 dome, h1 tips/edges | (8,8,8) | MARKER-GAP LAW refined: band sum = effnc(LEFT plane, h1 cols EXCLUDED) + full nc(RIGHT). BYTE-EXACT first fix. Reg=96. |
| (3714/3715-era imports) | Deployments 15d/15a/15 final | nc15+nc17 domes mt2+h1 | (8,8,8) | ★★★ ALL THREE RENDERED — big-nc curved family + h=1 rims DEPLOY-PROVEN end-to-end. |
| 3723/3725 | NC16 diamond (nx3) + WNC16 run (nx7, no identical planes) | x8.5-10.5 [12,16,12] / x8.5-14.5 [14,14,16,16,16,14,14] | (8,8,8) | nc16 pad = 242-10nx +2 STEP at nx>=5 — same cell as nc17; WNC16 (no id-runs) KILLS the idrun reading. Both BYTE-EXACT (diamond first-diff). Reg=99. |
| 3728/3730 | NC13 diamond + WNC13 run (nc12-14 verification bracket) | x8.5-10.5 [9,13,9] / x8.5-14.5 [11,11,13,13,13,11,11] | (8,8,8) | Legacy slope-9 (235-9nx) VERIFIED at nx3+nx7 (208/172) — nc12-14 branch REAL. WNC13 mc=767 (hidden 0xff mat) end-to-end. Both BYTE-EXACT first diff. Reg=101. |
| 3734-3744 | P6A-F nx6 pocket sweep (x0 11/14/24 x z 8/20) | nx6 nc4 h4 boxes | (8,8,8) | x0 11/24 CLEAN (reg); x0 14: grp+2@z8, LEAD+2&pad+2@z20 (lead z-dependence = NEW); x0 19 grp+2@z20. Hooks = lead short-step cells xp%5==1, attenuating. Reg=105. |
| 3746-3756 | Y12-Y23 nx4 lead-y sweep | nx4 nc4 h4 boxes y12-23 | (8,8,8) | THREE laws: lead y-term 7-PERIOD at nx<=4 (2*((yp+1)//7)); grp_off = mat + max(lead7,lead9) - 9 (DECOUPLES from lead); pad y-band = %7 in {4,5} not %15 (aliased). nx3 sweep 3520-3534 RECLAIMED (8 donors). Reg=119. |
| 3758/3760/3762 | NC9/NC10 diamonds + WNC10 run (item 8) | nx3 [7,9,7]/[8,10,8]; nx7 [8,8,10,10,10,8,8] (as-built x14=x13 variance) | (8,8,8) | Curved nc9/10 = 244-10nx +2@nx>=5 +2*((nx-5)//4)^2 (old 239-9nx = nx7/nx9 degeneracy). BONUS: shadow gate WIDER-previous clause (ncp(L-1)>ncp(L)). Reg=122. |
| 3764/3766/3768 | C49/C315/C20 item-9 cell fluke-guards | (4,9) far coords / (3,15) x20y10z18 / nx20 flat slab | (8,8,8) | C49+C20 BYTE-EXACT (cells confirmed). C315 -2 -> spawned probe grid. |
| 3770-3780 | C315 1-var + pairwise probes | flat nx3 nc15 h3 at x/y/z single+pairs | (8,8,8) | Single axes CLEAN; x20*y10 -> grp+2 (3776); *z18 -> +pad-2 (3766). New off-origin small-nx hook pocket -> GUARDED. |
| (3768 LOD) | C20 extent-20 LOD set | — | — | ITEM 10 SOLVED: h4 phantom = POSITION lov%32<8 (not extent>16); mass-scan 283 exports nested-consistent; M1/C20 verified. Reg=130. |
| 3786/3784 | G11/G24 gband-edge probes (FIRST asymmetric +1-col widenings) | nx2: [5|6] / [12|13] flat-band+curved | (8,8,8) | FIVE laws: 35*INT-mean F (all F sites; even-sum donors were aliased); ncg(interior)=span of LOWER-ylo plane; +X wider-last=own-pair; pad nx2 -2; gband edges confirmed. |
| (3481) | NCV6 RECLAIMED (item 17) | nc[1,3,3,3,5] widest-last, ys (11,10,10,10,9) | (8,8,8) | Byte 740 = +X wider-last own-pair with Tlast_OWN. BYTE-EXACT after G-laws + own-T. Items 11+17 CLOSED. Reg=133. |

- **tests/deployment16_sem_yridge.blueprint** (2026-07-18) — DEPLOYMENT 16: FIRST SEMANTIC-PIPELINE deploy test (`build_blueprint_sem` -> du_semantic, zero empirical laws). Novel curved ridge crossing the Y chunk boundary: voxels x8..12, y27..36, z8 base, heights 2,3,4,5,6,6,5,4,3,2 (tops z9..13; NOT a donor clone — nx5 vs 3400's nx3). Exercises: dense fill rules, canonical Y-seam payload from OUR emitter (never deploy-proven), empty h4-h7 LOD bodies, 3187 envelope. Chunks (8,8,8)+(8,9,8) + 14 LOD records. **RENDERED PERFECTLY 2026-07-18 — SEMANTIC PATH HARDWARE-PROVEN (incl our canonical Y-seam payload + empty LODs).**

- **tests/dep18_cargohold.blueprint** (2026-07-17) — DEPLOYMENT 18: novel hollow cargo hold (12^3 shell, 8^3 void, +x door). FAILED DEPLOY: server panic "wrong cell" — built on XS core (Size 32) but compute_lod_set_mc emits the M-core octree (chunk0=8, h3..h7); the octree coords do not fit a Size-32 core. ROOT CAUSE: core-size envelope synthesis changed Model.Size without a matching per-core LOD octree layout (only M is derived/proven).
- **tests/dep18b_cargohold_M.blueprint** (2026-07-17) — DEPLOYMENT 18b: same cargo hold REBUILT on the proven M core (Size 128, h3..h7 root h7 (0,0,0)); all records parse; synthesized envelope deep-diffs to template only on benign identity fields. AWAITING DEPLOY (validates hollow shape + synthesized M envelope).

- **tests/dep19b_sphere_smooth.blueprint** (2026-07-17) — DEPLOYMENT 19b: anchor-smoothed sphere. DEPLOYED BLOCKY (smoothing failed). ROOT CAUSE: placement translation shifted anchor KEYS but not anchor TARGET POINTS -> every deflection saturated at the +-100 clamp in random directions (noise, not smoothing). Also the conservative SAT surface band put the solid boundary ~0.74 vox proud of the mesh.
- **tests/dep19d_sphere_smooth_fixed.blueprint** (2026-07-17) — DEPLOYMENT 19d: sphere, smoothing FIXED. (1) anchor_smooth_fn shifts key AND target by the placement delta; (2) du_voxelize solid_mode=contain (mesh-tight scanline z-parity solid) so boundary corners sit <=0.5 vox from the mesh. Deflection profile now mean 29, 0% clamped (3191 smooth-sphere ref: max 41). AWAITING DEPLOY (validates vertex smoothing in-game).

- **tests/dep19e_sphere_robust.blueprint** (2026-07-17) — DEPLOYMENT 19e: smooth sphere with ROBUST solid fill. dep19d had knife-cut missing columns (single-axis z-scan miscounted crossings where the ray grazed the UV sphere meridian edges). FIX: solid_by_containment robust=True casts rays along all 3 axes + majority-votes (>=2/3) -> 0 missing columns, 0 enclosed empties, 0.4s. Smoothing intact (mean 29 deflection). AWAITING DEPLOY (smooth + whole sphere).

- **tests/dep19f_sphere.blueprint** (2026-07-17) — DEPLOYMENT 19f: smooth sphere, equatorial-cut FIXED. dep19e still cut a horizontal XY plane at mid-Z: the UV sphere equator is a full ring of COPLANAR edges that both the x-ray and y-ray graze at once -> 2/3 axes fail -> majority vote loses. FIX: perturb each ray sample point by tiny incommensurate irrationals (sqrt2/sqrt3 e-3) so rays never hit an edge/vertex/coplanar ring. All 3 orientations 0 missing columns, 0 enclosed empties. Deflection mean 26 max 57 (3191 ref max 41). **RENDERED PERFECTLY 2026-07-18 — clean whole SMOOTH sphere. Full .obj front-end (scale+hollow+smooth on robust custom voxelizer) HARDWARE-PROVEN.**

- **tests/dep20c_box_Mmin.blueprint** (2026-07-18) — DEPLOYMENT 20c: 6^3 box, M core, MINIMAL octree (5 records: h3..h7 ancestors only, NO phantom low-neighbour LOD nodes; proven phantom-M path emits 26). Tests whether DU needs the phantom LOD nodes or regenerates from h3. KEY control for per-core-size support. AWAITING DEPLOY.
- **tests/dep20_box_S.blueprint** (2026-07-18) — DEPLOYMENT 20: 6^3 box, S core (Size 64), minimal octree h3..h6, chunk0=4/OFF=128. Tests derived per-core octree params. AWAITING DEPLOY.
- **tests/dep20b_box_L.blueprint** (2026-07-18) — DEPLOYMENT 20b: 6^3 box, L core (Size 256), minimal octree h3..h8, chunk0=16/OFF=512. AWAITING DEPLOY.

- **tests/dep21_tile_0.blueprint + dep21_tile_1.blueprint** (2026-07-18) — DEPLOYMENT 21: multi-core TILING test. A 40x10x10 voxel bar split across 2 XS cores (tile 0 = x0..31, tile 1 = x32..39). Place tile_1 core adjacent to tile_0 core along +X (offset (1,0,0)*32 voxels). Tests that tiled constructs abut seamlessly. Both XS static, valid. AWAITING DEPLOY (verify the two halves line up into one continuous bar).

- **tests/dep22_half_A.blueprint + dep22_half_B.blueprint** (2026-07-18) — DEPLOYMENT 22: SMOOTH SPHERE CUT IN HALF across two XS cores (tiling + smoothing seam test). Diameter-30 sphere straddling the x=32 core boundary, split at x=32: half A (core 0) = x17..31, half B (core 1, local x0..14). Each half smooths its own curved surface (~2000 deflected verts); flat cut faces meet at the seam. PLACEMENT: deploy both XS cores, use DU grid-align to place core B one core-width (+X) adjacent to core A -> the two halves form one continuous smooth sphere. AWAITING DEPLOY.

- **tests/dep23_sphere_centered.blueprint** (2026-07-18) — DEPLOYMENT 23: single M smooth sphere, PLACEMENT FIX. Content now CENTRED on the core element (world center ~64.25 vs element 64.125) + real Model.Bounds from the material bbox. Verifies the deploy-offset fix (was: content min-corner at chunk0 -> centre half-an-extent past anchor). AWAITING DEPLOY (should sit ON the placement point, no offset).
- **tests/dep24_half_A.blueprint + dep24_half_B.blueprint** (2026-07-18) — DEPLOYMENT 24: split smooth sphere across 2 XS cores, FIXED. Half A at core RIGHT edge (cells 113..127), half B at LEFT edge (0..14), SHARED y,z placement (identical y,z bounds) so the seam matches exactly. Grid-align core B one core-width (+X) from A -> continuous smooth sphere. Supersedes dep22 (which centred both halves at chunk 2). AWAITING DEPLOY.
