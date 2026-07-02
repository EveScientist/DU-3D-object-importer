#!/usr/bin/env python3
"""
generate_hollow_cube.py
Voxel body format reverse-engineered from 122_export.blueprint (hollow cube, XS static core).

Scan format (h=3) — verified against 188_export (all 8 chunks) and 187_export:
  CV      = (32*n + BASE_corner) % 256  — position + material dependent
  n       = (4 - Wx - 3*Wy - Wz) % 8   — Wx=1 if lx==0, Wy=1 if ly==0, Wz=1 if lz==0
  n1_first = 4 + (153*lx + 4*ly + lz_eff) // 31  — position-dependent (leading 00ff pairs)
              where lz_eff = 32 if (lz==0 and (lx>0 or ly>0)) else lz
  gap     = 162 if n in {4,7} else 163
  FG_START = n1_first + 3 + gap
  marker_val = (120 - CV) % 256   — varies per chunk; if 0xff, replace with 0x00
  ftr_val  = 512 + marker_val     — stored as uint32LE at mat[0:4]
  marker_pair = gap + 7           — absolute pair index (169 or 170)
  G1_opener = (CV + 19) % 256     — if 0xff (reserved), fallback to marker_val
  trailing = (166 if n in {4,7} else 167) - n1_first

  Verified: 188_export 8/8 chunks, 187_export 8/8 chunks.
  BASE_corner: hcSodium=249, hcCarbon=31 (NOT 179 -- 179 gave CV=51 for n=4 interior
    voxels -> negative GAP; MATERIALS_INFO uses 31). hcAlLiPa=12 UNCALIBRATED (real ~89).
    NOTE: this file is REFERENCE-ONLY (sparse decoder aid), not the pipeline; the pipeline
    encodes interiors via the DENSE h3_generator lineage (byte-exact). See architecture-decision.
"""

import argparse, base64, hashlib, json, random, struct
import lz4.block
from scan_gen_h4 import make_h4_blob, h4_chunk_coords
from scan_gen_h5 import make_h5_blob, h5_chunk_coords

BLOB_MAGIC = bytes([0xF9, 0xB6, 0x14, 0xFB])
CHUNK_SIZE  = 32
_HDR_C0 = 666411027; _HDR_C1 = 6; _HDR_C2 = 3900781470; _HDR_C3 = 9
STATIC_CORE_XS_NQID = 2738359963  # Static Core Unit XS (from 122_export)
STATIC_CORE_M_NQID  = 909184430   # Static Core Unit M

# Material definitions: (hash_bytes4, 8-char name, BASE_corner, BASE_face)
# hash_bytes4: raw 4 bytes as they appear in the blueprint file
MATERIALS_INFO = {
    'hcSodium':  (bytes.fromhex('69670374'), b'hcSodium', 249, 1),
    'hcCarbon':  (bytes.fromhex('a502b0cb'), b'hcCarbon',  31, 9),
    'hcAlLiPa':  (bytes.fromhex('c60fb674'), b'hcAlLiPa',  12, 12),
}
DEFAULT_MAT = 'hcSodium'

_DEBUG1_HASH = bytes.fromhex('c7686909')
_DEBUG1_NAME = b'Debug1\x00\x00'

def _mat_section(mat_name_bytes, mat_hash_bytes, marker=0):
    """Build 40-byte material section. ftr_val = 512 + marker (uint32LE at offset 0)."""
    def record(hash4, name8, local_id):
        return hash4 + b'\x00\x00\x00\x00' + name8 + bytes([local_id])
    r1 = record(_DEBUG1_HASH, _DEBUG1_NAME, 1)
    r2 = record(mat_hash_bytes, mat_name_bytes, 2)
    section = bytes([marker & 0xFF]) + struct.pack('<I', 2) + r1 + r2 + b'\x01'
    assert len(section) == 40
    return section

def _blob(p):
    c = lz4.block.compress(p, store_size=False)
    return BLOB_MAGIC + struct.pack('<I', len(p)) + b'\x00\x00\x00\x00' + c

def _b64(b): return base64.b64encode(b).decode()

def _hdr(cx, cy, cz):
    h = bytearray(64)
    for i, v in enumerate([_HDR_C0, _HDR_C1, _HDR_C2, _HDR_C3,
                            (cx*CHUNK_SIZE-1) & 0xFFFFFFFF,
                            (cy*CHUNK_SIZE-1) & 0xFFFFFFFF,
                            (cz*CHUNK_SIZE-1) & 0xFFFFFFFF,
                            CHUNK_SIZE+3, CHUNK_SIZE+3, CHUNK_SIZE+3,
                            cx*CHUNK_SIZE, cy*CHUNK_SIZE, cz*CHUNK_SIZE,
                            CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE]):
        struct.pack_into('<I', h, i*4, v)
    return bytes(h)

def _n1_first(lx, ly, lz):
    """Leading 00ff pairs before declarations. Position-dependent."""
    lz_eff = 32 if (lz == 0 and (lx > 0 or ly > 0)) else lz
    return 4 + (153*lx + 4*ly + lz_eff) // 31

def _scan_n1(lx, ly, lz):
    """Sort key for voxels by scan position (= n1_first value)."""
    return _n1_first(lx, ly, lz)

def _get_n(lx, ly, lz):
    Wx = 1 if lx == 0 else 0
    Wy = 1 if ly == 0 else 0
    Wz = 1 if lz == 0 else 0
    return (4 - Wx - 3*Wy - Wz) % 8

def _corner_val(lx, ly, lz, base_corner):
    return (32 * _get_n(lx, ly, lz) + base_corner) % 256


def _voxel_blob_h3(cx, cy, cz, vox_set, mat_name, base_corner):
    """Build h=3 voxel blob.

    Scan structure (verified against 188_export and 187_export, all chunks):
      n1_first = 4 + (153*lx + 4*ly + lz_eff)//31   (position-dependent)
      gap      = 162 if n in {4,7} else 163
      FG_START = n1_first + 3 + gap
      marker_val = (120 - CV) % 256;  if 0xff → 0x00 (and no scan marker placed)
      marker_pair = gap + 7             (169 or 170, absolute position)
      G1_opener = (CV+19)%256;  if 0xff → marker_val (fallback)
      trailing = (166 if n in {4,7} else 167) - n1_first
    """
    mat_info = MATERIALS_INFO[mat_name]

    if not vox_set:
        scan = bytearray(352 * 2)
        for i in range(0, len(scan), 2):
            scan[i] = 0x00; scan[i+1] = 0xff
        mat = _mat_section(mat_info[1], mat_info[0], 0)
        return _blob(_hdr(cx, cy, cz) + bytes(scan) + mat)

    sorted_vox = sorted(vox_set, key=lambda v: _scan_n1(*v))
    N = len(sorted_vox)

    # Scan parameters derived from first (minimum-n1) voxel
    CV = _corner_val(*sorted_vox[0], base_corner)
    n  = _get_n(*sorted_vox[0])
    N1_FIRST = _n1_first(*sorted_vox[0])
    gap      = 162 if n in (4, 7) else 163
    # At position (0,0,0) the formula gives n1_first=4, placing FG_START=169=marker_pair.
    # When G1_raw≠0xff the marker (marker_val) and FG opener (G1_OPENER) differ, so they
    # can't share the same pair. Game resolves this by using n1_first=9 → FG_START=174.
    # When G1_raw==0xff the fallback makes G1_OPENER=marker_val — they are identical so
    # sharing pair 169 is fine and n1_first stays 4.
    if N1_FIRST == 4 and (CV + 19) % 256 != 0xff and CV != 0xff:
        N1_FIRST = 9
    FG_START = N1_FIRST + 3 + gap
    marker_val = (120 - CV) % 256
    # 0xFF means the gap background (ff00) IS the implicit marker — no explicit overwrite needed
    marker_pair = gap + 7          # absolute pair: 169 (gap=162) or 170 (gap=163)
    G1_OPENER = (CV + 19) % 256
    if G1_OPENER == 0xff or CV == 0xff:
        G1_OPENER = marker_val     # engine fallback when 0xff is reserved

    # ftr encodes the byte actually at marker_pair in the scan (marker_val normally;
    # G1_OPENER only when they share the same pair, i.e. the 0xff-fallback/n1=4 case)
    ftr_marker = G1_OPENER if marker_pair >= FG_START else marker_val
    mat = _mat_section(mat_info[1], mat_info[0], ftr_marker)

    # CV=0xff special case (hcCarbon bc=31, n=7, lx=ly=lz=0, single voxel).
    # The (00,ff) declaration byte is background-identical and must be omitted.
    # The scan starts with (01,02),(00,00) directly, uses only one FG group, and uses
    # 0x00 (not 0x01) at FG bytes 2 and 6. Derived from 143_export chunk (3,3,3).
    if CV == 0xff and N == 1:
        scan = bytearray(680)
        scan[0], scan[1] = 0x01, 0x02
        scan[2], scan[3] = 0x00, 0x00
        for i in range(2, 169):
            scan[i*2] = 0xff; scan[i*2+1] = 0x00
        scan[338:346] = bytes([marker_val & 0xFF, 0x01, 0x00, 0x7e, 0x7e, 0x7e, 0x00, 0x00])
        for i in range(173, 340):
            scan[i*2] = 0xff; scan[i*2+1] = 0x00
        return _blob(_hdr(cx, cy, cz) + bytes(scan) + mat)

    # Build corner declaration section: 3 pairs per voxel + 2 compact pairs between voxels
    decl_bytes = bytearray()
    for i, (lx, ly, lz) in enumerate(sorted_vox):
        cv = _corner_val(lx, ly, lz, base_corner)
        decl_bytes += bytes([0x00, cv, 0x01, 2, 0x00, 0x00])  # 3 pairs
        if i < N - 1:
            decl_bytes += bytes([0x21, 0x01, 0x02, 0x00])      # 2 compact face pairs
    decl_pairs = len(decl_bytes) // 2  # = 5*N - 2

    # Face groups: 4 per voxel (Z1 group, optional gap, Z0 group)
    FG_Z1 = bytes([G1_OPENER, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00,
                   0x20,       0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00])
    FG_Z0 = bytes([0xa3, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00,
                   0x20, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00])
    fg_bytes = bytearray()
    for _ in range(N):
        fg_bytes += FG_Z1
    if N == 1:
        fg_bytes += bytes([0xff, 0x00] * 4)  # 4-pair gap for single-voxel chunks
    for _ in range(N):
        fg_bytes += FG_Z0
    fg_pairs = len(fg_bytes) // 2

    trailing = (166 if n in (4, 7) else 167) - N1_FIRST
    total_scan_pairs = FG_START + fg_pairs + trailing

    scan = bytearray(total_scan_pairs * 2)
    # Preamble: n1_first pairs of 00ff
    for i in range(N1_FIRST):
        scan[i*2] = 0x00; scan[i*2+1] = 0xff
    # Declarations
    dstart = N1_FIRST * 2
    scan[dstart:dstart + len(decl_bytes)] = decl_bytes
    # Gap: ff00 from end-of-decl to FG_START
    for i in range(N1_FIRST + decl_pairs, FG_START):
        scan[i*2] = 0xff; scan[i*2+1] = 0x00
    # Pre-FG marker: place only when not 0xFF (0xFF = gap background ff00 is the implicit marker)
    # Skip when marker_pair >= FG_START (G1_OPENER byte at FG_START serves as marker)
    if marker_pair < FG_START and marker_val != 0xFF:
        scan[marker_pair * 2]     = marker_val
        scan[marker_pair * 2 + 1] = 0x00
    # Face groups
    fg_start_byte = FG_START * 2
    scan[fg_start_byte:fg_start_byte + len(fg_bytes)] = fg_bytes
    # Trailing: ff00
    for i in range(FG_START + fg_pairs, total_scan_pairs):
        scan[i*2] = 0xff; scan[i*2+1] = 0x00

    return _blob(_hdr(cx, cy, cz) + bytes(scan) + mat)


# h=5: placeholder (formula not yet derived)
_META_BASE = bytearray(347)
_META_BASE[0:4] = bytes([0xC0, 0xF3, 0x81, 0x9F])
_META_BASE[4] = 8; _META_BASE[8] = 9; _META_BASE[9] = 1
_META_BASE[18] = 1; _META_BASE[27] = 1; _META_BASE[68] = 1
_MESH = bytes.fromhex('1c974a7503000000000000000000000000000000')

_H5_SCAN = bytearray(672)
for i in range(0, 672, 2):
    _H5_SCAN[i] = 0x00; _H5_SCAN[i+1] = 0xff
_H5_SCAN[334] = 0x00; _H5_SCAN[335] = 0x7a
_H5_SCAN[670] = 0x00; _H5_SCAN[671] = 0x7a
_H5_MAT = bytes.fromhex('01000000c76869090000000044656275673100000101')

def _voxel_blob_h5(cx, cy, cz):
    return _blob(_hdr(cx, cy, cz) + bytes(_H5_SCAN) + _H5_MAT)


# Server-recognized placeholder for h4/h5 — ftr=0xFF00FF00 signals "regenerate from h3".
# Derived from 143_export (in-game export of hcCarbon construct).
_PLACEHOLDER_SCAN = bytearray(654)
for _i in range(327):
    _PLACEHOLDER_SCAN[_i*2] = 0x00; _PLACEHOLDER_SCAN[_i*2+1] = 0xff
_PLACEHOLDER_SCAN[334] = 0x00; _PLACEHOLDER_SCAN[335] = 0x7a
_PLACEHOLDER_MAT = bytes.fromhex(
    '00ff00ff00ff00ff00ff00ff00ff00ff007a0100'
    '0000c76869090000000044656275673100000101'
)

def _placeholder_blob(cx, cy, cz):
    return _blob(_hdr(cx, cy, cz) + bytes(_PLACEHOLDER_SCAN) + _PLACEHOLDER_MAT)


def _extract_scan_mat(blob_bytes):
    """Decompress blob and return (scan, mat) sections."""
    unc = struct.unpack('<I', blob_bytes[4:8])[0]
    raw = lz4.block.decompress(blob_bytes[12:], uncompressed_size=unc)
    return raw[64:-40], raw[-40:]

def _meta_blob(cx, cy, cz):
    m = bytearray(_META_BASE)
    m[10:18] = hashlib.sha256(f'{cx},{cy},{cz}'.encode()).digest()[:8]
    m[93] = 1; m[98] = 1
    return _blob(bytes(m))

def _mesh_blob(): return _blob(_MESH)

def _compute_bounds(voxels, pad=0.2):
    """Approximate Bounds from raw voxel-index AABB + fixed padding.

    The server's actual rendered mesh extends past the nominal voxel grid
    due to corner-declination smoothing (confirmed empirically: a single
    voxel adjacent to the construct center has its true mesh bulge ~0.17m
    past the nominal boundary). Replicating that exactly would mean
    reimplementing DU's mesher. Confirmed via real deployment (2026-06-19)
    that the server regenerates mesh/bounds independently of what's
    supplied here, so an approximate AABB+padding value is sufficient.
    """
    xs = [v[0] for v in voxels]
    ys = [v[1] for v in voxels]
    zs = [v[2] for v in voxels]
    return {
        "min": {"x": min(xs) * 0.25 - pad, "y": min(ys) * 0.25 - pad, "z": min(zs) * 0.25 - pad},
        "max": {"x": (max(xs) + 1) * 0.25 + pad, "y": (max(ys) + 1) * 0.25 + pad,
                "z": (max(zs) + 1) * 0.25 + pad},
    }


def hollow_cube(x0, y0, z0, x1, y1, z1):
    v = set()
    for x in range(x0, x1+1):
        for y in range(y0, y1+1):
            for z in range(z0, z1+1):
                if x in (x0, x1) or y in (y0, y1) or z in (z0, z1):
                    v.add((x, y, z))
    return v


def build(voxels, grid_size, core_nqid, name, mat_name=DEFAULT_MAT, json_size=None):
    mat_info = MATERIALS_INFO[mat_name]
    base_corner = mat_info[2]

    chunks = {}
    for vx, vy, vz in voxels:
        k = (vx//CHUNK_SIZE, vy//CHUNK_SIZE, vz//CHUNK_SIZE)
        chunks.setdefault(k, set()).add((vx%CHUNK_SIZE, vy%CHUNK_SIZE, vz%CHUNK_SIZE))

    model_id = random.randint(10_000_000, 99_999_999)
    now = "2025-01-01T00:00:00.000000+00:00"

    def entry(cx, cy, cz, lset, h):
        vb = _voxel_blob_h3(cx, cy, cz, lset, mat_name, base_corner)
        return {
            "created_at": {"$date": now}, "h": h, "k": 0,
            "metadata": {"mversion": 0, "pversion": 4, "uptodate": True, "version": 8},
            "oid": {"$numberLong": model_id},
            "records": {
                "meta":  {"data": {"$binary": _b64(_meta_blob(cx, cy, cz)), "$type": "0x0"},
                          "hash": {"$numberLong": 0}, "updated_at": {"$date": now}},
                "voxel": {"data": {"$binary": _b64(vb), "$type": "0x0"},
                          "hash": {"$numberLong": 0}, "updated_at": {"$date": now}},
            },
            "updated_at": {"$date": now}, "version": {"$numberLong": 1},
            "x": {"$numberLong": cx}, "y": {"$numberLong": cy}, "z": {"$numberLong": cz},
        }

    # Phase 1: generate h=3 blobs, store scan/mat for h4 derivation
    vd = []
    h3_blob_data = {}  # (cx3,cy3,cz3) → (blob_bytes, scan, mat)
    for (cx3, cy3, cz3), lset in sorted(chunks.items()):
        vb = _voxel_blob_h3(cx3, cy3, cz3, lset, mat_name, base_corner)
        scan, mat = _extract_scan_mat(vb)
        h3_blob_data[(cx3, cy3, cz3)] = (vb, scan, mat)
        vd.append(entry(cx3, cy3, cz3, lset, 3))

    # Phase 2: generate h=4 blobs from h=3 scans.
    # h4 coord = h3 coord // 2 (each h4 covers 2×2×2 h3 chunks).
    # Simple case (one h3 per h4): generate from h3 scan — formula verified.
    # Complex case (multiple h3 per h4): aggregation formula not yet solved, use placeholder.
    h4_to_h3 = {}  # (cx4,cy4,cz4) → list of (cx3,cy3,cz3)
    for (cx3, cy3, cz3) in h3_blob_data:
        k4 = h4_chunk_coords(cx3, cy3, cz3)
        h4_to_h3.setdefault(k4, []).append((cx3, cy3, cz3))

    h4_data = {}  # (cx4,cy4,cz4) → (scan, mat) or None if placeholder
    for (cx4, cy4, cz4), h3_list in sorted(h4_to_h3.items()):
        if len(h3_list) == 1:
            cx3, cy3, cz3 = h3_list[0]
            _, scan, mat = h3_blob_data[(cx3, cy3, cz3)]
            if scan[0] == 0x01 and scan[1] == 0x02:
                # CV=0xff: h3 scan starts (01,02) — migration panics on this h4 format.
                # Use server-recognized placeholder; server regenerates h4 from h3.
                h4_blob = _placeholder_blob(cx4, cy4, cz4)
                h4_data[(cx4, cy4, cz4)] = None
            else:
                h4_blob = make_h4_blob(cx3, cy3, cz3, scan, mat)
                h4_scan, h4_mat = _extract_scan_mat(h4_blob)
                h4_data[(cx4, cy4, cz4)] = (h4_scan, h4_mat)
        else:
            # Multi-h3 h4: placeholder until aggregation formula is solved
            h4_blob = _voxel_blob_h5(cx4, cy4, cz4)
            h4_data[(cx4, cy4, cz4)] = None
        vd.append({
            "created_at": {"$date": now}, "h": 4, "k": 0,
            "metadata": {"mversion": 0, "pversion": 4, "uptodate": True, "version": 8},
            "oid": {"$numberLong": model_id},
            "records": {
                "meta":  {"data": {"$binary": _b64(_meta_blob(cx4, cy4, cz4)), "$type": "0x0"},
                          "hash": {"$numberLong": 0}, "updated_at": {"$date": now}},
                "voxel": {"data": {"$binary": _b64(h4_blob), "$type": "0x0"},
                          "hash": {"$numberLong": 0}, "updated_at": {"$date": now}},
            },
            "updated_at": {"$date": now}, "version": {"$numberLong": 1},
            "x": {"$numberLong": cx4}, "y": {"$numberLong": cy4}, "z": {"$numberLong": cz4},
        })

    # Phase 3: h=5 blobs.
    # Simple case (one h4 per h5): generate from h4 scan — formula verified vs 188_export.
    # Complex case (multiple h4 per h5): placeholder.
    h5_to_h3 = {}  # (cx5,cy5,cz5) → list of (cx3,cy3,cz3)
    for (cx3, cy3, cz3) in h3_blob_data:
        k5 = h5_chunk_coords(cx3, cy3, cz3)
        h5_to_h3.setdefault(k5, []).append((cx3, cy3, cz3))

    for (cx5, cy5, cz5), h3_list in sorted(h5_to_h3.items()):
        # Find the corresponding h4 for first h3 in this h5 region
        cx3, cy3, cz3 = h3_list[0]
        cx4, cy4, cz4 = h4_chunk_coords(cx3, cy3, cz3)
        h4_info = h4_data.get((cx4, cy4, cz4))
        if h4_info is not None:
            h4_scan, h4_mat = h4_info
            h5_blob = make_h5_blob(cx3, cy3, cz3, h4_scan, h4_mat)
        else:
            h5_blob = _placeholder_blob(cx5, cy5, cz5)
        vd.append({
            "created_at": {"$date": now}, "h": 5, "k": 0,
            "metadata": {"mversion": 0, "pversion": 4, "uptodate": True, "version": 8},
            "oid": {"$numberLong": model_id},
            "records": {
                "meta":  {"data": {"$binary": _b64(_meta_blob(cx5, cy5, cz5)), "$type": "0x0"},
                          "hash": {"$numberLong": 0}, "updated_at": {"$date": now}},
                "voxel": {"data": {"$binary": _b64(h5_blob), "$type": "0x0"},
                          "hash": {"$numberLong": 0}, "updated_at": {"$date": now}},
            },
            "updated_at": {"$date": now}, "version": {"$numberLong": 1},
            "x": {"$numberLong": cx5}, "y": {"$numberLong": cy5}, "z": {"$numberLong": cz5},
        })

    # js: physical size in meters (0.25m/voxel)
    js = json_size if json_size is not None else grid_size // 4
    c = js / 2.0 + 0.125  # core element center: always grid-center, independent of voxel shape
    bounds = _compute_bounds(voxels)
    return {
        "Model": {
            "Id": model_id, "Name": name, "Size": js,
            "CreatedAt": now, "CreatorId": 0,
            "JsonProperties": {
                "kind": 3, "size": js,
                "serverProperties": {
                    "creatorId": {"playerId": 0, "organizationId": 0},
                    "originConstructId": 0, "blueprintId": None,
                    "isFixture": None, "isBase": None, "isFlaggedForModeration": None,
                    "isDynamicWreck": False, "fuelType": None, "fuelAmount": None,
                    "rdmsTags": {"constructTags": [], "elementsTags": []},
                    "compacted": False, "dynamicFixture": None, "constructCloneSource": None,
                },
                "header": {
                    "uniqueIdentifier": None, "parentUniqueIdentifier": None,
                    "constructIdHint": None, "prettyName": "UnknownOrigin",
                    "fixtureHash": None, "folder": None,
                    "artWorkSVNRevision": None, "biomeEditorVersion": None,
                    "biomeEditorGitRevision": None,
                },
                "voxelGeometry": {
                    "size": js, "kind": 1, "voxelLod0": 3,
                    "radius": None, "minRadius": None, "maxRadius": None,
                },
                "planetProperties": None, "isNPC": False, "isUntargetable": False,
            },
            "Static": True,
            "Bounds": bounds,
            "FreeDeploy": False, "MaxUse": None, "HasMaterials": False, "DataId": None,
        },
        "VoxelData": vd,
        "Elements": [{
            "elementId": random.randint(4_000_000_000, 4_294_967_295),
            "localId": 1, "constructId": 0, "playerId": 0,
            "elementType": core_nqid,
            "position": {"x": c, "y": c, "z": c},
            "rotation": {"x": 0., "y": 0., "z": 0., "w": 1.},
            "properties": [["drmProtected", {"type": 1, "value": True}]],
            "serverProperties": {}, "links": [],
        }],
        "Links": [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='hollow_cube')
    ap.add_argument('--material', choices=list(MATERIALS_INFO.keys()), default=DEFAULT_MAT)
    ap.add_argument('--grid', type=int, default=128)
    args = ap.parse_args()

    GRID = args.grid
    X0, Y0, Z0 = 4, 4, 4
    X1, Y1, Z1 = GRID-5, GRID-5, GRID-5
    voxels = hollow_cube(X0, Y0, Z0, X1, Y1, Z1)
    n_chunks = len(set((v[0]//32, v[1]//32, v[2]//32) for v in voxels))
    print(f"Hollow cube [{X0},{X1}]^3: {len(voxels)} voxels, {n_chunks} h=3 chunks")

    # json_size: Size in blueprint JSON = physical meters (grid/4 voxels per meter at 0.25m/voxel)
    json_size = GRID // 4
    bp = build(voxels, GRID, STATIC_CORE_XS_NQID, f"HollowCube_{args.material}", args.material,
               json_size=json_size)
    out = f"{args.out}.json"
    with open(out, 'w') as f:
        json.dump(bp, f, separators=(',', ':'))
    import os; kb = os.path.getsize(out) // 1024
    print(f"Written: {out} ({kb}KB, {len(bp['VoxelData'])} VoxelData entries)")

    # Sanity check
    for c in bp['VoxelData']:
        if c['h'] != 3: continue
        blob = base64.b64decode(c['records']['voxel']['data']['$binary'])
        sz = struct.unpack('<I', blob[4:8])[0]
        v = lz4.block.decompress(blob[12:], uncompressed_size=sz)
        body = v[64:]
        scan_pairs = (len(body) - 40) // 2
        print(f"  h=3 ({c['x']['$numberLong']},{c['y']['$numberLong']},{c['z']['$numberLong']}): "
              f"body={len(body)}B scan={scan_pairs}pairs mat={body[-40:].hex()}")
        break


if __name__ == '__main__':
    main()
