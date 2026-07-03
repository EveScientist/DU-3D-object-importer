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

## Pending (spec'd, awaiting export number)
- (none)

## Generated import tests
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

## Archive / earlier exports (coords to backfill as confirmed)
Older referenced exports whose exact XYZ should be added here when re-confirmed:
2494 (solid interior, chunk (2,2,2)); 2906/2910/2935/2937 (z=0 seams, base position
UNKNOWN — do not byte-match blind); 2952/2954/2956 (staircases descent/peak/valley);
2959/2961/2963/2965/2967/2969/2971 (relief profiles); 2941/2943 (x=0 / y=0 seams).
