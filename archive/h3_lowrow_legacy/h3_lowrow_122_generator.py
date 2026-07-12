"""
h3 scan generator for the (1,2,2) chunk (negative-x, positive-y, positive-z quadrant).

This chunk is COMPLETELY CONSTANT across all Nc/Ye/lz values — identical bytes
regardless of what voxels are placed (as long as at least one positive-x neg-y
voxel exists to activate it). It encodes the neg-x/pos-y corner boundary.

Structure (all constants):
  pos1_122       = 325   (= pos1_222 + 306 = 19 + 306)
  1 marker       at [325]: [0xc1, 0x01, 0x02, 0x00, 0x00]
  mat_byte_pos   = 338   (= gs - pos1 + 9)
  gs_122         = 654
  groups_total   = 24    (groupA(8) + sep(8) + groupB(8))
  gap2           = 8
  scan_len       = 686

  own_val_122    = 0xc1 = 193  (marker)
  groupA_val_122 = 0xf7 = 247
  groupB_val_122 = 0xc6 = 198
  mc_122         = 695  (constant)

Background: [0..324] uses even=00/odd=ff (flip=0).
After the 5-byte marker section: flip=True (even=ff, odd=00).

Header differs from HEADER_212 at:
  byte[16]: 0x3f → 0x1f  (neg-x flag)
  byte[20]: 0x1f → 0x3f  (pos-y flag)
  byte[40]: 0x40 → 0x20
  byte[44]: 0x20 → 0x40

Validated byte-exact (constant) across:
  1545, 1547, 1549, 1551 (Nc=1..4, lz=4, Ye=29)
"""

from h3_lowrow_212_generator import MAT_TAIL

HEADER_122 = bytes.fromhex(
    "13a0b827060000009e3381e8090000001f0000003f0000003f000000"
    "230000002300000023000000200000004000000040000000200000002000000020000000"
)
assert len(HEADER_122) == 64

MC_122 = 695

_POS1_122 = 325
_GS_122 = 654
_SCAN_LEN_122 = 686
_OWN_VAL_122 = 0xc1
_GROUPA_VAL_122 = 0xf7
_GROUPB_VAL_122 = 0xc6
_MAT_BYTE_POS_122 = 338   # = _GS_122 - _POS1_122 + 9


def generate_122_scan(mat_counter=MC_122):
    """
    Generate the constant voxel scan bytes for the (1,2,2) chunk.

    mat_counter is always MC_122=695; parameter kept for API consistency.
    """
    scan = bytearray(_SCAN_LEN_122)

    # Background [0..pos1-1]: even=00, odd=ff
    for i in range(_POS1_122):
        scan[i] = 0x00 if i % 2 == 0 else 0xff

    # Single marker at pos1
    scan[_POS1_122:_POS1_122 + 5] = bytes([_OWN_VAL_122, 0x01, 0x02, 0x00, 0x00])

    # Background [lme..scan_len-1]: flip=True (5 marker bytes → parity flips)
    lme = _POS1_122 + 5   # = 330
    for i in range(lme, _SCAN_LEN_122):
        scan[i] = 0xff if i % 2 == 0 else 0x00

    # Mat byte
    scan[_MAT_BYTE_POS_122] = mat_counter & 0xff

    # Groups: groupA + sep(background) + groupB
    def halfblock(val):
        return bytes([val, 0x01, 0x01, 0x7e, 0x7e, 0x7e, 0x01, 0x00])

    p = _GS_122
    scan[p:p + 8] = halfblock(_GROUPA_VAL_122)
    p += 8
    p += 8   # sep (background already written)
    scan[p:p + 8] = halfblock(_GROUPB_VAL_122)

    return bytes(scan)


# Pre-built constant scan (computed once at import)
_SCAN_122 = generate_122_scan()


def generate_122_blob(mat_counter=MC_122):
    """Return (header64, scan, mat40) ready for LZ4 packing."""
    scan = generate_122_scan(mat_counter)
    mat = mat_counter.to_bytes(4, 'little') + MAT_TAIL
    return HEADER_122, scan, mat


if __name__ == "__main__":
    import json, base64, lz4.block

    def load_122(path):
        with open(path) as f:
            bp = json.load(f)
        for entry in bp["VoxelData"]:
            if (entry["h"] == 3 and entry["x"]["$numberLong"] == 1
                    and entry["y"]["$numberLong"] == 2
                    and entry["z"]["$numberLong"] == 2):
                vraw = base64.b64decode(entry["records"]["voxel"]["data"]["$binary"])
                dec = lz4.block.decompress(vraw[12:],
                                           uncompressed_size=int.from_bytes(vraw[4:8], 'little'))
                idx = dec.find(b'Debug1')
                return dec[64:idx - 13], int.from_bytes(dec[idx - 13:idx - 13 + 4], 'little')

    # (1,2,2) is constant — any export works; test with all 4
    tests = [
        ("exports/1545_export.blueprint", 1),
        ("exports/1547_export.blueprint", 2),
        ("exports/1549_export.blueprint", 3),
        ("exports/1551_export.blueprint", 4),
    ]

    gen_scan = generate_122_scan()
    for path, Nc in tests:
        real_scan, mc = load_122(path)
        match = gen_scan == real_scan
        print(f"Nc={Nc} vs {path.split('/')[-1]}: scan_len={len(real_scan)} mc={mc} MATCH={match}")
        if not match:
            diffs = [(i, real_scan[i], gen_scan[i])
                     for i in range(min(len(real_scan), len(gen_scan)))
                     if real_scan[i] != gen_scan[i]]
            print(f"  len: real={len(real_scan)} gen={len(gen_scan)}")
            for i, r, g in diffs[:10]:
                print(f"  [{i}] real=0x{r:02x} gen=0x{g:02x}")
