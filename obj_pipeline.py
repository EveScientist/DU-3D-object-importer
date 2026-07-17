"""obj_pipeline.py -- ARC #13: voxel occupancy -> column intervals -> build_multichunk
-> deployable blueprint. The back half of the .obj pipeline (front half = obj_to_du_voxels.py
surface voxelizer). Strategy (user-locked): voxelize a BLOCKY base, deploy it, then later
deflect face-points to the true surface via the wired smoothing layer.

Stage map:
  voxels {(x,y,z)}  --solid_fill-->  solid voxels  --to_columns-->  cols {(x,y):[(zlo,zhi)..]}
  cols  --build_multichunk-->  {(cx,cy,cz): scan}  --assemble-->  blueprint JSON
"""
import sys
sys.path.insert(0, '/home/du')
import du_general as dg


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
    if voxels is not None and len(scans) == 1:
        cols = to_columns(voxels)
        safe, reason = V.in_confidence_region(cols)
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
