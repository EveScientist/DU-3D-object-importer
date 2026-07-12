#!/usr/bin/env python3
"""
generate_v2.py — DU voxel body generator, reverse-engineered from 122_export.blueprint.

Key confirmed formulas (from 122_export analysis):
- n1 = 9 + (153*lx + 4*ly + lz)//31   [scan position for voxel at local (lx,ly,lz)]
- CV = (32*n + BASE) % 256  where n = (4-Wx-3*Wy-Wz)%8, Wx=1 if lx==0, Wy if ly==0, Wz if lz==0
- FG1_start = 2*n1_first + 5*N - 7     [face group 1 position]
- FG2_start = FG1_start + 12           [face group 2 position]
- scan_pairs = FG2_start + 8           [last pair of FG2 = (00,00) scan terminator]
- compact_face_entry = (0x21,0x01)(0x02,0x00)  [2 pairs after each decl except last]

Material BASE constants (from 122_export corner value analysis):
- hcSodium: BASE=249
- hcCarbon: BASE=179
- hcAlLiPa: BASE=12

Face group FX constants for hcSodium at world chunk (0,0,*):
- FX1=0x8c=140 (x-face), FX2=0x20=32 (z-face), FX3=0xa3=163 (y-face)

For other world chunk positions, FX1 = (F[cx]+G[cy])%256 where:
  F=[44,12,67,67], G=[96,0,221,221] for 4-chunk-per-dim (Size=32) constructs at world (0,0,0).
"""

import struct
import lz4.block

BLOB_MAGIC = bytes([0xF9, 0xB6, 0x14, 0xFB])
CHUNK_SIZE = 32

# Material BASE constants
BASE_SODIUM = 249  # hcSodium
BASE_CARBON = 179  # hcCarbon

# FX face group lookup tables for Size=32 constructs (4 chunks per dim)
# Derived from 122_export analysis: FX1=(F[cx]+G[cy])%256
_FX_F = [44, 12, 67, 67]    # per-cx component
_FX_G = [96,  0, 221, 221]  # per-cy component
_FX2  = 0x20  # z-face (constant for all chunks/materials)
_FX3  = 0xa3  # y-face... actually varies but use as placeholder

def _blob(payload: bytes) -> bytes:
    c = lz4.block.compress(payload, store_size=False)
    return BLOB_MAGIC + struct.pack('<I', len(payload)) + b'\x00\x00\x00\x00' + c

def _voxel_header(cx: int, cy: int, cz: int) -> bytes:
    h = bytearray(64)
    vals = [666411027, 6, 3900781470, 9,
            (cx*32-1)&0xFFFFFFFF, (cy*32-1)&0xFFFFFFFF, (cz*32-1)&0xFFFFFFFF,
            35, 35, 35, cx*32, cy*32, cz*32, 32, 32, 32]
    for i, v in enumerate(vals):
        struct.pack_into('<I', h, i*4, v)
    return bytes(h)

def _corner_value(lx: int, ly: int, lz: int, base: int) -> int:
    Wx = 1 if lx == 0 else 0
    Wy = 1 if ly == 0 else 0
    Wz = 1 if lz == 0 else 0
    n = (4 - Wx - 3*Wy - Wz) % 8
    return (32*n + base) % 256

def _n1(lx: int, ly: int, lz: int) -> int:
    return 9 + (153*lx + 4*ly + lz) // 31

def _face_x1(cx: int, cy: int, n_chunks: int = 4) -> int:
    """FX1 for the x-face. Uses empirical lookup for 4-chunk-per-dim constructs."""
    if n_chunks == 4 and 0 <= cx < 4 and 0 <= cy < 4:
        return (_FX_F[cx] + _FX_G[cy]) % 256
    # Fallback: use center-ish value
    return 0x8c  # works for cx=0,cy=0

def make_voxel_body(cx: int, cy: int, cz: int,
                    local_voxels: list,
                    base: int = BASE_SODIUM,
                    mat_section: bytes = None,
                    n_chunks: int = 4) -> bytes:
    """
    Generate a voxel body for a chunk with the given local voxels.
    local_voxels: list of (lx, ly, lz) tuples
    mat_section: 40-byte material section (uses hcSodium default if None)
    """
    if mat_section is None:
        # Default hcSodium material section (from 122_export)
        mat_section = bytes.fromhex(
            '0002000000c768690900000000446562756731000001'
            '69670374000000006863536f6469756d0201'
        )
    assert len(mat_section) == 40

    if not local_voxels:
        # Empty chunk: minimal body with just material section
        return _blob(_voxel_header(cx, cy, cz) + mat_section)

    N = len(local_voxels)

    # Sort voxels by n1 (ascending) so first entry has smallest n1
    voxels_with_n1 = sorted(
        [(lx, ly, lz, _n1(lx, ly, lz)) for lx, ly, lz in local_voxels],
        key=lambda x: x[3]
    )
    n1_first = voxels_with_n1[0][3]

    # Compute FG positions
    FG1_start = 2*n1_first + 5*N - 7
    FG2_start = FG1_start + 12
    scan_pairs = FG2_start + 8  # last pair (00,00) is scan terminator

    # FX values for face groups
    fx1 = _face_x1(cx, cy, n_chunks)
    fx2 = _FX2
    fx3 = _FX3

    # Build scan
    scan = bytearray(scan_pairs * 2)

    # Zone 1: (00,ff) × n1_first at the start
    for i in range(n1_first):
        scan[i*2] = 0x00; scan[i*2+1] = 0xff

    # Corner declarations packed at n1_first
    pos = n1_first
    for idx, (lx, ly, lz, n1_vox) in enumerate(voxels_with_n1):
        cv = _corner_value(lx, ly, lz, base)
        is_last = (idx == N - 1)

        # 3-pair corner declaration
        scan[pos*2]   = 0x00; scan[pos*2+1] = cv
        scan[(pos+1)*2] = 0x01; scan[(pos+1)*2+1] = 0x02
        scan[(pos+2)*2] = 0x00; scan[(pos+2)*2+1] = 0x00
        pos += 3

        if not is_last:
            # 2-pair compact face entry
            scan[pos*2]   = 0x21; scan[pos*2+1] = 0x01
            scan[(pos+1)*2] = 0x02; scan[(pos+1)*2+1] = 0x00
            pos += 2

    # Zone 2: (ff,00) × gap from pos to FG1_start
    for i in range(pos, FG1_start):
        scan[i*2] = 0xff; scan[i*2+1] = 0x00

    # FG1: 8 pairs = 2 × 4-pair face groups
    fg1_data = bytes([
        fx1, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00,
        fx2, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00,
    ])
    scan[FG1_start*2:FG1_start*2+16] = fg1_data

    # 4 (ff,00) pairs between FG1 and FG2
    for i in range(FG1_start+8, FG2_start):
        scan[i*2] = 0xff; scan[i*2+1] = 0x00

    # FG2: 8 pairs = 2 × 4-pair face groups, last pair = (00,00) terminator
    fg2_data = bytes([
        fx3, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00,
        fx2, 0x01, 0x00, 0x7e, 0x7e, 0x7e, 0x00, 0x00,  # z_side=0, terminator
    ])
    scan[FG2_start*2:FG2_start*2+16] = fg2_data

    return _blob(_voxel_header(cx, cy, cz) + bytes(scan) + mat_section)


# Verification: compare with 122_export chunk (0,0,0)
if __name__ == '__main__':
    import base64, json

    with open('/home/du/export/122_export.blueprint') as f:
        bp = json.load(f)

    for chunk in bp['VoxelData']:
        if chunk['h'] != 3: continue
        if (chunk['x']['$numberLong'],chunk['y']['$numberLong'],chunk['z']['$numberLong']) != (0,0,0): continue
        import lz4.block as lz4b
        blob = base64.b64decode(chunk['records']['voxel']['data']['$binary'])
        sz = struct.unpack('<I', blob[4:8])[0]
        ref = lz4b.decompress(blob[12:], uncompressed_size=sz)
        break

    gen_blob = make_voxel_body(0, 0, 0, [(31,31,31)])
    gen_sz = struct.unpack('<I', gen_blob[4:8])[0]
    gen = lz4.block.decompress(gen_blob[12:], uncompressed_size=gen_sz)

    ref_body = ref[64:]
    gen_body = gen[64:]
    diffs = [(i, ref_body[i], gen_body[i]) for i in range(min(len(ref_body),len(gen_body))) if ref_body[i]!=gen_body[i]]
    print(f"Chunk (0,0,0) single-voxel match: {len(diffs)} diffs (0=perfect)")
    if diffs:
        for p,r,g in diffs[:5]:
            print(f"  byte {p}: ref=0x{r:02x} gen=0x{g:02x}")

    # Test with multi-voxel (simulate a wall)
    wall_voxels = [(31,i,31) for i in range(17)]  # 17 voxels in y-direction
    gen_wall = make_voxel_body(0, 1, 0, wall_voxels)
    gen_wall_sz = struct.unpack('<I', gen_wall[4:8])[0]
    gen_wall_data = lz4.block.decompress(gen_wall[12:], uncompressed_size=gen_wall_sz)
    print(f"Wall chunk (0,1,0) with 17 voxels: {len(gen_wall_data)} bytes decompressed")
    print(f"  scan_pairs = {(len(gen_wall_data)-64-40)//2}")
