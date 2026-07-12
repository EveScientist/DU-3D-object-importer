#!/usr/bin/env python3
"""
generate_v3.py — Voxel body generator (single-voxel confirmed working).

CONFIRMED WORKING RULES (from 8chunks_122export.json rendering test 2026-05-22):
  n1 = 9 + (153*lx + 4*ly + lz)//31
  CV = (32*n + BASE) % 256  where n=(4-Wx-3*Wy-Wz)%8, Wx=1 if lx==0
  FG1 = n1 + 165
  FG2 = FG1 + 12  (4 empty pairs between FG1 and FG2, for 3-face corner voxels)
  scan_pairs = FG2 + 8  (= FG2_end + 1 — must end EXACTLY here, NO trailing pairs)

CRITICAL: scan_pairs must equal FG2_end+1. Trailing (ff,00) after (00,00) terminator
causes "Reading too far!" in DU's migration parser.
"""

import struct
import lz4.block

BLOB_MAGIC = bytes([0xF9, 0xB6, 0x14, 0xFB])

BASE_SODIUM = 249   # hcSodium (White Sodium Panel)
BASE_CARBON = 179   # hcCarbon (Orange Carbon Panel) 
BASE_ALLIPA = 12    # hcAlLiPa

# hcSodium material section (40 bytes, from 122_export)
MAT_SODIUM = bytes.fromhex(
    '0002000000c768690900000000446562756731000001'
    '69670374000000006863536f6469756d0201'
)
# hcCarbon material section (40 bytes, from 132_export)
MAT_CARBON = bytes.fromhex(
    '4502000000c768690900000000446562756731000001'
    'a502b0cb000000006863436172626f6e0201'
)

# FX lookup tables — from 122_export empirical analysis (Size=32, 4-chunk grid)
# FX1(cx,cy) = (F[cx] + G[cy]) % 256
_FX_F4 = [44, 12, 67, 67]    # per-cx for 4-chunk grid
_FX_G4 = [96, 0, 221, 221]   # per-cy for 4-chunk grid

def _blob(payload: bytes) -> bytes:
    c = lz4.block.compress(payload, store_size=False)
    return BLOB_MAGIC + struct.pack('<I', len(payload)) + b'\x00\x00\x00\x00' + c

def _hdr(cx, cy, cz):
    h = bytearray(64)
    vals = [666411027, 6, 3900781470, 9,
            (cx*32-1)&0xFFFFFFFF, (cy*32-1)&0xFFFFFFFF, (cz*32-1)&0xFFFFFFFF,
            35, 35, 35, cx*32, cy*32, cz*32, 32, 32, 32]
    for i, v in enumerate(vals): struct.pack_into('<I', h, i*4, v)
    return bytes(h)

def _cv(lx, ly, lz, base):
    Wx = 1 if lx == 0 else 0
    Wy = 1 if ly == 0 else 0
    Wz = 1 if lz == 0 else 0
    n = (4 - Wx - 3*Wy - Wz) % 8
    return (32*n + base) % 256

def _n1(lx, ly, lz):
    return 9 + (153*lx + 4*ly + lz) // 31

def _fx1(cx, cy, n_chunks=4):
    """FX for the primary (x) face group. Uses 4-chunk empirical lookup."""
    if n_chunks == 4 and 0 <= cx < 4 and 0 <= cy < 4:
        return (_FX_F4[cx] + _FX_G4[cy]) % 256
    return 0x8c  # fallback

def make_voxel_body(cx, cy, cz, local_voxels, base=BASE_SODIUM,
                    mat_section=None, n_chunks=4):
    """
    Generate h=3 voxel body. CONFIRMED WORKING for single-voxel n1=167 case.

    CRITICAL: scan_pairs = FG2_end + 1. No trailing pairs after (00,00) terminator.
    Each voxel independently encodes at its n1 position.
    """
    if mat_section is None:
        mat_section = MAT_SODIUM
    assert len(mat_section) == 40

    if not local_voxels:
        return _blob(_hdr(cx, cy, cz) + mat_section)

    fx1 = _fx1(cx, cy, n_chunks)
    fx2 = 0x20
    fx3 = 0xa3

    # Sort by n1 descending — highest n1 voxel determines FG positions
    all_n1 = sorted([(_n1(lx,ly,lz), lx, ly, lz) for lx,ly,lz in local_voxels],
                    reverse=True)
    n1_max = all_n1[0][0]
    n1_min = all_n1[-1][0]

    # CONFIRMED: FG1 = n1_max + 165, FG2 = n1_max + 177
    # scan_pairs = FG2 + 8 exactly (no trailing pairs!)
    FG1 = n1_max + 165
    FG2 = n1_max + 177
    SCAN_PAIRS = FG2 + 8

    scan = bytearray(SCAN_PAIRS * 2)
    # (00,ff) before n1_min, (ff,00) everywhere else
    for i in range(n1_min):
        scan[i*2] = 0x00; scan[i*2+1] = 0xff
    for i in range(n1_min, SCAN_PAIRS):
        scan[i*2] = 0xff; scan[i*2+1] = 0x00

    # Write corner declaration for each voxel at its n1 position
    for n1v, lx, ly, lz in all_n1:
        CV = _cv(lx, ly, lz, base)
        if n1v + 2 < SCAN_PAIRS:
            scan[n1v*2]     = 0x00; scan[n1v*2+1]     = CV
            scan[n1v*2+2]   = 0x01; scan[n1v*2+3]     = 0x02
            scan[n1v*2+4]   = 0x00; scan[n1v*2+5]     = 0x00

    # FG1 at n1_max+165, FG2 at n1_max+177 (gap of 4 (ff,00) between)
    scan[FG1*2:FG1*2+16] = bytes([fx1,0x01, 0x01,0x7e, 0x7e,0x7e, 0x01,0x00,
                                   fx2,0x01, 0x01,0x7e, 0x7e,0x7e, 0x01,0x00])
    for i in range(FG1+8, FG2):
        scan[i*2] = 0xff; scan[i*2+1] = 0x00
    # FG2: last pair (00,00) is the scan terminator
    scan[FG2*2:FG2*2+16] = bytes([fx3,0x01, 0x01,0x7e, 0x7e,0x7e, 0x01,0x00,
                                   fx2,0x01, 0x00,0x7e, 0x7e,0x7e, 0x00,0x00])

    return _blob(_hdr(cx, cy, cz) + bytes(scan) + mat_section)


if __name__ == '__main__':
    import base64, json

    # Verify single-voxel match with 122_export chunk (0,0,0)
    with open('/home/du/export/122_export.blueprint') as f:
        bp = json.load(f)
    for chunk in bp['VoxelData']:
        if chunk['h']!=3: continue
        if (chunk['x']['$numberLong'],chunk['y']['$numberLong'],chunk['z']['$numberLong'])!=(0,0,0): continue
        import lz4.block as lz4b
        blob = base64.b64decode(chunk['records']['voxel']['data']['$binary'])
        ref = lz4b.decompress(blob[12:], uncompressed_size=struct.unpack('<I',blob[4:8])[0])
        break

    gen_blob = make_voxel_body(0, 0, 0, [(31,31,31)])
    gen = lz4.block.decompress(gen_blob[12:], uncompressed_size=struct.unpack('<I',gen_blob[4:8])[0])
    diffs = [(i,ref[64+i],gen[64+i]) for i in range(min(len(ref[64:]),len(gen[64:]))) if ref[64+i]!=gen[64+i]]
    print(f"Single-voxel (0,0,0): {len(diffs)} diffs (0=perfect)")

    # Verify with 203_export chunk (1,1,1)
    with open('/home/du/export/203_export.blueprint') as f:
        bp203 = json.load(f)
    for chunk in bp203['VoxelData']:
        if chunk['h']!=3: continue
        if (chunk['x']['$numberLong'],chunk['y']['$numberLong'],chunk['z']['$numberLong'])!=(1,1,1): continue
        blob = base64.b64decode(chunk['records']['voxel']['data']['$binary'])
        ref2 = lz4.block.decompress(blob[12:], uncompressed_size=struct.unpack('<I',blob[4:8])[0])
        break

    # 203_export uses hcAlLiPa material and Dynamic XS core
    # Chunk (1,1,1) has single voxel at (31,31,31), CV=0x79, same as 122_export
    MAT_ALLIPA_203 = ref2[64+704:][:40]  # extract mat section from reference
    gen203_blob = make_voxel_body(1, 1, 1, [(31,31,31)], base=BASE_SODIUM, mat_section=MAT_ALLIPA_203, n_chunks=4)
    gen203 = lz4.block.decompress(gen203_blob[12:], uncompressed_size=struct.unpack('<I',gen203_blob[4:8])[0])
    # Note: 203 uses hcAlLiPa (BASE=12) and different FX, so CV and FX will differ
    # Just check the scan structure (decl position, FG position) is same
    ref2_scan = ref2[64:64+704]
    gen203_scan = gen203[64:64+704]
    structural_diffs = sum(1 for i in range(352) if
        (ref2_scan[i*2]!=0x00 or ref2_scan[i*2+1]!=0xff) and  # ref non-trivial
        (gen203_scan[i*2]!=ref2_scan[i*2] or gen203_scan[i*2+1]!=ref2_scan[i*2+1]))
    print(f"203_export (1,1,1) structural match: {352-structural_diffs}/352 pairs correct")
    print(f"  Note: CV and FX differ due to material (AlLiPa vs Sodium)")
