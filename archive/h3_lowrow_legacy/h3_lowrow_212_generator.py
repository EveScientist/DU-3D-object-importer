"""
h3 scan generator for a flat (Ncols x Yextent) plate in the (2,1,2) chunk
(positive-x, negative-y, positive-z quadrant), spanning the full negative-y
range ly_signed=-1..-29 (Yextent=29) at a fixed lz.

Coordinate conventions (same as (2,2,2)):
  lx_local  = game_x + 0.5   (integer 1..31 for positive-x half)
  ly_signed = game_y + 0.5   (NEGATIVE integer -1..-29 for neg-y half)
  lz_local  = game_z - 0.5   (integer; game Z=14.5 → lz=14)

Differences vs (2,2,2):
  - val_212 formula: (141*lx + 156*ly_signed + lz + 72) % 256
  - n1_first_212: same formula with signed ly
  - Anchor at (lx=1, ly_signed=-Yextent, lz) — furthest row, same column order
  - Row direction: ly_signed=-Ye to -1 (furthest-first, toward center)
  - groupB and ystep: always use effective lz=14 regardless of actual lz
  - gap1 = 328-10*Nc+2*W  (no Nc=1 special case, unlike (2,2,2))
  - gap2 = gap1 - 12       (= gap1 - pos1 + 9 for fixed pos1=21)
  - W uses (64+55*k) wrap events, not (410+55*k) as in (2,2,2)
  - mc formula: 512 + (64 + 55*Nc) % 256
  - NO column separator between marker columns
  - NO group separator between halfblock groups (PACKED)
  - HEADER_212 differs from HEADER_222 at bytes [20]=0x1f and [44]=0x20

Validated byte-exact against:
  1545 (Nc=1, lz=4):  gap1=318, gap2=306, mc=631 ✓
  1547 (Nc=2, lz=4):  gap1=308, gap2=296, mc=686 ✓
  1557 (Nc=1, Ye=1, lz=14): pos1=29, gap1=326, gt=40  ✓ (pos1 formula only)
  1559 (Nc=1, Ye=2, lz=14): pos1=27, gap1=324, gt=56  ✓ (pos1 formula only)
"""

from h3_k2_generator import decode_blob

HEADER_212 = bytes.fromhex(
    "13a0b827060000009e3381e8090000003f0000001f0000003f000000"
    "230000002300000023000000400000002000000040000000200000002000000020000000"
)
MAT_TAIL = bytes.fromhex(
    "00c768690900000000446562756731000001a502b0cb000000006863436172626f6e0201"
)
assert len(HEADER_212) == 64
assert len(MAT_TAIL) == 36

_EFF_LZ = 14   # effective lz for groupB and ystep formulas (hardcoded)


def val_212(lx, ly_signed, lz):
    """(2,1,2) voxel value. ly_signed is negative for negative-y voxels."""
    return (141 * lx + 156 * ly_signed + lz + 72) % 256


def n1_first_212(lx, ly_signed, lz):
    """n1_first for (2,1,2) using signed ly."""
    return 4 + (153 * lx + 4 * ly_signed + lz) // 31


def mc_212(Ncols):
    """mat_counter for (2,1,2) chunk. Validated at Nc=1 (631) and Nc=2 (686)."""
    return 512 + (64 + 55 * Ncols) % 256


def generate_212_scan(Ncols, mat_counter, lz=14, Yextent=29, N=1):
    """
    Generate the voxel scan bytes for a (Ncols x Yextent) plate in (2,1,2).

    lz:        local z-coordinate of the plate (game_z - 0.5; game Z=14.5 → lz=14)
    Yextent:   number of negative-y rows (29 = full range ly_signed=-1..-29)
    Ncols:     number of x-columns (1..31)
    N:         voxels per cell (1 only supported)

    Nc=1 and Nc=2 are byte-verified. Nc>=3 uses the same formula (unverified).
    """
    assert N == 1, "only N=1 implemented"

    # pos1 uses -(Yextent+2) anchor — 2 rows further than actual extent.
    # Validated: Ye=1/lz=14→29, Ye=2/lz=14→27, Ye=29/lz=4→21.
    pos1 = 2 * n1_first_212(1, -(Yextent + 2), lz) + 11

    marker_span = 5 * Ncols * Yextent   # no column separator
    last_marker_end = pos1 + marker_span

    # Separator between groupA and groupB (background bytes, not halfblock content).
    # sep = 2 * (n1_first_212(1, -(Yextent-2), lz) - 5)
    # As n1 decreases with larger Ye: n1=9→sep=8, 8→6, 7→4, 6→2, 5→0.
    # At lz=14: sep=8 for Ye≤5, 6 for 6≤Ye≤12, 4 for 13≤Ye≤20, 2 for 21≤Ye≤28, 0 for Ye=29.
    # Confirmed: Ye=1,2,5→8; Ye=12→6; Ye=13,14,15→4; Ye=25→2; Ye=29(lz=4)→0.
    ye1 = Yextent + 1
    sep = 2 * (n1_first_212(1, -(Yextent - 2), lz) - 5)
    groups_total = (Ncols + 1) * ye1 * 8 + sep

    # gap1 = pos1 + 297 - 10*(Nc-1) + 2*W.
    # This follows because gap2 = 306 - 10*(Nc-1) + 2*W is the true constant.
    # For Nc=1: gap1=pos1+297, gap2=306 (verified across Ye=1,2,29 at multiple lz).
    # For Nc>1: formula validated only at Ye=29; assumed to generalize by symmetry.
    # W counts (64+55*k) wrap events for k in [3..Ncols]
    W = sum(
        1 for k in range(3, Ncols + 1)
        if (64 + 55 * k) % 256 < (64 + 55 * (k - 1)) % 256
    )
    gap1 = pos1 + 297 - 10 * (Ncols - 1) + 2 * W
    gap2 = gap1 - (pos1 - 9)   # = 306 - 10*(Nc-1) + 2*W

    groups_start = last_marker_end + gap1
    mat_byte_pos = groups_start - pos1 + 9  # = groups_start - 12
    scan_len = groups_start + groups_total + gap2

    # val is lz-independent (like groupB/ystep) — uses effective lz=14 hardcoded.
    # Correct formula confirmed: Ye=29/lz=4 → 45, Ye=1/lz=14 → 1, Ye=1/N=2 → 0.
    # val_212(1,-Ye,lz) coincidentally matches for Ye=29/lz=4 but is wrong otherwise.
    groupB_val = (212 - _EFF_LZ - 35 * Yextent - (N - 1)) % 256
    own_val = (groupB_val - 162) % 256   # = (36 - 35*Ye - (N-1)) % 256
    groupA_val = (own_val + 19) % 256
    ystep_val  = (304 - _EFF_LZ - N) % 256
    xstep_val  = (234 - 35 * Yextent - (N - 1)) % 256

    scan = bytearray(scan_len)

    # Background: even=0x00, odd=0xff before pos1
    for i in range(pos1):
        scan[i] = 0x00 if i % 2 == 0 else 0xff

    # Background after last_marker_end: flip parity if Ncols*Yextent is odd
    flip = (Ncols * Yextent) % 2 == 1
    for i in range(last_marker_end, scan_len):
        if flip:
            scan[i] = 0xff if i % 2 == 0 else 0x00
        else:
            scan[i] = 0x00 if i % 2 == 0 else 0xff

    # Markers: no column separator; columns lx=1..Ncols; rows ly=-Ye..-1
    def marker(val):
        return bytes([val, 0x01, 0x02, (N - 1) & 0xff, 0x00])

    p = pos1
    for col in range(Ncols):
        first_val = own_val if col == 0 else xstep_val
        scan[p:p + 5] = marker(first_val)
        p += 5
        for _ in range(Yextent - 1):
            scan[p:p + 5] = marker(ystep_val)
            p += 5
    assert p == last_marker_end, f"marker end mismatch: {p} vs {last_marker_end}"

    # Groups: (Ncols+1) groups of (Yextent+1) halfblocks, packed
    def halfblock(val):
        return bytes([val, 0x01, N & 0xff, 0x7e, 0x7e, 0x7e, N & 0xff, 0x00])

    default_val = (0x20 - (N - 1)) % 256

    def group_bytes(first_val):
        return halfblock(first_val) + halfblock(default_val) * Yextent

    p = groups_start
    scan[p:p + (Yextent + 1) * 8] = group_bytes(groupA_val)
    p += (Yextent + 1) * 8
    p += sep   # sep bytes are background (already written); skip past them
    for _ in range(Ncols):
        scan[p:p + (Yextent + 1) * 8] = group_bytes(groupB_val)
        p += (Yextent + 1) * 8
    assert p == groups_start + groups_total, f"groups end mismatch: {p}"

    scan[mat_byte_pos] = mat_counter & 0xff
    return bytes(scan)


def generate_212_blob(Ncols, mat_counter=None, lz=14):
    """Return (header64, scan, mat40) ready for LZ4 packing."""
    if mat_counter is None:
        mat_counter = mc_212(Ncols)
    scan = generate_212_scan(Ncols, mat_counter, lz=lz)
    mat = mat_counter.to_bytes(4, 'little') + MAT_TAIL
    return HEADER_212, scan, mat


if __name__ == "__main__":
    import json, base64, lz4.block

    def load_212(path):
        with open(path) as f:
            bp = json.load(f)
        for entry in bp["VoxelData"]:
            if (entry["h"] == 3 and entry["x"]["$numberLong"] == 2
                    and entry["y"]["$numberLong"] == 1
                    and entry["z"]["$numberLong"] == 2):
                vraw = base64.b64decode(entry["records"]["voxel"]["data"]["$binary"])
                dec = lz4.block.decompress(vraw[12:], uncompressed_size=int.from_bytes(vraw[4:8], 'little'))
                idx = dec.find(b'Debug1')
                scan = dec[64:idx - 13]
                mc = int.from_bytes(dec[idx - 13:idx - 13 + 4], 'little')
                return scan, mc

    tests = [
        ("exports/1545_export.blueprint", 1, 4,  29),
        ("exports/1547_export.blueprint", 2, 4,  29),
        ("exports/1549_export.blueprint", 3, 4,  29),
        ("exports/1551_export.blueprint", 4, 4,  29),
        ("exports/1567_export.blueprint", 1, 14, 25),
        ("exports/1569_export.blueprint", 1, 14, 13),
        ("exports/1571_export.blueprint", 1, 14, 12),
    ]

    for path, Nc, lz, Ye in tests:
        real_scan, mc = load_212(path)
        gen_scan = generate_212_scan(Nc, mc, lz=lz, Yextent=Ye)
        match = gen_scan == real_scan
        print(f"Nc={Nc} Ye={Ye} lz={lz} vs {path.split('/')[-1]}: scan_len={len(real_scan)} MATCH={match}")
        if not match:
            diffs = [(i, real_scan[i], gen_scan[i])
                     for i in range(min(len(real_scan), len(gen_scan)))
                     if real_scan[i] != gen_scan[i]]
            print(f"  len: real={len(real_scan)} gen={len(gen_scan)}")
            for i, r, g in diffs[:15]:
                print(f"  [{i}] real=0x{r:02x} gen=0x{g:02x}")
