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
import numpy as np

MAT_HCCARBON = (3417309861, 'hcCarbon')
MAT_HCCARBON_B = (3417309861, 'hcCarbon')  # Placeholder: same hash, second mapping slot
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
               mapping=None, mat_idx=2, yseam_payload=True, matocc=None):
    """One chunk record body (uncompressed). voxels = GLOBAL absolute voxel set.
    inner_origin = 32*chunk_key triple. pos_fn(cell)->(px,py,pz) or None for default.
    mapping/mat_idx: override the material palette (donor palettes vary by build
    session, e.g. 3325 has hcCarbon at slot 3).
    matocc: FAST PATH -- a (35,35,35) bool occupancy of the material window [io-2, io+32]
    (build_blueprint_sem slices it from a global grid). When given, skips the per-voxel
    loop AND the canonical Y-seam payload (generation doesn't need the blocky build-state
    payload -- DU accepts plain; pos_fn handles all smoothing)."""
    io = inner_origin
    ro = (io[0] - 1, io[1] - 1, io[2] - 1)
    N = 35 * 35 * 35
    b = (io[0] - 2, io[1] - 2, io[2] - 2)          # window base voxel (index 0)

    # occupancy of the material window [inner-2, inner+32] as a (36,36,36) numpy grid
    # (index a -> voxel base+a; slots 0..34 = matwin voxels, slot 35 = the +33 phantom).
    occ = np.zeros((36, 36, 36), bool)
    if matocc is not None:
        occ[:35, :35, :35] = matocc
    else:
        for (vx, vy, vz) in voxels:
            x, y, z = vx - b[0], vy - b[1], vz - b[2]
            if 0 <= x <= 34 and 0 <= y <= 34 and 0 <= z <= 34:
                occ[x, y, z] = True
    mat_occ = occ[:35, :35, :35]                   # materials from matwin only (no phantom)

    # vertex window = matwin + phantom +33 plane per axis = COPY of the +32 plane, applied
    # sequentially x,y,z (matches the old set-union order incl. cross-axis phantoms).
    # Convert to bool for phantom copy logic (occupancy only), then back if needed.
    win = occ.astype(bool) if occ.dtype == np.int8 else occ.copy()
    win[35, :, :] |= win[34, :, :]
    win[:, 35, :] |= win[:, 34, :]
    win[:, :, 35] |= win[:, :, 34]

    # surface-corner predicate: grid cell [x,y,z] (abs cell ro+[x,y,z]) counts the 8 voxels
    # win[x+1-dx, y+1-dy, z+1-dz]; a vertex exists where 1<=count<=7.
    count = np.zeros((35, 35, 35), np.int8)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                count += win[1 - dx:36 - dx, 1 - dy:36 - dy, 1 - dz:36 - dz]
    surface = (count >= 1) & (count <= 7)

    if matocc is not None:
        ypay = {}
    else:
        open_pos, seam_pos = canonical_y_payload(voxels, io)
        ypay = dict(open_pos)
        if yseam_payload:
            ypay.update(seam_pos)

    # materials list (z-fastest C order) -- mat_idx where occupied else None
    # When mat_occ is int8 (per-voxel material labels), use values directly; 0 = empty
    if mat_occ.dtype == np.int8:
        mats = np.where(mat_occ.reshape(-1) == 0, -1, mat_occ.reshape(-1)).tolist()
    else:  # bool grid: broadcast scalar mat_idx
        mats = np.where(mat_occ.reshape(-1), mat_idx, -1).tolist()
    mats = [None if v < 0 else v for v in mats]

    # vertices: default (126,126,126) at every surface cell, then apply sparse pos overrides
    verts = [None] * N
    sidx = np.flatnonzero(surface.reshape(-1))
    for idx in sidx.tolist():
        verts[idx] = (126, 126, 126)
    if pos_fn is not None or ypay:
        for idx in sidx.tolist():
            x = idx // (35 * 35); y = (idx // 35) % 35; z = idx % 35
            p = (ro[0] + x, ro[1] + y, ro[2] + z)
            pos = pos_fn(p) if pos_fn is not None else None
            if pos is None and ypay:
                pos = ypay.get(p)
            if pos is not None:
                verts[idx] = tuple(pos)

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


def bucket_by_chunk(voxels):
    """{chunk_key: [voxels]} keyed by voxel//32 -- lets callers hand each build_cell only its
    local window instead of the whole shape (O(window) vs O(shape) per chunk)."""
    buckets = {}
    for v in voxels:
        buckets.setdefault((v[0] // 32, v[1] // 32, v[2] // 32), []).append(v)
    return buckets


def window_voxels(buckets, io):
    """Voxels of the material/vertex window [inner-2, inner+33] for a chunk, gathered from the
    3x3x3 neighbourhood of buckets (the window reaches 2 below and 1 above the chunk)."""
    cx, cy, cz = io[0] // 32, io[1] // 32, io[2] // 32
    win = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for v in buckets.get((cx + dx, cy + dy, cz + dz), ()):
                    if (io[0] - 2 <= v[0] <= io[0] + 33 and io[1] - 2 <= v[1] <= io[1] + 33
                            and io[2] - 2 <= v[2] <= io[2] + 33):
                        win.append(v)
    return win


def global_occupancy(voxels):
    """Dense (bool grid, lo, dim) over the shape's voxel bounding box -- a chunk's material
    window is then a numpy SLICE (O(1)) instead of per-voxel Python filtering. `voxels` may
    be a set of triples or an (N,3) numpy array (fast path, vectorized fill)."""
    arr = voxels if isinstance(voxels, np.ndarray) else np.asarray(list(voxels))
    lo = tuple(int(arr[:, i].min()) for i in range(3))
    dim = tuple(int(arr[:, i].max()) - lo[i] + 1 for i in range(3))
    g = np.zeros(dim, bool)
    g[arr[:, 0] - lo[0], arr[:, 1] - lo[1], arr[:, 2] - lo[2]] = True
    return g, lo, dim


def global_material_grid(voxels, labels, label_to_matidx):
    """Dense (int8 grid, lo, dim) of per-voxel material indices. Used when multi-material
    support is enabled. labels: (N,) uint8 array of per-voxel material labels.
    label_to_matidx: dict mapping label -> mat_idx byte (e.g. {1: 2, 2: 3})."""
    arr = voxels if isinstance(voxels, np.ndarray) else np.asarray(list(voxels))
    lo = tuple(int(arr[:, i].min()) for i in range(3))
    dim = tuple(int(arr[:, i].max()) - lo[i] + 1 for i in range(3))
    g = np.zeros(dim, np.int8)  # 0=empty
    mat_indices = np.array([label_to_matidx.get(int(l), 0) for l in labels], np.int8)
    g[arr[:, 0] - lo[0], arr[:, 1] - lo[1], arr[:, 2] - lo[2]] = mat_indices
    return g, lo, dim


def mat_window(gocc, lo, dim, io):
    """(35,35,35) window [io-2, io+32] sliced from global occupancy (bool or int8).
    When gocc is int8 (per-voxel material indices), returns the int8 window (0=empty).
    When gocc is bool, returns bool window."""
    dtype = gocc.dtype
    out = np.zeros((35, 35, 35), dtype)
    ss, ds = [], []
    for i in range(3):
        a0 = io[i] - 2
        s0 = max(a0, lo[i]); s1 = min(a0 + 35, lo[i] + dim[i])
        if s1 <= s0:
            return out
        ss.append(slice(s0 - lo[i], s1 - lo[i]))
        ds.append(slice(s0 - a0, s1 - a0))
    out[tuple(ds)] = gocc[tuple(ss)]
    return out


def build_chunks(voxels, material=MAT_HCCARBON, pos_fn=None, mapping=None, mat_idx=2,
                 yseam_payload=True):
    """{chunk_key: cell bytes} for every chunk owning >=1 voxel. voxels = absolute set."""
    buckets = bucket_by_chunk(voxels)
    keys = set(buckets)
    return {k: build_cell(window_voxels(buckets, (32*k[0], 32*k[1], 32*k[2])),
                          (32 * k[0], 32 * k[1], 32 * k[2]), material=material,
                          pos_fn=pos_fn, mapping=mapping, mat_idx=mat_idx,
                          yseam_payload=yseam_payload)
            for k in sorted(keys)}


def semantic_confidence(voxels):
    """Geometry-only confidence check for the SEMANTIC emitter (voxels = local coords,
    chunk0 covers 0..31). Returns (safe, reasons[]). The du_general layout pockets
    (nc pad bands, nx6, off-origin, period leads) DO NOT APPLY here -- the emitter has
    no per-shape arithmetic. The only donor-unverified regions are GEOMETRY classes the
    surface-corner + phantom-copy + Y-payload rules have never been checked against a
    game export:
      * a curved shape crossing TWO OR MORE chunk axes at once (curved corner): the
        Y-seam payload is only donor-proven on a lone Y crossing; corner payload
        interaction is unprobed. (Blocky corners ARE proven: 3380.)
      * per-x variation in a Y-seam payload neighborhood (donors are x-uniform there).
    Flat/single-axis/single-chunk shapes of any size and column height are geometrically
    routine -- NOT flagged."""
    reasons = []
    arr = voxels if isinstance(voxels, np.ndarray) else np.asarray(list(voxels))
    if len(arr) == 0:
        return True, reasons
    cross = [int(arr[:, i].min()) // 32 != int(arr[:, i].max()) // 32 for i in range(3)]
    # curved iff the per-(x,y) column top z is not uniform -- vectorized via lexsort on (x,y)
    order = np.lexsort((arr[:, 1], arr[:, 0]))
    a = arr[order]
    xy = a[:, :2]
    boundary = np.any(xy[1:] != xy[:-1], axis=1)
    seg_ends = np.append(np.flatnonzero(boundary), len(a) - 1)
    tops = np.maximum.reduceat(a[:, 2], np.concatenate(([0], seg_ends[:-1] + 1)))
    curved = len(np.unique(tops)) > 1
    if curved and sum(cross) >= 2:
        reasons.append("curved shape crossing >=2 chunk axes (curved corner): Y-seam "
                       "payload interaction at a corner is donor-unverified")
    return (not reasons), reasons
