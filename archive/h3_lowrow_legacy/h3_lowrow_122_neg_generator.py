"""
h3 scan generator for the (1,2,2) chunk — neg-x voxels (neg-x/pos-y corner).

When neg-x voxels exist, (1,2,2) encodes the neg-x/pos-y corner boundary.

For Nc_neg=1, the scan structure depends on n1:
  n1 = n1_first_212(1, -(Ye+2), lz)  — same n1 as the (2,1,2) bnd generator

  n1 <= 8 (most cases): 2 markers, scan_len=709
    pos1=315, lme=325, gap1=326, gs=651, mat_byte_pos=343, gap2=18
    own_val=(249+55*Nc_neg)%256=248 (=(own_val_222+32)%256), ystep=33
    groupA=46, groupB=163

  n1 >= 9 (same edge cases as (2,2,2)): 1 marker, scan_len=706
    pos1=max(315,2*n1+299)=317, lme=322, gap1=326, gs=648, mat_byte_pos=340, gap2=18
    own_val=(own_val_222_n1ge9+32)%256=(251+32)%256=27
    groupA=46, groupB=163

pos1_122 = max(315, 2*n1+299):
  n1<=8: clamped to 315 (constant).
  n1=9:  2*9+299=317.

mat_byte_pos = lme + 18 (constant offset, works for both n1 cases).
gap1=326 and groups_total=40 are constant.

NOTE: Nc_neg>1 needs testing.
Validated byte-exact against:
  1573 (Ye=30, n1=5, lz=14, Nc_neg=1) — 2-marker case, scan_len=709
  1575 (Ye=5,  n1=8, lz=14, Nc_neg=1) — 2-marker case, scan_len=709
  1577 (Ye=1,  n1=9, lz=14, Nc_neg=1) — 1-marker case, scan_len=706
"""

from h3_lowrow_212_generator import n1_first_212, MAT_TAIL
from h3_lowrow_122_generator import HEADER_122
from h3_lowrow_222_neg_generator import MC_222_NEG

MC_122_NEG = MC_222_NEG - 32   # = 605


def mc_122_neg(Nc_neg=1):
    return MC_222_NEG - 32 * (1 if Nc_neg == 1 else 0)   # only Nc_neg=1 validated


def generate_122_neg_scan(Nc_neg=1, mat_counter=MC_122_NEG, lz=14, Yextent=30, N=1):
    """
    Generate (1,2,2) voxel scan bytes for neg-x voxels.

    Nc_neg:   number of negative-x columns (only Nc_neg=1 validated)
    Yextent:  number of negative-y rows
    lz:       effective z-coordinate (= abs(game_z) - 0.5)
    """
    assert N == 1
    assert Nc_neg == 1, "Only Nc_neg=1 validated; Nc_neg>1 needs testing"

    n1 = n1_first_212(1, -(Yextent + 2), lz)
    num_markers = 1 if n1 >= 9 else 2

    own_val_222 = (161 + 55 * Nc_neg + 35 * (1 if n1 >= 9 else 0)) % 256
    own_val = (own_val_222 + 32) % 256

    pos1 = max(315, 2 * n1 + 299)
    lme = pos1 + num_markers * 5
    gap1 = 326
    gap2 = 18
    groups_total = 40          # constant for Nc_neg=1
    gs = lme + gap1
    mat_byte_pos = lme + 18    # constant 18-byte offset from end of marker section
    scan_len = gs + groups_total + gap2

    ystep  = 33
    groupA = 46
    groupB = 163

    scan = bytearray(scan_len)

    # Background: starts flip=False; 1 marker flips, 2 keeps parity
    flip = num_markers % 2 == 1
    for i in range(scan_len):
        if i < pos1:
            scan[i] = 0x00 if i % 2 == 0 else 0xff
        elif i >= lme:
            scan[i] = (0xff if i % 2 == 0 else 0x00) if flip else (0x00 if i % 2 == 0 else 0xff)

    # Markers at pos1
    scan[pos1:pos1 + 5] = bytes([own_val, 0x01, 0x02, 0x00, 0x00])
    if num_markers == 2:
        scan[pos1 + 5:lme] = bytes([ystep, 0x01, 0x02, 0x00, 0x00])

    # Mat byte (fixed 18-byte offset from lme)
    scan[mat_byte_pos] = mat_counter & 0xff

    # Groups at gs: groupA(2 HBs) + sep(8 bg) + groupB(2 HBs)
    def halfblock(val):
        return bytes([val, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00])

    p = gs
    scan[p:p + 8] = halfblock(groupA)
    p += 8
    scan[p:p + 8] = halfblock(0x20)   # default
    p += 8
    p += 8   # sep (background)
    scan[p:p + 8] = halfblock(groupB)
    p += 8
    scan[p:p + 8] = halfblock(0x20)   # default
    p += 8
    assert p == gs + groups_total

    return bytes(scan)


def generate_122_neg_blob(Nc_neg=1, mat_counter=None, lz=14, Yextent=30):
    """Return (header64, scan, mat40) ready for LZ4 packing."""
    if mat_counter is None:
        mat_counter = mc_122_neg(Nc_neg)
    scan = generate_122_neg_scan(Nc_neg, mat_counter, lz=lz, Yextent=Yextent)
    mat = mat_counter.to_bytes(4, 'little') + MAT_TAIL
    return HEADER_122, scan, mat


if __name__ == "__main__":
    import json, base64, lz4.block

    def load_122(path):
        with open(path) as f:
            bp = json.load(f)
        for entry in bp["VoxelData"]:
            if (entry["h"] == 3
                    and entry["x"]["$numberLong"] == 1
                    and entry["y"]["$numberLong"] == 2
                    and entry["z"]["$numberLong"] == 2):
                vraw = base64.b64decode(entry["records"]["voxel"]["data"]["$binary"])
                dec = lz4.block.decompress(
                    vraw[12:], uncompressed_size=int.from_bytes(vraw[4:8], 'little'))
                idx = dec.find(b'Debug1')
                return dec[64:idx - 13], int.from_bytes(dec[idx - 13:idx - 13 + 4], 'little')

    tests = [
        ("exports/1573_export.blueprint", 1, 14, 30),   # n1=5, 2-marker
        ("exports/1575_export.blueprint", 1, 14, 5),    # n1=8, 2-marker
        ("exports/1577_export.blueprint", 1, 14, 1),    # n1=9, 1-marker
    ]

    for path, Nc_neg, lz, Ye in tests:
        real_scan, mc = load_122(path)
        gen_scan = generate_122_neg_scan(Nc_neg, mc, lz=lz, Yextent=Ye)
        match = gen_scan == real_scan
        print(f"Nc_neg={Nc_neg} Ye={Ye} lz={lz}: scan_len={len(real_scan)} mc={mc} MATCH={match}")
        if not match:
            diffs = [(i, real_scan[i], gen_scan[i])
                     for i in range(min(len(real_scan), len(gen_scan)))
                     if real_scan[i] != gen_scan[i]]
            print(f"  len: real={len(real_scan)} gen={len(gen_scan)}")
            for i, r, g in diffs[:15]:
                print(f"  [{i}] real=0x{r:02x} gen=0x{g:02x}")
