"""obj_pipeline.py -- ARC #13: voxel occupancy -> column intervals -> build_multichunk
-> deployable blueprint. The back half of the .obj pipeline (front half = obj_to_du_voxels.py
surface voxelizer). Strategy (user-locked): voxelize a BLOCKY base, deploy it, then later
deflect face-points to the true surface via the wired smoothing layer.

Stage map:
  voxels {(x,y,z)}  --solid_fill-->  solid voxels  --to_columns-->  cols {(x,y):[(zlo,zhi)..]}
  cols  --build_multichunk-->  {(cx,cy,cz): scan}  --assemble-->  blueprint JSON
"""
import os
import sys
import multiprocessing
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import du_general as dg

# Per-chunk emitter parallelism (build_blueprint_sem). Capped well under cpu_count by default
# (not "one process per core"): fork() COW-maps the whole parent address space into every
# worker, and CPython refcounting defeats COW on anything touched, so worker count multiplies
# memory risk, not just speed -- see the del/gc.collect() before Pool() creation below.
# OBJTODU_WORKERS overrides once you've verified your headroom. Only kicks in with
# >= _PARALLEL_MIN_CHUNKS chunks (pool startup isn't worth it for small shapes) and only where
# fork() exists (Linux/Docker) -- see _emit_chunk for why fork specifically is required.
# 12: measured grid-512 peak stays ~15GB (well under the 40g mem_limit) at this width on
# the 128GB / 24-core host; raise via OBJTODU_WORKERS if you re-verify headroom.
_PARALLEL_MIN_CHUNKS = 64
_DEFAULT_MAX_WORKERS = 12


def _n_workers():
    n = os.environ.get('OBJTODU_WORKERS')
    if n:
        try:
            return max(1, int(n))
        except ValueError:
            pass
    return max(1, min(_DEFAULT_MAX_WORKERS, (os.cpu_count() or 2) - 1))


# Set by build_blueprint_sem in the PARENT process before Pool() creation, so fork()'d
# workers inherit it via copy-on-write -- nothing in here (notably pos_fn, a closure) ever
# needs to be pickled across a process boundary. NOT thread-safe (fine: gunicorn's sync
# workers are one-request-per-process, so this is never touched by two threads at once).
_WORKER_CTX = None


def _emit_chunk(hxyz):
    """Build ONE blueprint LOD record dict for chunk key (h,x,y,z). Module-level (picklable
    by reference, so multiprocessing.Pool can dispatch it) -- the actual shared inputs come
    from _WORKER_CTX, not from arguments, so only this small tuple and the returned dict ever
    cross the process boundary."""
    import copy
    import du_semantic
    h, x, y, z = hxyz
    ctx = _WORKER_CTX
    e = copy.deepcopy(ctx['proto'])
    e['h'] = h
    for k, v in (('x', x), ('y', y), ('z', z)):
        e[k] = {'$numberLong': v}
    io = (32 * x, 32 * y, 32 * z)
    if h == 3:
        mo = du_semantic.mat_window(ctx['gocc'], ctx['glo'], ctx['gdim'], io)
        body = du_semantic.build_cell(None, io, material=ctx['mat'], pos_fn=ctx['pos_fn'],
                                      yseam_payload=ctx['yseam_payload'], matocc=mo,
                                      mapping=ctx.get('mapping'))
    else:
        body = du_semantic.build_cell(set(), io,
            mapping=[(du_semantic.MAT_DEBUG1[0], du_semantic.MAT_DEBUG1[1], 1)])
    b64, hsh = _encode_body(body)
    e['records']['voxel']['data']['$binary'] = b64
    e['records']['voxel']['hash']['$numberLong'] = hsh
    return e


def solid_fill_z(surface_voxels):
    """Fill a SURFACE voxel set into a solid by spanning z between the min/max surface
    voxel per (x,y) column. Cheap and correct for z-convex shapes (most hulls/organic
    forms per column); for z-concave columns use solid_fill_parity. Returns a set."""
    cols = {}
    for x, y, z in surface_voxels:
        cols.setdefault((x, y), []).append(z)
    out = set()
    for (x, y), zs in cols.items():
        for z in range(min(zs), max(zs) + 1):
            out.add((x, y, z))
    return out


def solid_fill_parity(surface_voxels):
    """Fill using even-odd crossing parity along z per (x,y) column (handles z-concave
    columns / hollows). A voxel is inside if it lies between an odd number of surface
    spans. Falls back to span-fill when a column has an odd count of surface runs."""
    cols = {}
    for x, y, z in surface_voxels:
        cols.setdefault((x, y), set()).add(z)
    out = set()
    for (x, y), zset in cols.items():
        zs = sorted(zset)
        # group contiguous surface runs
        runs = []
        s = zs[0]; p = zs[0]
        for z in zs[1:]:
            if z == p + 1:
                p = z
            else:
                runs.append((s, p)); s = z; p = z
        runs.append((s, p))
        # fill the runs themselves, plus the gaps between pairs of runs (interior)
        for a, b in runs:
            for z in range(a, b + 1):
                out.add((x, y, z))
        for i in range(0, len(runs) - 1, 2):
            gap_lo = runs[i][1] + 1
            gap_hi = runs[i + 1][0] - 1
            for z in range(gap_lo, gap_hi + 1):
                out.add((x, y, z))
    return out


def to_columns(voxels, min_thickness=2):
    """Voxel set {(x,y,z)} -> {(x,y): [(zlo,zhi), ...]} sorted z-intervals per column
    (the build_multichunk / build_scan_general input format; multiple intervals = overhangs).

    min_thickness: every interval is grown UPWARD to at least this many voxels.
    h=1 IS now fully decoded for FLAT/STEPPED shapes (2026-07-14: plates, wedges, steps,
    1-thick shells, 1-tall gaps -- pass min_thickness=1 for those). Default stays 2 because
    CURVED h=1 (dome rims) has no donor yet, and a >=2 base is legitimate for the smoothing
    deflection layer anyway. Merges any intervals that overlap after growth."""
    by_col = {}
    for x, y, z in voxels:
        by_col.setdefault((x, y), []).append(z)
    cols = {}
    for (x, y), zs in by_col.items():
        zs = sorted(set(zs))
        intervals = []
        s = zs[0]; p = zs[0]
        for z in zs[1:]:
            if z == p + 1:
                p = z
            else:
                intervals.append([s, p]); s = z; p = z
        intervals.append([s, p])
        for iv in intervals:
            if iv[1] - iv[0] + 1 < min_thickness:
                iv[1] = iv[0] + min_thickness - 1
        # re-merge overlaps created by growth
        merged = [intervals[0]]
        for a, b in intervals[1:]:
            if a <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        cols[(x, y)] = [tuple(iv) for iv in merged]
    return cols


def voxel_stats(voxels):
    xs = [v[0] for v in voxels]; ys = [v[1] for v in voxels]; zs = [v[2] for v in voxels]
    return dict(n=len(voxels),
                xr=(min(xs), max(xs)), yr=(min(ys), max(ys)), zr=(min(zs), max(zs)),
                chunks_x=(min(xs) // 32, max(xs) // 32),
                chunks_y=(min(ys) // 32, max(ys) // 32),
                chunks_z=(min(zs) // 32, max(zs) // 32))


def build_scans(voxels, mc=None):
    """Full back-half: solid voxels -> columns -> multi-chunk scans."""
    cols = to_columns(voxels)
    return dg.build_multichunk(cols, mc=mc)


def validate_scans(scans, voxels=None, strict=True):
    """Pre-deploy gate over a {chunk: scan} dict. Raises ValueError on any STRUCTURAL issue
    (malformed / invalid-vertex -> would crash DU); returns confidence-region WARNINGS for
    single-chunk shapes in the unmapped +/-2 pocket (needs voxels for the per-chunk footprint).
    strict=False downgrades structural issues to the returned list instead of raising."""
    import du_validate as V
    warnings = []
    for k, scan in scans.items():
        ok, issues = V.validate_scan(scan)
        if not ok:
            msg = f"chunk {k} FAILED structural validation: {issues}"
            if strict:
                raise ValueError(msg)
            warnings.append(msg)
    if voxels is not None:
        cols = to_columns(voxels)
        if len(scans) == 1:
            safe, reason = V.in_confidence_region(cols)
        else:
            # multi-chunk: pass which 32-boundaries the shape crosses so the curved-Y
            # envelope pockets (item 14) get flagged (single-chunk pockets don't apply)
            xs = [x for x, _ in cols]; ys = [y for _, y in cols]
            safe, reason = V.in_confidence_region(
                cols,
                xseam_lo=(min(xs) // 32 != max(xs) // 32),
                yseam=(min(ys) // 32 != max(ys) // 32))
        if not safe:
            warnings.append(f"{reason} -- deploy at own risk / verify with a donor")
    return warnings


# --- multi-chunk LOD set (SOLVED 2026-07-13; exact on 3178/3187/3376/3382/3380/3189/3191) ---
import itertools as _it

def _h6_full(voxels):
    # h6 full-8 banding over sorted extents (mn,mid,mx). Pinned by 18 donor configs
    # (2026-07-15 LOD mass-check): FULL iff mn>=4 OR mx>=6 OR (mx<=4 AND mid>=4).
    # PARENT pockets: small cubes (<=3^3, cube sweep 3335-43), (3,3,5) C1 3590,
    # (3,4,5) NCV1 3466. Replaces the old solid/horiz-prism heuristic (wrong on
    # H1/H3 plates [FULL] and small diamonds [PARENT]). Empirical banding.
    xs=[p[0] for p in voxels]; ys=[p[1] for p in voxels]; zs=[p[2] for p in voxels]
    ex=sorted((max(xs)-min(xs)+1, max(ys)-min(ys)+1, max(zs)-min(zs)+1))
    mn,mid,mx=ex
    return mn>=4 or mx>=6 or (mx<=4 and mid>=4)

def core_octree_params(size):
    """(max_h, chunk0, OFF) for a core size, derived from blueprint.rs create_lods:
    height = CoreSize.height()-3; octree is 2^height leaf-chunks/axis at origin 0; record
    h = trailing_zeros(node_extent)+3 so levels run h3..h(CoreSize.height()); the shape's
    local chunk 0 maps to octree chunk 2^(height-1) (M: height4 -> chunk 8, matches donors);
    the emitter voxel origin OFF = chunk0*32 (M -> 256)."""
    import du_envelope
    core_h = du_envelope.core_height(size)      # CoreSize.height(): XS5..M7..L8
    height = core_h - 3                          # create_lods height: XS2,S3,M4,L5
    chunk0 = 1 << (height - 1)                   # centre chunk: M->8, S->4, XS->2, L->16
    return core_h, chunk0, chunk0 * 32


def octree_from_cells(cells, core_h):
    """MINIMAL valid octree {(h,x,y,z)} from ABSOLUTE VOXEL cells: a voxel is OWNED by the
    chunk that holds its MATERIAL cell (voxel+1, since materials sit at voxel+(1,1,1)) --
    chunk (v+1)//32. Emitting by voxel//32 drops edge voxels whose material spills into the
    next chunk (the 1-voxel tiling-seam gap). Leaves + all ancestors to the single root
    h(core_h); placement-agnostic (tracks centering/tiling offsets). `cells` may be an
    iterable of triples or an (N,3) numpy array."""
    import numpy as np
    arr = cells if isinstance(cells, np.ndarray) else np.asarray(list(cells))
    if len(arr) == 0:
        return set()
    # np.unique(..., axis=0) row-dedup is a structured-array sort and is dramatically slower
    # than a 1D unique -- measured 242s for 134M rows (grid 512) vs 8.5s for the equivalent
    # via this int64-key encode/decode (21 bits/axis is far beyond any real chunk-space
    # extent, so the encoding is lossless; verified byte-identical results on real data).
    lc = (arr + 1) // 32
    lo3 = lc.min(axis=0)
    sh = lc - lo3
    BITS = 21
    key = ((sh[:, 0].astype(np.int64) << (2 * BITS))
           | (sh[:, 1].astype(np.int64) << BITS)
           | sh[:, 2].astype(np.int64))
    ukey = np.unique(key)
    mask = (1 << BITS) - 1
    ux = (ukey >> (2 * BITS)) & mask
    uy = (ukey >> BITS) & mask
    uz = ukey & mask
    leaves = {(int(ux[i] + lo3[0]), int(uy[i] + lo3[1]), int(uz[i] + lo3[2]))
              for i in range(len(ukey))}
    want = {(3,) + c for c in leaves}
    for L in range(4, core_h + 1):
        shift = L - 3
        want |= {(L,) + tuple(c[i] >> shift for i in range(3)) for c in leaves}
    return want


def compute_lod_set_octree(voxels, size, chunk0=None):
    """MINIMAL valid octree {(h,x,y,z)} for a core size: every non-empty leaf chunk (h3)
    plus ALL its ancestors up to the single root h(CoreSize.height()). No phantom neighbours
    -- DU regenerates LOD content from h3 on import, so the coarse nodes only need to exist
    and form a complete tree. Leaf coords = chunk0 + voxel//32."""
    core_h, ck0, _ = core_octree_params(size)
    if chunk0 is None:
        chunk0 = (ck0, ck0, ck0)
    leaves = {tuple(chunk0[i] + [p[0], p[1], p[2]][i] // 32 for i in range(3))
              for p in voxels}
    want = {(3,) + c for c in leaves}
    for L in range(4, core_h + 1):
        shift = L - 3
        want |= {(L,) + tuple(c[i] >> shift for i in range(3)) for c in leaves}
    return want


def compute_lod_set_mc(voxels, chunk0=(8,8,8)):
    """LOD chunk SET {(h,x,y,z)} for a single- OR multi-chunk shape. Octree: per axis, each
    coarser level's range = [lo>>L .. hi>>L] with a low phantom neighbour, taken as the
    CROSS PRODUCT over axes. Phantom: h5 on single-chunk axes; h4 on single-chunk axes with
    voxel-extent>16 (provisional threshold, bracketed [4,24]); h6 full 0-1 if h6_full else
    parent range; h7 parent. Reduces to the single-chunk law. chunk0 = h3 coord of chunk 0."""
    xs=[p[0] for p in voxels]; ys=[p[1] for p in voxels]; zs=[p[2] for p in voxels]
    ext=[max(xs)-min(xs)+1, max(ys)-min(ys)+1, max(zs)-min(zs)+1]
    chunks={tuple(chunk0[i]+[p[0],p[1],p[2]][i]//32 for i in range(3)) for p in voxels}
    axes=[sorted(set(c[i] for c in chunks)) for i in range(3)]
    single=[len(a)==1 for a in axes]
    lo=[a[0] for a in axes]; hi=[a[-1] for a in axes]
    want={(3,)+c for c in chunks}
    def rng(L, phantom):
        return [ list(range((lo[i]>>L)-(1 if phantom[i] else 0), (hi[i]>>L)+1)) for i in range(3) ]
    lov=[min(xs),min(ys),min(zs)]
    # h4 phantom is POSITION-based like h5 (2026-07-16, item 10): low phantom iff the shape's
    # low voxel sits in the low QUARTER of the h4 cell (lov%32 < 8). The old extent>16 rule
    # was a misfit: C20 3768 (extent 20, lov 8) has NO phantom; M1 3273 (extent 10, zlo 4)
    # HAS one. Mass-scan of 283 single-chunk exports: h4-phantoms nest inside h5-phantoms
    # (thresholds 8 < 16), 2 legacy-format exceptions (2515/2517).
    ph4=[single[i] and (lov[i]%32)<8 for i in range(3)]
    for c in _it.product(*rng(1,ph4)): want.add((4,)+c)
    # h5 phantom is POSITION-based (2026-07-15 mass-check, donors 3502/3508/3510 off-base
    # boxes): low phantom iff the shape occupies the LOW HALF of its low chunk on that axis
    # (local voxel < 16). H1 3579 (4x4x1 plate): the 1-THICK axis gets it too -- extent is
    # NOT the discriminator; only the degenerate 1-voxel cube (sweep 3335) has none at all.
    # The old extent>=2 rule coincided at base-8 donors (always low half).
    ph5=[len(voxels)>1 and (lov[i]%32)<16 for i in range(3)]
    for c in _it.product(*rng(2,ph5)): want.add((5,)+c)
    if _h6_full(voxels):
        for c in _it.product((0,1),(0,1),(0,1)): want.add((6,)+c)
    else:
        for c in _it.product(*rng(3,[False]*3)): want.add((6,)+c)
    for c in _it.product(*rng(4,[False]*3)): want.add((7,)+c)
    return want


def _extract_empty_lod_body(template_path):
    """Grab the standard 694B empty-region LOD body from a template's h6/h7 entry."""
    import json, base64, lz4.block
    bp=json.load(open(template_path))
    for e in bp['VoxelData']:
        if e['h'] in (6,7):
            raw=base64.b64decode(e['records']['voxel']['data']['$binary'])
            dec=bytes(lz4.block.decompress(raw[12:],uncompressed_size=int.from_bytes(raw[4:8],'little')))
            if len(dec)==758: return dec[64:]   # header(64)+body(694), empty cell
    raise ValueError('no empty LOD cell in template')

def _encode_body(body):
    import base64, struct, lz4.block, du_hash
    comp=lz4.block.compress(body, store_size=False)
    raw=b'\xf9\xb6\x14\xfb'+struct.pack('<I',len(body))+b'\x00\x00\x00\x00'+comp
    return base64.b64encode(raw).decode(), du_hash.to_signed64(du_hash.compute_hash(raw))

def _scan_mc(scan):
    """Recover full mc from a scan's mat byte: mc = 512 + mat_byte (mc_law always in [512,768),
    so mc&0xff == mat_byte). Uses du_validate's VALUE-AGNOSTIC parser: marker values 0x00/0xff
    are LEGAL (H6/C3), and big-nc domes emit 0xff OPENERS -- the old local walk here excluded
    them, exited the marker region early and returned 512+0x01 (second byte of a marker) ->
    mc 513 instead of 544 -> 'Deserializing invalid vertex' on EVERY rebuilt big-nc dome
    (Deployments 3659/3694/3697; found via 1-byte blueprint diff vs donor 3700)."""
    import du_validate
    P=du_validate.parse_scan(scan)
    if P.get('mat_hidden') or P['mat'] is None:
        raise ValueError("mat byte is bg-valued (0x00/0xff) -- unrecoverable from scan bytes; "
                         "use du_general.LAST_MC from the build")
    return 512+P['mat']

# Model-skeleton donor: build_blueprint_sem clones VoxelData[0] from it (core-size-independent;
# DU recomputes meta on import). Resolved relative to this module so a fresh clone / container
# works with no absolute paths; OBJTODU_TEMPLATE overrides if you relocate it.
TEMPLATE_M = os.environ.get(
    'OBJTODU_TEMPLATE',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports', 'archive',
                 '3187_export.blueprint'))


def build_blueprint_sem(out_path, voxels, name, smooth_fn=None, yseam_payload=True,
                        material=None, size='M', core_type='static',
                        record_template=TEMPLATE_M, place=None, labels=None, materials=None):
    """From-scratch blueprint via the SEMANTIC emitter (du_semantic). Every voxel body is
    generated whole (h3 = real cells; h4..hN = EMPTY -- DU regenerates LODs client-side).
    The Model/Elements envelope is synthesized via du_envelope. The per-record JSON skeleton
    is cloned from record_template (core-size-independent; DU recomputes meta on import).
    voxels in construct-local coords. smooth_fn(x,y,z)->target maps to per-vertex positions
    (84 steps/vox, clamp +/-100).
    labels: optional (N,) uint8 array of per-voxel material labels (1=base, 2=crease, etc).
    materials: optional [mat_base, mat_crease] list when multi-material is enabled.

    CORE SIZE: all sizes (XS..XXXXXL) are deploy-verified 2026-07-18 (dep20/20b/20c: S/M/L
    boxes rendered). The octree layout per core comes from core_octree_params (levels
    h3..CoreSize.height(), chunk0=2^(height-1), OFF=chunk0*32) + the minimal LOD set."""
    import json, copy
    import time
    import du_semantic, du_envelope
    t0 = time.time()
    print(f"[build_blueprint_sem] Starting blueprint generation for {len(voxels)} voxels...")
    size = size.upper()
    core_h, chunk0, _ = core_octree_params(size)
    # PLACEMENT: the core's placement element sits at world vsz/2 == cell chunk0*32 (donor
    # 3187: element 64.125, content centred at cell 256 == chunk 8*32). So CENTRE the content
    # bbox on chunk0*32 -- the old OFF=chunk0*32 put the content's MIN corner there, leaving
    # its centre half-an-extent past the anchor (dep19f/dep22 deployed offset by ~half the
    # shape). `place` overrides with an explicit per-axis cell offset (tiling: edge-align).
    import numpy as np
    anchor = chunk0 * 32
    # order-independent (output is built from occupancy) -- no sort, just materialise.
    # `voxels` may already be a compact (N,3) numpy array (the 'scale' path via
    # obj_frontend.voxelize_obj) -- use it directly instead of the per-voxel Python
    # generator below, which is both slow and (for a numpy array) would crash on the
    # `if voxels:` truth test (ambiguous for arrays with >1 element).
    if isinstance(voxels, np.ndarray):
        varr = voxels.astype(np.int64, copy=False) if len(voxels) else np.zeros((0, 3), np.int64)
    else:
        varr = (np.fromiter((c for v in voxels for c in v), np.int64, count=3 * len(voxels)).reshape(-1, 3)
                if voxels else np.zeros((0, 3), np.int64))
    if len(varr):
        lo = varr.min(0); hix = varr.max(0)
        if place is None:
            OFF = tuple(int(anchor - (lo[i] + hix[i]) // 2) for i in range(3))
        else:
            OFF = tuple(place)
    else:
        OFF = (anchor, anchor, anchor)
    abs_arr = varr + np.array(OFF, np.int64)                  # placed cells (N,3), numpy
    safe, reasons = du_semantic.semantic_confidence(varr)
    for r in reasons:
        print(f"[validate] WARNING: {r} -- deploy at own risk / verify with a donor")
    # core-fit check: content must sit inside the octree build volume (2^core_h*32 cells)
    build_cells = (1 << (core_h - 3)) * 32
    amax = int(abs_arr.max()) if len(abs_arr) else 0
    amin = int(abs_arr.min()) if len(abs_arr) else 0
    if amin < 0 or amax >= build_cells:
        raise ValueError(f"placed content cells [{amin}..{amax}] fall outside the {size} core "
                         f"build volume [0..{build_cells}) -- scale down or pick a larger core")
    pos_fn = None
    if smooth_fn is not None:
        def pos_fn(p):
            Pl = (p[0] - OFF[0], p[1] - OFF[1], p[2] - OFF[2])
            T = smooth_fn(*Pl)
            d = [max(-100, min(100, round(84 * (T[i] - Pl[i])))) for i in range(3)]
            if d == [0, 0, 0]:
                return None
            return (126 + d[0], 126 + d[1], 126 + d[2])
    mat = material or du_semantic.MAT_HCCARBON
    proto = copy.deepcopy(json.load(open(record_template))['VoxelData'][0])
    # MINIMAL octree derived from the ACTUAL PLACED cells (vox_abs), so the h3 records land on
    # the chunks that really hold the content -- must track the centering/`place` offset, NOT
    # a fixed chunk0 (mismatch = empty meshes, dep23). Non-empty leaves + all ancestors to the
    # single root h(core_h); DU regenerates LOD content from h3 (phantoms unneeded).
    want = octree_from_cells(abs_arr, core_h)
    # Build occupancy grid (bool for single-material, int8 for multi-material)
    if labels is not None and materials is not None:
        label_to_matidx = {1: 2, 2: 3}  # base=2, crease=3 in mapping table
        gocc, glo, gdim = du_semantic.global_material_grid(abs_arr, labels, label_to_matidx)
        # Build multi-material mapping: [DEBUG1@1, base@2, crease@3]
        mapping = [
            (du_semantic.MAT_DEBUG1[0], du_semantic.MAT_DEBUG1[1], 1),
            (materials[0][0], materials[0][1], 2),
            (materials[1][0], materials[1][1], 3)
        ]
        import numpy as np
        print(f"[build_blueprint_sem] MULTI-MATERIAL enabled: mapping={mapping}, "
              f"labels unique={np.unique(labels).tolist()}, dtype={gocc.dtype}")
    else:
        gocc, glo, gdim = du_semantic.global_occupancy(abs_arr)   # slice windows O(1)/chunk
        mapping = None  # single-material: default mapping used in build_cell
        print(f"[build_blueprint_sem] Single-material mode")
    # real Model.Bounds from the material-cell bbox (voxel+1), /4 world units -- DU anchors
    # placement to these; a placeholder box (old bug) deployed the construct offset. Computed
    # here (not after the entries loop) so abs_arr/varr can be freed before the fork below.
    if len(abs_arr):
        mnb = tuple(int(abs_arr[:, i].min()) + 1 for i in range(3))
        mxb = tuple(int(abs_arr[:, i].max()) + 1 for i in range(3))
        bbox = (mnb, mxb)
    else:
        bbox = None
    chunk_list = sorted(want)
    n_workers = _n_workers()
    use_pool = (n_workers > 1 and len(chunk_list) >= _PARALLEL_MIN_CHUNKS
                and 'fork' in multiprocessing.get_all_start_methods())
    global _WORKER_CTX
    ctx_dict = dict(proto=proto, gocc=gocc, glo=glo, gdim=gdim, mat=mat,
                    pos_fn=pos_fn, yseam_payload=yseam_payload)
    if mapping is not None:
        ctx_dict['mapping'] = mapping
    _WORKER_CTX = ctx_dict
    try:
        if use_pool:
            # fork (not spawn/forkserver): pos_fn is a closure and can't be pickled, but a
            # fork()'d child inherits _WORKER_CTX via copy-on-write, so it never has to be --
            # only the small (h,x,y,z) task tuples and the returned record dicts cross the
            # process boundary. Windows/macOS-spawn-default hosts fall through to the serial
            # loop below (still correct, just single-core).
            #
            # fork() COW-maps the WHOLE parent address space into every child, not just
            # _WORKER_CTX -- and CPython refcounting writes to an object's header on every
            # touch, which is a well-known COW-defeater. varr/abs_arr/voxels can be multi-GB
            # for a dense high-res shape and aren't needed past this point (gocc is a separate
            # array already derived from abs_arr), so drop them and force a collection before
            # forking N workers -- otherwise N copies of "mostly untouched but still resident"
            # multi-GB arrays is exactly the OOM this whole fix exists to prevent.
            del varr, abs_arr, voxels
            import gc
            gc.collect()
            ctx = multiprocessing.get_context('fork')
            with ctx.Pool(min(n_workers, len(chunk_list))) as pool:
                entries = pool.map(_emit_chunk, chunk_list)
        else:
            entries = [_emit_chunk(k) for k in chunk_list]
    finally:
        _WORKER_CTX = None
    out = du_envelope.build_envelope(entries, size=size, core_type=core_type, name=name,
                                     bbox=bbox)
    json.dump(out, open(out_path, 'w'))
    elapsed = time.time() - t0
    n_voxels = len(abs_arr) if len(abs_arr) else 0
    print(f"[build_blueprint_sem] Blueprint complete: {len(entries)} LOD entries, "
          f"{n_voxels} voxels, {elapsed:.1f}s, {len(entries)/max(1,elapsed):.1f} entries/sec")
    return want


def build_blueprint_mc(template_path, out_path, scans, voxels, name, mc=None):
    """From-scratch MULTI-CHUNK blueprint. scans: {(cx,cy,cz): h3_scan}. Builds every LOD
    entry from compute_lod_set_mc: h3 = real body (build_h3_body w/ mc-law), h4-h7 = the
    standard empty LOD body (DU regenerates from h3). Clones the template's Model skeleton +
    one VoxelData entry as the JSON prototype. mc: dict/int/None (None -> mc_law per chunk).
    Pre-deploy VALIDATED: raises on any structurally-broken scan (would crash DU); prints
    confidence-region warnings for unmapped single-chunk layout pockets."""
    import json, copy
    import du_assemble, du_synth
    import du_general as dg
    for w in validate_scans(scans, voxels=voxels):   # raises on structural failure
        print(f"[validate] WARNING: {w}")
    bp=json.load(open(template_path))
    out=copy.deepcopy(bp)
    proto=copy.deepcopy(out['VoxelData'][0])
    empty=_extract_empty_lod_body(template_path)
    want=compute_lod_set_mc(voxels)
    cols=to_columns(voxels)
    entries=[]
    for (h,x,y,z) in sorted(want):
        e=copy.deepcopy(proto)
        e['h']=h
        for k,v in (('x',x),('y',y),('z',z)): e[k]={'$numberLong':v}
        if h==3:
            scan=scans[(x,y,z)]
            if mc is not None:
                m = mc[(x,y,z)] if isinstance(mc,dict) else mc
            else:
                try: m = _scan_mc(scan)
                except ValueError:
                    m = dg.LAST_MC[(x,y,z)]   # bg-valued mat byte: take mc from the build
            # encode_voxel_b64 writes voxel_header(x,y,z) -> correct per-chunk coord in the
            # blob header (build_h3_body hardcodes chunk (8,8,8) -> wrong for other chunks,
            # Deployment 14 "Reading too far"). Same proven path as du_assemble/11d.
            b64,hsh=du_assemble.encode_voxel_b64(x,y,z,scan,m)
        else:
            body=du_assemble.voxel_header(x,y,z)+empty
            b64,hsh=_encode_body(body)
        e['records']['voxel']['data']['$binary']=b64
        e['records']['voxel']['hash']['$numberLong']=hsh
        entries.append(e)
    out['VoxelData']=entries
    out['Model']['Name']=name
    json.dump(out, open(out_path,'w'))
    return want
