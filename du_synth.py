"""du_synth.py — Dense flat-skeleton SYNTHESIZER (no donor needed).

Emits a byte-exact h3 dense-solid voxel scan from per-X-plane column heights,
using the fully-derived encoding (2026-07-08). Then the deflection layer
(du_dense) drops onto the vertex slots to make arbitrary closed shapes.

Encoding laws (all verified byte-exact on flat donors 3174/3201/3203/3197/3209/3211):
  MARKER region (per X-plane, columns h[0..nc-1] in Y order):
    marker(val,h) = [val,01,02,h-1,00]
    opener  val[0]   = (235 - 35*nc - h[-1]) % 256          (interior planes)
    opener  val[0]   = bnd_op                                (-X boundary plane, position CV)
    cont    val[i>=1]= (34 - h[i-1]) % 256
  GROUP region (per X vertex-plane, nx+1 planes):
    boundary plane (x=xlo): opener=(bnd_op+19)%256 run=h[0]; then per c=1..nc:
        val=(33-max(h[c-1],h[c-2] if c>=2 else 0))%256 run=max(h[c],h[c-1])
    boundary plane (x=xhi): opener=(199-35*nc-h[-1])%256 run=h[0]; rest same Bottom-family
    interior plane: [Y-lo wall (199-35*nc-h[-1], run h[0])]
                    + for c=1..nc-1: [Bottom (33-max(h[c-1],h[c-2])), run 0]
                                     [Top    (min(h[c],h[c-1])-2, run |h[c]-h[c-1]|)]
                    + [Y-hi wall (33-max(h[-1],h[-2]), run h[-1])]
  LAYOUT (standard position, chunk-local voxel-8 start): lead=99, bnd_op=65.
    marker plane stride = 5*nc + mkgap ; mat byte at marker_end+pad ; group at +90.
    gaps: mkgap = 8 if nc<=6 else 6 ; ggap = 8 if nc<=5 else 6.
    pad (gap8/nc<=5) = 230 - 8*nx + 2*nc.
  BACKGROUND: absolute parity (even->00, odd->ff) per byte, with per-segment flip;
    flip=True iff the preceding marker/token region ended at an even offset;
    mat byte is phase-transparent.
"""

def _marker(val, h):
    return bytes([val & 0xff, 0x01, 0x02, (h - 1) & 0xff, 0x00])

def _tok(val, run):
    return bytes([val & 0xff, 0x01, run & 0xff, 0x7e, 0x7e, 0x7e, run & 0xff, 0x00])

def _mk_val(H, i, nc):
    if i == 0:
        return (235 - 35 * nc - H[-1]) % 256
    return (34 - H[i - 1]) % 256

def marker_plane(H, nc, is_neg_boundary, bnd_op):
    out = b''
    for i in range(nc):
        if i == 0 and is_neg_boundary:
            val = bnd_op
        else:
            val = _mk_val(H, i, nc)
        out += _marker(val, H[i])
    return out

def group_interior(H, nc):
    o = _tok((199 - 35 * nc - H[-1]) % 256, H[0])            # Y-lo wall
    for c in range(1, nc):
        hp2 = H[c - 2] if c >= 2 else 0
        o += _tok((33 - max(H[c - 1], hp2)) % 256, 0)                     # Bottom_c
        o += _tok((min(H[c], H[c - 1]) - 2) % 256, abs(H[c] - H[c - 1]))  # Top_c
    o += _tok((33 - max(H[-1], H[-2])) % 256, H[-1])         # Y-hi wall
    return o

def group_boundary(H, nc, opener):
    o = _tok(opener % 256, H[0])
    for c in range(1, nc):
        hp2 = H[c - 2] if c >= 2 else 0
        o += _tok((33 - max(H[c - 1], hp2)) % 256, max(H[c], H[c - 1]))
    o += _tok((33 - max(H[-1], H[-2])) % 256, H[-1])
    return o

def position_params(x, y, z):
    """Chunk-LOCAL voxel start (x,y,z) -> (lead, bnd_op). Fits all 11 position
    donors (2026-07-09). lead z-independent; bnd_op x&2 bit term empirical
    (odd-x untested). Tall-regime coeffs differ from h3's plate 153."""
    lead = 11 + 2 * (6 + (147 * x) // 31 + (4 * y) // 31)
    bnd_op = (218 + z + (279 * x) // 31 + (1084 * y) // 31 + 128 * ((x >> 1) & 1)) % 256
    return lead, bnd_op


def _pad(nx, nc):
    """Pre-mat padding (per-nc empirical regimes; verified nc4-8)."""
    if nc == 4:   return 246 - 10 * nx
    if nc == 5:   return 240 - 8 * nx if nx <= 3 else 246 - 10 * nx
    if nc == 6:   return 246 - 10 * nx
    return 241 - 9 * nx                  # nc>=7


def build_scan(planes, mat_counter, bnd_op=65, lead=99):
    """planes: list (per X-plane, x=xlo..xhi) of height-lists (len nc, Y order).
    bnd_op/lead default to standard position (voxel-8 start); for other positions
    pass position_params(x,y,z)."""
    nx = len(planes)
    nc = len(planes[0])
    mkgap = 8 if nc <= 6 else 6
    ggap = 8 if nc <= 5 else 6
    pad = _pad(nx, nc)

    # --- content pieces ---
    mplanes = [marker_plane(planes[p], nc, p == 0, bnd_op) for p in range(nx)]
    gregs = ([group_boundary(planes[0], nc, (bnd_op + 19) % 256)]
             + [group_interior(planes[p], nc) for p in range(1, nx)]
             + [group_boundary(planes[-1], nc, (199 - 35 * nc - planes[-1][-1]) % 256)])

    # --- offsets ---
    # mat byte + group region sit at POSITION-INDEPENDENT offsets (computed as if
    # lead were the standard 99); only the leading bg + marker region shift with
    # the actual lead, compressing the pre-mat pad.
    placements = []   # (offset, bytes, is_token)
    markerspan = nx * 5 * nc + (nx - 1) * mkgap
    off = lead
    for mp in mplanes:
        placements.append((off, mp, True)); off += len(mp) + mkgap
    mat_off = (99 + markerspan) + pad        # FIXED (independent of actual lead)
    placements.append((mat_off, bytes([mat_counter & 0xff]), False))
    grpspan = sum(len(gr) for gr in gregs) + (len(gregs) - 1) * ggap
    # group region shifts with lead (mat does not); scanlen is position-independent
    off = mat_off + 90 + (lead - 99)
    for gr in gregs:
        placements.append((off, gr, True)); off += len(gr) + ggap
    scanlen = (mat_off + 90) + grpspan + pad  # as if lead=99 -> constant

    # --- assemble: absolute-parity bg with per-segment flip, content overwrite ---
    S = bytearray(scanlen)
    placements.sort()
    last_tok_end = None
    prev = 0
    def fill(a, b, flip):
        for j in range(a, b):
            if flip: S[j] = 0xff if j % 2 == 0 else 0x00
            else:    S[j] = 0x00 if j % 2 == 0 else 0xff
    for o, data, is_tok in placements:
        if o > prev:
            fill(prev, o, last_tok_end is not None and last_tok_end % 2 == 0)
        S[o:o + len(data)] = data
        if is_tok: last_tok_end = o + len(data)
        prev = o + len(data)
    if prev < scanlen:
        fill(prev, scanlen, last_tok_end is not None and last_tok_end % 2 == 0)
    return bytes(S)


def build_blueprint(template_path, out_path, planes, mc, bnd_op=65, lead=99,
                    cx=8, cy=8, cz=8):
    """Synthesize a flat dense scan and wrap it in a blueprint envelope.
    Clones template_path's JSON, substitutes the single h3 chunk's blob+hash.
    `mc` = full material counter (e.g. 512 + low-byte); scan uses mc & 0xff.
    Returns scan length. (Envelope via du_assemble.encode_voxel_b64 — the same
    path du_dense deploys with; b64 need not match a donor byte-for-byte since
    LZ4 output is non-canonical, but the (b64,hash) pair is self-consistent.)"""
    import json, copy, du_assemble
    scan = build_scan(planes, mc, bnd_op=bnd_op, lead=lead)
    bp = json.load(open(template_path))
    out = copy.deepcopy(bp)
    done = False
    for e in out['VoxelData']:
        if e['h'] != 3:
            continue
        b64, h = du_assemble.encode_voxel_b64(cx, cy, cz, scan, mc)
        e['records']['voxel']['data']['$binary'] = b64
        e['records']['voxel']['hash']['$numberLong'] = h
        done = True
        break
    assert done, "no h3 chunk in template"
    json.dump(out, open(out_path, 'w'))
    return len(scan)


def build_blueprint_safe(template_path, out_path, planes, bnd_op=65, lead=99,
                         cx=8, cy=8, cz=8):
    """Safest wrap: preserve the template h3 chunk's ACTUAL 64B header + 40B tail
    (material descriptor + mc) and substitute ONLY the scan. Avoids the hcCarbon
    MAT_TAIL / material-mismatch trap (e.g. an hcAlLiPa donor). The scan's lone
    mat byte is set to the template's mc & 0xff so it matches the tail."""
    import json, copy, base64, struct, lz4.block
    import du_hash
    bp = json.load(open(template_path))
    out = copy.deepcopy(bp)
    for e in out['VoxelData']:
        if e['h'] != 3:
            continue
        raw = base64.b64decode(e['records']['voxel']['data']['$binary'])
        size = int.from_bytes(raw[4:8], 'little')
        dec = lz4.block.decompress(raw[12:], uncompressed_size=size)
        if len(dec) < 700:
            continue
        header, tail = dec[:64], dec[-40:]
        mc = struct.unpack('<I', tail[:4])[0]
        scan = build_scan(planes, mc, bnd_op=bnd_op, lead=lead)
        blob = header + scan + tail
        comp = lz4.block.compress(blob, store_size=False)
        newraw = b'\xf9\xb6\x14\xfb' + struct.pack('<I', len(blob)) + b'\x00\x00\x00\x00' + comp
        e['records']['voxel']['data']['$binary'] = base64.b64encode(newraw).decode()
        e['records']['voxel']['hash']['$numberLong'] = du_hash.to_signed64(du_hash.compute_hash(newraw))
        json.dump(out, open(out_path, 'w'))
        return len(scan)
    raise AssertionError("no h3 chunk in template")


def wrap_scan_safe(template_path, out_path, scan, cx=8, cy=8, cz=8):
    """Wrap an ALREADY-BUILT scan (e.g. after du_dense deflection) preserving the
    template h3 chunk's actual header + tail (material + mc). Material-agnostic."""
    import json, copy, base64, struct, lz4.block
    import du_hash
    out = copy.deepcopy(json.load(open(template_path)))
    for e in out['VoxelData']:
        if e['h'] != 3:
            continue
        raw = base64.b64decode(e['records']['voxel']['data']['$binary'])
        size = int.from_bytes(raw[4:8], 'little')
        dec = lz4.block.decompress(raw[12:], uncompressed_size=size)
        if len(dec) < 700:
            continue
        blob = dec[:64] + bytes(scan) + dec[-40:]
        comp = lz4.block.compress(blob, store_size=False)
        newraw = b'\xf9\xb6\x14\xfb' + struct.pack('<I', len(blob)) + b'\x00\x00\x00\x00' + comp
        e['records']['voxel']['data']['$binary'] = base64.b64encode(newraw).decode()
        e['records']['voxel']['hash']['$numberLong'] = du_hash.to_signed64(du_hash.compute_hash(newraw))
        json.dump(out, open(out_path, 'w'))
        return len(scan)
    raise AssertionError("no h3 chunk in template")


# ---------------------------------------------------------------------------
# 2D blocky base: arbitrary height field h(x,y). planes = list per voxel-X-plane
# of Y-height-lists (len nc). Group region uses the CORNER LAW (2026-07-09).
# ---------------------------------------------------------------------------

def _corner_top(L, R, c):
    """Top token for the vertex between voxel-planes L,R at column c."""
    C = (L[c - 1], L[c], R[c - 1], R[c])
    return (min(C) - 2) % 256, (max(C) - min(C))

def group_interior_2d(L, R, nc):
    """Interior vertex-plane between adjacent voxel-planes L,R (height lists)."""
    t = [max(L[j], R[j]) for j in range(nc)]        # taller-per-column profile
    # Y-lo wall (-Y side-face CV). Normally 199-35nc-L[-1]. In the FLIP case (both planes
    # carry an interior peak that crosses mid-plane, e.g. PY2 3252 x10: L=[4,6,8,6] R=[6,8,6,4]
    # -> needs 8, not L[-1]=6) it takes the peak height. Guarded so it == L[-1] for every
    # validated donor (X1/3238/PY2 x9), fixing only the true flip byte (deflection-overwritten;
    # donors 3252/3238 cleaned from exports, so validated against the recorded values only).
    xlo = L[-1]
    if max(L) > L[-1] and max(R) > R[-1] and max(R) >= max(L):
        xlo = max(L)
    o = _tok((199 - 35 * nc - xlo) % 256, t[0])      # Y-lo wall
    for c in range(1, nc):
        hp2 = t[c - 2] if c >= 2 else 0
        o += _tok((33 - max(t[c - 1], hp2)) % 256, 0)          # Bottom_c
        tv, tr = _corner_top(L, R, c)
        o += _tok(tv, tr)                                       # Top_c (corner law)
    o += _tok((33 - max(t[-1], t[-2])) % 256, t[-1])           # Y-hi wall
    return o

def group_boundary_2d(plane, nc, opener_val):
    """All-wall boundary plane (x=xlo or xhi) for a voxel-plane's Y-profile."""
    o = _tok(opener_val % 256, plane[0])
    for c in range(1, nc):
        hp2 = plane[c - 2] if c >= 2 else 0
        o += _tok((33 - max(plane[c - 1], hp2)) % 256, max(plane[c], plane[c - 1]))
    o += _tok((33 - max(plane[-1], plane[-2])) % 256, plane[-1])   # last token
    return o

def build_scan_2d(planes, mat_counter, bnd_op=65, lead=99):
    """Full scan for an arbitrary 2D blocky base. planes[xi] = Y-height-list."""
    nx = len(planes); nc = len(planes[0])
    mkgap = 8 if nc <= 6 else 6
    ggap = 8 if nc <= 5 else 6
    pad = _pad(nx, nc)

    # marker opener (interior plane p) uses the PREVIOUS plane's last column
    def mplane(p):
        out = b''
        for i in range(nc):
            if i == 0:
                val = bnd_op if p == 0 else (235 - 35 * nc - planes[p - 1][-1]) % 256
            else:
                val = (34 - planes[p][i - 1]) % 256
            out += _marker(val, planes[p][i])
        return out
    mplanes = [mplane(p) for p in range(nx)]
    gregs = ([group_boundary_2d(planes[0], nc, (bnd_op + 19) % 256)]
             + [group_interior_2d(planes[k - 1], planes[k], nc) for k in range(1, nx)]
             + [group_boundary_2d(planes[-1], nc,
                                  (199 - 35 * nc - max(planes[-1][-1], planes[-2][-1])) % 256)])

    markerspan = nx * 5 * nc + (nx - 1) * mkgap
    placements = []
    off = lead
    for mp in mplanes:
        placements.append((off, mp, True)); off += len(mp) + mkgap
    mat_off = (99 + markerspan) + pad
    placements.append((mat_off, bytes([mat_counter & 0xff]), False))
    grpspan = sum(len(gr) for gr in gregs) + (len(gregs) - 1) * ggap
    off = mat_off + 90 + (lead - 99)
    for gr in gregs:
        placements.append((off, gr, True)); off += len(gr) + ggap
    scanlen = (mat_off + 90) + grpspan + pad

    S = bytearray(scanlen); placements.sort(); last_tok_end = None; prev = 0
    def fill(a, b, flip):
        for j in range(a, b):
            S[j] = (0xff if j % 2 == 0 else 0x00) if flip else (0x00 if j % 2 == 0 else 0xff)
    for o, data, is_tok in placements:
        if o > prev: fill(prev, o, last_tok_end is not None and last_tok_end % 2 == 0)
        S[o:o + len(data)] = data
        if is_tok: last_tok_end = o + len(data)
        prev = o + len(data)
    if prev < scanlen: fill(prev, scanlen, last_tok_end is not None and last_tok_end % 2 == 0)
    return bytes(S)


# ---------------------------------------------------------------------------
# TWO-SURFACE (full sphere/lens): per column (z_lo, z_hi) instead of just h.
# X-uniform first (all planes identical zlo/zhi). 2026-07-09.
# ---------------------------------------------------------------------------

def _bshift(zlo, c):
    step = zlo[c] - zlo[c - 1]
    if step > 0 and (c < 2 or zlo[c - 1] <= zlo[c - 2]):   # turning point (zlo local-min/plateau)
        return 0
    return step

def group_interior_2surf(zlo, zhi, nc, ylo_wall_val, yhi_wall_val):
    h = [zhi[j] - zlo[j] + 1 for j in range(nc)]
    o = _tok(ylo_wall_val % 256, h[0])                         # Y-lo wall
    for c in range(1, nc):
        hp2 = h[c - 2] if c >= 2 else 0
        o += _tok((33 - max(h[c - 1], hp2) + _bshift(zlo, c)) % 256, abs(zlo[c] - zlo[c - 1]))   # Bottom
        o += _tok((min(h[c], h[c - 1]) - 2) % 256, abs(zhi[c] - zhi[c - 1]))                      # Top
    o += _tok(yhi_wall_val % 256, h[-1])                       # Y-hi wall
    return o

def group_boundary_2surf(zlo, zhi, nc, opener_val):
    h = [zhi[j] - zlo[j] + 1 for j in range(nc)]
    o = _tok(opener_val % 256, h[0])
    for c in range(1, nc):
        hp2 = h[c - 2] if c >= 2 else 0
        o += _tok((33 - max(h[c - 1], hp2) + _bshift(zlo, c)) % 256, max(h[c], h[c - 1]))
    o += _tok((33 - max(h[-1], h[-2]) + max(0, zlo[-1] - zlo[-2])) % 256, h[-1])
    return o

def _marker_plane_2surf(zlo, zhi, nc, is_neg, bnd_op):
    h = [zhi[j] - zlo[j] + 1 for j in range(nc)]
    opener = bnd_op if is_neg else (235 - 35 * nc - h[-1] + (zlo[0] - zlo[-1])) % 256
    out = _marker(opener, h[0])
    for c in range(1, nc):
        out += _marker((34 - h[c - 1] + (zlo[c] - zlo[c - 1])) % 256, h[c])
    return out

def build_scan_2surf(zlo_planes, zhi_planes, mat_counter, bnd_op=65, lead=99):
    """X-uniform-capable: zlo_planes[xi]=zlo list, zhi_planes[xi]=zhi list per plane."""
    nx = len(zlo_planes); nc = len(zlo_planes[0])
    mkgap = 8 if nc <= 6 else 6; ggap = 8 if nc <= 5 else 6; pad = _pad(nx, nc)
    ylo = lambda zl, zh: (199 - 35 * nc - (zh[-1] - zl[-1] + 1) + (zl[0] - zl[-1])) % 256
    yhi = lambda zl, zh: (33 - max((zh[-1]-zl[-1]+1), (zh[-2]-zl[-2]+1)) + max(0, zl[-1]-zl[-2])) % 256
    mplanes = [_marker_plane_2surf(zlo_planes[p], zhi_planes[p], nc, p == 0, bnd_op) for p in range(nx)]
    gregs = ([group_boundary_2surf(zlo_planes[0], zhi_planes[0], nc, (bnd_op + 19) % 256)]
             + [group_interior_2surf(zlo_planes[k], zhi_planes[k], nc, ylo(zlo_planes[k],zhi_planes[k]), yhi(zlo_planes[k],zhi_planes[k])) for k in range(1, nx)]
             + [group_boundary_2surf(zlo_planes[-1], zhi_planes[-1], nc, (199 - 35 * nc - (zhi_planes[-1][-1]-zlo_planes[-1][-1]+1) + (zlo_planes[-1][0]-zlo_planes[-1][-1])) % 256)])
    markerspan = nx * 5 * nc + (nx - 1) * mkgap
    placements = []; off = lead
    for mp in mplanes: placements.append((off, mp, True)); off += len(mp) + mkgap
    mat_off = (99 + markerspan) + pad; placements.append((mat_off, bytes([mat_counter & 0xff]), False))
    grpspan = sum(len(gr) for gr in gregs) + (len(gregs) - 1) * ggap
    off = mat_off + 90 + (lead - 99)
    for gr in gregs: placements.append((off, gr, True)); off += len(gr) + ggap
    scanlen = (mat_off + 90) + grpspan + pad
    S = bytearray(scanlen); placements.sort(); last_tok_end = None; prev = 0
    def fill(a, b, flip):
        for j in range(a, b): S[j] = (0xff if j % 2 == 0 else 0x00) if flip else (0x00 if j % 2 == 0 else 0xff)
    for o, data, is_tok in placements:
        if o > prev: fill(prev, o, last_tok_end is not None and last_tok_end % 2 == 0)
        S[o:o + len(data)] = data
        if is_tok: last_tok_end = o + len(data)
        prev = o + len(data)
    if prev < scanlen: fill(prev, scanlen, last_tok_end is not None and last_tok_end % 2 == 0)
    return bytes(S)


# ---------------------------------------------------------------------------
# 2D TWO-SURFACE (real sphere/ellipsoid): zlo(x,y), zhi(x,y) both vary in X & Y.
# Combines the 2D corner law (validated single-surface) with the 1D two-surface
# law (validated lenses). NOT yet donor-validated -> needs an E1 ellipsoid probe.
# ---------------------------------------------------------------------------

def group_interior_2surf_2d(zloL, zhiL, zloR, zhiR, nc):
    hL = [zhiL[j] - zloL[j] + 1 for j in range(nc)]
    hR = [zhiR[j] - zloR[j] + 1 for j in range(nc)]
    t  = [max(hL[j], hR[j]) for j in range(nc)]              # taller-per-col height
    zc = [min(zloL[j], zloR[j]) for j in range(nc)]          # per-col bottom (lowest of the two planes)
    def bshift(c):
        step = zc[c] - zc[c - 1]
        if step > 0 and (c < 2 or zc[c - 1] <= zc[c - 2]): return 0   # zlo local-min/plateau turning pt
        return step
    o = _tok((199 - 35 * nc - hL[-1] + (zloL[0] - zloL[-1])) % 256, t[0])   # Y-lo wall
    for c in range(1, nc):
        hcorn = (hL[c - 1], hL[c], hR[c - 1], hR[c])
        zhic  = (zhiL[c - 1], zhiL[c], zhiR[c - 1], zhiR[c])
        zloc  = (zloL[c - 1], zloL[c], zloR[c - 1], zloR[c])
        hp2 = t[c - 2] if c >= 2 else 0
        o += _tok((33 - max(t[c - 1], hp2) + bshift(c)) % 256, max(zloc) - min(zloc))   # Bottom
        o += _tok((min(hcorn) - 2) % 256, max(zhic) - min(zhic))                        # Top
    o += _tok((33 - max(t[-1], t[-2]) + max(0, zc[-1] - zc[-2])) % 256, t[-1])          # Y-hi wall
    return o

# (build_scan_2surf_2d wrapper omitted until E1 validates the interior law.)
print("2D two-surface stub added (needs E1 ellipsoid donor to validate/fix).") if __name__=="__main__" else None


def _marker_plane_2surf1(zlo, zhi, nc, is_neg, bnd_op):
    """One voxel-plane's markers for the two-surface case (uses own zlo/zhi)."""
    h = [zhi[j] - zlo[j] + 1 for j in range(nc)]
    opener = bnd_op if is_neg else (235 - 35 * nc - h[-1] + (zlo[0] - zlo[-1])) % 256
    out = _marker(opener, h[0])
    for c in range(1, nc):
        out += _marker((34 - h[c - 1] + (zlo[c] - zlo[c - 1])) % 256, h[c])
    return out

def build_scan_2surf_2d(zlo_planes, zhi_planes, mat_counter, bnd_op=65, lead=99):
    """Full 2D two-surface scan (real sphere/ellipsoid). zlo_planes[xi], zhi_planes[xi]."""
    nx = len(zlo_planes); nc = len(zlo_planes[0])
    mkgap = 8 if nc <= 6 else 6; ggap = 8 if nc <= 5 else 6; pad = _pad(nx, nc)
    mplanes = [_marker_plane_2surf1(zlo_planes[p], zhi_planes[p], nc, p == 0, bnd_op) for p in range(nx)]
    def bnd(zl, zh):   # boundary plane = its own 1D two-surface silhouette
        return group_boundary_2surf(zl, zh, nc, (bnd_op + 19) % 256)
    gregs = ([group_boundary_2surf(zlo_planes[0], zhi_planes[0], nc, (bnd_op + 19) % 256)]
             + [group_interior_2surf_2d(zlo_planes[k-1], zhi_planes[k-1], zlo_planes[k], zhi_planes[k], nc) for k in range(1, nx)]
             + [group_boundary_2surf(zlo_planes[-1], zhi_planes[-1], nc,
                (199 - 35 * nc - (zhi_planes[-1][-1]-zlo_planes[-1][-1]+1) + (zlo_planes[-1][0]-zlo_planes[-1][-1])) % 256)])
    markerspan = nx * 5 * nc + (nx - 1) * mkgap
    placements = []; off = lead
    for mp in mplanes: placements.append((off, mp, True)); off += len(mp) + mkgap
    mat_off = (99 + markerspan) + pad; placements.append((mat_off, bytes([mat_counter & 0xff]), False))
    grpspan = sum(len(gr) for gr in gregs) + (len(gregs) - 1) * ggap
    off = mat_off + 90 + (lead - 99)
    for gr in gregs: placements.append((off, gr, True)); off += len(gr) + ggap
    scanlen = (mat_off + 90) + grpspan + pad
    S = bytearray(scanlen); placements.sort(); last_tok_end = None; prev = 0
    def fill(a, b, flip):
        for j in range(a, b): S[j] = (0xff if j % 2 == 0 else 0x00) if flip else (0x00 if j % 2 == 0 else 0xff)
    for o, data, is_tok in placements:
        if o > prev: fill(prev, o, last_tok_end is not None and last_tok_end % 2 == 0)
        S[o:o + len(data)] = data
        if is_tok: last_tok_end = o + len(data)
        prev = o + len(data)
    if prev < scanlen: fill(prev, scanlen, last_tok_end is not None and last_tok_end % 2 == 0)
    return bytes(S)


# ---------------------------------------------------------------------------
# Item #3: OWN ENVELOPE (Option B). Single-chunk hcCarbon XS-core construct.
# Header (64B) + tail-after-mc (36B) are byte-identical constants across every
# single-chunk standard-position donor (verified on 6). So the entire h3 body is
# synthesizable from scratch: HDR + scan + mc(4B) + TAIL_AFTER_MC. DU regenerates
# the h4..h7 LOD pyramid + mc from our h3 on import (proven: synth_ridge).
# ---------------------------------------------------------------------------
H3_HDR = (b"\x13\xa0\xb8'\x06\x00\x00\x00\x9e3\x81\xe8\t\x00\x00\x00\xff\x00\x00\x00\xff\x00\x00\x00"
          b"\xff\x00\x00\x00#\x00\x00\x00#\x00\x00\x00#\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00"
          b"\x00\x01\x00\x00 \x00\x00\x00 \x00\x00\x00 \x00\x00\x00")
H3_TAIL_AFTER_MC = b'\x00\xc7hi\t\x00\x00\x00\x00Debug1\x00\x00\x01\xa5\x02\xb0\xcb\x00\x00\x00\x00hcCarbon\x02\x01'

def _scan_b2(scan):
    """Plateau byte-2 of the scan's first marker, found position-independently: skip the
    leading 00/ff background alternation, read marker byte-2. (Matches du_assemble._scan_b2;
    the old fixed-offset-101 read assumed lead=99 and broke off-origin shapes.)"""
    i = 0
    while i < len(scan) and scan[i] == (0 if i % 2 == 0 else 0xff):
        i += 1
    if i + 4 < len(scan) and scan[i + 1] == 1:
        return scan[i + 2]
    return 2


def build_h3_body(scan, mc):
    """Full h3 voxel body from scratch: constant header + our scan + mc + constant tail.
    The tail's penultimate byte is a shape-global 'plateau' parameter that mirrors the
    marker byte-2 (=2 normally; the interior-plateau length for shapes like OCC3). It MUST
    match the scan's first marker byte-2 or the mesher over-reads (OCC3 3325 / Deployment
    11a-c). Detected position-independently (lead varies with shape position)."""
    import struct
    b2 = _scan_b2(scan)
    tail = H3_TAIL_AFTER_MC[:-2] + bytes([b2, H3_TAIL_AFTER_MC[-1]])
    return H3_HDR + bytes(scan) + struct.pack('<I', mc & 0xffffffff) + tail

def build_blueprint_own(template_path, out_path, scan, mc, name, voxels=None):
    """Generate OUR OWN envelope (Option B). Body is fully synthetic (build_h3_body);
    the JSON shell (Model skeleton, single XS core, h4..h7 LOD chunk SET) is taken from
    a canonical template we control -- DU refills all LOD data + mc from our h3. Sets a
    custom Model['Name'] (e.g. 'Deployment 1') for in-game tracking.

    NOTE: Model.Id and serverProperties.originConstructId are LEFT AS THE TEMPLATE'S.
    The server overrides Id on import, and originConstructId must reference a real source
    construct; pointing it at a made-up id breaks blueprint->construct migration and
    crashes the client (proven 2026-07-09: id 999002 crashed; unmodified control was
    perfect). Only Name is ours."""
    import json, copy, base64, struct, lz4.block
    import du_hash
    out = copy.deepcopy(json.load(open(template_path)))
    body = build_h3_body(scan, mc)
    comp = lz4.block.compress(body, store_size=False)
    newraw = b'\xf9\xb6\x14\xfb' + struct.pack('<I', len(body)) + b'\x00\x00\x00\x00' + comp
    # If the shape's voxel occupancy is given, prune the (superset) template's LOD chunk
    # SET to the EXACT set DU expects for this shape (else the mesher over-reads in build
    # mode, or misses cells). Template must be a 19-chunk h5x8/h6x8 superset.
    if voxels is not None:
        want = compute_lod_set(voxels)
        out['VoxelData'] = [e for e in out['VoxelData']
                            if (e['h'], int(e['x']['$numberLong']), int(e['y']['$numberLong']),
                                int(e['z']['$numberLong'])) in want or e['h'] == 3]
    done = False
    for e in out['VoxelData']:
        if e['h'] != 3:
            continue
        e['records']['voxel']['data']['$binary'] = base64.b64encode(newraw).decode()
        e['records']['voxel']['hash']['$numberLong'] = du_hash.to_signed64(du_hash.compute_hash(newraw))
        done = True
    assert done, "no h3 chunk in template"
    out['Model']['Name'] = name
    json.dump(out, open(out_path, 'w'))
    return len(body)


def compute_lod_set(voxels, cx=8, cy=8, cz=8):
    """Exact LOD chunk SET {(h,x,y,z)} for a single-chunk shape from its voxel occupancy
    (set of local (x,y,z)). SOLVED via the cube sweep (3335/3337/3339/3341/3343) + donors:
      h3=(8,8,8), h4=(4,4,4), h7=(0,0,0) always;
      h5: per-axis coord {1,2} if that axis extent>=2 else {2} (base 2);
      h6: base (1,1,1); expands to all (0..1)^3 iff min-extent>=4 OR max-extent>=6 OR the
          shape is neither a solid box nor a horizontal (X/Y) prism (i.e. has footprint /
          curved detail). Ridge-class simple prisms stay h6x1 (known soft spot for exotic
          in-between shapes; exact for spheres/discs/ellipsoids/boxes)."""
    xs = [p[0] for p in voxels]; ys = [p[1] for p in voxels]; zs = [p[2] for p in voxels]
    ex, ey, ez = max(xs)-min(xs)+1, max(ys)-min(ys)+1, max(zs)-min(zs)+1
    mn, mx = min(ex, ey, ez), max(ex, ey, ez)
    solid = len(voxels) == ex * ey * ez
    def horiz_prism():
        for ax in (0, 1):
            o = [i for i in range(3) if i != ax]; sl = {}
            for p in voxels: sl.setdefault(p[ax], set()).add((p[o[0]], p[o[1]]))
            v = list(sl.values())
            if len(v) > 1 and all(s == v[0] for s in v): return True
        return False
    mid = sorted((ex, ey, ez))[1]
    # 2026-07-15 rebanded (18 donors, see obj_pipeline._h6_full): FULL iff mn>=4 / mx>=6 / (mx<=4 and mid>=4)
    h6_full = (mn >= 4) or (mx >= 6) or (mx <= 4 and mid >= 4)
    lo5 = (min(xs), min(ys), min(zs))
    # h5 phantom POSITION-based (2026-07-15): low phantom iff shape occupies the chunk's
    # low half on that axis (local voxel<16) and extent>=2 (see obj_pipeline.compute_lod_set_mc)
    ax5 = [(1, 2) if len(voxels) > 1 and (l % 32) < 16 else (2,) for e, l in zip((ex, ey, ez), lo5)]
    want = {(3, cx, cy, cz), (4, cx//2, cy//2, cz//2), (7, 0, 0, 0)}
    for a in ax5[0]:
        for b in ax5[1]:
            for c in ax5[2]: want.add((5, a, b, c))
    if h6_full:
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1): want.add((6, a, b, c))
    else:
        want.add((6, 1, 1, 1))
    return want


# ---------------------------------------------------------------------------
# Item #5: PER-X OCCUPANCY (narrowing footprint) -- flat single-surface.
# Cracked byte-exact on OCC1 (3318, nc3->5->3) + OCC2 (3320, nc1->3->5->3->1).
# planes_cols[p] = set of occupied Y-indices (0-based) in plane p; flat height H.
# Absent columns are OMITTED (per-plane nc). Group vertex uses the COLLAPSE rule:
# a column present in only one of the two planes ("exposed") turns its (Bottom,Top)
# pair into a single wall token; flush columns keep the pair.
# CV model (validated levels 0-2): lvl(nc)=(max_nc-nc)//2; base_op(l)=20+35*(2^l-1).
# ---------------------------------------------------------------------------
def build_scan_narrow(planes_cols, H, mc):
    nx = len(planes_cols); ncs = [len(p) for p in planes_cols]; maxnc = max(ncs)
    lvl = lambda nc: (maxnc - nc) // 2
    base_op = lambda l: 20 + 35 * (2 ** l - 1)
    # marker byte-2: normally 02, but an INTERIOR width plateau (longest run of
    # consecutive identical column-sets, when it doesn't span the whole shape)
    # bumps it to the run length (OCC3=3325: nc[3,5,5,5,3] -> run 3 -> byte2=3).
    best = 1; cur = 1
    for i in range(1, nx):
        if planes_cols[i] == planes_cols[i-1]: cur += 1; best = max(best, cur)
        else: cur = 1
    b2 = 2 if best == nx else max(2, best)
    def _mkb(val, h): return bytes([val & 0xff, 0x01, b2 & 0xff, (h - 1) & 0xff, 0x00])
    def mkp(cols, op):
        out = _mkb(op, H)
        for _ in range(len(cols) - 1): out += _mkb(34 - H, H)
        return out
    def vtx(L, R, op):
        U = sorted(L | R); ex = {u for u in U if (u in L) != (u in R)}
        out = _tok(op, H)
        for i in range(1, len(U)):
            out += _tok(29, H) if (U[i-1] in ex or U[i] in ex) else _tok(29, 0) + _tok(2, 0)
        return out + _tok(29, H)
    def bnd(cols, op):
        out = _tok(op, H)
        for _ in range(len(cols)): out += _tok(29, H)
        return out
    bnd_op_mk = 65 + 35 * lvl(ncs[0])
    mk_base = 235 - 35 * maxnc - H
    mplanes = [mkp(planes_cols[0], bnd_op_mk)]
    for p in range(1, nx):
        lm = lvl(min(ncs[p], ncs[p-1]))
        mplanes.append(mkp(planes_cols[p], mk_base + 35 * (2 ** lm - 1)))
    gregs = [bnd(planes_cols[0], bnd_op_mk + 19)]
    for p in range(1, nx):
        gregs.append(vtx(planes_cols[p-1], planes_cols[p], base_op(lvl(ncs[p-1]))))
    gregs.append(bnd(planes_cols[-1], base_op(lvl(ncs[-1]))))
    lead = 99; gap = 8
    pad = (240 - 8 * nx if nx <= 3 else 246 - 10 * nx) if maxnc == 5 else (246 - 10 * nx)
    markerspan = sum(len(m) for m in mplanes) + gap * (nx - 1)
    mat_off = lead + markerspan + pad
    grp_off = mat_off + 90
    grpspan = sum(len(g) for g in gregs) + gap * (len(gregs) - 1)
    scanlen = grp_off + grpspan + pad
    S = bytearray(scanlen); pl = [(mat_off, bytes([mc & 0xff]), False)]; off = lead
    for m in mplanes: pl.append((off, m, True)); off += len(m) + gap
    off = grp_off
    for g in gregs: pl.append((off, g, True)); off += len(g) + gap
    pl.sort(); last = None; prev = 0
    def fill(a, b, flip):
        for j in range(a, b): S[j] = (0xff if j % 2 == 0 else 0) if flip else (0 if j % 2 == 0 else 0xff)
    for o, d, t in pl:
        if o > prev: fill(prev, o, last is not None and last % 2 == 0)
        S[o:o+len(d)] = d
        if t: last = o + len(d)
        prev = o + len(d)
    if prev < scanlen: fill(prev, scanlen, last is not None and last % 2 == 0)
    return bytes(S)
