"""
h3 scan generator for the (2,1,2) chunk — neg-x boundary role.

When negative-x voxels are placed, (2,1,2) encodes the positive-x
boundary of those voxels (mirrored role from the pos-x main case).

Key differences vs (2,1,2) main:
  - pos1 = 2*n1_first + 1         (not +11; boundary formula)
  - gap1 = pos1_main + 297         (= 2*n1+308; uses the +11 anchor)
  - gap2 = 316  (constant: gap1-(pos1-9) = (2n+308)-(2n-8) = 316 always)
  - own_val = (126 - 35*Ye) % 256  (not (36-35*Ye)%256 as in pos-x main)
  - mc: K=230; mc(Nc_neg) = 512 + (230 + 55*Nc_neg) % 256

Structure (Nc_neg=1, Ye=30, lz=14, n1=5):
  pos1=11, lme=161, gap1=318, gs=479, mat_byte_pos=477,
  groups_total=496, gap2=316, scan_len=1291

Validated byte-exact against export 1573 (Nc_neg=1, Ye=30, lz=14).
"""

from h3_lowrow_212_generator import (
    n1_first_212, HEADER_212, MAT_TAIL, _EFF_LZ
)

_K_212_BND = 230


def mc_212_bnd(Nc_neg):
    return 512 + (_K_212_BND + 55 * Nc_neg) % 256


def generate_212_bnd_scan(Nc_neg, mat_counter, lz=14, Yextent=30, N=1):
    """
    Generate the (2,1,2) voxel scan bytes for the neg-x boundary case.

    Nc_neg:    number of negative-x columns (1..31; only Nc_neg=1 validated)
    Yextent:   number of negative-y rows (1..30)
    lz:        local z-coordinate (game_z - 0.5)
    """
    assert N == 1

    n1 = n1_first_212(1, -(Yextent + 2), lz)
    pos1 = 2 * n1 + 1           # boundary: +1 not +11
    pos1_main = 2 * n1 + 11     # main anchor (for gap1 formula)
    lme = pos1 + Yextent * 5

    gap1 = pos1_main + 297      # = 2*n1 + 308
    gap2 = 316                  # constant: gap1-(pos1-9) = 316 for all n1

    sep = 2 * (n1_first_212(1, -(Yextent - 2), lz) - 5)
    groups_total = (Nc_neg + 1) * (Yextent + 1) * 8 + sep

    gs = lme + gap1
    mat_byte_pos = gs - max(pos1 - 9, 2)
    scan_len = gs + groups_total + gap2

    own_val   = (126 - 35 * Yextent) % 256
    groupA_val = (own_val + 19) % 256
    groupB_val = (212 - _EFF_LZ - 35 * Yextent - (N - 1)) % 256
    ystep_val  = (304 - _EFF_LZ - N) % 256

    scan = bytearray(scan_len)

    # Background before marker section: even=0x00, odd=0xff
    for i in range(pos1):
        scan[i] = 0x00 if i % 2 == 0 else 0xff

    # Background after marker section: parity flips if marker_span is odd
    flip = (Nc_neg * Yextent) % 2 == 1
    for i in range(lme, scan_len):
        if flip:
            scan[i] = 0xff if i % 2 == 0 else 0x00
        else:
            scan[i] = 0x00 if i % 2 == 0 else 0xff

    # Markers: Nc_neg columns × Ye rows, packed (no column separator)
    def marker(val):
        return bytes([val, 0x01, 0x02, (N - 1) & 0xff, 0x00])

    p = pos1
    for col in range(Nc_neg):
        # TODO: xstep_val for col>0 needs testing with Nc_neg>1
        scan[p:p + 5] = marker(own_val if col == 0 else ystep_val)
        p += 5
        for _ in range(Yextent - 1):
            scan[p:p + 5] = marker(ystep_val)
            p += 5
    assert p == lme, f"marker end mismatch: {p} vs {lme}"

    # Mat byte
    scan[mat_byte_pos] = mat_counter & 0xff

    # Groups: (Nc_neg+1) groups of (Ye+1) halfblocks, packed
    def halfblock(val):
        return bytes([val, 0x01, N & 0xff, 0x7e, 0x7e, 0x7e, N & 0xff, 0x00])

    default_val = (0x20 - (N - 1)) % 256

    def group_bytes(first_val):
        return halfblock(first_val) + halfblock(default_val) * Yextent

    p = gs
    scan[p:p + (Yextent + 1) * 8] = group_bytes(groupA_val)
    p += (Yextent + 1) * 8
    p += sep
    for _ in range(Nc_neg):
        scan[p:p + (Yextent + 1) * 8] = group_bytes(groupB_val)
        p += (Yextent + 1) * 8
    assert p == gs + groups_total, f"groups end mismatch: {p}"

    return bytes(scan)


def generate_212_bnd_blob(Nc_neg, mat_counter=None, lz=14, Yextent=30):
    """Return (header64, scan, mat40) ready for LZ4 packing."""
    if mat_counter is None:
        mat_counter = mc_212_bnd(Nc_neg)
    scan = generate_212_bnd_scan(Nc_neg, mat_counter, lz=lz, Yextent=Yextent)
    mat = mat_counter.to_bytes(4, 'little') + MAT_TAIL
    return HEADER_212, scan, mat


if __name__ == "__main__":
    import json, base64, lz4.block

    def load_212(path):
        with open(path) as f:
            bp = json.load(f)
        for entry in bp["VoxelData"]:
            if (entry["h"] == 3
                    and entry["x"]["$numberLong"] == 2
                    and entry["y"]["$numberLong"] == 1
                    and entry["z"]["$numberLong"] == 2):
                vraw = base64.b64decode(entry["records"]["voxel"]["data"]["$binary"])
                dec = lz4.block.decompress(
                    vraw[12:], uncompressed_size=int.from_bytes(vraw[4:8], 'little'))
                idx = dec.find(b'Debug1')
                return dec[64:idx - 13], int.from_bytes(dec[idx - 13:idx - 13 + 4], 'little')

    tests = [
        ("exports/1573_export.blueprint", 1, 14, 30),
    ]

    for path, Nc_neg, lz, Ye in tests:
        real_scan, mc = load_212(path)
        gen_scan = generate_212_bnd_scan(Nc_neg, mc, lz=lz, Yextent=Ye)
        match = gen_scan == real_scan
        print(f"Nc_neg={Nc_neg} Ye={Ye} lz={lz}: scan_len={len(real_scan)} mc={mc} MATCH={match}")
        if not match:
            diffs = [(i, real_scan[i], gen_scan[i])
                     for i in range(min(len(real_scan), len(gen_scan)))
                     if real_scan[i] != gen_scan[i]]
            print(f"  len: real={len(real_scan)} gen={len(gen_scan)}")
            for i, r, g in diffs[:15]:
                print(f"  [{i}] real=0x{r:02x} gen=0x{g:02x}")
