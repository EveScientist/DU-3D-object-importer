"""
h3 scan generator for the (1,1,2) chunk — boundary case.

This scanner models the (1,1,2) chunk when only positive-x voxels exist
(the chunk encodes the negative-x boundary of those voxels).  It is NOT
the full scanner for negative-x voxels.

Key structural differences vs (2,1,2) Nc=1:
  - HEADER differs at bytes [16] (0x3f→0x1f) and [40] (0x40→0x20)
  - pos1_112 = pos1_212 + 306
  - mat_byte_pos = pos1_112 + 5*Ye  (vs groups_start-12 in 212)
  - gap2 = 0  (no trailing gap)
  - own_val_112 = (own_val_212 + 32) % 256
  - groupA_val_112 = (own_val_112 + 19) % 256
  - groupB_val and ystep_val are identical to (2,1,2)
  - mc = 599 (constant)
  - sep_112 = sep_212

Known anomaly: at Yextent=2 with lz=14 (and likely any lz where n1 transitions
at the -(Ye+2) anchor), groups_start is 2 bytes higher than the formula predicts.
Handled as a special case.  Does not affect Ye=29 (hollow cube target).

Validated byte-exact against:
  1557 (Ye=1,  lz=14): pos1_112=335, gs=666,  scan_len=706  ✓
  1559 (Ye=2,  lz=14): pos1_112=333, gs=669,  scan_len=725  ✓  (anomaly +2)
  1561 (Ye=5,  lz=14): pos1_112=333, gs=682,  scan_len=786  ✓
  1571 (Ye=12, lz=14): pos1_112=333, gs=713,  scan_len=927  ✓
  1569 (Ye=13, lz=14): pos1_112=333, gs=718,  scan_len=946  ✓
  1567 (Ye=25, lz=14): pos1_112=327, gs=770, scan_len=1188  ✓
  1545 (Ye=29, lz=4):  pos1_112=327, gs=790, scan_len=1270  ✓
"""

from h3_lowrow_212_generator import (
    n1_first_212, MAT_TAIL, _EFF_LZ
)

HEADER_112 = bytes.fromhex(
    "13a0b827060000009e3381e8090000001f0000001f0000003f000000"
    "230000002300000023000000200000002000000040000000200000002000000020000000"
)
assert len(HEADER_112) == 64

MC_112 = 599   # constant for the boundary (positive-x-only) case


def generate_112_scan(mat_counter, lz=14, Yextent=29, N=1):
    """
    Generate the voxel scan bytes for the (1,1,2) chunk boundary case.

    mat_counter: always MC_112=599 for the boundary case
    lz:          local z-coordinate (game_z - 0.5)
    Yextent:     number of negative-y rows (1..29)
    N:           voxels per cell (1 only)
    """
    assert N == 1

    pos1_212 = 2 * n1_first_212(1, -(Yextent + 2), lz) + 11
    pos1_112 = pos1_212 + 306

    # mat_byte sits at the first position after the marker section
    mat_byte_pos = pos1_112 + 5 * Yextent   # = pos1_212 + 306 + 5*Ye

    sep_112 = 2 * (n1_first_212(1, -(Yextent - 2), lz) - 5)
    groups_total = 2 * (Yextent + 1) * 8 + sep_112

    # groups_start = 2*pos1_212 + 5*Ye + 603  (= mat_byte_pos + pos1_212 + 297)
    groups_start = 2 * pos1_212 + 5 * Yextent + 603
    # Anomaly: at Ye=2 when n1 transitions at the -(Ye+2) anchor, groups_start
    # is 2 bytes higher than the formula predicts.
    if (Yextent == 2
            and n1_first_212(1, -(Yextent + 2), lz)
            < n1_first_212(1, -(Yextent + 1), lz)):
        groups_start += 2

    scan_len = groups_start + groups_total   # gap2 = 0

    # Values: A-side shifted +32 vs (2,1,2); B-side and ystep identical
    groupB_val  = (212 - _EFF_LZ - 35 * Yextent - (N - 1)) % 256
    own_val_212 = (groupB_val - 162) % 256
    own_val_112 = (own_val_212 + 32) % 256
    groupA_val  = (own_val_112 + 19) % 256
    ystep_val   = (304 - _EFF_LZ - N) % 256

    scan = bytearray(scan_len)

    # Background before marker section: even=0x00, odd=0xff
    for i in range(pos1_112):
        scan[i] = 0x00 if i % 2 == 0 else 0xff

    # Background from mat_byte_pos onward: parity flips if Yextent is odd
    # (marker section spans Yextent markers × 5 bytes = 5*Yextent bytes)
    flip = Yextent % 2 == 1
    for i in range(mat_byte_pos, scan_len):
        if flip:
            scan[i] = 0xff if i % 2 == 0 else 0x00
        else:
            scan[i] = 0x00 if i % 2 == 0 else 0xff

    # Markers: first = own_val_112, rest = ystep_val
    p = pos1_112
    scan[p:p + 5] = bytes([own_val_112, 0x01, 0x02, (N - 1) & 0xff, 0x00])
    p += 5
    for _ in range(Yextent - 1):
        scan[p:p + 5] = bytes([ystep_val, 0x01, 0x02, (N - 1) & 0xff, 0x00])
        p += 5

    # Mat byte overwrites the background at mat_byte_pos
    scan[mat_byte_pos] = mat_counter & 0xff

    # Groups: groupA then sep (background, already filled) then groupB
    def halfblock(val):
        return bytes([val, 0x01, N & 0xff, 0x7e, 0x7e, 0x7e, N & 0xff, 0x00])

    default_val = (0x20 - (N - 1)) % 256

    def group_bytes(first_val):
        return halfblock(first_val) + halfblock(default_val) * Yextent

    p = groups_start
    scan[p:p + (Yextent + 1) * 8] = group_bytes(groupA_val)
    p += (Yextent + 1) * 8
    p += sep_112   # sep bytes are background, skip
    scan[p:p + (Yextent + 1) * 8] = group_bytes(groupB_val)
    p += (Yextent + 1) * 8
    assert p == scan_len, f"groups end mismatch: {p} vs {scan_len}"

    return bytes(scan)


def generate_112_blob(mat_counter=None, lz=14, Yextent=29):
    """Return (header64, scan, mat40) ready for LZ4 packing."""
    if mat_counter is None:
        mat_counter = MC_112
    scan = generate_112_scan(mat_counter, lz=lz, Yextent=Yextent)
    mat = mat_counter.to_bytes(4, 'little') + MAT_TAIL
    return HEADER_112, scan, mat


if __name__ == "__main__":
    import json, base64, lz4.block

    def load_112(path):
        with open(path) as f:
            bp = json.load(f)
        for entry in bp["VoxelData"]:
            if (entry["h"] == 3 and entry["x"]["$numberLong"] == 1
                    and entry["y"]["$numberLong"] == 1
                    and entry["z"]["$numberLong"] == 2):
                vraw = base64.b64decode(entry["records"]["voxel"]["data"]["$binary"])
                dec = lz4.block.decompress(vraw[12:],
                                           uncompressed_size=int.from_bytes(vraw[4:8], 'little'))
                idx = dec.find(b'Debug1')
                scan = dec[64:idx - 13]
                mc = int.from_bytes(dec[idx - 13:idx - 13 + 4], 'little')
                return scan, mc

    tests = [
        ("exports/1557_export.blueprint", 14,  1),
        ("exports/1559_export.blueprint", 14,  2),
        ("exports/1561_export.blueprint", 14,  5),
        ("exports/1571_export.blueprint", 14, 12),
        ("exports/1569_export.blueprint", 14, 13),
        ("exports/1567_export.blueprint", 14, 25),
        ("exports/1545_export.blueprint",  4, 29),
    ]

    for path, lz, Ye in tests:
        real_scan, mc = load_112(path)
        gen_scan = generate_112_scan(mc, lz=lz, Yextent=Ye)
        match = gen_scan == real_scan
        print(f"Ye={Ye:2d} lz={lz:2d} vs {path.split('/')[-1]}: "
              f"scan_len={len(real_scan)} MATCH={match}")
        if not match:
            diffs = [(i, real_scan[i], gen_scan[i])
                     for i in range(min(len(real_scan), len(gen_scan)))
                     if real_scan[i] != gen_scan[i]]
            print(f"  len: real={len(real_scan)} gen={len(gen_scan)}")
            for i, r, g in diffs[:15]:
                print(f"  [{i}] real=0x{r:02x} gen=0x{g:02x}")
