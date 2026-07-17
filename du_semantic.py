"""du_semantic.py -- SEMANTIC-MODEL voxel cell emitter (the du_general rewrite core).

Replaces the empirical token-grammar generator: shape -> dense material/vertex grids ->
greedy RLE serialization (see du_squarion.py for the verified format model).

FILL RULES (derived 2026-07-17/18 from the donor corpus; reg: 143/156 chunks byte-exact,
remainder = documented stale-build payload bytes):
  * chunk record emitted iff the shape OWNS >=1 voxel in the chunk's inner 32^3.
    (Game exports may also contain EMPTY placeholder records and per-chunk palette
    variants -- benign build state, not emulated.)
  * range = 35^3 at inner-1. Materials: cell c holds the material of voxel c-1
    (materials sit at voxel+(1,1,1)); fill = GLOBAL shape clipped to the voxel window
    [inner-2, inner+32] per axis (2 carried below, 1 above -- the empirical S-2/S carry).
  * vertex window = material window PLUS a phantom +33 plane per axis that is a COPY of
    the +32 plane (winfit: copy beats true-row on curved seam donors, uniform X/Y/Z).
  * vertices: strict SURFACE-CORNER predicate over the windowed set: grid point p gets a
    vertex iff among the 8 voxels {p-(dx,dy,dz)} at least one is filled and at least one
    empty. flags=1, position=(126,126,126) default; 84 steps/voxel.
  * Y-seam smoothing payload positions via canonical_y_payload (open-side tail always;
    seam-side toggled by yseam_payload). X/Z seams carry NO payload (3367/3378 exact).
  * further position overrides (mesh smoothing) via pos_fn.
  * greedy maximal RLE reproduces DU's encoder byte-exactly (verified 467/467 records
    incl LOD h4-h7 on 2026-07-17).

Old-lineage laws (val/pad/lead/gap/mc, all layout hooks/pockets) are NOT used anywhere --
they were RLE distance arithmetic all along and dissolved under direct serialization.
"""
import struct

MAT_HCCARBON = (3417309861, 'hcCarbon')
MAT_DEBUG1 = (157903047, 'Debug1\x00\x00')

CELL_MAGIC = 0x27b8a013
CELL_VERSION = 6
GRID_MAGIC = 0xe881339e
GRID_VERSION = 9


def _rle_pairs(out, first_bytes, count):
    """serialize_rle pattern: value bytes then count byte, splitting at 256 cells."""
    while count:
        out += first_bytes
        count -= 1
        more = min(count, 255)
        out.append(more)
        count -= more


def _col(voxels, x, y, lo, hi):
    """(zlo, h) of the column at (x,y) within [lo,hi], or None."""
    zs = [z for z in range(lo, hi + 1) if (x, y, z) in voxels]
    return (min(zs), len(zs)) if zs else None


def canonical_y_payload(voxels, io, zlo=None, zhi=None):
    """Canonical fresh-build Y-seam smoothing payload {cell: (px,py,pz)} (item-14 laws
    in dense form, 2026-07-18). Payload is DU build state, not a shape function -- this
    is the form fresh sequential builds produce (12 canonical donors byte-exact).
      * yopen side (shape continues past y=io+32): at the phantom cell layer y=io+33,
        footprint x-corner cells only, z = zlo + h(S) - 1, dz = +14 -- unless the open
        edge ascends (h(S+1) > h(S)) or is locally flat (h(S-1)==h(S)==h(S+1)).
      * yseam side (shape continues below y=io): at the first cell layer y=io-1, the
        footprint x-cell range: corner cells dz=+14, interior dz=+42, z = zlo +
        min(h(S-1), h(S)) - 1 -- unless the seam triple h(S-2..S) is flat.
    Heights per x taken from the x-extreme columns (donors are x-uniform; per-x law
    unprobed -- see in_confidence notes).
    Returns (open_pos, seam_pos): the OPEN-side tail payload is law-driven (every
    non-ascending donor carries it, incl the otherwise-plain 3450); the SEAM-side
    payload is the build-state-nondeterministic half (yseam_payload toggles it;
    3438/3450 exported plain)."""
    if not voxels:
        return {}, {}
    if zlo is None:
        zlo = min(v[2] for v in voxels)
        zhi = max(v[2] for v in voxels)
    open_pos = {}
    seam_pos = {}
    S_hi = io[1] + 32          # the carried S row on the open side
    S_lo = io[1]               # the chunk's first own row on the seam side
    for side in ('open', 'seam'):
        if side == 'open':
            if not any(v[1] == S_hi + 1 for v in voxels):
                continue
            row = S_hi
        else:
            if not any(v[1] == S_lo - 1 for v in voxels):
                continue
            row = S_lo - 1
        xs = sorted({v[0] for v in voxels if v[1] == row})
        if not xs:
            continue
        x0, x1 = xs[0], xs[-1]
        if side == 'open':
            c0 = _col(voxels, x0, S_hi, zlo, zhi)
            cn = _col(voxels, x0, S_hi + 1, zlo, zhi)
            cp = _col(voxels, x0, S_hi - 1, zlo, zhi)
            if not c0:
                continue
            hs = c0[1]
            hn = cn[1] if cn else 0
            hp = cp[1] if cp else 0
            if hn > hs or (hp == hs == hn):
                continue                    # ascending / locally flat -> plain
            zc = c0[0] + hs - 1
            for xc in (x0, x1 + 1):
                open_pos[(xc, io[1] + 33, zc)] = (126, 126, 126 + 14)
        else:
            ca = _col(voxels, x0, S_lo - 1, zlo, zhi)   # S-1
            cb = _col(voxels, x0, S_lo, zlo, zhi)       # S
            cm = _col(voxels, x0, S_lo - 2, zlo, zhi)   # S-2
            if not ca or not cb:
                continue
            hm = cm[1] if cm else 0
            if hm == ca[1] == cb[1]:
                continue                    # flat seam triple -> plain
            zc = ca[0] + min(ca[1], cb[1]) - 1
            for xc in range(x0, x1 + 2):
                dz = 14 if xc in (x0, x1 + 1) else 42
                seam_pos[(xc, io[1] - 1, zc)] = (126, 126, 126 + dz)
    return open_pos, seam_pos


def build_cell(voxels, inner_origin, material=MAT_HCCARBON, pos_fn=None,
               mapping=None, mat_idx=2, yseam_payload=True):
    """One chunk record body (uncompressed). voxels = GLOBAL absolute voxel set.
    inner_origin = 32*chunk_key triple. pos_fn(cell)->(px,py,pz) or None for default.
    mapping/mat_idx: override the material palette (donor palettes vary by build
    session, e.g. 3325 has hcCarbon at slot 3)."""
    io = inner_origin
    ro = (io[0] - 1, io[1] - 1, io[2] - 1)
    N = 35 * 35 * 35

    # material window: the chunk's copy of the shape, voxels [inner-2, inner+32]
    matwin = {v for v in voxels
              if all(io[i] - 2 <= v[i] <= io[i] + 32 for i in range(3))}

    # vertex window: [inner-2, inner+33] with the +33 plane per axis a COPY of the
    # +32 plane (the "phantom"; winfit 2026-07-18: copy beats true-row on the curved
    # seam donors 3400/3432/3436, uniform over X/Y/Z)
    win = set(matwin)
    for a in range(3):
        ext = {tuple(c + (1 if i == a else 0) for i, c in enumerate(v))
               for v in win if v[a] == io[a] + 32}
        win |= ext

    # dense arrays in index order (z fastest)
    mats = [None] * N
    for (vx, vy, vz) in matwin:
        # material cell = voxel+1 -> local index of cell (v+1)-ro
        x, y, z = vx + 1 - ro[0], vy + 1 - ro[1], vz + 1 - ro[2]
        if 0 <= x < 35 and 0 <= y < 35 and 0 <= z < 35:
            mats[(x * 35 + y) * 35 + z] = mat_idx

    open_pos, seam_pos = canonical_y_payload(voxels, io)
    ypay = dict(open_pos)
    if yseam_payload:
        ypay.update(seam_pos)

    verts = [None] * N
    corner = set()
    for (vx, vy, vz) in win:
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    corner.add((vx + dx, vy + dy, vz + dz))
    for p in corner:
        n = sum(1 for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)
                if (p[0] - dx, p[1] - dy, p[2] - dz) in win)
        if n == 8:
            continue                       # strictly interior corner
        x, y, z = p[0] - ro[0], p[1] - ro[1], p[2] - ro[2]
        if not (0 <= x < 35 and 0 <= y < 35 and 0 <= z < 35):
            continue
        pos = pos_fn(p) if pos_fn is not None else None
        if pos is None and ypay:
            pos = ypay.get(p)
        verts[(x * 35 + y) * 35 + z] = tuple(pos) if pos is not None else (126, 126, 126)

    out = bytearray()
    out += struct.pack('<I', CELL_MAGIC) + struct.pack('<I', CELL_VERSION)
    out += struct.pack('<I', GRID_MAGIC) + struct.pack('<I', GRID_VERSION)
    out += struct.pack('<3i', *ro) + struct.pack('<3i', 35, 35, 35)
    out += struct.pack('<3i', *io) + struct.pack('<3i', 32, 32, 32)

    # materials: greedy equal-value runs
    i = 0
    while i < N:
        v = mats[i]
        j = i + 1
        while j < N and mats[j] == v:
            j += 1
        _rle_pairs(out, b'\x00' if v is None else bytes([1, v]), j - i)
        i = j

    # vertices: greedy flags runs; present runs in 256-blocks with greedy inner quads
    i = 0
    while i < N:
        present = verts[i] is not None
        j = i + 1
        while j < N and (verts[j] is not None) == present:
            j += 1
        if not present:
            _rle_pairs(out, b'\x00', j - i)
        else:
            k = i
            while k < j:
                blk = min(j - k, 256)
                out.append(1)
                out.append(blk - 1)
                m = k
                while m < k + blk:
                    p = verts[m]
                    q = m + 1
                    while q < k + blk and verts[q] == p:
                        q += 1
                    _rle_pairs(out, bytes(p), q - m)
                    m = q
                k += blk
        i = j

    if mapping is None:
        mapping = [(MAT_DEBUG1[0], MAT_DEBUG1[1], 1), (material[0], material[1], mat_idx)]
    out += struct.pack('<I', len(mapping))
    for mid, name, idx in mapping:
        nm = name.ljust(8, '\x00')[:8].encode()
        out += struct.pack('<Q', mid) + nm + bytes([idx])
    out.append(1)  # is_diff
    return bytes(out)


def build_chunks(voxels, material=MAT_HCCARBON, pos_fn=None, mapping=None, mat_idx=2,
                 yseam_payload=True):
    """{chunk_key: cell bytes} for every chunk owning >=1 voxel. voxels = absolute set."""
    keys = {tuple(c // 32 for c in v) for v in voxels}
    return {k: build_cell(voxels, (32 * k[0], 32 * k[1], 32 * k[2]), material=material,
                          pos_fn=pos_fn, mapping=mapping, mat_idx=mat_idx,
                          yseam_payload=yseam_payload)
            for k in sorted(keys)}
