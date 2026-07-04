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
