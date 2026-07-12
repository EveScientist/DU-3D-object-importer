"""
h3 scan generator for the (2,2,2) chunk (positive-x, positive-y, positive-z quadrant).

This chunk encodes the positive-y boundary of neg-y voxels placed at positive-x.
Unlike (2,1,2), the (2,2,2) chunk is Ye-independent — it only tracks how many
x-columns (Nc) are present.

Structure:
  Markers: Nc columns, 1 row each, separated by 8 background bytes.
    col_k marker: [xstep_val, 0x01, 0x02, 0x00, 0x00]  (col 1 uses own_val)
    inter-marker gap: 8 background bytes
    marker_span = 13*Nc - 8;  lme = pos1 + 13*Nc - 8 = 11 + 13*Nc

  Groups: groupA(8B) + sep(8B) + [groupB_colK(8B) + col_sep(8B)]*(Nc-1) + groupB_colNc(8B)
    groups_total = 8 + 16*Nc
    All halfblocks: [val, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00]

  mat_byte_pos = gs - pos1 + 9 = gs - 10   (same formula as (2,1,2))
  gap2 = gap1 - (pos1 - 9) = gap1 - 10     (same relationship as (2,1,2))
  scan_len = 677 + 9*Nc + 4*W_222

  Anomaly (new-wrap correction): when W_222(Nc) > W_222(Nc-1), byte[3] of the
  first groupB halfblock gets mat_byte ADDED: byte3 = 0x7e + (mc & 0xff).
  Confirmed at Nc=2 (W goes 0→1).

W_222 = sum(1 for k in range(2, Nc+1)
            if (160+55*k)%256 < (160+55*(k-1))%256)
Wraps at k=2,7,12 within Nc=1..31.

Constants:
  pos1_222     = 19
  own_val_222  = 0xa1 = 161
  xstep_val_222 = 0xc7 = 199
  groupA_val_222 = 0xd7 = 215
  groupB_val_222 = 0xc6 = 198
  K_222        = 160   (for mc_222 and W_222)

mc_222(Nc) = 512 + (160 + 55*Nc) % 256

Validated byte-exact against:
  1545 (Nc=1, lz=4, Ye=29): scan_len=686  mc=727  ✓
  1547 (Nc=2, lz=4, Ye=29): scan_len=699  mc=526  ✓  (0x8c anomaly)
  1549 (Nc=3, lz=4, Ye=29): scan_len=708  mc=581  ✓
  1551 (Nc=4, lz=4, Ye=29): scan_len=717  mc=636  ✓
"""

from h3_lowrow_212_generator import MAT_TAIL

HEADER_222 = bytes.fromhex(
    "13a0b827060000009e3381e8090000003f0000003f0000003f000000"
    "230000002300000023000000400000004000000040000000200000002000000020000000"
)
assert len(HEADER_222) == 64

_K_222 = 160
_POS1_222 = 19
_OWN_VAL_222 = 0xa1
_XSTEP_VAL_222 = 0xc7
_GROUPA_VAL_222 = 0xd7
_GROUPB_VAL_222 = 0xc6


def mc_222(Ncols):
    return 512 + (_K_222 + 55 * Ncols) % 256


def _w_222(Ncols):
    return sum(
        1 for k in range(2, Ncols + 1)
        if (_K_222 + 55 * k) % 256 < (_K_222 + 55 * (k - 1)) % 256
    )


def generate_222_scan(Ncols, mat_counter):
    """
    Generate voxel scan bytes for the (2,2,2) chunk with Ncols x-columns.

    Ncols:       number of x-columns (1..31)
    mat_counter: use mc_222(Ncols) from this module
    """
    pos1 = _POS1_222
    W = _w_222(Ncols)
    new_wrap = W > _w_222(Ncols - 1) if Ncols > 1 else False

    # Marker section: Nc columns with 8-byte inter-marker gap
    marker_span = 13 * Ncols - 8       # 5*Nc + 8*(Nc-1)
    lme = pos1 + marker_span            # = 11 + 13*Nc

    # Gap and groups
    gap1 = 324 - 10 * (Ncols - 1) + 2 * W   # = pos1+305 - 10*(Nc-1) + 2*W
    gap2 = gap1 - (pos1 - 9)                 # = gap1 - 10
    groups_total = 8 + 16 * Ncols            # groupA(8) + sep(8) + Nc*groupB(8) + (Nc-1)*col_sep(8)
    gs = lme + gap1

    mat_byte_pos = gs - pos1 + 9             # = gs - 10
    scan_len = gs + groups_total + gap2

    scan = bytearray(scan_len)

    # Background before marker section: even=0x00, odd=0xff
    for i in range(pos1):
        scan[i] = 0x00 if i % 2 == 0 else 0xff

    # Background after marker section: flip parity = Ncols % 2
    flip_after = Ncols % 2 == 1
    for i in range(lme, scan_len):
        if flip_after:
            scan[i] = 0xff if i % 2 == 0 else 0x00
        else:
            scan[i] = 0x00 if i % 2 == 0 else 0xff

    # Markers: col 1 uses own_val, cols 2..Nc use xstep_val.
    # Each 5-byte marker flips the background parity for the following col_sep.
    # Col_sep after col k (0-indexed) uses flip = (k+1) % 2.
    p = pos1
    for col in range(Ncols):
        val = _OWN_VAL_222 if col == 0 else _XSTEP_VAL_222
        scan[p:p + 5] = bytes([val, 0x01, 0x02, 0x00, 0x00])
        p += 5
        if col < Ncols - 1:
            flip_sep = (col + 1) % 2 == 1  # True after odd-indexed cols
            for i in range(p, p + 8):
                if flip_sep:
                    scan[i] = 0xff if i % 2 == 0 else 0x00
                else:
                    scan[i] = 0x00 if i % 2 == 0 else 0xff
            p += 8
    assert p == lme, f"marker end mismatch: {p} vs {lme}"

    # Mat byte
    scan[mat_byte_pos] = mat_counter & 0xff

    # Groups
    def halfblock(val):
        return bytes([val, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00])

    p = gs
    scan[p:p + 8] = halfblock(_GROUPA_VAL_222)
    p += 8
    p += 8  # sep (background)
    for col in range(Ncols):
        scan[p:p + 8] = halfblock(_GROUPB_VAL_222)
        p += 8
        if col < Ncols - 1:
            p += 8  # col_sep (background)
    assert p == gs + groups_total, f"groups end mismatch: {p}"

    # New-wrap correction: byte[3] of first groupB gets mat_byte added
    # Confirmed at Nc=2 (W: 0→1). Assumed pattern for Nc=7,12 (next wrap points).
    if new_wrap:
        b3_pos = gs + 8 + 8 + 3   # groupA + sep + groupB[3]
        scan[b3_pos] = (0x7e + (mat_counter & 0xff)) & 0xff

    return bytes(scan)


def generate_222_blob(Ncols, mat_counter=None):
    """Return (header64, scan, mat40) ready for LZ4 packing."""
    if mat_counter is None:
        mat_counter = mc_222(Ncols)
    scan = generate_222_scan(Ncols, mat_counter)
    mat = mat_counter.to_bytes(4, 'little') + MAT_TAIL
    return HEADER_222, scan, mat


if __name__ == "__main__":
    import json, base64, lz4.block

    def load_222(path):
        with open(path) as f:
            bp = json.load(f)
        for entry in bp["VoxelData"]:
            if (entry["h"] == 3 and entry["x"]["$numberLong"] == 2
                    and entry["y"]["$numberLong"] == 2
                    and entry["z"]["$numberLong"] == 2):
                vraw = base64.b64decode(entry["records"]["voxel"]["data"]["$binary"])
                dec = lz4.block.decompress(vraw[12:],
                                           uncompressed_size=int.from_bytes(vraw[4:8], 'little'))
                idx = dec.find(b'Debug1')
                scan = dec[64:idx - 13]
                mc = int.from_bytes(dec[idx - 13:idx - 13 + 4], 'little')
                return scan, mc

    tests = [
        ("exports/1545_export.blueprint", 1),
        ("exports/1547_export.blueprint", 2),
        ("exports/1549_export.blueprint", 3),
        ("exports/1551_export.blueprint", 4),
    ]

    for path, Nc in tests:
        real_scan, mc = load_222(path)
        gen_scan = generate_222_scan(Nc, mc)
        match = gen_scan == real_scan
        print(f"Nc={Nc} vs {path.split('/')[-1]}: scan_len={len(real_scan)} MATCH={match}")
        if not match:
            diffs = [(i, real_scan[i], gen_scan[i])
                     for i in range(min(len(real_scan), len(gen_scan)))
                     if real_scan[i] != gen_scan[i]]
            print(f"  len: real={len(real_scan)} gen={len(gen_scan)}")
            for i, r, g in diffs[:15]:
                print(f"  [{i}] real=0x{r:02x} gen=0x{g:02x}")
