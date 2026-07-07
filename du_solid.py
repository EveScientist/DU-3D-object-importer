"""
DU fully-solid (dense) chunk generator — Phase B (large solid cubes).

Reverse-engineered from export 2494 (solid cube spanning 4x4x4 chunks, with 8
fully-interior chunks {1,2}^3). The dense fully-solid chunk encodes the 32^3
solid as a W x H grid (W cols ~ lx, H rows ~ ly) of:
  - 5-byte MARKERS  [val,01,02,32,00]   (one per column, val=1 bulk / 71 last col)
  - 8-byte GROUPS   [val,01,mat,7e,7e,7e,N,00]  (one per column; bulk val=33 = SOLID)
separated by [255,0]*9 + [sep,0], framed by a 4-byte preamble + [255,0]*9 trailing.

STATUS: byte-EXACT for the canonical interior chunk (2,2,2) of 2494 (33x33 grid).
The other 7 interior chunks are POSITION-DEPENDENT (preamble, separator byte,
corner/edge group values, grid W/H, and the mat/N depth flag all shift with cx,cy,cz)
— same complexity class as the crossing generators. Observed so far:
  - cz=2 -> special mat/N = 32 ; cz=1 -> 33   (z-depth flag)
  - low-coord side (cx==1 or cy==1) adds an extra row/col (W or H = 34)
  - first-group/corner values (236,201,35,34,31...) are origin-relative
    (236 == corner-generator base) -> near-origin chunks encode vs construct origin.
TODO: derive the (cx,cy,cz)->(preamble, sep, grid, edge-values) rule to cover all
positions, then face/edge/corner solid chunks, then envelope + generate_solid_cube().
"""

# ── DEEP-INTERIOR PRIMITIVE ────────────────────────────────────────────────
# The fully-solid chunk with NO exposed surface (all 6 neighbors solid).
# UNIFORM + translation-invariant: verified byte-identical across all 64 deep
# chunks of 2495 (192-voxel solid cube on a Static-M / Size-128 core).
# Compact run-encoding: [01 02 ff]*167 + [01 02 7a] + [00 ff]*167 (839 bytes).
# This is THE reusable interior building block for any large solid cube.
_DEEP_INTERIOR_SCAN = bytes.fromhex(
    "0102ff" * 167 + "01027a" + "00ff" * 167 + "00"
)


def gen_deep_interior_scan():
    """Return the fully-solid no-surface interior chunk scan (839 bytes, constant)."""
    return _DEEP_INTERIOR_SCAN


# ── SINGLE-COLUMN SURFACE ENCODER ──────────────────────────────────────────
# An isolated 1x1xh column (bottom-aligned) at chunk-local (lx,ly,lz). This is
# the atomic SURFACE primitive (the path to complex shapes + smooth surfaces).
# Byte-exact vs 2497/2499/2509/2511/2513/2517/2519/2521 (Static-M, hcCarbon).
#   CV   = (217 - 55*lx + 35*ly + lz) % 256          (corner value; 7 pts)
#   decl = [0,CV,01,02,h-1,00] at pair floor((153*lx+358)/32)
#   pre-FG byte = (120 - CV - (h-1)) % 256            (also the mat-tail ftr)
#   FG (4 groups) [val,01,h,7e,7e,7e,h,00]: vals = CV+19, 33-h, 164-h, 33-h
#   run-length byte = h (height); 7e7e7e = displacement slots (0 = flat).
# NOTE: length / FG-offset use an empirical floor-step (validated lx<=22, ly<=13);
# the exact floor form + ly/lz position terms + COMPOSITION (adjacent/gap/2D) are
# the next sub-problems toward the general occupancy->scan encoder.
def gen_single_column(lx, ly, lz, h):
    CV = (217 - 55 * lx + 35 * ly + lz) % 256
    declpair = (153 * lx + 358) // 32
    step = not (lx <= 13 and ly <= 10)        # empirical floor-step (tested range)
    L = 702 if step else 706
    prepair = 169 if step else 170
    fg0 = declpair + (165 if step else 166)
    s = bytearray(bytes([255, 0]) * (L // 2))             # ff00 background
    for p in range(declpair):                             # 00ff before declaration
        s[2 * p] = 0; s[2 * p + 1] = 255
    s[2 * declpair:2 * declpair + 6] = bytes([0, CV, 1, 2, h - 1, 0])
    s[2 * prepair] = (120 - CV - (h - 1)) % 256
    def grp(pp, val):
        s[2 * pp:2 * pp + 8] = bytes([val % 256, 1, h, 0x7e, 0x7e, 0x7e, h, 0])
    grp(fg0, CV + 19); grp(fg0 + 4, 33 - h); grp(fg0 + 12, 164 - h); grp(fg0 + 16, 33 - h)
    return bytes(s)


def interior_params(cx, cy, cz):
    """Position-dependent scalar params for a fully-solid chunk near the construct
    origin. Derived from 2494's 8 interior chunks {1,2}^3 (cx,cy,cz in {1,2}).

    These are crossing-class formulas: the LOW-x side (cx==1) collapses to a pure
    background form; the high-x side (cx==2) carries the marker structure.
      depth = 32 if cz==2 else 33                      (z-depth flag; CONFIRMED)
      sep   = 217 - 2*(cz==1) - 70*(cy==1)  for cx==2  (217/215/147/145; CONFIRMED)
      cx==1 -> preamble [0,255,0,255], sep region all background (sep byte 255)
    NOTE: only validated for cx,cy,cz in {1,2} (near origin). The reusable DEEP-
    interior primitive (all sides uniform) is NOT present in 2494 (too small / not
    chunk-aligned) and needs a bigger cube to capture. The cz=1 / cy=1 chunks also
    carry internal grid structure beyond the edges (origin/boundary coupling).
    """
    depth = 32 if cz == 2 else 33
    if cx == 2:
        sep = (217 - 2 * (cz == 1) - 70 * (cy == 1)) & 0xFF
    else:
        sep = 255
    return depth, sep


def gen_interior_scan(W=33, H=33, sep=217, depth=32):
    """Fully-solid interior chunk scan (canonical case, byte-exact vs 2494 (2,2,2)).

    W = column count, H = row count (33 for the high-coord canonical chunk).
    sep = separator byte before the group grid. depth = mat/N flag (32 for cz=2).
    """
    s = bytearray()
    s += bytes([1, 2, 32, 0])                              # preamble
    # markers: H rows x W cols, omitting the very last cell (r=H-1, c=W-1)
    for r in range(H):
        for c in range(W):
            if r == H - 1 and c == W - 1:
                continue
            val = 71 if c == W - 1 else 1
            s += bytes([val, 0x01, 0x02, 32, 0x00])
    s += bytes([255, 0] * 9 + [sep, 0])                    # separator
    # groups: H rows x W cols
    for r in range(H):
        for c in range(W):
            if r == H - 1:
                val, mat, N = (71, depth, depth) if c == 0 else (1, depth, depth)
            elif c == W - 1:
                val, mat, N = 1, depth, depth
            elif c == 0:
                val, mat, N = (31, 0, 0) if r == 0 else (103, 0, 0)
            else:
                val, mat, N = 33, 0, 0
            s += bytes([val, 0x01, mat, 0x7e, 0x7e, 0x7e, N, 0x00])
    s += bytes([255, 0] * 9)                               # trailing
    return bytes(s)


if __name__ == "__main__":
    import sys, json, base64, lz4.block, struct
    sys.path.insert(0, "/home/du")
    try:
        from tests.archive.test_h3_generator import find_export
    except ImportError:
        from tests.test_h3_generator import find_export
    bp = json.load(open(find_export(2494)))
    byc = {(e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong']): e
           for e in bp['VoxelData'] if e['h'] == 3}
    raw = base64.b64decode(byc[(2, 2, 2)]['records']['voxel']['data']['$binary'])
    v = lz4.block.decompress(raw[12:], uncompressed_size=struct.unpack('<I', raw[4:8])[0])
    idx = v.find(b'Debug1'); real = v[64:idx - 13]
    print("interior (2,2,2) byte-exact:", gen_interior_scan(33, 33) == real)


# ── 2D FLAT-PLATE COMPOSITION (surface) ────────────────────────────────────
# A flat rectangular nx*ny footprint at constant height h, base column at
# chunk-local (10,10,10) (CV=27). Byte-exact vs 2497(1x1)/2523(2x1)/2525(1x2)/
# 2531(1x3)/2535(2x2). Composition nests: y-cluster inside x-row.
# (High nx>~5 hits an unmodeled n1 floor-step; fine for small shapes.)
def gen_plate_scan(nx, ny, h, CV=27):
    def pad_to(s, t):
        while len(s) < t: s += bytes([255, 0])
        return s[:t]
    s = bytearray(bytes([0, 255]) * 59)                         # 00ff prefix (118B)
    for xi in range(nx):
        if xi > 0: s += bytes([255, 0]) * 4                     # x-gap
        if xi == 0: s += bytes([0, CV, 1, 2, h - 1, 0])         # first decl
        else: s += bytes([(200 - h - 35 * (ny - 1)) % 256, 1, 2, h - 1, 0])  # x-marker
        for _ in range(1, ny): s += bytes([33, 1, 2, h - 1, 0]) # y-markers
    pre = 340 + 3 * (nx - 1) + 5 * nx * (ny - 1)
    s = pad_to(s, pre)
    s += bytes([(120 - CV - (h - 1) - 35 * (ny - 1) + 55 * (nx - 1)) % 256, 0])
    s = pad_to(s, pre + 110)                                    # fg0 = pre+110
    clusters = 1 + nx
    for ci in range(clusters):
        opener = (CV + 19) if ci == 0 else (164 - h - 35 * (ny - 1))
        s += bytes([opener % 256, 1, h, 0x7e, 0x7e, 0x7e, h, 0])
        for _ in range(ny): s += bytes([(33 - h) % 256, 1, h, 0x7e, 0x7e, 0x7e, h, 0])
        if ci < clusters - 1: s += bytes([255, 0]) * 4
    L = (pre + 110) + clusters * (1 + ny) * 8 + (clusters - 1) * 8 + (216 - 10 * (nx - 1))
    return bytes(pad_to(s, L))


# ── 2D HEIGHTMAP COMPOSITION (arbitrary per-column heights) ─────────────────
# H[xi][yi] = height of column (xi,yi); base column at chunk-local (10,10,10),
# all columns bottom-aligned (z0=10). Byte-EXACT vs ALL references (flat,
# monotonic ramps/staircases, AND non-monotonic peak): 2497/2523/2525/2531/
# 2535/2505/2529/2539/2541/2545. Handles arbitrary heightmaps (pyramids/domes/
# terrain). Composition nests: y-cluster (vertical running-max) inside x-row
# (running-MAX PROFILE that propagates peaks forward; last cluster caps at the
# actual end column). x-axis values key off each column's LAST y-row.
# Positions are height-independent. (nx>~4 / ny>~3 may hit an n1 floor-step.)
def gen_heightmap_scan(H, CV=27):
    nx = len(H); ny = len(H[0])
    rInc = lambda c, j: max(c[:j + 1])              # running max from row 0..j
    rDec = lambda c, j: max(c[j:])                  # running max from row j..end
    lastrow = [H[i][ny - 1] for i in range(nx)]
    rmaxLR = [max(lastrow[:k + 1]) for k in range(nx)]   # running max of last-rows
    prof = lambda upto: [max(H[i][j] for i in range(upto + 1)) for j in range(ny)]
    h00 = H[0][0]
    def pad_to(s, t):
        while len(s) < t: s += bytes([255, 0])
        return s[:t]
    s = bytearray(bytes([0, 255]) * 59)                          # 00ff prefix
    for xi in range(nx):
        if xi > 0: s += bytes([255, 0]) * 4                      # x-gap
        for yi in range(ny):
            h = H[xi][yi]
            if xi == 0 and yi == 0: s += bytes([0, CV, 1, 2, h - 1, 0])
            elif yi == 0: s += bytes([(200 - H[xi - 1][ny - 1] - 35 * (ny - 1)) % 256, 1, 2, h - 1, 0])
            else: s += bytes([(34 - H[xi][yi - 1]) % 256, 1, 2, h - 1, 0])
    step = 2 * ((nx - 1) // 4) - 2 * ((ny - 1) // 3)   # n1 floor-step (nx<=8, ny<=5 validated)
    pre = 340 + 3 * (nx - 1) + 5 * nx * (ny - 1) + step - 2 * (nx - 1) * (ny >= 7) + 2 * (declpair0 - 59)
    s = pad_to(s, pre)
    s += bytes([(120 - CV - (h00 - 1) - 35 * (ny - 1) + 55 * (nx - 1) - (H[nx - 1][ny - 1] - h00)) % 256, 0])
    s = pad_to(s, pre + 110)
    def grp(val, run): return bytes([val % 256, 1, run, 0x7e, 0x7e, 0x7e, run, 0])
    s += grp(CV + 19, h00)                                       # top cluster (col0)
    for j in range(ny): s += grp(33 - rInc(H[0], j), rDec(H[0], j))
    s += bytes([255, 0]) * 4
    for k in range(nx):                                          # bottom clusters
        EC = H[nx - 1] if k == nx - 1 else prof(k + 1)           # end-cap vs running-max profile
        s += grp(164 - rmaxLR[k] - 35 * (ny - 1), EC[0])
        for j in range(ny): s += grp(33 - rInc(EC, j), rDec(EC, j))
        if k < nx - 1: s += bytes([255, 0]) * 4
    L = (pre + 110) + (1 + nx) * (1 + ny) * 8 + nx * 8 + (216 - 10 * (nx - 1)) + step
    return bytes(pad_to(s, L))


# ── EXTRUDED-PROFILE DESCENT GENERATOR (ny-uniform, arbitrary profile) ──────
# A 1D height profile p[0..nx-1] extruded along ny (every y-row identical).
# Handles ANY profile: rises, descents, peaks, plateaus, valleys. Byte-exact vs
# 17 refs incl held-out: 2575/2577/2579/2581/2583/2585/2571/2573/2569/2501/2505/2535/2497
# + HO 2587[4,3,2,1] / 2589[3,2,1,2,3].
#   cluster run  R[k] = max(p[k],p[k+1]) (k<nx-1) else p[nx-1]
#   opener       = 164 - max(p[k-1],p[k]) - 35*(ny-1)   (LEFT-boundary max)
#   SPECIAL (interior peak / gradual / plateau / valley-ascent): 2*ny groups, inner pair:
#     plateau -> [1,0]; consecutive descent-specials -> first [1,1]; else gradual -> [0,1].
def gen_extruded_scan(p, ny, CV=27):
    nx = len(p); base = min(p)
    R = [max(p[k], p[k + 1]) if k < nx - 1 else p[nx - 1] for k in range(nx)]
    RL = [p[0] if k == 0 else max(p[k - 1], p[k]) for k in range(nx)]
    def descent_ahead(k): return any(p[j] < p[k] for j in range(k + 1, nx))
    def interior_peak(i): return any(p[j] < p[i] for j in range(i + 1, nx))
    def special(k):
        if k >= nx - 1: return None
        a, b = p[k], p[k + 1]
        if a == b: return 'plat' if descent_ahead(k) else None
        if a > b:  return 'grad' if b > base else None
        rose_after_descent = any(p[j] > p[j + 1] for j in range(k))    # a descent occurred before k
        return 'grad' if (a > base and (interior_peak(k + 1) or rose_after_descent)) else None
    def desc_special(k): return k < nx - 1 and special(k) == 'grad' and p[k] > p[k + 1]
    def pad_to(s, t):
        while len(s) < t: s += bytes([255, 0])
        return s[:t]
    s = bytearray(bytes([0, 255]) * declpair0)
    for xi in range(nx):
        if xi > 0: s += bytes([255, 0]) * 4
        for yi in range(ny):
            h = p[xi]
            if xi == 0 and yi == 0: s += bytes([0, CV, 1, 2, h - 1, 0])
            elif yi == 0: s += bytes([(200 - p[xi - 1] - 35 * (ny - 1)) % 256, 1, 2, h - 1, 0])
            else: s += bytes([(34 - p[xi]) % 256, 1, 2, h - 1, 0])
    step = 2 * ((nx - 1) // 4) - 2 * ((ny - 1) // 3)
    pre = 340 + 3 * (nx - 1) + 5 * nx * (ny - 1) + step - 2 * (nx - 1) * (ny >= 7) + 2 * (declpair0 - 59)
    h00 = p[0]
    s = pad_to(s, pre)
    s += bytes([(120 - CV - (h00 - 1) - 35 * (ny - 1) + 55 * (nx - 1) - (p[nx - 1] - h00)) % 256, 0])
    s = pad_to(s, pre + 110)
    def grp(val, run): return bytes([val % 256, 1, run, 0x7e, 0x7e, 0x7e, run, 0])
    s += grp(CV + 19, h00)
    for _ in range(ny): s += grp(33 - h00, h00)
    s += bytes([255, 0]) * 4
    nspec = 0
    for k in range(nx):
        h = R[k]; sp = special(k)
        s += grp(164 - RL[k] - 35 * (ny - 1), h)
        if sp:
            nspec += 1
            if sp == 'plat':
                inner = (1, 0)
            else:  # gradual: 2nd byte = step magnitude; 1st = 1 for run of consecutive descent-specials
                inner = (1 if (desc_special(k) and desc_special(k + 1)) else 0, abs(p[k + 1] - p[k]))
            for _ in range(ny - 1):
                s += grp(33 - h, 0); s += grp(inner[0], inner[1])
            s += grp(33 - h, h)
        else:
            for _ in range(ny): s += grp(33 - h, h)
        if k < nx - 1: s += bytes([255, 0]) * 4
    L = (pre + 110) + (1 + nx) * (1 + ny) * 8 + nx * 8 + (216 - 10 * (nx - 1)) + step + nspec * (ny - 1) * 8
    return bytes(pad_to(s, L))


# ── UNIFIED GENERAL HEIGHTMAP GENERATOR (ny-varying + descents) ─────────────
# H[xi][yi] = height of column (xi,yi). Supersedes gen_heightmap_scan +
# gen_extruded_scan: handles ARBITRARY 2D heightmaps incl per-row variation AND
# gradual descents/valleys/peaks/plateaus. Byte-exact vs 27 refs (flat, monotonic,
# dome, pyramid, all extruded descents incl 4 held-outs, CR/CB corner ramps).
#   x-marker/decls: as before (x uses H[xi-1][ny-1], y uses H[xi][yi-1]).
#   opener VALUE from LAST-row profile p=H[*][ny-1]; opener RUN from FIRST-row R.
#   seconds: per-row boundary-max EC[j]=max(H[k][j],H[k+1][j]) -> (33-rInc(EC,j),rDec(EC,j)).
#   SPECIAL clusters (descent on last-row profile): inner [0,1]/[1,1]/[1,0] (see gen_extruded_scan).
# NOTE: ny-varying + special-trigger (gradual descent on a y-varying last-row) is the
# one path with no reference yet -> validate via held-out before fully trusting.
def gen_heightmap_unified(H, lx0=10, ly0=10, lz0=10, dstep=0, cz_neg=False):
    nx = len(H); ny = len(H[0])
    CV = (217 - 55 * lx0 + 35 * ly0 + lz0) % 256        # first-column corner value
    # decl-prefix constant: positive octant (cz>=8) uses C=322; the NEGATIVE-Z octant
    # (cz<8) uses C=324 (verified byte-exact vs neg-Z plates 2904-2925; the +2 tips the
    # floor when base%32>=30). Everything else (CV, structure, values) mirrors positive:
    # negative-Z is gen_heightmap_unified(lx0, ly0, lz0=gz%32, cz_neg=True), cz=8+gz//32.
    declpair0 = (153 * lx0 + 4 * ly0 + (324 if cz_neg else 322)) // 32
    p = [H[xi][ny - 1] for xi in range(nx)]; base = min(p)
    rInc = lambda c, j: max(c[:j + 1]); rDec = lambda c, j: max(c[j:])
    def EC(k): return list(H[nx - 1]) if k == nx - 1 else [max(H[k][j], H[k + 1][j]) for j in range(ny)]
    def descent_ahead(k): return any(p[j] < p[k] for j in range(k + 1, nx))
    def interior_peak(i): return any(p[j] < p[i] for j in range(i + 1, nx))
    def special(k):
        if k >= nx - 1: return None
        a, b = p[k], p[k + 1]
        if a == b: return 'plat' if descent_ahead(k) else None
        if a > b: return 'grad' if b > base else None
        rose = any(p[j] > p[j + 1] for j in range(k))
        return 'grad' if (a > base and (interior_peak(k + 1) or rose)) else None
    def desc_special(k): return k < nx - 1 and special(k) == 'grad' and p[k] > p[k + 1]
    def pad_to(s, t):
        while len(s) < t: s += bytes([255, 0])
        return s[:t]
    # floor-step & gap-shrinks (validated nx<=12, ny<=10):
    step = (2 * ((nx + 1) // 5) if ny == 1 else 2 * ((nx - 1) // 5)) - 2 * (ny >= 4) + 2 * (4 <= ny <= 6 and (nx >= 3 or (nx == 2 and ly0 >= 0))) + dstep  # nx floor-step (ny>=2: //5, pinned by flat nx5 2969=step0 + nx7 wave 2965=step2); ny>=4 corr -2 base, +2 back for ny=4..6 & (nx>=3 or nx==2 w/ ly0>=0); nx==2 neg-ly0 (y-seam) keeps -2; dstep=+2 down-ghost
    xgap = bytes([255, 0]) * (4 - (ny >= 7) - 2 * (14 <= ny < 33) - (ny == 32))  # decl x-gap: 6B(ny>=7); 2B in 14..31; 0B at ny=32 edge (3114); ny>=33 stays 6B
    clgap = bytes([255, 0]) * (4 - (ny >= 6) - (12 <= ny < 33) - (14 <= ny < 33) - (ny == 32))  # FG cluster gap: shrinks to 0 at ny=32 edge (3114); ny>=33 stays 6B
    s = bytearray(bytes([0, 255]) * declpair0)
    for xi in range(nx):
        if xi > 0: s += xgap
        for yi in range(ny):
            h = H[xi][yi]
            if xi == 0 and yi == 0: s += bytes([0, CV, 1, 2, h - 1, 0])
            elif yi == 0: s += bytes([(200 - H[xi - 1][ny - 1] - 35 * (ny - 1)) % 256, 1, 2, h - 1, 0])
            else: s += bytes([(34 - H[xi][yi - 1]) % 256, 1, 2, h - 1, 0])
    h00 = H[0][0]
    preval_signed = 120 - CV - (h00 - 1) - 35 * (ny - 1) + 55 * (nx - 1) - (H[nx - 1][ny - 1] - h00)
    # base-position align jitter DECOUPLED into TWO independent CV bands (was one `bfs`):
    #   bw (WIDE, CV>160): shifts preval position -2 and total length -2.
    #   bn (NARROW, 160<CV<=BN_HI): shifts fg0 anchor -2 and total length -2.
    #   L_shift = bw + bn.  Usually bw==bn, so the old bfs=CV>160 (pre/fg0 -2, L -4)
    #   worked everywhere EXCEPT the top of the band, where bn drops to 0 while bw
    #   stays 1 (pre -2, fg0 +0, L -2). Verified byte-exact across the full lx0 cycle
    #   2739-2870 @ nx3ny3ly0=10, incl. the long-"jittering" lx0=20/CV245.
    BN_HI = 236                                          # narrow-band upper bound; PINNED via in-game sweep (bn=1 @CV236/2900, bn=0 @CV237/2902)
    bw = 0 if ny == 1 else (1 if CV > 160 else 0)           # wide band: preval pos + total length
    bn = 0 if ny == 1 else (1 if 160 < CV <= BN_HI else 0)  # narrow band: fg0 anchor
    pre_b10 = 340 + 3 * (nx - 1) + 5 * nx * (ny - 1) + step - 2 * (nx - 1) * (ny >= 7) - 4 * nx * (14 <= ny < 33) - (2 * nx - 2) * (ny == 32)
    pre = pre_b10 - 2 * bw                               # pre byte position (wide band)
    pre = max(pre, len(s))                               # don't truncate decls when the declpair0 prefix (large lx0) overruns pre
    fg0pos = max(pre + 2, pre_b10 + 110 + 2 * (declpair0 - 59) - 2 * bn)  # fg0 (narrow band; floored at pre+2)
    s = pad_to(s, pre)
    s += bytes([preval_signed % 256, 0])
    s = pad_to(s, fg0pos)
    def grp(val, run): return bytes([val % 256, 1, run, 0x7e, 0x7e, 0x7e, run, 0])
    s += grp(CV + 19, h00)
    for j in range(ny): s += grp(33 - rInc(H[0], j), rDec(H[0], j))
    s += clgap; nspec = 0
    # innerX (gradual specials) = R_p[k] - min(R_p over contiguous gradual-special run)
    Rp = [max(p[k], p[k + 1]) if k < nx - 1 else p[nx - 1] for k in range(nx)]
    spc = [special(k) for k in range(nx)]
    innerXa = [0] * nx
    k = 0
    while k < nx:
        if spc[k] == 'grad':
            j = k
            while j < nx and spc[j] == 'grad': j += 1
            rmin = min(Rp[k:j])
            for i in range(k, j): innerXa[i] = Rp[i] - rmin
            k = j
        else: k += 1
    for k in range(nx):
        ec = EC(k)
        orun = max(H[k][0], H[k + 1][0]) if k < nx - 1 else H[nx - 1][0]
        oval = 164 - (p[0] if k == 0 else max(p[k - 1], p[k])) - 35 * (ny - 1)
        sp = spc[k]
        s += grp(oval, orun)
        if sp:
            nspec += 1
            stepsz = 0 if sp == 'plat' else abs(p[k + 1] - p[k])
            innerX = 1 if sp == 'plat' else innerXa[k]
            for j in range(ny - 1):
                s += grp(33 - rInc(ec, j), 0)
                s += grp(innerX, rDec(ec, j) - rDec(ec, j + 1) + stepsz)
            s += grp(33 - rInc(ec, ny - 1), rDec(ec, ny - 1))
        else:
            for j in range(ny): s += grp(33 - rInc(ec, j), rDec(ec, j))
        if k < nx - 1: s += clgap
    L = (pre_b10 + 110) + (1 + nx) * (1 + ny) * 8 + nx * (8 - 2 * (ny >= 6) - 2 * (12 <= ny < 33) - 2 * (14 <= ny < 33) - 4 * (ny == 32)) + (216 - 10 * (nx - 1)) + step + nspec * (ny - 1) * 8 - 2 * bw - 2 * bn - 4 * (14 <= ny < 32)
    return bytes(pad_to(s, max(L, len(s))))               # guard: ny=32 edge L must not truncate the last FG group


# ── CHUNK SEAM (x-axis) ─────────────────────────────────────────────────────
# When a surface crosses the lx=32 chunk boundary it produces TWO h3 chunks with
# a 2-column OVERLAP (LOD/mesh continuity). Byte-exact vs seam refs 2669/2673.
#   LOW side  (exits high edge): a normal (nx+1)-wide plate (1 forward ghost @lx32)
#                                -> just gen_heightmap_unified with +1 column.
#   HIGH side (enters low edge): gen_seam_high below. Decls = (R+2)-wide plate @lx-2
#     (lead = CV(lx-2)); FG groups = (R+1)-wide plate @lx-1 (opener = CV(lx-1)+19);
#     pre uses nx=R+2; fg0 anchors to declpair0(lx-1). R = #real columns in the chunk.
def gen_seam_high(R, ly0=10, lz0=10, h=1, ny=2, verts=None):
    """HIGH-side seam chunk for ANY ny, optionally carrying displacement. R = #real
    columns; verts = per-FG-group (V0,V1) offsets in emit order (None = flat).
    Byte-exact vs 2669/2673 (ny=2 flat) and SR1 2721 (ny=1 smooth ramp)."""
    CVm2 = (217 - 55 * (-2) + 35 * ly0 + lz0) % 256       # lead decl  = CV(lx-2)
    CVm1 = (217 - 55 * (-1) + 35 * ly0 + lz0) % 256       # opener base = CV(lx-1)
    dp_d = (153 * (-2) + 4 * ly0 + 322) // 32             # decl prefix (declpair0 @lx-2, C=322)
    dp_g = (153 * (-1) + 4 * ly0 + 322) // 32             # FG anchor   (declpair0 @lx-1, C=322)
    nxd = R + 2; nxg = R + 1
    bfs = 1 if (217 + 35 * ly0 + lz0) % 256 > 160 else 0  # align-jitter: CV(lx0=0, ly0) > 160
    def pad_to(s, t):
        while len(s) < t: s += bytes([255, 0])
        return s[:t]
    s = bytearray(bytes([0, 255]) * dp_d)
    for xi in range(nxd):
        if xi > 0: s += bytes([255, 0]) * (4 - (ny >= 7))  # decl x-gap shrink (3105)
        for yi in range(ny):
            if xi == 0 and yi == 0: s += bytes([0, CVm2, 1, 2, h - 1, 0])
            elif yi == 0: s += bytes([(200 - h - 35 * (ny - 1)) % 256, 1, 2, h - 1, 0])
            else: s += bytes([(34 - h) % 256, 1, 2, h - 1, 0])
    pre_nb = 340 + 3 * (nxd - 1) + 5 * nxd * (ny - 1) + 2 * ((nxd - 4) // 4) \
        - 2 * nxd * (ny >= 7)                             # (validated R=2,4,6 at ny=3; ny=13 by 3105: -2 per col incl lead)
    pre_nb = max(pre_nb, len(s))                          # don't truncate the last decl at large R (decl region overruns formula pre)
    s = pad_to(s, pre_nb)
    s += bytes([(120 - CVm2 - (h - 1) - 35 * (ny - 1) + 55 * (nxd - 1)) % 256, 0])
    fg0 = pre_nb + 110 + 2 * (dp_g - 59)
    s = pad_to(s, fg0)
    def grp(val, run): return bytes([val % 256, 1, run, 0x7e, 0x7e, 0x7e, run, 0])
    sgap = bytes([255, 0]) * (4 - (ny >= 6) - (12 <= ny < 32))  # FG cluster gap (3105 band)
    s += grp(CVm1 + 19, h)
    for j in range(ny): s += grp(33 - h, h)
    s += sgap
    for k in range(nxg):
        s += grp(164 - h - 35 * (ny - 1), h)
        for j in range(ny): s += grp(33 - h, h)
        if k < nxg - 1: s += sgap
    Lnb = fg0 + (1 + nxg) * (1 + ny) * 8 + nxg * (8 - 2 * (ny >= 6) - 2 * (12 <= ny < 32)) \
        + (322 - 10 * R) + 2 * ((nxd - 4) // 4) - 4 * (12 <= ny < 32) - 2 * (ny >= 7)  # + wide-plate floor-step trailing
    s = bytearray(pad_to(s, Lnb - 2 * ny * bfs))
    if verts:                                             # post-patch FG groups -> displaced
        grps = [i for i in range(len(s) - 7) if s[i+1] == 1 and s[i+3] == 0x7e
                and s[i+5] == 0x7e and s[i+7] == 0 and not (s[i+2] == 2 and s[i+4] == 0)]
        enc = lambda d: (d + 126) % 256; gmap = {grps[k]: verts[k] for k in range(len(verts))}
        out = bytearray(); i = 0
        while i < len(s):
            if i in gmap:
                V0, V1 = gmap[i]
                if V0 == ORIGIN and V1 == ORIGIN: out += s[i:i+8]
                else: out += bytes([s[i], 1, s[i+2], enc(V0[0]), enc(V0[1]), enc(V0[2]),
                                    0, enc(V1[0]), enc(V1[1]), enc(V1[2]), 0, 0])
                i += 8
            else: out += bytes([s[i]]); i += 1
        s = out
    return bytes(s)


def gen_middle_x(R=32, ly0=10, lz0=10, h=1, ny=1, verts=None):
    """MIDDLE x-chunk: a span that ENTERS the low edge AND EXITS the high edge of
    a chunk (the surface continues on both sides). = high-x seam (back-ghosts
    lx-2,-1) on the low edge + a forward ghost on the high edge. h3 chunks are
    always 32 voxels wide, so an INTERIOR middle carries exactly R=32 real columns
    (nxd=35 decls, nxg=34 FG clusters). R<32 is the CORE-EDGE high chunk (e.g. R=30
    for the high real chunk of a full-width fill, which back-ghosts on its low edge
    and forward-ghosts into the high-edge ghost chunk). The wide-plate floor-step
    (which gen_seam_high omits, being validated only at small R) is REQUIRED here
    because at large nxd the decl region overruns the un-stepped pre position.
    Byte-exact vs MID-1 2762 (9,8,8) at R=32/ny=1, FULLWIDTH 2777 (11,8,8) at
    R=30/ny=1, and MID2 2779 (9,8,8) at R=32/ny=2. Flat (no displacement) so far."""
    CVm2 = (217 - 55 * (-2) + 35 * ly0 + lz0) % 256       # lead decl  = CV(lx-2)
    CVm1 = (217 - 55 * (-1) + 35 * ly0 + lz0) % 256       # opener base = CV(lx-1)
    dp_d = (153 * (-2) + 4 * ly0 + 322) // 32
    dp_g = (153 * (-1) + 4 * ly0 + 322) // 32
    nxd = R + 2 + 1; nxg = R + 1 + 1                       # +1 forward ghost each
    step = 2 * ((nxd + 1) // 5) - 2 * (ny >= 2)            # wide floor-step (ny1->14, ny>=2->-2; validated ny=1,2,4)
    def pad_to(s, t):
        while len(s) < t: s += bytes([255, 0])
        return s[:t]
    s = bytearray(bytes([0, 255]) * dp_d)
    for xi in range(nxd):
        if xi > 0: s += bytes([255, 0]) * (4 - (ny >= 7) - 2 * (14 <= ny < 33) - (31 <= ny <= 32))  # decl x-gap band (ny=31/32 edge flush, 3151) (3105; ny=32 edge flush, 3114)
        for yi in range(ny):
            if xi == 0 and yi == 0: s += bytes([0, CVm2, 1, 2, h - 1, 0])
            elif yi == 0: s += bytes([(200 - h - 35 * (ny - 1)) % 256, 1, 2, h - 1, 0])
            else: s += bytes([(34 - h) % 256, 1, 2, h - 1, 0])
    pre_nb = 340 + 3 * (nxd - 1) + 5 * nxd * (ny - 1) + step - 2 * (nxd - 1) * (ny >= 7) - (4 * nxd + 2) * (14 <= ny < 32)
    bumped = len(s) > pre_nb                              # decl region overruns the formula pre (higher ly0, larger dp_d)
    pre_nb = max(pre_nb, len(s))                          # -> don't truncate the last decl
    if 31 <= ny <= 32: pre_nb = len(s)                    # ny=31/32 edge: decls flush into preval (3114/3151)
    s = pad_to(s, pre_nb)
    s += bytes([(120 - CVm2 - (h - 1) - 35 * (ny - 1) + 55 * (nxd - 1)) % 256, 0])
    fg0 = pre_nb + 110 + 2 * (dp_g - 59)
    s = pad_to(s, fg0)
    def grp(val, run): return bytes([val % 256, 1, run, 0x7e, 0x7e, 0x7e, run, 0])
    clgap = bytes([255, 0]) * (4 - (ny >= 6) - (12 <= ny < 33) - (14 <= ny < 33) - (31 <= ny <= 32))  # FG cluster gap (ny=31/32 edge flush, 3151)
    s += grp(CVm1 + 19, h)
    for j in range(ny): s += grp(33 - h, h)
    s += clgap
    for k in range(nxg):
        s += grp(164 - h - 35 * (ny - 1), h)
        for j in range(ny): s += grp(33 - h, h)
        if k < nxg - 1: s += clgap
    Lnb = fg0 + (1 + nxg) * (1 + ny) * 8 + nxg * (8 - 2 * (ny >= 6) - 2 * (12 <= ny < 33) - 2 * (14 <= ny < 33) - 2 * (31 <= ny <= 32)) \
        + (322 - 10 * R) + step - 10 - 4 * bumped - 4 * (12 <= ny < 32) - 2 * (14 <= ny < 32) - 4 * (31 <= ny <= 32)
    Lnb = max(Lnb, len(s))                                # never truncate real FG content (large-ny band under-sizes)
    s = bytearray(pad_to(s, Lnb))
    if verts:                                             # post-patch FG groups -> displaced (same as gen_seam_high)
        grps = [i for i in range(len(s) - 7) if s[i+1] == 1 and s[i+3] == 0x7e
                and s[i+5] == 0x7e and s[i+7] == 0 and not (s[i+2] == 2 and s[i+4] == 0)]
        enc = lambda d: (d + 126) % 256; gmap = {grps[k]: verts[k] for k in range(len(verts))}
        out = bytearray(); i = 0
        while i < len(s):
            if i in gmap:
                V0, V1 = gmap[i]
                if V0 == ORIGIN and V1 == ORIGIN: out += s[i:i+8]
                else: out += bytes([s[i], 1, s[i+2], enc(V0[0]), enc(V0[1]), enc(V0[2]),
                                    0, enc(V1[0]), enc(V1[1]), enc(V1[2]), 0, 0])
                i += 8
            else: out += bytes([s[i]]); i += 1
        s = out
    return bytes(s)


# ── CORE-EDGE GHOST CHUNKS ───────────────────────────────────────────────────
# When a fill reaches a chunk boundary at the core's low edge, or the core's high
# edge, DU emits a minimal GHOST chunk beyond the real range (the LOD-overlap
# representation of the surface continuing off the filled region). Byte-exact vs
# FULLWIDTH 2777 chunk 3 (low ghost) and chunk 12 (high ghost). ny=1 flat only;
# CV values validated at ly0=lz0=10 (structure fixed, values scale with CV).
def gen_low_ghost(ly0=10, lz0=10, h=1):
    """Low-edge ghost chunk (below the low real chunk). lead = CV(lx0=0)+32."""
    AB = lambda n: bytes([0, 255]) * n; BA = lambda n: bytes([255, 0]) * n
    G = lambda v: bytes([v % 256, 1, h, 126, 126, 126, h, 0])
    CV = (217 + 35 * ly0 + lz0 + 32) % 256
    return (AB(164) + bytes([0, CV, 1, 2, h - 1]) + AB(3) + bytes([0, 23]) + AB(159)
            + bytes([0]) + G(CV + 19) + G(33 - h) + BA(4) + G(164 - h) + G(33 - h) + BA(3))


def gen_high_ghost(ly0=10, lz0=10, h=1):
    """High-edge ghost chunk (above the high real chunk). lead = CV(lx-2)."""
    AB = lambda n: bytes([0, 255]) * n
    G = lambda v: bytes([v % 256, 1, h, 126, 126, 126, h, 0])
    CVm2 = (217 + 110 + 35 * ly0 + lz0) % 256; CVm1 = (217 + 55 + 35 * ly0 + lz0) % 256
    return (AB(1) + bytes([0, CVm2, 1, 2, h - 1]) + AB(165) + bytes([0, 201]) + AB(1)
            + bytes([0]) + G(CVm1 + 19) + bytes([33 - h, 1, h, 126, 126, 126, h]) + AB(165) + bytes([0]))


def gen_fullwidth_x(ly0=10, lz0=10, h=1):
    """FULL M-core-width flat fill in x (game -127.5..+126.5): 10 h3 chunks (3..12).
      3  = low-edge ghost                       (gen_low_ghost)
      4  = low real (32 real + fwd ghost, dstep=2 for the down-ghost)
      5-10 = 6 interior middle chunks           (gen_middle_x, R=32)
      11 = high real (both-sides middle, R=30)  (gen_middle_x R=30)
      12 = high-edge ghost                      (gen_high_ghost)
    Returns {(cx,cy,cz): scan}. Byte-exact vs FULLWIDTH 2777. ny=1 flat only."""
    cy = 8 + ly0 // 32; cz = 8 + lz0 // 32
    out = {(3, cy, cz): gen_low_ghost(ly0, lz0, h),
           (4, cy, cz): gen_heightmap_unified([[h]] * 33, lx0=0, ly0=ly0, lz0=lz0, dstep=2),
           (11, cy, cz): gen_middle_x(30, ly0=ly0, lz0=lz0, h=h, ny=1),
           (12, cy, cz): gen_high_ghost(ly0, lz0, h)}
    for cx in range(5, 11):
        out[(cx, cy, cz)] = gen_middle_x(32, ly0=ly0, lz0=lz0, h=h, ny=1)
    return out


def gen_terrain_smooth_x(corner_z, gx, ly0=10, lz0=10, h=1, ny=1):
    """SMOOTH multi-chunk terrain crossing ANY number of x-boundaries. corner_z =
    per x-grid-line top-vertex z-offset (len = total_cells + 1), extruded uniformly
    in y (ny cells deep). gx = global voxel x of the footprint's low corner.
    Splits the profile into low chunk (fwd ghost) -> middle chunk(s) (both-sides
    ghost) -> high seam, with SHARED GHOST columns (adjacent chunks overlap in the
    profile). Returns {(cx,cy,cz): scan}. Byte-exact vs SMID2 2783 (3-chunk z-ramp).
    ny=1 validated; heightmap-style displacement (V0=origin, V1=(0,0,dz))."""
    ncells = len(corner_z) - 1
    bx = 32 * ((gx // 32) + 1)
    n_left = bx - gx                                       # cells in low chunk
    cxl = 8 + gx // 32; cxh = 8 + (gx + ncells - 1) // 32
    n_right = (gx + ncells) - 32 * ((gx + ncells - 1) // 32)  # cells in high chunk
    M = cxh - cxl - 1                                      # number of middle chunks
    lx = gx % 32; cy = 8 + ly0 // 32; cz = 8 + lz0 // 32
    def vts(dzs):                                          # per x-line dz -> (ny+1) verts/line
        v = []
        for dz in dzs:
            for _ in range(ny + 1):
                v.append((ORIGIN, ORIGIN) if dz == 0 else (ORIGIN, (0, 0, dz)))
        return v
    if cxh == cxl:                                         # no boundary: single displaced chunk
        return {(cxl, cy, cz): gen_surface_displaced([[h] * ny] * ncells,
                vts(corner_z), lx0=lx, ly0=ly0, lz0=lz0)}
    out = {(cxl, cy, cz): gen_surface_displaced([[h] * ny] * (n_left + 1),
            vts(corner_z[0:n_left + 2]), lx0=lx, ly0=ly0, lz0=lz0)}
    for j in range(M):                                     # middle chunks (32 real cols each)
        st = (n_left - 1) + j * 32
        out[(cxl + 1 + j, cy, cz)] = gen_middle_x(32, ly0=ly0, lz0=lz0, h=h, ny=ny,
                                                  verts=vts(corner_z[st:st + 35]))
    hst = (n_left - 1) + M * 32
    out[(cxh, cy, cz)] = gen_seam_high(n_right, ly0=ly0, lz0=lz0, h=h, ny=ny,
                                       verts=vts(corner_z[hst:]))
    return out


def gen_terrain_smooth_2d(corner_z, gx, ly0=10, lz0=10, h=1):
    """SMOOTH multi-chunk terrain with a FULL 2D offset grid (varies in both x and y).
    corner_z = [x-line][y-line] grid: (ncells_x+1) x-lines, each a list of (ny+1)
    top-vertex z-offsets. Crosses any number of x-boundaries (low -> middle(s) ->
    high) with shared ghost columns; each x-line carries its own y-profile. Generalises
    gen_terrain_smooth_x (which extrudes a 1D profile uniformly in y). Byte-exact vs
    SMID2Dy 2795 (y-slope, ny=4). Emit order x-outer / y-inner, each corner independent."""
    ncells = len(corner_z) - 1; ny = len(corner_z[0]) - 1
    bx = 32 * ((gx // 32) + 1); n_left = bx - gx
    cxl = 8 + gx // 32; cxh = 8 + (gx + ncells - 1) // 32
    n_right = (gx + ncells) - 32 * ((gx + ncells - 1) // 32)
    M = cxh - cxl - 1; lx = gx % 32; cy = 8 + ly0 // 32; cz = 8 + lz0 // 32
    def vts(xlines):                                      # each x-line = list of (ny+1) dz
        v = []
        for yprof in xlines:
            for dz in yprof:
                v.append((ORIGIN, ORIGIN) if dz == 0 else (ORIGIN, (0, 0, dz)))
        return v
    if cxh == cxl:
        return {(cxl, cy, cz): gen_surface_displaced([[h] * ny] * ncells,
                vts(corner_z), lx0=lx, ly0=ly0, lz0=lz0)}
    out = {(cxl, cy, cz): gen_surface_displaced([[h] * ny] * (n_left + 1),
            vts(corner_z[0:n_left + 2]), lx0=lx, ly0=ly0, lz0=lz0)}
    for j in range(M):
        st = (n_left - 1) + j * 32
        out[(cxl + 1 + j, cy, cz)] = gen_middle_x(32, ly0=ly0, lz0=lz0, h=h, ny=ny,
                                                  verts=vts(corner_z[st:st + 35]))
    hst = (n_left - 1) + M * 32
    out[(cxh, cy, cz)] = gen_seam_high(n_right, ly0=ly0, lz0=lz0, h=h, ny=ny,
                                       verts=vts(corner_z[hst:]))
    return out


def gen_terrain_smooth_grid(grid, gx, gy, lz0=10, h=1):
    """SMOOTH 2D terrain over a full chunk grid, crossing ANY number of x-boundaries
    AND (up to) one y-boundary. grid = [x-line][y-line] top-vertex z-offsets
    ((ncells_x+1) x-lines, each (ncells_y+1) y-offsets). Composes the 6-way chunk grid:
    y-low row [corner-low | x-middle(s) | x-high] with a y-forward-ghost, and y-high row
    [x-fwd-ghost y-seam | corner-middle(s) | 2-axis corner]. Shared ghost columns AND
    rows (adjacent slices overlap). Byte-exact vs SMID2AX 2825. Falls back to
    gen_terrain_smooth_2d when there's no y-boundary."""
    ncells = len(grid) - 1; ny = len(grid[0]) - 1
    bx = 32 * ((gx // 32) + 1); by = 32 * ((gy // 32) + 1)
    ycross = gy < by <= gy + ny - 1
    cxl, cyl = 8 + gx // 32, 8 + gy // 32
    cxh = 8 + (gx + ncells - 1) // 32
    lx, ly = gx % 32, gy % 32; cz = 8 + lz0 // 32
    def vts(xslice, y0, y1):                              # per (x-line, y-line) verts, x-outer/y-inner
        v = []
        for xl in xslice:
            for yl in range(y0, y1):
                dz = xl[yl]
                v.append((ORIGIN, ORIGIN) if dz == 0 else (ORIGIN, (0, 0, dz)))
        return v
    if not ycross or (gy + ny) > by + 32:                # no y-boundary (or multi-y unsupported)
        return gen_terrain_smooth_2d([grid[x] for x in range(len(grid))], gx, ly0=ly, lz0=lz0, h=h)
    nL = bx - gx; Rx = (gx + ncells) - 32 * ((gx + ncells - 1) // 32)
    nLy = by - gy; Ry = (gy + ny) - by; M = cxh - cxl - 1
    hst = (nL - 1) + M * 32
    out = {}
    # y-LOW row (y-forward-ghost -> ny=nLy+1; y-lines [0 : nLy+2])
    out[(cxl, cyl, cz)] = gen_surface_displaced([[h] * (nLy + 1)] * (nL + 1),
        vts(grid[0:nL + 2], 0, nLy + 2), lx0=lx, ly0=ly, lz0=lz0)
    for j in range(M):
        st = (nL - 1) + j * 32
        out[(cxl + 1 + j, cyl, cz)] = gen_middle_x(32, ly0=ly, lz0=lz0, h=h, ny=nLy + 1,
                                                   verts=vts(grid[st:st + 35], 0, nLy + 2))
    out[(cxh, cyl, cz)] = gen_seam_high(Rx, ly0=ly, lz0=lz0, h=h, ny=nLy + 1,
                                        verts=vts(grid[hst:], 0, nLy + 2))
    # y-HIGH row (y-seam back-ghost, Ry real rows; y-lines [nLy-1 : ny+1])
    out[(cxl, cyl + 1, cz)] = gen_seam_high_y(Ry, nL + 1, lx0=lx, lz0=lz0, h=h,
        x_fwd_ghost=True, verts=vts(grid[0:nL + 2], nLy - 1, ny + 1))
    for j in range(M):
        st = (nL - 1) + j * 32
        out[(cxl + 1 + j, cyl + 1, cz)] = gen_corner_middle(Ry, lz0=lz0, h=h,
                                                            verts=vts(grid[st:st + 35], nLy - 1, ny + 1))
    out[(cxh, cyl + 1, cz)] = gen_corner_hh(Rx, Ry, lz0=lz0, h=h,
                                            verts=vts(grid[hst:], nLy - 1, ny + 1))
    return out


def gen_terrain_smooth_y(corner_z, gy, nx=1, lx0=10, lz0=10, h=1):
    """SMOOTH multi-chunk terrain crossing ANY number of Y-boundaries (row-direction
    mirror of gen_terrain_smooth_x). corner_z = per y-grid-line top-vertex z-offset
    (len = total_rows+1), uniform across the nx columns. gy = global voxel y of the
    footprint's low corner. Splits into low chunk (fwd ghost) -> y-middle(s) -> high
    y-seam with shared ghost rows. Byte-exact vs SMIDY 2789 (3-chunk z-ramp along Y).
    nx=1 validated (matches gen_middle_y scope)."""
    nrows = len(corner_z) - 1
    by = 32 * ((gy // 32) + 1)
    n_low = by - gy                                        # rows in low-y chunk
    cyl = 8 + gy // 32; cyh = 8 + (gy + nrows - 1) // 32
    n_high = (gy + nrows) - 32 * ((gy + nrows - 1) // 32)  # rows in high-y chunk
    M = cyh - cyl - 1                                      # number of y-middle chunks
    ly_start = gy % 32; cx = 8 + lx0 // 32; cz = 8 + lz0 // 32
    def vts(dzs):                                          # (nx+1) x-lines, uniform in x
        v = []
        for _ in range(nx + 1):
            for dz in dzs:
                v.append((ORIGIN, ORIGIN) if dz == 0 else (ORIGIN, (0, 0, dz)))
        return v
    if cyh == cyl:
        return {(cx, cyl, cz): gen_surface_displaced([[h] * nrows] * nx,
                vts(corner_z), lx0=lx0, ly0=ly_start, lz0=lz0)}
    out = {(cx, cyl, cz): gen_surface_displaced([[h] * (n_low + 1)] * nx,
            vts(corner_z[0:n_low + 2]), lx0=lx0, ly0=ly_start, lz0=lz0)}
    for j in range(M):
        st = (n_low - 1) + j * 32
        out[(cx, cyl + 1 + j, cz)] = gen_middle_y(nx=nx, lx0=lx0, lz0=lz0, h=h,
                                                  verts=vts(corner_z[st:st + 35]))
    hst = (n_low - 1) + M * 32
    out[(cx, cyh, cz)] = gen_seam_high_y(n_high, nx, lx0=lx0, lz0=lz0, h=h,
                                         verts=vts(corner_z[hst:]))
    return out


def gen_terrain_xramp(corner_z, n_left, ny=1, ly0=10, lz0=10, h=1):
    """A continuous smooth surface (ny cells deep) crossing the lx=32 x-seam.
    corner_z = per x-grid-line z-offset (len = total_cells + 1, extruded uniformly
    in y); n_left = cells in the low chunk.
    Returns {0: low_scan, 1: high_scan}. Both chunks share the overlap offsets.
    Byte-exact vs SR1 2721 (corner_z=[0,-21,-42,-63,-84], n_left=2)."""
    ncells = len(corner_z) - 1; n_right = ncells - n_left
    left_lx = 32 - n_left
    def vts(dzs):
        v = []
        for dz in dzs:
            for _ in range(ny + 1):                       # (ny+1) y-grid-lines per x-line
                v.append((ORIGIN, ORIGIN) if dz == 0 else (ORIGIN, (0, 0, dz)))
        return v
    low = gen_surface_displaced([[h] * ny] * (n_left + 1), vts(corner_z[:n_left + 2]),
                                lx0=left_lx, ly0=ly0, lz0=lz0)
    high = gen_seam_high(n_right, ly0=ly0, lz0=lz0, h=h, ny=ny,
                         verts=vts(corner_z[n_left - 1:]))
    return {0: low, 1: high}


# ── VERTEX DISPLACEMENT (smooth surfaces: wedge / ramp / sphere) ─────────────
# Each surface corner-group holds up to TWO stacked vertices (bottom V0, top V1)
# at that footprint position. Flat = the inert [7e 7e 7e, run2, 00]; displaced =
# [V0(dx,dy,dz), 00, V1(dx,dy,dz), 00, 00]. Offsets are byte-126 per axis:
# 126 = origin, range +-126, cube edge = 84 steps (so +-42 = half cell, the wedge).
# Byte-exact vs W1/W3/W4 (2679/2683/2685) and 2687 (full 8-corner manip).
ORIGIN = (0, 0, 0)


def gen_voxel_displaced(corners, lx0=10, ly0=10, lz0=10, h=1):
    """One deformed surface voxel. `corners` = list of 4 (V0, V1) for the footprint
    corners in order [(-X,-Y), (-X,+Y), (+X,-Y), (+X,+Y)]; V0 = bottom corner,
    V1 = top corner; each V = (dx,dy,dz) offset (ORIGIN = no move). Range +-126."""
    b = gen_heightmap_unified([[h]], lx0=lx0, ly0=ly0, lz0=lz0)
    grps = [i for i in range(len(b) - 7)
            if b[i+1] == 1 and b[i+3] == 0x7e and b[i+5] == 0x7e and b[i+7] == 0
            and not (b[i+2] == 2 and b[i+4] == 0)]
    assert len(grps) == 4, f"expected 4 corner groups, got {len(grps)}"
    enc = lambda d: (d + 126) % 256
    gmap = {grps[k]: corners[k] for k in range(4)}
    out = bytearray(); i = 0
    while i < len(b):
        if i in gmap:
            V0, V1 = gmap[i]
            if V0 == ORIGIN and V1 == ORIGIN:
                out += b[i:i+8]                                   # flat, unchanged
            else:
                out += bytes([b[i], 1, b[i+2],
                              enc(V0[0]), enc(V0[1]), enc(V0[2]), 0,
                              enc(V1[0]), enc(V1[1]), enc(V1[2]), 0, 0])
            i += 8
        else:
            out += bytes([b[i]]); i += 1
    return bytes(out)


# Wedge presets: low-side corners drop (horizontal +-42, dz -42); ridge stays flat.
# Orientation = which way it slopes DOWN. Corner order [(-X,-Y),(-X,+Y),(+X,-Y),(+X,+Y)].
WEDGE = {
    '+x': [ORIGIN_ := (ORIGIN, ORIGIN), ORIGIN_, (ORIGIN, (-42, 0, -42)), (ORIGIN, (-42, 0, -42))],
    '-x': [(ORIGIN, (42, 0, -42)), (ORIGIN, (42, 0, -42)), ORIGIN_, ORIGIN_],
    '-y': [(ORIGIN, (0, 42, -42)), ORIGIN_, (ORIGIN, (0, 42, -42)), ORIGIN_],
    '+y': [ORIGIN_, (ORIGIN, (0, -42, -42)), ORIGIN_, (ORIGIN, (0, -42, -42))],
}


def gen_wedge(direction='+x', lx0=10, ly0=10, lz0=10):
    """A single wedge voxel sloping DOWN toward `direction` (+x/-x/+y/-y)."""
    return gen_voxel_displaced(WEDGE[direction], lx0=lx0, ly0=ly0, lz0=lz0)


# ── SMOOTH SURFACES (continuous displacement) ───────────────────────────────
# Displacement is a property of GRID CORNERS (vertices), not cells: an nx*ny
# footprint has (nx+1)*(ny+1) corners = exactly the FG-group count, and adjacent
# cells SHARE a corner's offset (stored once). So a smooth surface = the heightmap
# framework + one (V0_bottom, V1_top) offset per corner-group (emit order =
# column-major: x0(y0..yN), x1(y0..yN), ...). Byte-exact vs ramps 2689(x)/2691(y).
def gen_surface_displaced(H, verts, lx0=10, ly0=10, lz0=10):
    """H = heightmap (base surface); verts = list of (V0,V1) per FG group/grid corner
    in emit order; each V = (dx,dy,dz) offset (ORIGIN = no move). Range +-126, cube 84."""
    b = gen_heightmap_unified(H, lx0=lx0, ly0=ly0, lz0=lz0)
    grps = [i for i in range(len(b) - 7)
            if b[i+1] == 1 and b[i+3] == 0x7e and b[i+5] == 0x7e and b[i+7] == 0
            and not (b[i+2] == 2 and b[i+4] == 0)]
    assert len(grps) == len(verts), f"{len(grps)} groups vs {len(verts)} verts"
    enc = lambda d: (d + 126) % 256
    gmap = {grps[k]: verts[k] for k in range(len(verts))}
    out = bytearray(); i = 0
    while i < len(b):
        if i in gmap:
            V0, V1 = gmap[i]
            if V0 == ORIGIN and V1 == ORIGIN:
                out += b[i:i+8]
            else:
                out += bytes([b[i], 1, b[i+2],
                              enc(V0[0]), enc(V0[1]), enc(V0[2]), 0,
                              enc(V1[0]), enc(V1[1]), enc(V1[2]), 0, 0])
            i += 8
        else:
            out += bytes([b[i]]); i += 1
    return bytes(out)


def gen_linear_ramp(ncells, drop_cells=1, ny=1, lx0=10, ly0=10, lz0=10):
    """A continuous linear smooth ramp: `ncells` cells long (x), dropping
    `drop_cells` over the run, `ny` cells deep. Each grid corner's top vertex
    drops V1.z = -(84*drop/ncells)*i (sheared/parallelogram). Byte-exact vs 2700."""
    per = 84.0 * drop_cells / ncells
    verts = []
    for i in range(ncells + 1):
        dz = round(-per * i)
        for _ in range(ny + 1):
            verts.append((ORIGIN, ORIGIN) if dz == 0 else (ORIGIN, (0, 0, dz)))
    H = [[1] * ny for _ in range(ncells)]
    return gen_surface_displaced(H, verts, lx0=lx0, ly0=ly0, lz0=lz0)


def gen_smooth_surface(corner_z, lx0=10, ly0=10, lz0=10):
    """Arbitrary smooth heightmap. corner_z = (nx+1) x (ny+1) grid of top-vertex
    z-offsets in 84-steps (<=0 = down, 84 = one voxel). Offsets compose ADDITIVELY
    per corner (x-slope + y-slope), confirmed in-game. Byte-exact vs 2700 + the 3x3
    diagonal tilt; the tilt rendered perfectly as a flat plane (novel, un-referenced)."""
    nx = len(corner_z) - 1
    ny = len(corner_z[0]) - 1
    verts = []
    for i in range(nx + 1):
        for j in range(ny + 1):
            dz = corner_z[i][j]
            verts.append((ORIGIN, ORIGIN) if dz == 0 else (ORIGIN, (0, 0, dz)))
    H = [[1] * ny for _ in range(nx)]
    return gen_surface_displaced(H, verts, lx0=lx0, ly0=ly0, lz0=lz0)


def gen_terrain_2dseam(corner_z, n_left, ly0=10, lz0=10, h=1):
    """A continuous smooth surface sloping in BOTH x and y while crossing the lx=32
    x-seam. corner_z[i][j] = z-offset at x-grid-line i, y-grid-line j
    (len = (total_cells+1) x (ny+1)); n_left = cells in the low chunk. Both chunks
    share the overlap. Byte-exact vs SR1/flat-seam in their uniform-y forms."""
    ncells = len(corner_z) - 1; n_right = ncells - n_left
    ny = len(corner_z[0]) - 1; left_lx = 32 - n_left
    def vts(rows):
        v = []
        for row in rows:
            for dz in row:
                v.append((ORIGIN, ORIGIN) if dz == 0 else (ORIGIN, (0, 0, dz)))
        return v
    low = gen_surface_displaced([[h] * ny] * (n_left + 1), vts(corner_z[:n_left + 2]),
                                lx0=left_lx, ly0=ly0, lz0=lz0)
    high = gen_seam_high(n_right, ly0=ly0, lz0=lz0, h=h, ny=ny,
                         verts=vts(corner_z[n_left - 1:]))
    return {0: low, 1: high}


def _fg0(g):
    """First FG group offset (flat 8-byte OR displaced 12-byte)."""
    i = 0
    while i <= len(g) - 8:
        if g[i+1] == 1 and g[i] not in (0, 255) and not (g[i+2] == 2 and g[i+4] == 0):
            if g[i+3] == 0x7e and g[i+5] == 0x7e and g[i+7] == 0: return i
            if i + 12 <= len(g) and g[i+6] == 0 and g[i+10] == 0 and g[i+11] == 0: return i
        i += 1
    return len(g)


def _fg_region(g):
    """Bytes of the FG-group region (fg0 .. last group end), flat or displaced groups."""
    f0 = _fg0(g); last = f0; i = f0
    while i <= len(g) - 8:
        if g[i+1] == 1 and g[i] not in (0, 255) and not (g[i+2] == 2 and g[i+4] == 0):
            if g[i+3] == 0x7e and g[i+5] == 0x7e and g[i+7] == 0: last = i + 8; i += 8; continue
            if i + 12 <= len(g) and g[i+6] == 0 and g[i+10] == 0 and g[i+11] == 0: last = i + 12; i += 12; continue
        i += 1
    return g[f0:last]


def gen_seam_high_y(R, nx, lx0=10, lz0=10, h=1, verts=None, x_fwd_ghost=False):
    """HIGH-side chunk of a Y-axis seam: nx real columns, R real ROWS, back-ghost
    rows ly-1,ly-2. Row-direction analog of gen_seam_high. Decls from nx x (R+2)
    plate @ly-2 (lead CV(ly-2)); FG from nx x (R+1) plate @ly-1 (opener CV(ly-1)+19),
    optionally displaced via verts. Byte-exact vs YS1 2729; smooth hardware-validated.
    x_fwd_ghost=True (this y-seam is the x-LOW chunk of a multi-x 2D patch, so its top
    x-column is a forward ghost): suppresses the ybfs align-jitter (byte-exact vs MID2AX
    2808 (8,9,8) at lx0=30; the ybfs=1 branch was unvalidated and mis-fires at high lx0)."""
    base_decl = gen_heightmap_unified([[h] * (R + 2)] * nx, lx0=lx0, ly0=-2, lz0=lz0)
    base_fg = (gen_surface_displaced([[h] * (R + 1)] * nx, verts, lx0=lx0, ly0=-1, lz0=lz0)
               if verts else gen_heightmap_unified([[h] * (R + 1)] * nx, lx0=lx0, ly0=-1, lz0=lz0))
    fgr = _fg_region(base_fg)
    ybfs = 0 if x_fwd_ghost else (1 if (217 - 55 * lx0 + lz0) % 256 < 160 else 0)  # y-seam align-jitter: CV(lx0, ly=0) < 160
    de = 0; i = 0                                          # last decl end in base_decl
    while i < len(base_decl) - 5:
        if base_decl[i+1] == 1 and base_decl[i+2] == 2 and base_decl[i+4] == 0 and base_decl[i] not in (0, 255):
            de = i + 5; i += 5
        else: i += 1
    head = base_decl[:de] + (bytes([255, 0]) if ybfs else b"") + base_decl[de:_fg0(base_decl)]
    s = bytearray(head + fgr)
    Ltot = len(base_decl) - len(_fg_region(base_decl)) + len(fgr) + 4 * ybfs
    while len(s) < Ltot: s += bytes([255, 0])
    return bytes(s[:Ltot])


def gen_corner_middle(Ry, lz0=10, h=1, verts=None):
    """CORNER-MIDDLE chunk: an x-MIDDLE that is also a y-SEAM-high (2D patch interior
    where an x-middle column meets a y-boundary). = the y-seam splice (like
    gen_seam_high_y) applied to gen_middle_x instead of gen_heightmap: decls from the
    x-middle at ny=Ry+2 rows @ly-2, FG from the x-middle at ny=Ry+1 rows @ly-1. Always
    R=32 x-columns (full x-middle). ybfs fires here (unlike the x-fwd-ghost y-seam).
    Byte-exact vs MID2AX 2808 (9,9,8) at Ry=2. Flat (verts wiring pending)."""
    base_decl = gen_middle_x(32, ly0=-2, lz0=lz0, h=h, ny=Ry + 2)
    base_fg = gen_middle_x(32, ly0=-1, lz0=lz0, h=h, ny=Ry + 1, verts=verts)
    fgr = _fg_region(base_fg)
    de = 0; i = 0
    while i < len(base_decl) - 5:
        if base_decl[i+1] == 1 and base_decl[i+2] == 2 and base_decl[i+4] == 0 and base_decl[i] not in (0, 255):
            de = i + 5; i += 5
        else: i += 1
    head = base_decl[:de] + (b'' if Ry == 30 else bytes([255, 0])) + base_decl[de:_fg0(base_decl)]  # ybfs=1 insertion (skipped @Ry=30: ny=32 decl already flushes, 3151)
    s = bytearray(head + fgr)
    Ltot = len(base_decl) - len(_fg_region(base_decl)) + len(fgr) + 4 + 2 - 2 * (13 <= Ry < 31) - 4 * (Ry == 30)  # +4 ybfs, +2 corner-middle; -2 band (Ry=24); Ry=30 no-ybfs (3151)
    while len(s) < Ltot: s += bytes([255, 0])
    return bytes(s[:Ltot])


def gen_double_middle(lz0=10, h=1, verts=None):
    """DOUBLE-MIDDLE chunk: an x-MIDDLE that is ALSO a y-MIDDLE (both-sides ghost in
    BOTH axes) -- the interior chunk of a landscape spanning >=3 chunks in each of x
    and y. = gen_corner_middle(Ry=33) (the y-seam splice of gen_middle_x at the
    y-middle's ny=35/34) with the y-middle forward-ghost transform: remove ALL the FG
    clgap 00ff-x3 AND decl-gap 00ff-x4 runs (the fwd ghost merges every gap). 35x35
    decls. Byte-exact vs MID2D33 2848 (9,9,8)."""
    g = bytearray(gen_corner_middle(33, lz0=lz0, h=h, verts=verts))
    runs = []; i = 0
    while i < len(g):
        if g[i:i+2] == bytes([0, 255]):
            j = i
            while g[j:j+2] == bytes([0, 255]): j += 2
            runs.append((i, (j - i) // 2)); i = j
        else: i += 1
    for a, n in sorted(runs, reverse=True):                # remove all 00ff-x3 and 00ff-x4 gaps
        if n in (3, 4): del g[a:a + 2 * n]
    return bytes(g)


def _abruns(g):
    r = []; i = 0
    while i < len(g):
        if g[i:i+2] == bytes([0, 255]):
            j = i
            while g[j:j+2] == bytes([0, 255]): j += 2
            r.append((i, (j - i) // 2)); i = j
        else: i += 1
    return r


def gen_ymid_xlow(nL, lx0, lz0=10, h=1, verts=None):
    """y-MIDDLE chunk at the x-LOW position (a y-middle whose top x-column is a forward
    ghost) -- the left edge of the y-middle row in a large 2D patch. = gen_middle_y at
    nx=nL+1, lx0, then grow the largest 00ff background run by 4 pairs and remove the two
    00ff-x4 decl gaps. Byte-exact vs 2848/2854/2856 (nL=2,4,6). nL even validated."""
    g = bytearray(gen_middle_y(nx=nL + 1, lx0=lx0, lz0=lz0, h=h, verts=verts))
    runs = _abruns(g); mx = max(n for _, n in runs); biggest = [a for a, n in runs if n == mx][0]
    ops = [(a, 'del') for a, n in runs if n == 4] + [(biggest, 'grow')]
    for a, kind in sorted(ops, reverse=True):
        if kind == 'del': del g[a:a + 8]
        else: g[a:a] = bytes([0, 255]) * 4
    return bytes(g)


def gen_ymid_xhigh(Rx, lz0=10, h=1, verts=None):
    """y-MIDDLE chunk at the x-HIGH position (a y-middle that also back-ghosts the x-seam)
    -- the right edge of the y-middle row. = gen_corner_hh(Rx, 33) then remove the (2Rx+2)
    00ff-x3 clgaps and shrink the two big background runs to T = 158 - 5*Rx + (Rx>=6).
    Byte-exact vs 2848/2850/2852 (Rx=2,4,6). Rx even validated (odd/Rx>6 untested)."""
    g = bytearray(gen_corner_hh(Rx, 33, lz0=lz0, h=h, verts=verts))
    runs = _abruns(g); T = 158 - 5 * Rx + (Rx >= 6) + 2 * ((Rx + 1) // 12) + (Rx == 30)  # 2nd term Rx=24 (3105); +1 @Rx=30 (3151 east col)
    big2 = sorted([(n, a) for a, n in runs], reverse=True)[:2]
    ops = [(a, 2 * (n - T)) for n, a in big2] + [(a, 6) for a, n in runs if n == 3]
    for a, cnt in sorted(ops, reverse=True): del g[a:a + cnt]
    return bytes(g)


def gen_middle_y(nx=1, lx0=10, lz0=10, h=1, verts=None):
    """MIDDLE y-chunk: a span that ENTERS the low-y edge AND EXITS the high-y edge
    (surface continues on both sides in Y). Row-direction analog of gen_middle_x.
    h3 chunks are always 32 rows, so a y-middle carries R=32 real rows. Content is
    byte-identical to gen_seam_high_y(R+1=33); the forward-ghost row only reshapes
    PADDING: remove the (2*nx-1) FG clgap 00ff-x3 runs (the forward ghost merges them)
    and shrink the two long background 00ff runs by 4 pairs each -- EXCEPT nx=4, which
    shrinks 3 pairs (the fwd ghost shifts gen_heightmap's wide-plate floor-step one nx
    earlier, so base steps at nx=5 but the y-middle steps at nx=4). Byte-exact vs MIDY-NX
    nx=1..8 (2787/2830/2844/2846/2836/2838/2840/2842; the nx=3 CV jitter in the original
    2832 was a build slip, disproven by rebuild 2844). nx>8: floor-step may recur."""
    g = bytearray(gen_seam_high_y(33, nx, lx0=lx0, lz0=lz0, h=h, verts=verts))
    runs = []; i = 0                                       # maximal 00ff runs (start, pairs)
    while i < len(g):
        if g[i:i+2] == bytes([0, 255]):
            j = i
            while g[j:j+2] == bytes([0, 255]): j += 2
            runs.append((i, (j - i) // 2)); i = j
        else: i += 1
    mx = max(n for _, n in runs)
    shrink = 8 - 2 * (nx == 4)                             # bytes: 4 pairs (3 at the nx=4 floor-step)
    ops = sorted([(a, shrink) for a, n in runs if n == mx] +   # two long bg runs
                 [(a, 6) for a, n in runs if n == 3], reverse=True)  # (2nx-1) FG clgaps removed
    for a, cnt in ops: del g[a:a + cnt]
    return bytes(g)


def gen_terrain_yramp(corner_z, n_low, nx, lx0=10, lz0=10, h=1):
    """A continuous smooth surface (nx cols wide) crossing the lx-fixed Y-seam at
    y=32. corner_z = per y-grid-line z-offset (len = total_rows+1, uniform in x);
    n_low = rows in the low-y chunk. Returns {0: low_scan, 1: high_scan}."""
    nrows = len(corner_z) - 1; R = nrows - n_low; ly_start = 32 - n_low
    def vts(dzs):
        v = []
        for _ in range(nx + 1):                       # x-grid-lines (uniform in x)
            for dz in dzs:
                v.append((ORIGIN, ORIGIN) if dz == 0 else (ORIGIN, (0, 0, dz)))
        return v
    low = gen_surface_displaced([[h] * (n_low + 1)] * nx, vts(corner_z[:n_low + 2]),
                                lx0=lx0, ly0=ly_start, lz0=lz0)
    high = gen_seam_high_y(R, nx, lx0=lx0, lz0=lz0, h=h, verts=vts(corner_z[n_low - 1:]))
    return {0: low, 1: high}


def gen_seam_high_z(R, lx0=10, ly0=10, nx=1, ny=1):
    """UPPER chunk of a Z-axis seam: a column (nx x ny footprint) tall enough to span
    z=32, with R real voxels above the boundary + back-ghost voxels at lz-1,lz-2.
    Same splice as gen_seam_high, applied to the column HEIGHT: decls from height R+2
    @lz-2 (lead CV(lz-2)); FG from height R+1 @lz-1 (opener CV(lz-1)+19). Byte-exact
    vs ZS1 2733. (Lower chunk is just gen_heightmap_unified([[n_low+1]] footprint, base lz.)"""
    base_decl = gen_heightmap_unified([[R + 2] * ny] * nx, lx0=lx0, ly0=ly0, lz0=-2)
    base_fg = gen_heightmap_unified([[R + 1] * ny] * nx, lx0=lx0, ly0=ly0, lz0=-1)
    fgr = _fg_region(base_fg)
    s = bytearray(base_decl[:_fg0(base_decl)] + fgr)
    Ltot = len(base_decl) - len(_fg_region(base_decl)) + len(fgr)
    while len(s) < Ltot: s += bytes([255, 0])
    return bytes(s[:Ltot])


def _flat_groups(s):
    """Start indices of 8-byte flat FG groups [val,1,run,7e,7e,7e,run,0] in the FG region."""
    f0 = _fg0(s); gs = []; i = f0
    while i <= len(s) - 8:
        if s[i+1] == 1 and s[i+3] == 0x7e and s[i+5] == 0x7e and s[i+7] == 0 \
           and s[i] not in (0, 255) and not (s[i+2] == 2 and s[i+4] == 0):
            gs.append(i); i += 8
        else: i += 1
    return gs


def _zgrp(val, run): return bytes([val % 256, 1, run, 0x7e, 0x7e, 0x7e, run, 0])


def _first_decl(s):
    """Index of the first declaration [val,1,2,h-1,0] (val not 0/255)."""
    i = 0
    while i < len(s) - 4:
        if s[i+1] == 1 and s[i+2] == 2 and s[i+4] == 0 and s[i] not in (0, 255):
            return i
        i += 1
    return None


def _seam_nx_step(g, nx):
    """z=0 seams follow the OLD //4 floor-step boundary (one column earlier than the
    heightmap's fixed //5). units = (nx-1)//4 - (nx-1)//5 extra pad pairs: one [255,0]
    at the decl end + one at the tail per unit. +4 bytes at nx=5,9,10..; 0 elsewhere.
    Confirmed nx=5 (2996/3000 both +4) vs nx=6 (2998 exact); nx<=4 unaffected."""
    units = (nx - 1) // 4 - (nx - 1) // 5
    if not units:
        return g
    g = bytearray(g)
    de = _last_decl_end(g)
    g[de:de] = bytes([255, 0]) * units
    g += bytes([255, 0]) * units
    return bytes(g)


def _seam_z_value_nudge(g, gs, depth, sign=+1):
    """Depth-scaled base-position value correction for a z=0 seam chunk. The z=0
    seam's first-decl / preval / first-opener shift with depth (a normal heightmap's
    don't). dep = depth-2 (0 at depth-2 => no-op, preserving the depth-2 baseline).
    LOW uses sign=+1 (first-decl -dep, preval +dep, opener -dep); HIGH mirrors."""
    dep = depth - 2
    if dep == 0:
        return
    fd = _first_decl(g); f0 = _fg0(g)
    g[fd]     = (g[fd]     - sign * dep) % 256          # first declaration value
    g[f0-110] = (g[f0-110] + sign * dep) % 256          # preval
    g[f0]     = (g[f0]     - sign * dep) % 256          # first FG opener


# ── z=0 OCTANT SEAM (positive/negative Z half-spaces meet at z=0) ───────────────
# Distinct from gen_seam_high_z (which crosses the INTRA-octant z=32 boundary). A
# solid patch straddling z=0 -> two chunks: HIGH (cz=8, +Z side) and LOW (cz=7, -Z).
# Each chunk's z-depth = its own real layer count + 1 boundary ghost (2-cell overlap).
# Depth-generalized (2x2): byte-exact vs known-position game exports 2986 (d2) /
# 2983 (d3) / 2988 (d4), BOTH chunks. LOW = base heightmap(H=depth,cz_neg) + mirror
# interior transform + value nudge(+-dep). HIGH: depth-2 is a degenerate special form
# (extra (0,0) filler, ghost val 31, h-1=depth-1); depth>=3 uses decls@H=depth+1 +
# FG@H=depth + constant first-decl-1/preval+1. (Archive 2906/2935/2937/2910 are at an
# UNKNOWN base position -> not byte oracles; see EXPORTS_LOG.md.)
def gen_seam_z_high(nx, ny, lx0=10, ly0=10, depth=2, opp_depth=None,
                    x_fwd_ghost=False, y_fwd_ghost=False):
    """+Z chunk of a z=0 seam. depth = (#real +Z layers) + 1 ghost. opp_depth = the
    LOW side's depth (= #real -Z layers + 1); defaults to depth (symmetric straddle).
    The HIGH form is COUPLED to the LOW side's real-layer count (low_real = opp_depth-1):
      - low_real == 1 (opp_depth<=2): DEGENERATE form. FG@H=depth (runs=depth), decls
        h-1=depth-1, interior x-cols = (val,0)+(inner,0)+(real) with inner=depth-2.
      - low_real >= 2: CLEAN form. FG@H=depth with mirror interior transform (ghost rows
        -> (33,run0), last stays real); decls from H=depth+1 (declares the overlap cell
        -> h-1=depth); constant first-decl -1 / preval +1.
    x_fwd_ghost: xz-corner rule (A) for the -x (cx=7) chunk -- its forward ghost
    column makes the LAST cluster special too (special range 1..nx instead of
    1..nx-1). y_fwd_ghost: the yz-corner analog for the -y (cy=7) chunk -- its
    forward ghost ROW makes ALL content rows of special clusters take the
    filler form (k range ny instead of ny-1; pinned by 3077 (8,7,8)). Both
    validated in the degenerate branch only (2945/2947/3077, depth=2).
    Byte-exact vs 2986(d2)/2983(d3)/2988(d4) symmetric + 2990(3x3) + 2992(3up/1down asym)."""
    if opp_depth is None:
        opp_depth = depth
    sp_hi = nx if x_fwd_ghost else nx - 1
    if opp_depth <= 2:                                    # LOW side <=1 real layer -> degenerate
        inner = depth - 2
        g = gen_heightmap_unified([[depth] * ny] * nx, lx0=lx0, ly0=ly0, lz0=-1)
        gs = _flat_groups(g); f0 = _fg0(g)
        gvals = [(g[i], g[i+2]) for i in gs]; per = 1 + ny
        clgap = bytes([255, 0]) * (4 - (ny >= 6))
        fg = bytearray(); idx = 0
        krng = ny if y_fwd_ghost else ny - 1
        for c in range(nx + 1):
            ov, orr = gvals[idx]; idx += 1; fg += _zgrp(ov, orr)
            content = gvals[idx:idx + ny]; idx += ny
            if 1 <= c <= sp_hi:                           # interior: (val,0)+(inner,0) filler
                for k in range(krng):
                    fg += _zgrp(content[k][0], 0) + _zgrp(inner, 0)
                for k in range(krng, ny):
                    fg += _zgrp(*content[k])
            else:
                for v, r in content: fg += _zgrp(v, r)
            if c < nx: fg += clgap
        return _seam_nx_step(bytes(g[:f0]) + bytes(fg) + bytes(g[gs[-1] + 8:]), nx)
    # low_real >= 2: CLEAN form. FG runs = depth (mirror interior transform); decls from depth+1
    # (declares the overlap cell -> h-1 = depth); constant first-decl -1 / preval +1.
    gA = bytearray(gen_heightmap_unified([[depth] * ny] * nx, lx0=lx0, ly0=ly0, lz0=-1))
    gs = _flat_groups(gA); per = 1 + ny
    for c in range(1, sp_hi + 1):                         # interior (+ last if fwd-ghost) columns
        b = c * per
        for k in range(ny):
            gi = gs[b + 1 + k]
            if k < ny - 1:
                gA[gi] = 33; gA[gi+2] = 0; gA[gi+6] = 0   # ghost row -> 33, run 0
    gB = gen_heightmap_unified([[depth + 1] * ny] * nx, lx0=lx0, ly0=ly0, lz0=-1)
    fA = _fg0(gA); fB = _fg0(gB)
    out = bytearray(gB[:fB] + gA[fA:])
    fd = _first_decl(out)
    out[fd]     = (out[fd]     - 1) % 256                  # constant, depth>=3
    out[fB-110] = (out[fB-110] + 1) % 256
    return _seam_nx_step(bytes(out), nx)


def gen_seam_z_low(nx, ny, lx0=10, ly0=10, depth=2, lz0=31, x_fwd_ghost=False,
                   y_fwd_ghost=False):
    """-Z chunk of a z=0 seam (negative octant, cz_neg=True; lz0 = its own local z,
    31 for the Z=-0.5 layer). depth = (#real -Z layers) + 1 ghost. Interior x-columns
    do an IN-PLACE transform: first group run->0 (value kept); remaining groups value
    ->33 (up-facing ghost) with runs->0 except the last. Simpler than the HIGH side.
    x_fwd_ghost: xz-corner rule (A) -- the -x chunk's forward ghost column makes
    the LAST cluster special too (see gen_seam_z_high; pinned by 2945/2947).
    y_fwd_ghost: yz-corner analog -- the -y chunk's ghost ROW extends run->0 to
    the LAST row too (pinned by 3077 (8,7,7))."""
    g = bytearray(gen_heightmap_unified([[depth] * ny] * nx, lx0=lx0, ly0=ly0, lz0=lz0, cz_neg=True))
    gs = _flat_groups(g); per = 1 + ny
    for c in range(1, (nx + 1) if x_fwd_ghost else nx):   # interior (+ last if fwd-ghost)
        b = c * per
        for k in range(ny):
            gi = gs[b + 1 + k]
            if k == 0:
                if ny > 1:                                # first: run->0, value kept
                    g[gi+2] = 0; g[gi+6] = 0              # (ny=1: last-row rule wins, run kept; 3034)
            else:
                g[gi] = 33                                # up-facing ghost value
                if k < ny - 1 or y_fwd_ghost:
                    g[gi+2] = 0; g[gi+6] = 0              # run->0 except last (unless y-ghost)
    _seam_z_value_nudge(g, gs, depth)
    return _seam_nx_step(bytes(g), nx)


def gen_seam_z_low_varying(Ldepth, lx0=10, ly0=10, lz0=31):
    """-Z chunk of a z=0 seam with PER-COLUMN depth. Ldepth[xi][yi] = that column's
    depth (= #real -Z layers + 1 boundary ghost). Generalizes gen_seam_z_low's uniform
    in-place transform, everything keyed by diff = |Ldepth[c-1][0] - Ldepth[c][0]|:
    interior first group run -> |diff| (uniform: 0); later groups value -> 33-|diff|
    (uniform: 33). SIGNED step s(c) = Ldepth[c-1][0] - Ldepth[c][0] drives the rest:
    col c x-marker decl += s(c); interior opener c += min(0, s(c)) (negative part);
    final opener += max(0, s(nx-1)) (positive part of its adjacent step). Nudges split
    per column: first-decl & fg0 opener -= dep(col0), preval += dep(col_last)
    (dep = depth-2). Reduces exactly to gen_seam_z_low for uniform input. Byte-exact
    vs 3024 ([[5,5],[3,3]] descending) + 3026 ([[3,3],[4,4],[5,5]] ascending, nx=3).
    REPRESENTATION choice is WHOLE-CHUNK (3026): if ANY column extra >= 2, LOW carries
    ALL variation (incl extra=1 cols) and HIGH is plain uniform-min; if max extra == 1
    it folds into HIGH instead (3022) and LOW is min-uniform. DEFERRED: mixed
    ascend+descend steps (final-opener attribution), ny>2 varying-y LOW."""
    nx = len(Ldepth); ny = len(Ldepth[0])
    g = bytearray(gen_heightmap_unified(Ldepth, lx0=lx0, ly0=ly0, lz0=lz0, cz_neg=True))
    gs = _flat_groups(g); per = 1 + ny
    for c in range(1, nx):                                # interior columns
        diff = abs(Ldepth[c-1][0] - Ldepth[c][0])
        b = c * per
        for k in range(ny):
            gi = gs[b + 1 + k]
            if k == 0:
                g[gi+2] = diff; g[gi+6] = diff            # run -> diff (uniform: 0)
            else:
                g[gi] = (33 - diff) % 256                 # value -> 33-diff (uniform: 33)
                if k < ny - 1: g[gi+2] = 0; g[gi+6] = 0   # middle rows: run->0
    for c in range(1, nx):                                # interior opener: negative part
        s = Ldepth[c-1][0] - Ldepth[c][0]
        go = gs[c * per]
        g[go] = (g[go] + min(0, s)) % 256
    if nx >= 2:                                           # final opener: positive part
        s = Ldepth[nx-2][0] - Ldepth[nx-1][0]
        go = gs[nx * per]
        g[go] = (g[go] + max(0, s)) % 256
    decls = []; i = 0                                     # decl positions [val,1,2,d,0]
    while i < len(g) - 5:
        if g[i+1] == 1 and g[i+2] == 2 and g[i+4] == 0 and g[i] not in (0, 255):
            decls.append(i); i += 5
        else: i += 1
    for c in range(1, nx):                                # col c x-marker decl += signed step
        s = Ldepth[c-1][0] - Ldepth[c][0]
        di = decls[c * ny]
        g[di] = (g[di] + s) % 256
    dep0 = Ldepth[0][0] - 2; depL = Ldepth[-1][0] - 2     # per-column nudges
    f0 = _fg0(g)
    g[decls[0]] = (g[decls[0]] - dep0) % 256
    g[f0]       = (g[f0]       - dep0) % 256
    g[f0-110]   = (g[f0-110]   + depL) % 256
    return _seam_nx_step(bytes(g), nx)


def _split_fg_clusters(g):
    """Split the FG region of g into clusters (lists of 8-byte flat groups), separated
    by [255,0] gap runs. Trailing pad is dropped. Filler groups (val 0) are included."""
    f0 = _fg0(g); i = f0; clusters = []; cur = []
    while i < len(g) - 1:
        if g[i] == 255 and g[i+1] == 0:
            if cur: clusters.append(cur); cur = []
            i += 2
        elif i + 7 < len(g) and g[i+1] == 1 and g[i+3] == 0x7e and g[i+5] == 0x7e and g[i+7] == 0:
            cur.append(bytes(g[i:i+8])); i += 8
        else:
            i += 1
    if cur: clusters.append(cur)
    return f0, clusters


def gen_seam_z_high_varying(Hdepth, lx0=10, ly0=10):
    """CLEAN-form +Z chunk of a z=0 seam with PER-COLUMN depth (relief crossing z=0).
    Hdepth[xi][yi] = that column's depth (= #real +Z layers + 1 boundary ghost). The
    HIGH chunk = gen_heightmap_unified(Hdepth) with a UNIFIED value/run rule applied
    per 8-byte group index i within a cluster, over a sequence seq:
        value_i = 33 - (seq[0] if i == 0 else max(seq[i-1:]))  (SHIFTED bwd running max)
        run_i   = max(seq[i:])                                 (bwd running max)
    EDGE clusters: seq = the column profile, applied to content rows r>=1 (row 0 and
    all runs kept from the heightmap, which already matches). INTERIOR clusters:
    REBUILT as opener + (ny-1) markers + real last row (discarding the heightmap's
    relief filler); markers use seq = per-row diffs (diff(r) = |Hdepth[c-1][r] -
    Hdepth[c][r]|), last row uses the profile rule at r = ny-1. Interior profile =
    ADJACENT-pair max(col c-1, col c), not a running max from col0 (pinned by 3010).
    The SHIFTED-rDec value rule was pinned by 3020 (ny=4: diffs (3,2,1,0) -> markers
    (30,3),(30,2),(31,1); profile (5,4,3,2) content (28,5),(28,4),(29,3),(30,2));
    the earlier fwd-running-max hypothesis fit ny<=3 coincidentally. Decls from
    Hdepth+1 (declare overlap cell); constant first-decl -1 / preval +1; nx floor-step.
    Reduces to the uniform clean form at diff=0. Byte-exact vs 3004/3006/3008/
    3010(nx=3 desc)/3012(peak)/3014/3016(y-varying)/3018(ny=3 y-graded)/3020(ny=4
    y-staircase) + uniform 2983/2990. REQUIRES low_real >= 2 (clean form). DEFERRED
    (need builds): non-monotonic y-profiles at ny>=3 (y-peak/y-valley), valley nx>2,
    degenerate (low_real==1) varying."""
    nx = len(Hdepth); ny = len(Hdepth[0])
    gA = gen_heightmap_unified(Hdepth, lx0=lx0, ly0=ly0, lz0=-1)
    f0, clusters = _split_fg_clusters(gA)
    # cluster profiles: edge0 = col0; interior ci = elementwise max of the ADJACENT
    # col pair (ci-1, ci) -- NOT a running max from col0 (pinned by 3010 cluster2
    # last row (30,3) = max(col1,col2), not max(col0..col2)); final = last col
    prof = []
    for ci in range(nx + 1):
        if ci == 0: prof.append(list(Hdepth[0]))
        elif ci < nx:
            prof.append([max(a, b) for a, b in zip(Hdepth[ci-1], Hdepth[ci])])
        else: prof.append(list(Hdepth[nx - 1]))
    clgap = bytes([255, 0]) * (4 - (ny >= 6))
    fg = bytearray(); removed = 0
    for ci, cl in enumerate(clusters):
        P = prof[ci]
        if 1 <= ci <= nx - 1:                             # interior cluster -> rebuild
            diffs = [abs(Hdepth[ci-1][r] - Hdepth[ci][r]) for r in range(ny)]
            fg += cl[0]                                   # opener
            for k in range(ny - 1):                       # markers: shifted-rDec values
                val = diffs[0] if k == 0 else max(diffs[k-1:])
                fg += _zgrp(33 - val, max(diffs[k:]))
            last = bytearray(cl[-1])                      # real last row
            if ny >= 2:
                last[0] = (33 - max(P[ny-2:])) % 256
            fg += bytes(last)
            removed += (len(cl) - (ny + 1)) * 8           # discarded relief filler
        else:                                             # edge cluster: shift row values
            fg += cl[0]                                   # opener
            for r, grp in enumerate(cl[1:]):
                g2 = bytearray(grp)
                if r >= 1:
                    g2[0] = (33 - max(P[r-1:])) % 256     # value = rDec at prev row
                fg += bytes(g2)
        if ci < len(clusters) - 1: fg += clgap
    total = len(gA) - f0 - removed
    while len(fg) < total: fg += bytes([255, 0])
    fg = fg[:total]
    Hd1 = [[h + 1 for h in row] for row in Hdepth]        # decls declare the overlap cell
    gB = gen_heightmap_unified(Hd1, lx0=lx0, ly0=ly0, lz0=-1); fB = _fg0(gB)
    out = bytearray(gB[:fB] + bytes(fg))
    fd = _first_decl(out)
    out[fd]     = (out[fd]     - 1) % 256
    out[fB-110] = (out[fB-110] + 1) % 256
    return _seam_nx_step(bytes(out), nx)


# ── x=0 / y=0 OCTANT SEAMS (spatial column/row axes) ────────────────────────────
# Unlike z=0 (depth axis -> special clusters), a shape straddling x=0 or y=0 makes
# two chunks that are just PLAIN plates evaluated at the ghost position. NOTE
# 2026-07-03: the original minimal derivation (2941/2943 + _x0_jitter) is OBSOLETE —
# those exports are unknown-position and don't match under current (bw/bn-fixed) code.
# x=0 re-derived from known-position 3032/3036 (see gen_seam_x0_high/low below).
# y=0 still on the old model pending a fresh known-position reference.
def gen_seam_y0_high(n_real, nx=2, h=1, lx0=10, lz0=10):
    """+Y chunk (cy=8) of a y=0 seam: n_real real rows (y=0.5..) + 1 boundary ghost
    row. Same principle as z=0's clean form: the DECL region declares ONE EXTRA
    overlap row (from the (n_real+2)-row plate at ly0=-2 -- lead decl value becomes
    CV(ly0=-2), one extra 33 marker per column), while the FG region stays the
    (n_real+1)-row plate at ly0=-1; trailing pad pair trimmed. Byte-exact vs 3038
    (8,8,8) (n_real=2). VALIDATED at nx=2, h=1, n_real=2 only."""
    gB = gen_heightmap_unified([[h] * (n_real + 2)] * nx, lx0=lx0, ly0=-2, lz0=lz0)
    gA = gen_heightmap_unified([[h] * (n_real + 1)] * nx, lx0=lx0, ly0=-1, lz0=lz0)
    out = (gB[:_fg0(gB)] + gA[_fg0(gA):])[:-2]
    if h >= 2:
        out = _seam_y0_interior_fillers(out, n_real + 1, h, side='high')
    return out


def gen_seam_y0_low(n_real, nx=2, h=1, lx0=10, lz0=10):
    """-Y chunk (cy=7) of a y=0 seam: n_real real rows (ly 32-n_real..31) + 1 boundary
    ghost row = PLAIN (n_real+1)-row plate at ly0 = 32-n_real, no transform.
    Byte-exact vs 3038 (8,7,8) (n_real=2; CV=215>160 -- an x=0-LOW-style CV<=160
    band shift may exist here too, unprobed)."""
    g = gen_heightmap_unified([[h] * (n_real + 1)] * nx, lx0=lx0, ly0=32 - n_real, lz0=lz0)
    if h >= 2:
        g = _seam_y0_interior_fillers(g, n_real + 1, h, side='low')
    return g


def _seam_y0_interior_fillers(g, ny, h, side):
    """h>=2 transform for y=0 seam chunks (pinned by 3044, h=2): only the INTERIOR
    x-clusters transform (both edge clusters stay plain -- narrower than x=0's
    all-but-far-edge rule). Within a transformed cluster, each affected group ->
    run 0 + an (h-2, 0) filler appended:
      side='high': opener + rows 0..ny-2 affected, LAST row survives (the row
                   farthest from the seam; HIGH's ghost row is first).
      side='low' : opener survives, ALL rows 0..ny-1 affected (LOW's ghost row
                   is last). Filler value h-2 by analogy with x=0 (h=2 only probed)."""
    f0, clusters = _split_fg_clusters(g)
    n_cl = len(clusters)
    fg = bytearray()
    for ci, cl in enumerate(clusters):
        interior = 1 <= ci <= n_cl - 2
        if not interior:
            for grp in cl: fg += grp
        elif side == 'high':
            for k, grp in enumerate(cl):
                if k < len(cl) - 1:
                    g2 = bytearray(grp); g2[2] = 0; g2[6] = 0
                    fg += bytes(g2) + _zgrp(h - 2, 0)
                else:
                    fg += grp
        else:
            fg += cl[0]
            for grp in cl[1:]:
                g2 = bytearray(grp); g2[2] = 0; g2[6] = 0
                fg += bytes(g2) + _zgrp(h - 2, 0)
        if ci < n_cl - 1: fg += bytes([255, 0]) * 4
    orig = bytearray()
    for ci, cl in enumerate(clusters):
        for grp in cl: orig += grp
        if ci < n_cl - 1: orig += bytes([255, 0]) * 4
    return g[:f0] + bytes(fg) + g[f0 + len(orig):]


def _seam_x0_decl_third(g, h):
    """x=0-seam-specific (3042, h=3): ALL declarations' third byte = max(2, h)
    (plain heightmaps and z=0 seams keep 2 at any h; only x=0 seam chunks flip).
    Matches decls as [val,1,2,d,0] with val not 0/255 and rewrites in place."""
    if h <= 2:
        return g
    g = bytearray(g); i = 0
    while i < len(g) - 5:
        if g[i+1] == 1 and g[i+2] == 2 and g[i+4] == 0 and g[i] not in (0, 255):
            g[i+2] = max(2, h); i += 5
        else:
            i += 1
    return bytes(g)


def _seam_x0_interior_fillers(g, ny, h, far_edge):
    """h>=2 transform for x=0/y=0 seam chunks (pinned by 3040): every FG cluster
    EXCEPT the far-edge one (the only true edge in the cross-chunk sense; 'last'
    for the +side chunk, 'first' for the -side) takes the z=0-degenerate-style
    interior form: each of the first ny-1 content rows -> run 0 + an (h-2, 0)
    filler group appended. At h=2 the filler value is 0; the h-2 scaling is
    z=0-analogous but only h=2 is validated."""
    f0, clusters = _split_fg_clusters(g)
    n_cl = len(clusters)
    skip = n_cl - 1 if far_edge == 'last' else 0
    fg = bytearray()
    for ci, cl in enumerate(clusters):
        fg += cl[0]
        if ci != skip:
            for k, grp in enumerate(cl[1:]):
                if k < ny - 1:
                    g2 = bytearray(grp); g2[2] = 0; g2[6] = 0
                    fg += bytes(g2) + _zgrp(h - 2, 0)
                else:
                    fg += grp
        else:
            for grp in cl[1:]: fg += grp
        if ci < n_cl - 1: fg += bytes([255, 0]) * 4
    # preserve the original trailing pad verbatim (fillers extend length; no absorption)
    orig = bytearray()
    for ci, cl in enumerate(clusters):
        for grp in cl: orig += grp
        if ci < n_cl - 1: orig += bytes([255, 0]) * 4
    trail = g[f0 + len(orig):]
    return g[:f0] + bytes(fg) + trail


def gen_seam_x0_high(n_real, ny=2, h=1, ly0=10, lz0=10):
    """+X chunk (cx=8) of an x=0 seam: n_real real cols (x=0.5..) + 1 boundary ghost
    col. = plain (n_real+1)-wide plate at lx0=-1, with a WIDTH-INVARIANT head
    transform (pinned by 3032 n_real=2 / 3036 n_real=3): prepend the leading
    ghost-decl block [0,255,0, CV(lx0=-2),1,2,h-1,0, 33,1,2,h-1] after which 2 pad
    pairs are dropped, and first-decl value += 44. VALIDATED at ny=2, h=1 only
    (the +44 and block layout may scale with ny/h -- needs builds)."""
    g = gen_heightmap_unified([[h] * ny] * (n_real + 1), lx0=-1, ly0=ly0, lz0=lz0)
    if h >= 2:
        g = _seam_x0_interior_fillers(g, ny, h, far_edge='last')
    d2 = max(2, h)                                        # decl 3rd byte: 2 at h<=2, h above (3042)
    cvm2 = (217 - 55 * (-2) + 35 * ly0 + lz0) % 256
    block = bytes([0, 255, 0, cvm2, 1, d2, h - 1, 0, (33 - (h - 1)) % 256, 1, d2, h - 1])
    fd = _first_decl(g)                                   # g[fd] = first decl value
    xmark = (200 - h - 35 * (ny - 1)) % 256               # standard x-marker (was '+44')
    out = block + g[:fd - 4] + bytes([xmark]) + g[fd + 1:]
    return _seam_x0_decl_third(out, h)


def gen_seam_x0_low(n_real, ny=2, h=1, ly0=10, lz0=10):
    """-X chunk (cx=7) of an x=0 seam: n_real real cols (lx 32-n_real..31) + 1
    boundary ghost col = plain (n_real+1)-wide plate at lx0 = 32-n_real. CV-band
    jitter: iff CV(lx0) <= 160, move one pad pair from the tail to the head
    (3036 lx0=29 CV=6 needs it; 3032 lx0=30 CV=207 does not). Band edge at 160
    assumed from the bw band -- only 2 CV points probed."""
    lx0 = 32 - n_real
    g = gen_heightmap_unified([[h] * ny] * (n_real + 1), lx0=lx0, ly0=ly0, lz0=lz0)
    if h >= 2:
        g = _seam_x0_interior_fillers(g, ny, h, far_edge='first')
    g = _seam_x0_decl_third(g, h)
    CV = (217 - 55 * lx0 + 35 * ly0 + lz0) % 256
    if CV <= 160:
        g = bytearray(g)
        f0 = _fg0(g)
        g[f0:f0] = bytes([255, 0]); del g[-2:]            # fg0 +2, tail absorbs
        fd = _first_decl(g); de = _last_decl_end(g)
        g[fd:fd] = bytes([255, 0])                        # pre +2 ...
        del g[de+2:de+4]                                  # ... absorbed after decl run
        g = bytes(g)
    return g


def _last_decl_end(s):
    de = 0; i = 0
    while i < len(s) - 5:
        if s[i+1] == 1 and s[i+2] == 2 and s[i+4] == 0 and s[i] not in (0, 255):
            de = i + 5; i += 5
        else: i += 1
    return de


# ── x=0 seam with VARYING per-column height (relief crossing / near the seam) ──
# Derivation refs 3048 (sym hump 1,2|2,1) / 3050 (step-2 hump 1,3|3,1) /
# 3052 (step AT boundary 2,2|1,1) / 3054 (step 2 cols out 2,1,1|1,1,1).
# Against the correct VARYING plain baseline the refs decompose cleanly:
#   chunk = plain varying plate (heights incl ghost col = across-boundary col's
#   height) + the known uniform head / CV-band transforms + a per-cluster FG
#   rewrite (fillers by neighbor rule, boundary cluster optionally 16-byte
#   THREE-VERTEX "transition" form when relief steps 1 col from the seam).
# KEY FACTS pinned by the 4 refs:
#   * HIGH's head block + first-decl x-marker are parameterized by hB = the
#     height of the column at x=-1.5, TWO out across the boundary (3052 HIGH:
#     own cols h1 but block d=1 / first-decl 163 from the h2 across the seam;
#     rejects min- and far-col-hypotheses). Matches the conceptual model
#     "HIGH's decl region = that of the (n+2)-plate @lx0=-2" whose first col
#     is x=-1.5; the plain-plate x-marker value tracks the PREVIOUS column:
#     200 - h(prev) - 35*(ny-1).
#   * Filler rule: cluster gets the run0+(hc-2,0) filler form iff own hc >= 2
#     AND both neighbor clusters' heights >= own; far-edge cluster exempt;
#     missing outer neighbor of the ghost cluster counts as own. Reduces to
#     the uniform all-but-far-edge rule. Explains 3052 LOW c2 "unexpectedly
#     plain" (next cluster h1 < own h2).
#   * 16-byte form is NOT an extra cluster (earlier note compared against the
#     uniform baseline): the ghost cluster's own groups convert 8B -> 16B,
#     1:1, same values/runs. Group = [val,1,run, T0,s0, T1,s1, T2,s2, 0] with
#     T = (7e,7e,7e+dz), dz in sixths-of-voxel units (84/voxel):
#       HIGH ghost cluster: ALL rows TRI; dz = +14 opener/last row, +42 middle
#         row(s); s2 = hc-2, s1 = 0. No fillers (TRI overrides).
#       LOW ghost cluster: opener + LAST row TRI dz=+14 with s1 = hc-2, s2=0;
#         middle rows stay flat and take the filler rule as usual.
#     (h-2 slot position is SIDE-DEPENDENT -- pinned by 3050 h3; at h2 all
#     s-slots are 0 and 3048 couldn't distinguish. Memory's "final byte=h-2"
#     was the wrong slot.)
#   * TRI trigger: the OPPOSITE side's boundary pair DESCENDS away across
#     the seam (opp[0] > opp[1]) -- the chunk renders the backside slope of
#     the neighbor's drop-off. Direction pinned by valley 3058 (1,2|2,1:
#     opp pairs ASCEND away -> NO transition geometry at all, both chunks);
#     side pinned by one-sided 3056 (1,1|2,1: HIGH with own-pair step came
#     back plain, LOW with the opposite-side step carried the TRI cluster --
#     exact inverse of the own-pair hypothesis). 3048/3050 (both descend ->
#     both TRI) and 3052/3054 (no 1-out step -> none) fit.
#   * HIGH's ghost EDGE cluster is really the interior-pair cluster of the
#     TWO across-boundary columns: height = max(hB, ghost), not ghost
#     (pinned by 3058: h2 cluster over a h1 ghost col whose decl stays d0;
#     next opener shifts with it via the 129 - prev_cluster_h chain). The
#     hump refs masked this (max == ghost there). LOW has NO mirror rule --
#     3058 LOW is byte-exact plain (outer across-boundary col ignored).
#   * decl-third (3042 h3 flip): 3050 has h3 cols yet ALL decl thirds stay 2
#     -> the flip keys on the BOUNDARY WINDOW's min height (own pair + opp
#     pair), not the max. max(2, wmin) fits 3040/3042/3050; provisional.
# ny=3 VALIDATED (3060): HIGH TRI middles = +42 each, LOW TRI middles =
# filler'd flat each, head block gains one 33-marker per extra row (full
# ny-entry column decl group). UNVALIDATED: h >= 4, n_real >= 4, ny >= 4.
def _x0_tri16(val, run, dz, hc, side):
    """16-byte three-vertex transition group. h-2 slot: s2 for HIGH, s1 for LOW."""
    T = bytes([0x7e, 0x7e, 0x7e]); T1 = bytes([0x7e, 0x7e, (0x7e + dz) % 256])
    s = max(hc - 2, 0)
    if side == 'high':
        return bytes([val, 1, run]) + T + b'\0' + T1 + b'\0' + T + bytes([s, 0])
    return bytes([val, 1, run]) + T + b'\0' + T1 + bytes([s]) + T + b'\0\0'


def _parse_fg_clusters(g):
    """Parse the FG region: clusters of 8B flat groups separated by [255,0]
    runs. Returns (fg0, clusters, gap pad-pair counts, trailing-bytes offset)."""
    f0 = _fg0(g)
    i = f0; clusters = []; gaps = []; cur = []; end = f0
    while i < len(g) - 7:
        if g[i+1] == 1 and g[i+3] == 0x7e and g[i+4] == 0x7e and g[i+5] == 0x7e and g[i+7] == 0:
            cur.append(bytes(g[i:i+8])); i += 8
        elif g[i] == 255 and g[i+1] == 0:
            n = 0
            while i < len(g) - 1 and g[i] == 255 and g[i+1] == 0:
                n += 1; i += 2
            if cur:
                clusters.append(cur); cur = []; gaps.append(n)
            end = i
        else:
            break
    if cur:
        clusters.append(cur); gaps.append(0); end = i
    trail_at = end - 2 * gaps[-1] if gaps else end   # trailing pad = last gap + rest
    return f0, clusters, gaps, trail_at


def _x0_rebuild_fg(g, plate, ny, side, tri, hB=None):
    """Rewrite the FG region of plain varying plate g (heights `plate`, incl the
    ghost col: first for side='high', last for side='low') into seam form:
    per-cluster fillers by the neighbor rule + optional 16B ghost cluster.
    Cluster values/pads are taken from g; runs are rebuilt as the cluster
    height hc (= own col for edge clusters, max of the adjacent pair for
    interior ones) -- matches every observed group. For side='high', hB
    (the x=-1.5 col across the boundary) raises the ghost EDGE cluster to
    max(hB, ghost): it is really the interior-pair cluster of the two
    across-boundary columns (pinned by valley 3058, where it renders h2 over
    a h1 ghost; the next opener shifts by the same delta via the 129-prev_h
    chain). LOW ignores its outer across-boundary column (3058 LOW is plain)."""
    nx = len(plate)
    hc = [plate[0]] + [max(plate[i-1], plate[i]) for i in range(1, nx)] + [plate[-1]]
    d0 = 0
    if side == 'high' and hB is not None and hB > plate[0]:
        d0 = plate[0] - max(hB, plate[0])                 # negative height delta
        hc[0] = max(hB, plate[0])
    ghost_ci, far_ci = (0, nx) if side == 'high' else (nx, 0)
    f0, clusters, gaps, trail_at = _parse_fg_clusters(g)
    assert len(clusters) == nx + 1, (len(clusters), nx)
    fg = bytearray()
    for ci, cl in enumerate(clusters):
        h = hc[ci]
        vals = [cl[0][0]] + [grp[0] for grp in cl[1:]
                             if not (grp[0] < 16 and grp[2] == 0 and grp[6] == 0)]
        assert len(vals) == ny + 1, (ci, vals)
        if d0:                                            # ghost-edge cluster raised to hc[0]
            if ci == 0:
                vals[1:] = [(v + d0) % 256 for v in vals[1:]]
            elif ci == 1:
                vals[0] = (vals[0] + d0) % 256            # opener follows 129-prev_h chain
        prev_h = hc[ci-1] if ci > 0 else h
        next_h = hc[ci+1] if ci < nx else h
        filler = ci != far_ci and h >= 2 and prev_h >= h and next_h >= h
        if ci == ghost_ci and tri:
            if side == 'high':                        # all rows TRI, +42 middles
                for k, v in enumerate(vals):
                    dz = 14 if k in (0, ny) else 42
                    fg += _x0_tri16(v, h, dz, h, side)
            else:                                     # ends TRI, middles flat+filler
                fg += _x0_tri16(vals[0], h, 14, h, side)
                for v in vals[1:ny]:
                    if filler: fg += _zgrp(v, 0) + _zgrp(h - 2, 0)
                    else:      fg += _zgrp(v, h)
                fg += _x0_tri16(vals[ny], h, 14, h, side)
        elif filler:
            fg += _zgrp(vals[0], h)
            for v in vals[1:ny]:
                fg += _zgrp(v, 0) + _zgrp(h - 2, 0)
            fg += _zgrp(vals[ny], h)
        else:
            for v in vals:
                fg += _zgrp(v, h)
        if ci < nx:
            fg += bytes([255, 0]) * gaps[ci]
    return g[:f0] + bytes(fg) + g[trail_at:]


def gen_seam_x0_high_varying(cols, opp, ny=2, ly0=10, lz0=10):
    """+X chunk (cx=8) of an x=0 seam with per-column heights. cols = own real
    column heights boundary-first [h(+0.5), h(+1.5), ...]; opp = the -X side's,
    boundary-first [h(-0.5), h(-1.5), ...] (only the first two are used: ghost
    col height + head parameter hB). Byte-exact vs 3048/3050/3052/3054/3056
    HIGH; reduces to gen_seam_x0_high for uniform input."""
    assert len(cols) >= 2 and len(opp) >= 2
    ghost, hB = opp[0], opp[1]
    plate = [ghost] + list(cols)
    g = gen_heightmap_unified([[h] * ny for h in plate], lx0=-1, ly0=ly0, lz0=lz0)
    g = _x0_rebuild_fg(g, plate, ny, 'high', tri=opp[0] > opp[1], hB=hB)
    wmin = min(cols[0], cols[1], opp[0], opp[1])      # decl-third window (provisional)
    d2 = max(2, wmin)
    cvm2 = (217 - 55 * (-2) + 35 * ly0 + lz0) % 256
    # block = full ny-entry column decl group of the hB ghost-ghost column
    # (one 33-marker per row beyond the first -- pinned by ny=3 build 3060);
    # its final trailing 0 is supplied by the plate's leading pad byte.
    block = bytes([0, 255, 0, cvm2, 1, d2, hB - 1, 0]) \
        + bytes([(33 - (hB - 1)) % 256, 1, d2, hB - 1, 0]) * (ny - 1)
    block = block[:-1]
    fd = _first_decl(g)
    xmark = (200 - hB - 35 * (ny - 1)) % 256
    out = block + g[:fd - 4] + bytes([xmark]) + g[fd + 1:]
    return _seam_x0_decl_third(out, wmin)


def gen_seam_x0_low_varying(cols, opp, ny=2, ly0=10, lz0=10):
    """-X chunk (cx=7) of an x=0 seam with per-column heights. cols = own real
    column heights boundary-first [h(-0.5), h(-1.5), ...]; opp = the +X side's,
    boundary-first (opp[0] = ghost col height). Plain varying plate at
    lx0 = 32-n_real + FG rewrite + the uniform CV<=160 band shift. Byte-exact
    vs 3048/3050/3052/3054/3056 LOW; reduces to gen_seam_x0_low for uniform
    input."""
    assert len(cols) >= 2 and len(opp) >= 2
    n_real = len(cols); lx0 = 32 - n_real
    plate = list(reversed(cols)) + [opp[0]]
    g = gen_heightmap_unified([[h] * ny for h in plate], lx0=lx0, ly0=ly0, lz0=lz0)
    g = _x0_rebuild_fg(g, plate, ny, 'low', tri=opp[0] > opp[1])
    wmin = min(cols[0], cols[1], opp[0], opp[1])
    g = _seam_x0_decl_third(g, wmin)
    CV = (217 - 55 * lx0 + 35 * ly0 + lz0) % 256
    if CV <= 160:
        g = bytearray(g)
        f0 = _fg0(g)
        g[f0:f0] = bytes([255, 0]); del g[-2:]        # fg0 +2, tail absorbs
        fd = _first_decl(g); de = _last_decl_end(g)
        g[fd:fd] = bytes([255, 0])                    # pre +2 ...
        del g[de+2:de+4]                              # ... absorbed after decl run
        g = bytes(g)
    return g


# ── y=0 seam with VARYING per-row height ──────────────────────────────────────
# Derived from 3062 (hump 1,2|2,1 across y=0) = the TRANSPOSE of the x=0
# varying rules. y=0 clusters run per-X (rows inside), and the seam-adjacent
# element within each cluster is the OPENER for HIGH (ghost row first) / the
# GHOST ROW for LOW (last). The 16B transition form (same byte layout as x=0,
# T1 offset still in the Z slot -- displacement is vertical) lands on that
# element, with the x-END/x-MIDDLE pattern transposed from x=0's y-ends/
# y-middles: HIGH openers get dz +14 at x-edge clusters, +42 at x-interior;
# LOW ghost rows get +14 at x-edge clusters and the plain filler form at
# x-interior. Fillers stay confined to x-INTERIOR clusters (uniform 3044
# rule) with per-row gates: HIGH rows (last exempt) two-sided neighbor rule
# like x=0 (prev>=own AND next>=own, row0's prev = across-boundary = own);
# LOW rows gate one-sided toward the seam (next(+y) >= own -- pinned by 3062
# LOW row1 whose -y neighbor is LOWER yet fillers anyway; two-sided is
# REJECTED there, an x=0/y=0 asymmetry). TRI trigger transposes directly:
# opp[0] > opp[1] (neighbor descends away). HIGH decls = varying (rows+2)-
# plate @ly0=-2 with profile [hB=h(-y1.5), ghost]+rows (the -35/ly0 shift in
# 3062's decl vals 119/94 pins the hB rule transposing too). VALLEY 3064
# pins the SEAM CHAIN RESET (see _y0_rebuild_fg): row (val, run) rebuilt
# over own rows only + standalone ghost row group + HIGH opener run
# max(hB, ghost); no transition geometry (directional trigger transposes).
# ONE-SIDED STEP 3066 confirms the trigger side transposes (HIGH plain, LOW
# TRI) and pins PAIRWISE row runs (see _y0_rebuild_fg). VALIDATED at nx=2,
# h<=2, ny=2 rows/side (hump 3062 + valley 3064 + one-sided 3066); s-slot at
# h>=3 assumed x=0-analogous (unprobed); no decl-third flip (x=0-specific
# per 3046); LOW CV<=160 band unprobed.
def _y0_rebuild_fg(g, prof, nx, side, tri, hB=None):
    """Rewrite the FG of plain varying y-plate g (y-profile `prof` incl ghost
    row: first for side='high', last for side='low') into y=0 seam form.
    Row (val, run) are REBUILT with the seam chain reset (pinned by valley
    3064; the hump's chains coincided with the plain plate's): plain y-plates
    encode val = 33 - fwd-running-max, run = bwd-running-max over the profile,
    but seam chunks run that chain over the OWN rows only. The ghost row group
    is standalone: HIGH (33 - max(hB, ghost), run=ghost) with the opener run
    raised to max(hB, ghost) (= x=0's across-boundary-pair rule transposed);
    LOW (33 - ghost, run=ghost), outer neighbor ignored (= x=0 LOW asymmetry).
    Opener values always keep the plate's own (position-dependent) bytes."""
    ny = len(prof)
    f0, clusters, gaps, trail_at = _parse_fg_clusters(g)
    assert len(clusters) == nx + 1, (len(clusters), nx)
    # per-group (val, run) specs; None val = keep baseline opener value.
    # SEAM chunks encode rows PAIRWISE (vs the plain plate's running maxes):
    #   val_j = 33 - max(h_j, h_prev)   (prev = -y neighbor; HIGH ghost's prev
    #                                    is hB across the seam; LOW row0's is own)
    #   run_j = max(h_j, h_next)        (next = +y neighbor; last row's is own)
    # Runs pinned by 3066 (one-sided step; plain bwd-max fails there). Values:
    # pairwise-prev fits every real ref byte; the earlier "own-rows-only chain
    # reset" reading was indistinguishable on refs (all had ghost >= boundary
    # row) and produced an INVALID-VERTEX deploy failure on the first config
    # where they differ (y0 import test B, own boundary taller than ghost --
    # its LOW deviated from the plain oracle plate by exactly that one byte).
    # HIGH far-row descent profiles still can't discriminate pairwise-prev
    # from a with-ghost fwd chain (both fit all refs) -- needs an oracle.
    runs = [max(prof[j], prof[j+1]) if j < ny - 1 else prof[j] for j in range(ny)]
    prev0 = hB if side == 'high' else prof[0]
    vals_ = [(33 - max(prof[j], prof[j-1] if j > 0 else prev0)) % 256
             for j in range(ny)]
    if side == 'high':
        specs = [(None, max(hB, prof[0]))] + list(zip(vals_, runs))
    else:
        specs = [(None, None)] + list(zip(vals_, runs))
    fg = bytearray()
    for ci, cl in enumerate(clusters):
        assert len(cl) == ny + 1, (ci, len(cl))
        edge = ci in (0, nx)
        vals = [cl[0][0] if sv is None else sv for (sv, _), _ in zip(specs, cl)]
        runs = [op_grp[2] if sr is None else sr
                for (_, sr), op_grp in zip(specs, cl)]
        if side == 'high':
            if tri:
                fg += _x0_tri16(vals[0], runs[0], 14 if edge else 42, prof[0], side)
            elif not edge and prof[0] >= 2:
                fg += _zgrp(vals[0], 0) + _zgrp(prof[0] - 2, 0)
            else:
                fg += _zgrp(vals[0], runs[0])
            for j in range(ny):
                h = prof[j]
                prev_h = prof[j-1] if j > 0 else h
                next_h = prof[j+1] if j < ny - 1 else h
                if j < ny - 1 and not edge and h >= 2 and prev_h >= h and next_h >= h:
                    fg += _zgrp(vals[j+1], 0) + _zgrp(h - 2, 0)
                else:
                    fg += _zgrp(vals[j+1], runs[j+1])
        else:
            fg += _zgrp(vals[0], runs[0])
            for j in range(ny):
                h = prof[j]
                next_h = prof[j+1] if j < ny - 1 else h
                if j == ny - 1 and tri and edge:
                    fg += _x0_tri16(vals[j+1], runs[j+1], 14, h, side)
                elif not edge and h >= 2 and next_h >= h:
                    fg += _zgrp(vals[j+1], 0) + _zgrp(h - 2, 0)
                else:
                    fg += _zgrp(vals[j+1], runs[j+1])
        if ci < nx:
            fg += bytes([255, 0]) * gaps[ci]
    return g[:f0] + bytes(fg) + g[trail_at:]


def gen_seam_y0_high_varying(rows, opp, nx=2, lx0=10, lz0=10):
    """+Y chunk (cy=8) of a y=0 seam with per-row heights. rows = own real row
    heights boundary-first [h(+0.5), h(+1.5), ...]; opp = the -Y side's,
    boundary-first (opp[0] = ghost row height, opp[1] = decl parameter hB).
    Byte-exact vs 3062 HIGH; reduces to gen_seam_y0_high for uniform input."""
    assert len(rows) >= 2 and len(opp) >= 2
    ghost, hB = opp[0], opp[1]
    prof = [ghost] + list(rows)
    gB = gen_heightmap_unified([[hB] + prof] * nx, lx0=lx0, ly0=-2, lz0=lz0)
    gA = gen_heightmap_unified([prof] * nx, lx0=lx0, ly0=-1, lz0=lz0)
    fA = _fg0(gA)                                     # before rebuild: TRI breaks _fg0
    gA = _y0_rebuild_fg(gA, prof, nx, 'high', tri=opp[0] > opp[1], hB=hB)
    return (gB[:_fg0(gB)] + gA[fA:])[:-2]


def gen_seam_y0_low_varying(rows, opp, nx=2, lx0=10, lz0=10):
    """-Y chunk (cy=7) of a y=0 seam with per-row heights. rows = own real row
    heights boundary-first [h(-0.5), h(-1.5), ...]; opp = the +Y side's
    (opp[0] = ghost row height). Plain varying plate at ly0 = 32-n_real + FG
    rewrite. Byte-exact vs 3062 LOW; reduces to gen_seam_y0_low uniform."""
    assert len(rows) >= 2 and len(opp) >= 2
    n_real = len(rows)
    prof = list(reversed(rows)) + [opp[0]]
    g = gen_heightmap_unified([prof] * nx, lx0=lx0, ly0=32 - n_real, lz0=lz0)
    return _y0_rebuild_fg(g, prof, nx, 'low', tri=opp[0] > opp[1])


# ── x=0 + z=0 SURFACE CORNER (B3) ────────────────────────────────────────────
# A solid slab straddling BOTH x=0 and z=0 -> 4 chunks. Derived 2026-07-02
# (refs 2945 2x3x2 / 2947 2x4x2, both depth 2); recipes re-verified byte-exact
# under the current (rewritten) z-seam code 2026-07-04. TWO composition rules:
#  (A) special-cluster SPREAD: the -x (cx=7) chunks' forward ghost column makes
#      the z-seam's LAST cluster special too (x_fwd_ghost=True -> range 1..nx);
#      +x (cx=8) chunks keep interior-only (1..nx-1).
#  (B) corner jitter (-4): drop one pad pair before the preval + one trailing
#      pair. Applied to +x+z, +x-z and -x+z, NOT to the double-negative -x-z
#      octant. (This jitter is CORNER-ONLY: plain x=0 seams use the rewritten
#      head/CV-band transforms in gen_seam_x0_*.)
def _x0_corner_jitter(g):
    """Octant-edge jitter for xz-corner chunks: drop one 00ff pad pair before
    the preval (pre/fg0 -2) and one trailing pair (L -4 total)."""
    g = bytearray(g); f0 = _fg0(g); pv = None
    for i in range(f0 - 2, 0, -2):
        if g[i+1] == 0 and g[i] not in (0, 255) and g[i] != 1:
            pv = i; break
    del g[pv-2:pv]; del g[-2:]
    return bytes(g)


def gen_corner_xz(ny, nx=2, depth=2, ly0=10):
    """All 4 chunks of an x=0+z=0 surface corner as {(cx,cy,cz): scan}. nx =
    plate width per chunk incl the x-ghost col (nx-1 real cols/side); depth =
    (#real z layers)+1 ghost per side. Byte-exact vs 2945 (ny=3) + 2947 (ny=4).
    VALIDATED at nx=2, depth=2 (degenerate z-form) only -- deeper/wider corners
    exercise the clean z-form + x_fwd_ghost combination, unprobed."""
    lo = 33 - nx                                          # -x side plate origin
    j = _x0_corner_jitter
    return {
        (8, 8, 8): j(gen_seam_z_high(nx, ny, lx0=-1, ly0=ly0, depth=depth)),
        (8, 8, 7): j(gen_seam_z_low(nx, ny, lx0=-1, ly0=ly0, depth=depth)),
        (7, 8, 8): j(gen_seam_z_high(nx, ny, lx0=lo, ly0=ly0, depth=depth, x_fwd_ghost=True)),
        (7, 8, 7): gen_seam_z_low(nx, ny, lx0=lo, ly0=ly0, depth=depth, x_fwd_ghost=True),
    }


# ── y=0 + z=0 SURFACE CORNER (B3) ────────────────────────────────────────────
# Derived 2026-07-04 from 3077 (3x2x2 slab straddling y=0 AND z=0). The xz
# rules transpose PARTIALLY:
#   * +y chunks compose with NO jitter at all ((8,8,8) = plain gen_seam_z_high
#     @ly0=-1 byte-exact) -- the x0 corner jitter is x-SPECIFIC.
#   * (8,8,7) +y-z instead takes a REVERSE jitter (+4): one pad pair inserted
#     before the preval and one appended at the tail.
#   * -y chunks: fwd-ghost rule transposes as y_fwd_ghost = the ghost ROW makes
#     ALL content rows of special clusters take the filler/run0 form (rows are
#     y's cluster-axis; cf. x_fwd_ghost extending over clusters).
#   * (8,7,7) double-negative: TWO extras on top of y_fwd_ghost --
#     (a) cluster openers AFTER the first special cluster get +2 (the surface
#         echo of the dense yz-edge "double-neg fill +2 after first fill");
#     (b) an x0-CV-band-style layout shift: pad pair -> before first decl
#         (absorbed from the pre-preval gap) + pad pair -> after the preval
#         (absorbed from the tail). Trigger condition unknown (1 data point;
#         x0's analog was CV<=160-gated).
def _yz_rev_jitter(g):
    """(8,8,7) +y-z corner transform: +4 -- one pad pair before the preval,
    one appended at the tail (inverse of _x0_corner_jitter). Pinned by 3077."""
    g = bytearray(g); f0 = _fg0(g); pv = None
    for i in range(f0 - 2, 0, -2):
        if g[i+1] == 0 and g[i] not in (0, 255) and g[i] != 1:
            pv = i; break
    g[pv:pv] = bytes([255, 0]); g += bytes([255, 0])
    return bytes(g)


def gen_corner_yz(nx, depth=2, lx0=10):
    """All 4 chunks of a y=0+z=0 surface corner as {(cx,cy,cz): scan}: nx x-cols,
    1 real y-row each side (+1 ghost row -> ny=2), depth = (#real z layers)+1
    ghost per side. Byte-exact vs 3077 (nx=3). VALIDATED at nx=3, depth=2,
    1 row/side only; the double-neg opener+2 range (clusters >= 2) and the
    layout-shift trigger are single-data-point assumptions."""
    ny = 2
    out = {
        (8, 8, 8): gen_seam_z_high(nx, ny, lx0=lx0, ly0=-1, depth=depth),
        (8, 8, 7): _yz_rev_jitter(gen_seam_z_low(nx, ny, lx0=lx0, ly0=-1, depth=depth)),
        (8, 7, 8): gen_seam_z_high(nx, ny, lx0=lx0, ly0=31, depth=depth, y_fwd_ghost=True),
    }
    g = bytearray(gen_seam_z_low(nx, ny, lx0=lx0, ly0=31, depth=depth, y_fwd_ghost=True))
    gs = _flat_groups(g); per = 1 + ny
    for c in range(2, nx + 1):                            # double-neg opener +2
        go = gs[c * per]
        g[go] = (g[go] + 2) % 256
    fd = _first_decl(g)                                   # layout shift (see header)
    g[fd:fd] = bytes([255, 0])
    f0 = _fg0(g); pv = None
    for i in range(f0 - 2, 0, -2):
        if g[i+1] == 0 and g[i] not in (0, 255) and g[i] != 1:
            pv = i; break
    del g[pv-2:pv]
    pv -= 2
    g[pv+2:pv+2] = bytes([255, 0])
    del g[-2:]
    out[(8, 7, 7)] = bytes(g)
    return out


# ── 3-PLANE (x=0+y=0+z=0) SURFACE CORNER ─────────────────────────────────────
# Solved 2026-07-04 against 2949 (2x2x2 origin box, 1 voxel/octant, 8 chunks).
# The 2026-07-02 attempt managed 1/8 with the pre-B2 models; with the current
# toolkit SIX octants are plain z-seam bases and two need small extras:
#   (8,8,7) (8,7,8) (7,8,8) (7,7,8) (7,8,7) = gen_seam_z_high/low at
#       lx0/ly0 in {-1, 31} with x_fwd_ghost=(cx==7), y_fwd_ghost=(cy==7).
#   (8,7,7) = base + last-cluster opener +2 (the yz double-neg rule, WITHOUT
#       3077's layout shift -- that shift is position/config-dependent).
#   (7,7,7) = base + drop the pad pair before the FG lead (fg0 -2) + last-
#       cluster opener +2.
#   (8,8,8) = built from the PLAIN plate @(-1,-1,lz0=-1): the base generator
#       is unusable here because the plate's bfs SPLIT LEAD (pad pair inside
#       the opener: 9f 00 ff 01 02 ...) corrupts the degenerate rebuild. The
#       real chunk UNSPLITS the lead (pad pair moves before the opener), takes
#       the standard z interior special on c1 (row run0 + (0,0) filler), drops
#       the head pad pair and appends one at the tail.
# NO jitter anywhere (the x0 corner jitter and yz reverse jitter are 2-plane
# artifacts, absent at the triple crossing). Validated at the minimal box only.
def gen_corner_xyz():
    """All 8 chunks of the 3-plane surface corner (minimal 2x2x2 origin box,
    1 voxel per octant) as {(cx,cy,cz): scan}. Byte-exact vs 2949 (8/8)."""
    out = {}
    for cx in (7, 8):
        for cy in (7, 8):
            kw = dict(lx0=-1 if cx == 8 else 31, ly0=-1 if cy == 8 else 31,
                      depth=2, x_fwd_ghost=cx == 7, y_fwd_ghost=cy == 7)
            if (cx, cy) != (8, 8):
                out[(cx, cy, 8)] = gen_seam_z_high(2, 2, **kw)
            g = bytearray(gen_seam_z_low(2, 2, **kw))
            if cy == 7:                                   # y-neg -z octants: opener +2
                gs = _flat_groups(g)
                go = gs[2 * 3]                            # last cluster opener
                g[go] = (g[go] + 2) % 256
            if (cx, cy) == (7, 7):
                f0 = _fg0(g)
                del g[f0-2:f0]                            # fg0 -2
            out[(cx, cy, 7)] = bytes(g)
    # (8,8,8): from the plain plate (split lead breaks the base generator here)
    g = bytearray(gen_heightmap_unified([[2, 2]] * 2, lx0=-1, ly0=-1, lz0=-1))
    for i in range(len(g) - 5):                           # unsplit the bfs lead
        if g[i] not in (0, 255) and g[i+1] == 0 and g[i+2] == 255 and g[i+3] == 1:
            g[i:i+3] = bytes([255, 0, g[i]])
            break
    gs = _flat_groups(g)                                  # z interior special on c1
    r0 = gs[1 * 3 + 1]                                    # c1 row0
    g[r0+2] = 0; g[r0+6] = 0
    g[r0+8:r0+8] = _zgrp(0, 0)
    del g[0:2]                                            # head -2
    g += bytes([255, 0])                                  # tail +2
    out[(8, 8, 8)] = bytes(g)
    return out


# ── SMOOTH DISPLACEMENT OVERLAY for seam chunks (END-GOAL arc) ───────────────
# Pinned by 3081 (in-game smooth tool applied to the 3048 hump across x=0):
# smoothing changes ONLY displacement slots -- cluster structure, values,
# runs, decls and pads are byte-identical to the blocky seam encoding. Three
# carriers, selected per group form:
#   * 16B TRI groups: displacement goes in the T2 vertex slot; T1 keeps the
#     blocky transition offset (+14/+42).
#   * flat 8B groups with run>0: expand to the 12B two-vertex form
#     [val,1,run, 7e,7e,7e, run-1, V1, 0,0] -- the +6 slot is run-1, which
#     also fits the old single-chunk refs (run 1 -> 0).
#   * (0,0) FILLER groups: in-place 8B displacement (slots +3..+5).
#   * run-0 content rows stay NEUTRAL (7e).
# In 3081 displacement is PER-CLUSTER uniform: bevel clusters (+-28,0,-40),
# hump-top interior (0,0,-16), far/h1 clusters neutral. The VALUE function
# (DU's smoothing vertex solve) is the remaining unknown of this arc.
def apply_seam_displacement(g, tri_T2=None, cluster_disp=None, vlist=None):
    """Overlay smooth displacement onto a generated seam chunk.
    tri_T2: {cluster_idx: (dx,dy,dz)} written into TRI groups' T2 slot;
    cluster_disp: {cluster_idx: (dx,dy,dz)} applied to that cluster's flat
    groups (run>0 -> 12B expansion, filler -> in-place, run-0 row -> neutral).
    vlist: PER-GROUP mode instead -- a sequence indexed in FG walk order
    (one entry per corner group; None = neutral). Filler groups do NOT
    consume an index and inherit the preceding row's V (3081 behavior);
    TRI groups consume an index (V -> T2 slot).
    Byte-exact: 3081 == overlay(gen_seam_x0_*_varying([2,1],[2,1])) in both
    modes (cluster map and the equivalent per-group vlist)."""
    enc = lambda d: (d + 126) % 256
    out = bytearray(); i = 0; cl = -1; started = False
    gi = 0; last_v = None
    def group_V(is_filler):
        nonlocal gi, last_v
        if vlist is not None:
            if is_filler:
                return last_v
            v = vlist[gi] if gi < len(vlist) else None
            gi += 1; last_v = v
            return v
        return None
    while i < len(g):
        if i+1 < len(g) and g[i] == 255 and g[i+1] == 0:
            n = 0
            while i+1 < len(g) and g[i] == 255 and g[i+1] == 0:
                out += g[i:i+2]; n += 1; i += 2
            if started and n >= 3:
                cl += 1
            continue
        is16 = (i+15 < len(g) and g[i+1] == 1 and g[i+3] == 0x7e and g[i+6] == 0
                and g[i+7] == 0x7e and g[i+10] == 0 and g[i+15] == 0
                and not (g[i+4] == 0x7e and g[i+5] == 0x7e and g[i+6] == g[i+2]
                         and g[i+7] == 0))
        is8 = (i+7 < len(g) and g[i+1] == 1 and g[i+3] == 0x7e and g[i+4] == 0x7e
               and g[i+5] == 0x7e and g[i+7] == 0 and g[i+6] == g[i+2])
        if is16:
            if not started: started = True; cl = 0
            grp = bytearray(g[i:i+16])
            T2 = group_V(False) if vlist is not None else (tri_T2 or {}).get(cl)
            if T2:
                grp[11], grp[12], grp[13] = enc(T2[0]), enc(T2[1]), enc(T2[2])
            out += grp; i += 16
        elif is8:
            if not started: started = True; cl = 0
            is_filler = g[i+2] == 0 and g[i] < 16
            if vlist is not None:
                V = group_V(is_filler)
                if g[i+2] == 0 and not is_filler:
                    V = None                      # run-0 content row: neutral
            else:
                V = (cluster_disp or {}).get(cl)
                if V is not None and g[i+2] == 0 and not is_filler:
                    V = None
            if V is None:
                out += g[i:i+8]
            elif g[i+2] == 0:                     # filler: in-place
                grp = bytearray(g[i:i+8])
                grp[3], grp[4], grp[5] = enc(V[0]), enc(V[1]), enc(V[2])
                out += grp
            else:                                 # run>0: 8B -> 12B two-vertex
                out += bytes([g[i], 1, g[i+2], 0x7e, 0x7e, 0x7e, g[i+2] - 1,
                              enc(V[0]), enc(V[1]), enc(V[2]), 0, 0])
            i += 8
        else:
            out += g[i:i+1]; i += 1
    return bytes(out)


# ── x=0 + y=0 SURFACE CORNER (B3) ────────────────────────────────────────────
# Derived 2026-07-04 from 3079 (4x4x1 slab straddling x=0 AND y=0, h=1).
# The cleanest corner of the three:
#   (8,8,8) = gen_corner_hh(rx, ry) BYTE-EXACT -- the terrain-grid 2-axis
#             corner form IS the octant xy corner (unified seam principle:
#             decls from the (+2,+2)-plate @(-2,-2), FG from (+1,+1)@(-1,-1)).
#   (7,7,8) = PURE plain (rx+1)x(ry+1) plate @(32-rx, 32-ry). NOTE: its CV is
#             inside the x0-low band (<=160) yet NO band shift -- the x0 CV
#             band shift does not operate in xy-corner chunks.
#   (7,8,8) = the y0-high decl splice @lx0=32-rx WITHOUT the pure-y0 seam's
#             -2 tail trim.
#   (8,7,8) = plain (rx+1)x(ry+1) plate @(-1, 32-ry) + the x0-high head in its
#             UNIFIED placement: the full ghost-column decl group (5*(ry+1)
#             bytes) inserted at first_decl-10, one pad pair dropped after it,
#             first-decl value -> x-marker. (Verified byte-equivalent to the
#             existing gen_seam_x0_high block construction on 3048/3060.)
def gen_corner_xy(rx=2, ry=2, lz0=10):
    """All 4 chunks of an x=0+y=0 surface corner as {(cx,cy,cz): scan}. rx/ry =
    real cols/rows per side, h=1 single layer. Byte-exact vs 3079 (rx=ry=2);
    other sizes follow the constituent generators' validated ranges but the
    corner composition itself is single-build-pinned."""
    ny = ry + 1
    out = {(8, 8, 8): gen_corner_hh(rx, ry, lz0=lz0)}
    out[(7, 7, 8)] = gen_heightmap_unified(
        [[1] * ny] * (rx + 1), lx0=32 - rx, ly0=32 - ry, lz0=lz0)
    gB = gen_heightmap_unified([[1] * (ry + 2)] * (rx + 1), lx0=32 - rx, ly0=-2, lz0=lz0)
    gA = gen_heightmap_unified([[1] * ny] * (rx + 1), lx0=32 - rx, ly0=-1, lz0=lz0)
    out[(7, 8, 8)] = gB[:_fg0(gB)] + gA[_fg0(gA):]     # no -2 tail trim here
    g = gen_heightmap_unified([[1] * ny] * (rx + 1), lx0=-1, ly0=32 - ry, lz0=lz0)
    cvm2 = (217 - 55 * (-2) + 35 * (32 - ry) + lz0) % 256
    ins = bytes([cvm2, 1, 2, 0, 0]) + bytes([33, 1, 2, 0, 0]) * (ny - 1)
    fd = _first_decl(g)
    g2 = bytearray(g)
    g2[fd] = (200 - 1 - 35 * (ny - 1)) % 256           # x-marker
    g2[fd - 10:fd - 10] = ins
    del g2[fd - 10 + len(ins):fd - 8 + len(ins)]       # drop one pad pair after block
    out[(8, 7, 8)] = bytes(g2)
    return out


def gen_corner_hh(Rx, Ry, lz0=10, h=1, verts=None):
    """The HIGH-x HIGH-y chunk of a 2-axis (x & y) corner: Rx real cols, Ry real
    rows, with back-ghosts on BOTH axes. Decls from an (Rx+2)x(Ry+2) plate @(-2,-2);
    FG (and trailing) from an (Rx+1)x(Ry+1) plate @(-1,-1), optionally displaced via
    verts (per-FG-group (V0,V1), (Rx+2)x(Ry+2) grid corners). Byte-exact vs CR1 (9,9)."""
    bd = gen_heightmap_unified([[h] * (Ry + 2)] * (Rx + 2), lx0=-2, ly0=-2, lz0=lz0)
    bf = (gen_surface_displaced([[h] * (Ry + 1)] * (Rx + 1), verts, lx0=-1, ly0=-1, lz0=lz0)
          if verts else gen_heightmap_unified([[h] * (Ry + 1)] * (Rx + 1), lx0=-1, ly0=-1, lz0=lz0))
    pre_b10 = _fg0(bd) - 2  # preval position = bd's own (inherits large-ny gap bands; == old formula 340+3(Rx+1)+5(Rx+2)(Ry+1)+2((Rx+1)//4) at validated sizes)
    CVm2 = (217 - 55 * (-2) + 35 * (-2) + lz0) % 256
    preval = (120 - CVm2 - (h - 1) - 35 * (Ry + 1) + 55 * (Rx + 1)) % 256
    fgr = _fg_region(bf)
    s = bytearray(bd[:_last_decl_end(bd)])
    while len(s) < pre_b10: s += bytes([255, 0])
    s += bytes([preval, 0]); s += fgr
    Ltot = pre_b10 + 4 + (len(bf) - _fg0(bf)) + 2 * (13 <= Ry < 31)  # +2 large-ny band trailing (3105 Ry=24, single-point)
    while len(s) < Ltot: s += bytes([255, 0])
    return bytes(s[:Ltot])


# 2-AXIS CORNER chunk dispatch (all 4 types of a plate crossing both x=32 and y=32):
#   (low-x, low-y)  : gen_heightmap_unified((n_left+1) x (n_low+1) plate @ start)  [fwd ghosts both axes]
#   (high-x, low-y) : gen_seam_high(R_x, ly0=start_y, ny=n_low+1)                  [x col-splice]
#   (low-x, high-y) : gen_seam_high_y(R_y, n_left+1, lx0=start_x)                  [y row-splice]
#   (high-x, high-y): gen_corner_hh(R_x, R_y)                                       [both splices]
# All byte-exact vs CR1 2737. Base-position jitter SOLVED (bfs = CV>160 / CV<160 mirror; declpair0 C=322).


# ── MULTI-CHUNK TERRAIN GENERATOR (orchestration) ───────────────────────────
# Splits a flat footprint across chunk boundaries and dispatches each chunk to the
# right byte-exact generator. Validated scope: spans at most one boundary per axis
# (single chunk / single seam / 2-axis corner). gx,gy = global voxel coords of the
# footprint's low corner; chunk = 8 + g//32, local = g%32 (Static-M).
def gen_terrain_flat(gx, gy, nx, ny, lz0=10, h=1):
    """Return {(cx,cy,cz): scan} for a flat nx*ny footprint at global (gx,gy), z=lz0.
    Byte-exact vs single-chunk plates, x/y seams (2669/2673/2729), and 2-axis
    corners (CR1/CC-A/CC-B). Requires the footprint to cross <=1 x-boundary and
    <=1 y-boundary (the validated multi-chunk scope)."""
    cz = 8 + lz0 // 32
    bx = 32 * ((gx // 32) + 1)                            # next x chunk-boundary
    by = 32 * ((gy // 32) + 1)
    xcross = gx < bx <= gx + nx - 1
    ycross = gy < by <= gy + ny - 1
    lx, ly = gx % 32, gy % 32                            # local low corner
    cxl, cyl = 8 + gx // 32, 8 + gy // 32                # low chunk indices
    out = {}
    # MULTI-x-boundary span (any number of x-chunks), single y-chunk, any ny:
    #   low chunk (fwd ghost) -> middle chunk(s) (both-sides ghost) -> high seam.
    # Byte-exact vs MID-1 2762 (ny=1) and MID2 2779 (ny=2). Flat only (no displacement).
    if not ycross and (gx + nx) > bx + 32:
        cxh = 8 + (gx + nx - 1) // 32                     # high chunk index
        nL = bx - gx                                      # voxels in low chunk
        Rx = (gx + nx) - 32 * ((gx + nx - 1) // 32)       # voxels in high chunk
        out[(cxl, cyl, cz)] = gen_heightmap_unified([[h] * ny] * (nL + 1), lx0=lx, ly0=ly, lz0=lz0)
        for cx in range(cxl + 1, cxh):                    # fully-spanned middle chunks
            out[(cx, cyl, cz)] = gen_middle_x(32, ly0=ly, lz0=lz0, h=h, ny=ny)
        out[(cxh, cyl, cz)] = gen_seam_high(Rx, ly0=ly, lz0=lz0, h=h, ny=ny)
        return out
    if xcross and (gx + nx) > bx + 32:
        raise ValueError("footprint crosses >1 x-boundary with y-cross/ny>1 (unvalidated)")
    if ycross and (gy + ny) > by + 32:
        raise ValueError("footprint crosses >1 y-boundary (unvalidated)")
    if not xcross and not ycross:                        # single interior chunk
        out[(cxl, cyl, cz)] = gen_heightmap_unified([[h] * ny] * nx, lx0=lx, ly0=ly, lz0=lz0)
        return out
    nL = bx - gx if xcross else nx                       # x: voxels in low chunk
    Rx = (gx + nx) - bx if xcross else 0                 # x: voxels in high chunk
    nLy = by - gy if ycross else ny
    Ry = (gy + ny) - by if ycross else 0
    if xcross and not ycross:                            # x-seam only
        out[(cxl, cyl, cz)] = gen_heightmap_unified([[h] * ny] * (nL + 1), lx0=lx, ly0=ly, lz0=lz0)
        out[(cxl + 1, cyl, cz)] = gen_seam_high(Rx, ly0=ly, lz0=lz0, h=h, ny=ny)
    elif ycross and not xcross:                          # y-seam only
        out[(cxl, cyl, cz)] = gen_heightmap_unified([[h] * (nLy + 1)] * nx, lx0=lx, ly0=ly, lz0=lz0)
        out[(cxl, cyl + 1, cz)] = gen_seam_high_y(Ry, nx, lx0=lx, lz0=lz0, h=h)
    else:                                                # 2-axis corner (4 chunks)
        out[(cxl, cyl, cz)] = gen_heightmap_unified([[h] * (nLy + 1)] * (nL + 1), lx0=lx, ly0=ly, lz0=lz0)
        out[(cxl + 1, cyl, cz)] = gen_seam_high(Rx, ly0=ly, lz0=lz0, h=h, ny=nLy + 1)
        out[(cxl, cyl + 1, cz)] = gen_seam_high_y(Ry, nL + 1, lx0=lx, lz0=lz0, h=h)
        out[(cxl + 1, cyl + 1, cz)] = gen_corner_hh(Rx, Ry, lz0=lz0, h=h)
    return out


def gen_terrain_flat_ymulti(gx, gy, nx, ny, lz0=10, h=1):
    """Flat patch crossing ANY number of Y-boundaries within a single x-chunk (nx wide).
    Row-direction mirror of the multi-x path: low-y chunk (fwd ghost) -> y-middle(s)
    -> high-y seam. Returns {(cx,cy,cz): scan}. Byte-exact vs MIDY-NX 2830/2844 (3
    y-chunks). Falls back to gen_terrain_flat for <=1 y-boundary."""
    by = 32 * ((gy // 32) + 1)
    if (gy + ny) <= by:
        return gen_terrain_flat(gx, gy, nx, ny, lz0=lz0, h=h)
    n_low = by - gy; cyl = 8 + gy // 32; cyh = 8 + (gy + ny - 1) // 32
    n_high = (gy + ny) - 32 * ((gy + ny - 1) // 32); M = cyh - cyl - 1
    lx = gx % 32; ly = gy % 32; cx = 8 + gx // 32; cz = 8 + lz0 // 32
    out = {(cx, cyl, cz): gen_heightmap_unified([[h] * (n_low + 1)] * nx, lx0=lx, ly0=ly, lz0=lz0)}
    for j in range(M):
        out[(cx, cyl + 1 + j, cz)] = gen_middle_y(nx=nx, lx0=lx, lz0=lz0, h=h)
    out[(cx, cyh, cz)] = gen_seam_high_y(n_high, nx, lx0=lx, lz0=lz0, h=h)
    return out


def gen_terrain_flat_2d(gx, gy, nx, ny, lz0=10, h=1):
    """Flat patch crossing ANY number of x-boundaries AND (exactly) one y-boundary.
    Full 2D chunk grid: y-low row (fwd-ghost) x [low | middle(s) | high] and y-high row
    (seam) x [x-fwd-ghost seam | corner-middle(s) | 2-axis corner]. Returns {(cx,cy,cz):
    scan}. Byte-exact vs MID2AX 2808 (3 x-chunks x 2 y-chunks). Falls back to
    gen_terrain_flat when <=1 x-boundary or no y-boundary; requires exactly 1 y-boundary
    with >=1 x-boundary otherwise."""
    cz = 8 + lz0 // 32
    bx = 32 * ((gx // 32) + 1); by = 32 * ((gy // 32) + 1)
    xmulti = (gx + nx) > bx                                # crosses >=1 x-boundary
    ycross = gy < by <= gy + ny - 1
    if not (xmulti and ycross) or (gy + ny) > by + 32:
        return gen_terrain_flat(gx, gy, nx, ny, lz0=lz0, h=h)   # simpler cases / unsupported multi-y
    lx, ly = gx % 32, gy % 32
    cxl, cyl = 8 + gx // 32, 8 + gy // 32
    cxh = 8 + (gx + nx - 1) // 32
    nL = bx - gx                                          # x cells in low chunk
    Rx = (gx + nx) - 32 * ((gx + nx - 1) // 32)           # x cells in high chunk
    nLy = by - gy                                         # y cells in low y-chunk (below boundary)
    Ry = (gy + ny) - by                                   # y cells in high y-chunk
    out = {}
    # y-LOW row (each chunk has a y-forward-ghost -> ny=nLy+1)
    out[(cxl, cyl, cz)] = gen_heightmap_unified([[h] * (nLy + 1)] * (nL + 1), lx0=lx, ly0=ly, lz0=lz0)
    for cx in range(cxl + 1, cxh):
        out[(cx, cyl, cz)] = gen_middle_x(32, ly0=ly, lz0=lz0, h=h, ny=nLy + 1)
    out[(cxh, cyl, cz)] = gen_seam_high(Rx, ly0=ly, lz0=lz0, h=h, ny=nLy + 1)
    # y-HIGH row (y-seam back-ghost, Ry real rows)
    out[(cxl, cyl + 1, cz)] = gen_seam_high_y(Ry, nL + 1, lx0=lx, lz0=lz0, h=h, x_fwd_ghost=True)
    for cx in range(cxl + 1, cxh):
        out[(cx, cyl + 1, cz)] = gen_corner_middle(Ry, lz0=lz0, h=h)
    out[(cxh, cyl + 1, cz)] = gen_corner_hh(Rx, Ry, lz0=lz0, h=h)
    return out


def gen_terrain_flat_grid(gx, gy, nx, ny, lz0=10, h=1):
    """Flat patch crossing ANY number of x-boundaries AND ANY number of y-boundaries --
    the fully general 2D chunk grid. Composes the 3x3 chunk-type template scaled to the
    footprint: y-low row [corner-low | x-middle(s) | x-high] (fwd-ghost, ny=nLy+1);
    y-mid row(s) [x-low y-mid | double-middle(s) | x-high y-mid]; y-high row [x-fwd-ghost
    y-seam | corner-middle(s) | 2-axis corner]. Returns {(cx,cy,cz): scan}. Byte-exact vs
    MID2D33 2848 (3x3). Falls back to gen_terrain_flat_2d / gen_terrain_flat_ymulti /
    gen_terrain_flat for degenerate (<=1 boundary on an axis) cases."""
    bx = 32 * ((gx // 32) + 1); by = 32 * ((gy // 32) + 1)
    xmulti = (gx + nx) > bx; ymulti = (gy + ny) > by
    if not (xmulti and ymulti):
        return gen_terrain_flat_2d(gx, gy, nx, ny, lz0=lz0, h=h)
    if (gx + nx) <= bx + 32:                               # <=1 x-boundary but multi-y
        return gen_terrain_flat_ymulti(gx, gy, nx, ny, lz0=lz0, h=h) if (gx + nx) <= bx \
               else _grid_body(gx, gy, nx, ny, lz0, h)     # (single x-chunk handled below)
    return _grid_body(gx, gy, nx, ny, lz0, h)


def _grid_body(gx, gy, nx, ny, lz0, h):
    bx = 32 * ((gx // 32) + 1); by = 32 * ((gy // 32) + 1)
    cxl, cyl = 8 + gx // 32, 8 + gy // 32
    cxh = 8 + (gx + nx - 1) // 32; cyh = 8 + (gy + ny - 1) // 32
    lx, ly = gx % 32, gy % 32; cz = 8 + lz0 // 32
    nL = bx - gx; Rx = (gx + nx) - 32 * ((gx + nx - 1) // 32)
    nLy = by - gy; Ry = (gy + ny) - 32 * ((gy + ny - 1) // 32)
    Mx = cxh - cxl - 1; My = cyh - cyl - 1
    out = {}
    # y-low row (y-forward-ghost, ny=nLy+1)
    out[(cxl, cyl, cz)] = gen_heightmap_unified([[h] * (nLy + 1)] * (nL + 1), lx0=lx, ly0=ly, lz0=lz0)
    for j in range(Mx): out[(cxl + 1 + j, cyl, cz)] = gen_middle_x(32, ly0=ly, lz0=lz0, h=h, ny=nLy + 1)
    out[(cxh, cyl, cz)] = gen_seam_high(Rx, ly0=ly, lz0=lz0, h=h, ny=nLy + 1)
    # y-middle row(s)
    for iy in range(My):
        cy = cyl + 1 + iy
        out[(cxl, cy, cz)] = gen_ymid_xlow(nL, lx0=lx, lz0=lz0, h=h)
        for j in range(Mx): out[(cxl + 1 + j, cy, cz)] = gen_double_middle(lz0=lz0, h=h)
        out[(cxh, cy, cz)] = gen_ymid_xhigh(Rx, lz0=lz0, h=h)
    # y-high row (y-seam)
    out[(cxl, cyh, cz)] = gen_seam_high_y(Ry, nL + 1, lx0=lx, lz0=lz0, h=h, x_fwd_ghost=True)
    for j in range(Mx): out[(cxl + 1 + j, cyh, cz)] = gen_corner_middle(Ry, lz0=lz0, h=h)
    out[(cxh, cyh, cz)] = gen_corner_hh(Rx, Ry, lz0=lz0, h=h)
    return out


def gen_terrain_grid(corner_z, gx, gy, lz0=10, h=1):
    """DISPLACED multi-boundary grid: the smooth analog of gen_terrain_flat_grid.
    corner_z = global (nx+1)x(ny+1) grid of top-vertex z-offsets (84-steps);
    gx,gy = footprint low-corner global voxel coords. Routes each chunk its slice
    of the global corner grid (ghost-overlap ranges generalize gen_terrain's
    validated 2-chunk slices: x-low [0:nL+2], x-mid_j [nL+32j-2:nL+32j+33],
    x-high [nx-Rx-1:nx+1]; y symmetric). Adjacent chunks share overlap lines ->
    continuity by construction. corner_z all-zero reduces to gen_terrain_flat_grid
    byte-exact. Returns {(cx,cy,cz): scan}."""
    nx = len(corner_z) - 1; ny = len(corner_z[0]) - 1
    bx = 32 * ((gx // 32) + 1); by = 32 * ((gy // 32) + 1)
    cxl, cyl = 8 + gx // 32, 8 + gy // 32
    cxh = 8 + (gx + nx - 1) // 32; cyh = 8 + (gy + ny - 1) // 32
    lx, ly = gx % 32, gy % 32; cz = 8 + lz0 // 32
    nL = bx - gx; Rx = (gx + nx) - 32 * ((gx + nx - 1) // 32)
    nLy = by - gy; Ry = (gy + ny) - 32 * ((gy + ny - 1) // 32)
    Mx = cxh - cxl - 1; My = cyh - cyl - 1
    XS = {'low': (0, nL + 2), 'high': (nx - Rx - 1, nx + 1)}      # x-line ranges
    YS = {'low': (0, nLy + 2), 'high': (ny - Ry - 1, ny + 1)}     # y-line ranges
    xmid = lambda j: (nL + 32 * j - 2, nL + 32 * j + 33)
    ymid = lambda i: (nLy + 32 * i - 2, nLy + 32 * i + 33)
    def V(xr, yr):                                                # verts slice, x-outer/y-inner
        return _vts2d([corner_z[xi][yr[0]:yr[1]] for xi in range(xr[0], xr[1])])
    out = {}
    # y-low row
    out[(cxl, cyl, cz)] = gen_surface_displaced([[h] * (nLy + 1)] * (nL + 1),
                                                V(XS['low'], YS['low']), lx0=lx, ly0=ly, lz0=lz0)
    for j in range(Mx):
        out[(cxl + 1 + j, cyl, cz)] = gen_middle_x(32, ly0=ly, lz0=lz0, h=h, ny=nLy + 1,
                                                   verts=V(xmid(j), YS['low']))
    out[(cxh, cyl, cz)] = gen_seam_high(Rx, ly0=ly, lz0=lz0, h=h, ny=nLy + 1,
                                        verts=V(XS['high'], YS['low']))
    # y-middle row(s)
    for iy in range(My):
        cy = cyl + 1 + iy
        out[(cxl, cy, cz)] = gen_ymid_xlow(nL, lx0=lx, lz0=lz0, h=h, verts=V(XS['low'], ymid(iy)))
        for j in range(Mx):
            out[(cxl + 1 + j, cy, cz)] = gen_double_middle(lz0=lz0, h=h, verts=V(xmid(j), ymid(iy)))
        out[(cxh, cy, cz)] = gen_ymid_xhigh(Rx, lz0=lz0, h=h, verts=V(XS['high'], ymid(iy)))
    # y-high row
    out[(cxl, cyh, cz)] = gen_seam_high_y(Ry, nL + 1, lx0=lx, lz0=lz0, h=h, x_fwd_ghost=True,
                                          verts=V(XS['low'], YS['high']))
    for j in range(Mx):
        out[(cxl + 1 + j, cyh, cz)] = gen_corner_middle(Ry, lz0=lz0, h=h, verts=V(xmid(j), YS['high']))
    out[(cxh, cyh, cz)] = gen_corner_hh(Rx, Ry, lz0=lz0, h=h, verts=V(XS['high'], YS['high']))
    return out


def _mc_from_scan(s):
    """mc = 512 + pre byte (the lone non-bg byte between last decl and first FG group)."""
    decls = []; i = 0; fg0 = None
    while i < len(s):
        if i + 5 <= len(s) and s[i+1] == 1 and s[i+2] == 2 and s[i+4] == 0 and s[i] not in (0, 255):
            decls.append(i); i += 5
        elif i + 8 <= len(s) and s[i+1] == 1 and s[i] not in (0, 255) and not (s[i+2] == 2 and s[i+4] == 0):
            fg0 = i; break
        else: i += 1
    return 512 + [s[j] for j in range(decls[-1] + 5, fg0) if s[j] not in (0, 255)][0]


def gen_terrain_blueprint(chunks, template_path, out_path):
    """Assemble {(cx,cy,cz): scan} into an importable blueprint by cloning the template
    envelope and substituting each h3 chunk (mc=512+pre, hash recomputed). The template
    must contain the same h3 chunk coords. Returns #chunks written. Byte-validated:
    regen of CR1 (2737) is decompressed-identical + self-consistent."""
    import du_assemble
    def scan_for(cx, cy, cz):
        s = chunks.get((cx, cy, cz))
        return (s, _mc_from_scan(s)) if s else None
    return du_assemble.rebuild_h3(template_path, out_path, scan_for)


def _vts2d(rows):
    """Per-FG-group (V0,V1) verts from a 2D z-offset slice [x-grid-line][y-grid-line],
    emit order x-outer/y-inner (matches all surface generators)."""
    v = []
    for row in rows:
        for dz in row:
            v.append((ORIGIN, ORIGIN) if dz == 0 else (ORIGIN, (0, 0, dz)))
    return v


def gen_terrain(corner_z, gx, gy, lz0=10, h=1):
    """SMOOTH multi-chunk terrain. corner_z = (nx+1)x(ny+1) grid of top-vertex z-offsets;
    gx,gy = global voxel coords of the footprint's low corner. Splits across chunk
    boundaries (<=1 per axis) and dispatches each chunk to its displacement-capable
    generator with the shared ghost-line offsets. Returns {(cx,cy,cz): scan}.
    corner_z all-zero reduces to gen_terrain_flat (byte-exact)."""
    nx = len(corner_z) - 1; ny = len(corner_z[0]) - 1
    cz = 8 + lz0 // 32
    bx = 32 * ((gx // 32) + 1); by = 32 * ((gy // 32) + 1)
    xcross = gx < bx <= gx + nx - 1
    ycross = gy < by <= gy + ny - 1
    lx, ly = gx % 32, gy % 32
    cxl, cyl = 8 + gx // 32, 8 + gy // 32
    if (xcross and gx + nx > bx + 32) or (ycross and gy + ny > by + 32):
        raise ValueError("footprint crosses >1 boundary on an axis (unvalidated)")
    def sl(a, b, c, d):                                   # corner_z[a:b][c:d] (x-lines a..b, y-lines c..d)
        return [corner_z[i][c:d] for i in range(a, b)]
    nL = bx - gx if xcross else nx
    Rx = (gx + nx) - bx if xcross else 0
    nLy = by - gy if ycross else ny
    Ry = (gy + ny) - by if ycross else 0
    out = {}
    if not xcross and not ycross:
        out[(cxl, cyl, cz)] = gen_surface_displaced([[h] * ny] * nx, _vts2d(sl(0, nx + 1, 0, ny + 1)),
                                                     lx0=lx, ly0=ly, lz0=lz0)
    elif xcross and not ycross:
        out[(cxl, cyl, cz)] = gen_surface_displaced([[h] * ny] * (nL + 1), _vts2d(sl(0, nL + 2, 0, ny + 1)),
                                                     lx0=lx, ly0=ly, lz0=lz0)
        out[(cxl + 1, cyl, cz)] = gen_seam_high(Rx, ly0=ly, lz0=lz0, h=h, ny=ny, verts=_vts2d(sl(nL - 1, nx + 1, 0, ny + 1)))
    elif ycross and not xcross:
        out[(cxl, cyl, cz)] = gen_surface_displaced([[h] * (nLy + 1)] * nx, _vts2d(sl(0, nx + 1, 0, nLy + 2)),
                                                     lx0=lx, ly0=ly, lz0=lz0)
        out[(cxl, cyl + 1, cz)] = gen_seam_high_y(Ry, nx, lx0=lx, lz0=lz0, h=h, verts=_vts2d(sl(0, nx + 1, nLy - 1, ny + 1)))
    else:
        out[(cxl, cyl, cz)] = gen_surface_displaced([[h] * (nLy + 1)] * (nL + 1), _vts2d(sl(0, nL + 2, 0, nLy + 2)),
                                                     lx0=lx, ly0=ly, lz0=lz0)
        out[(cxl + 1, cyl, cz)] = gen_seam_high(Rx, ly0=ly, lz0=lz0, h=h, ny=nLy + 1, verts=_vts2d(sl(nL - 1, nx + 1, 0, nLy + 2)))
        out[(cxl, cyl + 1, cz)] = gen_seam_high_y(Ry, nL + 1, lx0=lx, lz0=lz0, h=h, verts=_vts2d(sl(0, nL + 2, nLy - 1, ny + 1)))
        out[(cxl + 1, cyl + 1, cz)] = gen_corner_hh(Rx, Ry, lz0=lz0, h=h, verts=_vts2d(sl(nL - 1, nx + 1, nLy - 1, ny + 1)))
    return out
