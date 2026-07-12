# DU Blueprint Generator — Formula Audit
*Generated 2026-06-06*

---

## TIER 1 — Core generators (current pipeline)

### `generate_hollow_cube.py` — h=3 generator

| Area | Status |
|---|---|
| CV formula `(32*n + base_corner) % 256` | ✅ Derived & verified |
| n formula `(4-Wx-3*Wy-Wz)%8` | ✅ Derived & verified |
| n1_first = `4 + (153*lx + 4*ly + lz_eff)//31` where `lz_eff=32 if (lz==0 and (lx>0 or ly>0)) else lz` | ✅ Verified against all 8 chunks of 188_export. Fixed in generator 2026-06-06. |
| gap = `162 if n in {4,7} else 163` | ✅ Verified (188_export all 8 chunks) |
| FG_START = `n1_first + 3 + gap` | ✅ Correct formula. Old formula `2*CV+47` was WRONG (only coincidentally correct for n1_first=162, n=4). Fixed 2026-06-06. |
| marker_val = `(120 - CV) % 256`; if 0xff → 0x00 | ✅ Verified against both 188_export and 187_export. Replaces wrong constant `0xec`. |
| ftr_val = `512 + marker_val` | ✅ Verified all 16 chunks across both exports |
| marker_pair = `gap + 7` (absolute pair 169 or 170) | ✅ Confirmed for n∈{4,7,1,2,3}. Note: n=0 hcSodium shows pair 169 (vs expected 170) — off by 1, mechanism unclear but low-impact. |
| trailing = `(166 if n in {4,7} else 167) - n1_first` | ✅ Derived from scan length = 351 (n∈{4,7}) or 353 (others) for N=1 |
| G1_opener = `(CV + 19) % 256`; if 0xff → marker_val | ✅ Derived formula — verified against all 8 chunks of 188_export. Fixed in generator 2026-06-06. |
| `_scan_n1` sort key = `_n1_first(lx,ly,lz)` | ✅ Updated to use correct lz_eff formula (fixes sort order for lz=0 boundary voxels) |
| **Empty chunk scan** (line 96-100) | ❌ Hardcoded 352-pair all-00ff blob — size not based on CV formula |
| **`_voxel_blob_h5` placeholder** (lines 159-173) | ❌ Old hardcoded scan from a completely wrong format — still present in the file, used as fallback for complex h4/h5 |
| **Multi-h3 h4** (line 269) | ❌ PLACEHOLDER — uses `_voxel_blob_h5()` as the blob; formula completely unknown |
| **Multi-h4 h5** (line 294) | ❌ PLACEHOLDER — same wrong blob |
| **Multi-voxel h3 FG structure** | ❌ The 4-pair gap between Z1 and Z0 groups is only coded for N=1; N>1 FG layout never tested in-game |
| **hcCarbon base_corner=179** | ❌ Gives CV=51 for interior voxels (n=4) → GAP=2*51-118=**-16** (negative). FG_START would be less than n1_first+decl_pairs, which is impossible. base_corner=179 is likely wrong for hcCarbon. |
| `_MESH` blob bytes | ❌ Hardcoded 20-byte hex from exports; mesh format not decoded |
| `_DEBUG1_HASH`, `_DEBUG1_NAME` | ⚠️ Extracted from exports. Assumed constant but Debug1 is a built-in material — probably safe. |
| `STATIC_CORE_XS_NQID = 2738359963` | ⚠️ From 122_export; not formula-derived but element type IDs are stable game data |
| `_meta_blob` generator | ⚠️ Hash-based fresh generation — not from exports, but the meta format itself is not decoded at all |

---

### `scan_gen_h4.py` — h=4 generator

| Area | Status |
|---|---|
| FG expansion 8B→12B | ✅ Verified byte-for-byte against all 8 188_export chunks |
| `_H4_G1_TAIL`, `_H4_G2/G3/G4_FULL` constants | ⚠️ Reverse-engineered from 188_export. The 0x93/0x69 bytes are vertex offset coordinates — meaning not decoded, but values verified correct for simple case |
| h4 JSON coord = h3//2 | ✅ Verified |
| h4 header chunk_pos = (h3//2)*32 | ✅ Verified |
| **Complex case** (multiple h3 FG groups in one h4) | ❌ Completely unhandled — current code only works when h3 has exactly 4 FG groups (single-voxel). A hollow cube h3 chunk can have hundreds of FG groups. |

---

### `scan_gen_h5.py` — h=5 generator

| Area | Status |
|---|---|
| N1S_REF = (h4_decl_pair-4)//2 | ✅ Derived & verified |
| h5 FG = h4 FG - N1S_REF | ✅ Verified byte-for-byte vs 188_export |
| ftr_val delta -48, opener delta +48 | ✅ Verified |
| `_H5_G2/G3/G4_FULL`, `_H5_G1_TAIL` constants | ⚠️ From 188_export; 0x9e/0x5f bytes not decoded geometrically, but verified correct |
| **Complex case** (multiple h4 per h5) | ❌ Not handled |

---

## TIER 2 — `blueprint_encoder.py` — 122_export-style multi-voxel blocks

Separate format from the above — for **nx×ny×nz solid blocks** at specific chunk positions (cx=2 only).

| Area | Status |
|---|---|
| `HEADER_CX2` — hardcoded 64-byte header | ❌ Only valid for cx=2 chunks. No formula for other cx values. |
| `n1_FG` formula (ODD FG / EVEN nx, ODD ny) | ✅ Confirmed 13/13 cases |
| `n1_FG` formula (EVEN FG / ODD nx) | ✅ Confirmed |
| `n1_FG` (EVEN ny cases: C_BASE_even) | ⚠️ `{4: 323, 6: 345}` — empirical values, not formula-derived |
| FG cluster step formula | ✅ Confirmed |
| Scan length formula | ✅ Confirmed |
| Marker formula (ODD FG) | ✅ Confirmed |
| **Marker formula (EVEN FG odd M)** | ❌ Wrong for 3 known cases: (3,5), (4,4), (4,6) |
| **cz1 companion scan** (`build_h3_cz1_scan`) | ⚠️ Partially working — constants like `(0xb6+0x20)%256` and marker `(252-35*ny)%256` are from export analysis, limited verification |
| **Only hcCarbon** | ❌ `build_footer` hardcodes hcCarbon hash. Not generalized to other materials. |
| **Only lx=14** (cx=2 chunk type) | ❌ `n1_sub1(14)=79` is the only path tested. cx=0, cx=1, cx=3 chunks not verified. |
| **nx=1** | ❌ Asserts `nx >= 2` — single-row blocks not supported |

---

## TIER 3 — Legacy generators (superseded, not used by current pipeline)

### `generate_single_voxel.py`
- **Loads meta blobs directly from `122_export.blueprint` at runtime** — hard dependency on the export file
- h4/h5 use old placeholder `make_lod_body()` with a hardcoded static scan
- FX1 is an empirical lookup table only valid for Size=32 at world origin

### `generate_v2.py` and `generate_v3.py`
- Use `n1 = 9 + (153*lx + 4*ly + lz)//31` — a **different formula** from the current n1_first=162. These target a different scan format (single-voxel within 122_export's chunk structure) and are not directly comparable.
- FX lookup tables from 122_export empirical analysis — only valid for Size=32 constructs
- `MAT_SODIUM` / `MAT_CARBON`: hardcoded 40-byte hex copied from exports

### `scan_gen_v2.py` / `obj_to_du_blueprint.py`
- `declaration_cv(n1)` returns `0xb6` — **placeholder, not derived**
- Pre-FG marker value `0x79` — **placeholder**
- Scan padding (52 for nx≥9, 86 otherwise) — **empirical**, no formula

---

## COMPLETELY UNDECODED AREAS

| # | Area | Impact |
|---|---|---|
| 1 | **Multi-voxel h3 → h4 aggregation** | Blocks hollow cube LOD. When one h4 chunk covers multiple h3 chunks, the formula for merging their FG groups is unknown. |
| 2 | **Meta blob format** | The 347-byte meta blob structure is opaque. `_meta_blob()` fills it with a hash but meaning of fields is unknown. |
| 3 | **Mesh blob format** | The 20-byte `_MESH` content is hardcoded from exports. Structure unknown. |
| 4 | **FX values / G1_opener formula** | ~~SOLVED~~ G1_opener=(CV+19)%256. G2/G3/G4 openers (0x20, 0xa3, 0x20) are universal constants. Exception: hcAlLiPa n=7 gives 0xff — engine fallback behavior unknown. |
| 5 | **hcCarbon base_corner** | Value 179 breaks the CV formula for interior voxels (negative GAP). Either the value is wrong or hcCarbon needs a different formula branch. |
| 6 | **Other materials** | Only hcSodium (249), hcCarbon (179, broken), hcAlLiPa (12) are known. Any other DU material requires its base_corner to be reverse-engineered from a captured export. |
| 7 | **S/M/L core element type IDs** | Only XS static (2738359963) and M static (909184430) known. No formula — just looked-up IDs. |
| 8 | **h4 complex FG structure** | What does an h4 blob look like when the underlying h3 has many FG groups (hollow cube, dense block)? Expansion rule for >4 groups unknown. |

---

## Priority Summary

| Priority | Gap |
|---|---|
| **P1 — Blocks current work** | Multi-h3 h4 aggregation (can't do hollow cube LOD) |
| **P1** | hcCarbon base_corner fix (negative GAP bug) |
| **P2 — Next test** | Multi-voxel h3 FG layout (N>1 gap structure) — needs in-game test of current generator |
| **P2** | Empty chunk correct scan size |
| **P3** | Meta blob format, mesh blob format |
| **DONE** | Scan structure fixed: n1_first (position-dependent), marker_val=(120-CV)%256, FG_START=n1+3+gap, trailing. All 8/8 188_export chunks pass. 2026-06-06. |
| **DONE** | G1_opener = (CV+19)%256, fallback to marker_val if 0xff. Fixed in generator. |
| **Low** | Legacy files (generate_v2/v3/single_voxel) — superseded by current pipeline |
