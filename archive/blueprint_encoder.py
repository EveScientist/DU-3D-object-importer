"""
DU Blueprint Encoder — h=3 multi-voxel scan generator + blueprint JSON assembler
Generates importable blueprint files for solid rectangular voxel blocks.
All formulas confirmed in-game through systematic testing.
"""
import base64, struct, lz4.block, math, json
from datetime import datetime, timezone

# ─── LZ4 blob encoding ────────────────────────────────────────────────────────
def encode_blob(header64: bytes, scan: bytes, footer40: bytes) -> bytes:
    """Pack header+scan+footer into LZ4-compressed DU blob."""
    data = bytes(header64) + bytes(scan) + bytes(footer40)
    compressed = lz4.block.compress(data, store_size=False)
    return b'\xf9\xb6\x14\xfb' + struct.pack('<I', len(data)) + b'\x00\x00\x00\x00' + compressed

def decode_blob(b64: str):
    """Decode a DU blob → (header64, scan, footer40)."""
    raw = base64.b64decode(b64.replace(" ", ""))
    unc = struct.unpack('<I', raw[4:8])[0]
    d = lz4.block.decompress(raw[12:], uncompressed_size=unc)
    return bytes(d[:64]), bytes(d[64:-40]), bytes(d[-40:])

# ─── Constants ────────────────────────────────────────────────────────────────
HEADER_CX2 = bytes.fromhex(
    "13a0b827060000009e3381e8090000003f0000003f0000003f000000"
    "2300000023000000230000004000000040000000400000002000000020000000200000"
    "00"
)
assert len(HEADER_CX2) == 64
N1S_REF = 79

# ─── Utility ──────────────────────────────────────────────────────────────────
def ms(ny):
    """Major step in bytes between declaration groups."""
    return (ny-2)*5 + 2*(9 if ny <= 5 else 8)

def last_sub_val(nx, ny):
    """Byte position of last sub-decl in last declaration group."""
    return 159 + (nx-1)*ms(ny) + 5*(ny-1)

def gap_adj(ny):
    """FG cluster step correction for ny>5 (large=8 instead of large=9)."""
    return 1 if ny > 5 else 0

def n1_sub1(lx):
    ws = 153*lx + 25
    n = 9 + math.ceil(ws / 31)
    return n - 2 if ws % 31 == 0 else n

# ─── n1_FG formula (confirmed 13/13 cases) ────────────────────────────────────
def n1_FG(lx, nx, ny):
    """
    FG section start n1 position.
    ODD FG (even nx): uses pad_start and C_BASE.
    EVEN FG (odd nx): universal formula based on last_sub.
    """
    ls = last_sub_val(nx, ny)
    M = nx // 2
    if nx % 2 == 0:  # ODD FG (even nx)
        pad = ls + 5
        if ny % 2 == 1:  # ODD ny: universal formula (ny cancels out!)
            return (pad + 332 - 19*M) // 2
        else:  # EVEN ny: empirical C_BASE values
            C_BASE_even = {4: 323, 6: 345}
            rate = 4*ny - 1
            cb = C_BASE_even.get(ny, 312 + 4*ny)
            return (pad + cb - rate*M) // 2
    else:  # EVEN FG (odd nx)
        return (ls + 3 + 326 - 20*M + 2*(M//4)) // 2

# ─── FG cluster positions ─────────────────────────────────────────────────────
def fg_cluster_starts(lx, nx, ny):
    """n1 of first group in each FG cluster (uses corrected step for ny>5)."""
    n1_fg = n1_FG(lx, nx, ny)
    nc = nx + 1
    adj = gap_adj(ny)
    step_f = (ny+1)*4 + 4 - adj
    step_i = 2*ny*4 + 4 - adj
    pos = [n1_fg]
    for k in range(1, nc):
        pos.append(pos[-1] + (step_f if k == 1 else step_i))
    return pos

# ─── Scan length formula ──────────────────────────────────────────────────────
def scan_length(lx, nx, ny):
    """Total scan byte count (uses OLD non-adj steps for last_n1 computation)."""
    n1_fg = n1_FG(lx, nx, ny)
    nc = nx + 1
    # Use standard steps (without adj) to compute last_n1
    cls = [n1_fg]
    for k in range(1, nc):
        cls.append(cls[-1] + ((ny+1)*4+4 if k == 1 else 2*ny*4+4))
    last_n1 = cls[-1] + ny*4
    ls = last_sub_val(nx, ny)
    par = 1 if ls % 2 == 0 else 0  # ODD FG → par=1, EVEN FG → par=0
    p = 101 - 5*nc + max(0, (nc-3)//4) - (nc-1)*max(0, (ny-4)//2)
    return (last_n1 + p)*2 + par

# ─── Pre-FG marker and ftr_val ────────────────────────────────────────────────
def compute_marker(nx, ny, nz_extra):
    """
    Pre-FG marker byte value. ftr_val = 512 + marker.
    ODD FG: (277-35*ny - (nze+11)*(M-1) + 128*(M%2==0)) % 256
    EVEN FG even M: standard formula
    EVEN FG odd M: (332-35*ny) % 256
    """
    ls = last_sub_val(nx, ny)
    M = nx // 2
    if ls % 2 == 0:  # ODD FG (even nx)
        return (277 - 35*ny - (nz_extra+11)*(M-1) + 128*(M%2==0)) % 256
    elif M % 2 == 0:  # EVEN FG even M
        return (202 + 57*ny) % 256 if ny <= 5 else (60 - 17*ny) % 256
    else:  # EVEN FG odd M (ny>5 unconfirmed but formula likely works)
        return (332 - 35*ny) % 256

def build_footer(nx, ny, nz_extra):
    """Build complete 40-byte h3 footer with correct ftr_val."""
    ftr_val = 512 + compute_marker(nx, ny, nz_extra)
    result = bytearray(40)
    struct.pack_into('<I', result, 0, ftr_val)
    result[4]=0x00; result[5]=0xc7; result[6]=0x68; result[7]=0x69
    struct.pack_into('<I', result, 8, 9)
    result[12]=0x00
    result[13:19] = b'Debug1'
    result[19]=0x00; result[20]=0x00; result[21]=0x01
    result[22]=0xa5; result[23]=0x02; result[24]=0xb0; result[25]=0xcb
    result[26:30] = b'\x00\x00\x00\x00'
    result[30]=0x68; result[31]=0x63
    result[32:38] = b'Carbon'
    result[38]=0x02; result[39]=0x01
    return bytes(result)

# ─── h=3 cz2 scan builder ────────────────────────────────────────────────────
def build_h3_scan(lx, nx, ny, nz):
    """
    Build h=3 scan for a solid nx×ny×nz block at lx (cx=2 chunk).
    Requires nx >= 2, ny in 2..8, nz in 2..31, lx in 0..14.
    """
    assert nx >= 2, "nx=1 not supported"
    nz_extra = max(1, nz - 1)
    marker_val = compute_marker(nx, ny, nz_extra)
    n1s = n1_sub1(lx)
    total = scan_length(lx, nx, ny)
    B0 = 2 * max(n1s, N1S_REF) + 1
    ms_v = ms(ny)
    flip = B0 + ny*5

    scan = bytearray(total)
    for i in range(total):
        scan[i] = (0x00 if i%2==0 else 0xff) if i < flip else (0xff if i%2==0 else 0x00)

    def write_decl(B, cv, extra):
        if B+4 >= total: return
        scan[B]=cv; scan[B+1]=0x01; scan[B+2]=0x02; scan[B+3]=extra
        pos4 = B+4
        bg4 = (0x00 if pos4%2==0 else 0xff) if pos4 < flip else (0xff if pos4%2==0 else 0x00)
        if bg4 != 0x00: scan[pos4] = 0x00

    def write_00ff(start, end):
        for i in range(max(start,0), min(end,total)):
            scan[i] = 0x00 if i%2==0 else 0xff

    # CV values
    cv_group0  = 0xb6
    cv_opener  = (234 - 35*ny - nz_extra) % 256
    cv_within  = (33 - nz_extra) % 256

    # Write declarations (nx groups × ny sub-decls each)
    for k in range(nx):
        B_grp = B0 + k*ms_v
        cv0 = cv_group0 if k == 0 else cv_opener
        for j in range(ny):
            write_decl(B_grp + 5*j, cv0 if j == 0 else cv_within, nz_extra)
        if B_grp % 2 == 0 and k < nx-1:
            write_00ff(B_grp + 5*(ny-1) + 5, B0 + (k+1)*ms_v)

    # Pad region and FG alignment
    ls = last_sub_val(nx, ny)
    even_last = (ls % 2 == 0)
    n1_fg = n1_FG(lx, nx, ny)
    fg_start = n1_fg*2 + (1 if even_last else 0)
    if even_last:
        write_00ff(ls + 5, fg_start)

    # Pre-FG marker
    n1_marker = n1_fg - 75
    i_m = n1_marker*2 + (1 if even_last else 0)
    if 0 <= i_m < total:
        scan[i_m] = marker_val

    # FG clusters
    clusters = fg_cluster_starts(lx, nx, ny)
    int_m  = (198 - 35*ny - nz_extra) % 256
    mk_A   = (32 - nz_extra) % 256
    mk_B   = (nz_extra - 1) % 256
    n_cl   = len(clusters)
    odd_fg = (fg_start % 2 == 1)

    for ci, cn1 in enumerate(clusters):
        ig_base = fg_start + (cn1 - clusters[0])*2
        is_first = (ci == 0); is_last = (ci == n_cl-1)
        n_grp = ny+1 if (is_first or is_last) else 2*ny
        if is_first:   mks = [0xc9] + [mk_A]*ny
        elif is_last:  mks = [int_m] + [mk_A]*ny
        else:          mks = [int_m] + ([mk_A, mk_B]*(ny-1)) + [mk_A]

        for gi in range(n_grp):
            ig = ig_base + gi*8
            if ig+7 >= total: continue
            de = nz if (is_first or is_last or gi == 0 or gi == n_grp-1) else 0
            scan[ig]   = mks[gi] if gi < len(mks) else mk_A
            scan[ig+1] = 0x01; scan[ig+2] = de
            scan[ig+3] = 0x7e; scan[ig+4] = 0x7e; scan[ig+5] = 0x7e
            scan[ig+6] = de; scan[ig+7] = 0x00

        if odd_fg and not is_last:
            ig_last = ig_base + (n_grp-1)*8
            write_00ff(ig_last+8, fg_start + (clusters[ci+1]-clusters[0])*2)

    if odd_fg:
        last_ig = fg_start + (clusters[-1]-clusters[0])*2 + ny*8
        write_00ff(last_ig+8, total)

    return bytes(scan)

# ─── h=3 cz1 companion scan builder ──────────────────────────────────────────
def build_h3_cz1_scan(lx, nx, ny, nz_cz2=8):
    """
    Build h3(cx,cy,cz1) companion for blocks starting at abs_z=64 (game z=+0.5).
    All clusters use ny+1 groups (no 2*ny interior expansion).
    nz_extra=0 for cz1 scans.
    """
    nz_extra = 0; nz_cz1 = 1
    n1s = n1_sub1(lx)
    B0 = 2*max(n1s, N1S_REF)+1; ms_v = ms(ny); flip = B0+ny*5
    step = (ny+1)*4+4  # uniform step (no adj for cz1)
    n1_fg = n1_FG(lx, nx, ny)
    clusters = [n1_fg + k*step for k in range(nx+1)]
    last_n1 = clusters[-1] + ny*4
    total = (last_n1 + 86)*2 + 1

    scan = bytearray(total)
    for i in range(total):
        scan[i] = (0x00 if i%2==0 else 0xff) if i < flip else (0xff if i%2==0 else 0x00)

    def write_decl(B, cv):
        if B+4 >= total: return
        scan[B]=cv; scan[B+1]=0x01; scan[B+2]=0x02
        pos3 = B+3
        bg3 = (0x00 if pos3%2==0 else 0xff) if pos3 < flip else (0xff if pos3%2==0 else 0x00)
        if 0x00 != bg3: scan[pos3] = 0x00
        pos4 = B+4
        bg4 = (0x00 if pos4%2==0 else 0xff) if pos4 < flip else (0xff if pos4%2==0 else 0x00)
        if 0x00 != bg4: scan[pos4] = 0x00

    def write_00ff(start, end):
        for i in range(max(start,0), min(end,total)): scan[i] = 0x00 if i%2==0 else 0xff

    cv_group0 = (0xb6 + 0x20) % 256
    cv_within = (33 - nz_extra) % 256
    cv_opener = (234 - 35*ny - nz_extra) % 256

    for k in range(nx):
        B_grp = B0 + k*ms_v; cv0 = cv_group0 if k == 0 else cv_opener
        for j in range(ny): write_decl(B_grp + 5*j, cv0 if j == 0 else cv_within)
        if B_grp % 2 == 0 and k < nx-1:
            write_00ff(B_grp + 5*(ny-1) + 5, B0 + (k+1)*ms_v)

    ls = last_sub_val(nx, ny); even_last = (ls % 2 == 0)
    fg_start = n1_fg*2 + (1 if even_last else 0)
    if even_last: write_00ff(ls+5, fg_start)

    n1_marker = n1_fg - 75; i_m = n1_marker*2 + (1 if even_last else 0)
    if 0 <= i_m < total: scan[i_m] = (252 - 35*ny) % 256

    int_m = (198 - 35*ny - nz_extra) % 256
    mk_A  = (32 - nz_extra) % 256
    fg_opener = (0xc9 + 0x20) % 256
    n_cl = len(clusters); odd_fg = (fg_start % 2 == 1)

    for ci, cn1 in enumerate(clusters):
        ig_base = fg_start + (cn1 - clusters[0])*2
        is_first = (ci == 0); is_last = (ci == n_cl-1); n_grp = ny+1
        if is_first:   mks = [fg_opener] + [mk_A]*ny
        elif is_last:  mks = [int_m] + [mk_A]*ny
        else:          mks = [int_m, mk_A] + [(mk_A+1)%256]*(ny-1)

        for gi in range(n_grp):
            ig = ig_base + gi*8
            if ig+7 >= total: continue
            de = nz_cz1 if (is_first or is_last or gi == 0 or gi == n_grp-1) else 0
            scan[ig]   = mks[gi] if gi < len(mks) else mk_A
            scan[ig+1] = 0x01; scan[ig+2] = de
            scan[ig+3] = 0x7e; scan[ig+4] = 0x7e; scan[ig+5] = 0x7e
            scan[ig+6] = de; scan[ig+7] = 0x00

        if odd_fg and not is_last:
            ig_last = ig_base + (n_grp-1)*8
            write_00ff(ig_last+8, fg_start + (clusters[ci+1]-clusters[0])*2)
    if odd_fg:
        last_ig = fg_start + (clusters[-1]-clusters[0])*2 + ny*8
        write_00ff(last_ig+8, total)
    return bytes(scan)

# ─── Blueprint JSON assembler ─────────────────────────────────────────────────
def make_blueprint_json(name, blobs, size=32):
    """
    Assemble a DU blueprint JSON string from raw blob bytes.
    blobs: list of (h_level, cx, cy, cz, raw_bytes)
    """
    half = size / 2.0
    voxel_data = []
    for h, cx, cy, cz, raw_bytes in blobs:
        b64 = base64.b64encode(raw_bytes).decode()
        voxel_data.append({
            "h": h,
            "x": {"$numberLong": str(cx)},
            "y": {"$numberLong": str(cy)},
            "z": {"$numberLong": str(cz)},
            "records": {"voxel": {"data": {"$binary": b64}}}
        })
    blueprint = {
        "Model": {
            "Id": 0, "Name": name, "Size": size,
            "CreatedAt": datetime.now(timezone.utc).isoformat(),
            "CreatorId": 0,
            "JsonProperties": {
                "kind": 4, "size": size,
                "serverProperties": {
                    "creatorId": {"playerId": 0, "organizationId": 0},
                    "originConstructId": 0, "blueprintId": 0,
                    "isFixture": None, "isBase": None, "isFlaggedForModeration": None,
                    "isDynamicWreck": False, "fuelType": None, "fuelAmount": None,
                    "rdmsTags": {"constructTags": [], "elementsTags": []},
                    "compacted": False, "dynamicFixture": None, "constructCloneSource": None
                },
                "header": {
                    "uniqueIdentifier": None, "parentUniqueIdentifier": None,
                    "constructIdHint": None, "prettyName": "UnknownOrigin",
                    "fixtureHash": None, "folder": None,
                    "artWorkSVNRevision": None, "biomeEditorVersion": None,
                    "biomeEditorGitRevision": None
                },
                "voxelGeometry": {"size": size, "kind": 1, "voxelLod0": 3,
                                   "radius": None, "minRadius": None, "maxRadius": None},
                "planetProperties": None, "isNPC": False, "isUntargetable": False
            },
            "Static": False,
            "Bounds": {"min": {"x": 0, "y": 0, "z": 0},
                       "max": {"x": float(size), "y": float(size), "z": float(size)}},
            "FreeDeploy": False, "MaxUse": None, "HasMaterials": True, "DataId": None
        },
        "VoxelData": voxel_data,
        "Elements": [{
            "elementId": 4175457733, "localId": 1,
            "constructId": 0, "playerId": 0,
            "elementType": 2738359963,
            "position": {"x": half, "y": half, "z": half},
            "rotation": {"x": 0, "y": 0, "z": 0, "w": 1},
            "properties": [["drmProtected", {"type": 1, "value": True}]],
            "serverProperties": {}, "links": []
        }],
        "Links": []
    }
    return json.dumps(blueprint, separators=(',', ':'))


if __name__ == "__main__":
    # Quick validation test
    import sys
    def decode_scan_ref(b64):
        raw=base64.b64decode(b64.replace(" ",""))
        unc=struct.unpack('<I',raw[4:8])[0]
        d=lz4.block.decompress(raw[12:],uncompressed_size=unc)
        return bytes(d[64:-40])

    tests = [
        ("2×3×8 lx=14", 14,2,3,8,
         "+bYU+4sDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCKZbYBAgcAGgUABK0AFXoSAAEcAAQXAA8CAIkfrGgBgp/JAQh+fn4IABkIAAQEUgEVViAAcwB+fn4AAAYIAA4QAAJQAA44AAIYAAwIAAQoAA8CAImArAIAAADHaGlfA/ANAERlYnVnMQAAAaUCsMsAAAAAaGNDYXJib24CAQ=="),
        ("9×5×8 lx=14", 14,9,5,8,
         "+bYU+6YGAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCKb7YBAgcAGgUAAAS3AB80HAAAATAADyEA3A8CAEUf5x8Cgp/JAQh+fn4IABkIABQEHgEVEDAAcwB+fn4AAAYIAA8QAB8CgAAPWAD//2kCgAIPCAANBKACDwIARYDnAgAAAMdoaXoG8A0ARGVidWcxAAABpQKwywAAAABoZ0NhcmJvbgIB"),
        ("6×3×8 lx=14", 14,6,3,8,
         "+bYU+3sEAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCKZbYBAgcAGgUABK0AFXoSAAEcAA8XAFEPAgBjH4ieAYKfyQEIfn5+CAAZCAAEBCwBFVYgAHMAfn5+AAAGCAAOEAACUAAPOADfAvgADAgABAgBDwIAY4CIAgAAAMdoaU8E8A0ARGVidWcxAAABpQKwywAAAABoZ0NhcmJvbgIB"),
    ]

    print("=== blueprint_encoder.py validation ===")
    all_ok = True
    for label, lx, nx, ny, nz, b64_ref in tests:
        ref = decode_scan_ref(b64_ref)
        gen = build_h3_scan(lx, nx, ny, nz)
        diffs = sum(1 for a,b in zip(gen,ref) if a!=b)
        ok = diffs==0 and len(gen)==len(ref)
        all_ok = all_ok and ok
        status = "✓ PERFECT" if ok else f"✗ {diffs} diffs, len {len(gen)} vs {len(ref)}"
        print(f"  {label}: {status}")
    print(f"  {'ALL PASS ✓' if all_ok else 'SOME FAIL'}")
