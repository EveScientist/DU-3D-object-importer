"""
Generalized h3 scan generator: N adjacent single-voxel columns (N_i=1 for all i),
all at the same lz, starting at (lx1, ly1, lz). Generalizes h3_k2_generator's K=2
(2-column) case to arbitrary Ncols >= 2.

Validated byte-exact (scan + full dec) against:
  - 1433 (Ncols=3, hcAlLiPa)
  - 1435 (Ncols=3, hcCarbon -- identical scan bytes to 1433, confirming
    material-independence of the scan body)
  - 1437 (Ncols=4, hcCarbon)

Key findings vs the K=2 (Ncols=2) formulas in h3_k2_generator.py:
  - scan_len = 723 + 17*(Ncols-2)
  - PAIR1_pos = 511 + 3*(Ncols-2)
  - mat_byte_pos = PAIR1_pos - 168  (generalizes the old fixed-343 rule)
  - marker_k @ pos1 + 13*(k-1) for k=1..Ncols (pos1 unchanged, anchor-dependent)
  - #markers = Ncols, #PAIRs = Ncols+1
  - marker1 / PAIR1 (col1) use the K=2 formulas with ZERO offset, always
  - marker_2..Ncols / PAIR_2..Ncols+1 (cols 2+) get a flat "+1" correction
    for ANY Ncols>=3 (confirmed constant at Ncols=3 AND Ncols=4 -- does not
    scale with Ncols, i.e. NOT "Ncols-2")
  - Background phase after the last marker flips based on Ncols parity:
    normal (even=0x00/odd=0xff) for Ncols even, inverted (even=0xff/odd=0x00)
    for Ncols odd. Each marker_k for k < Ncols is followed by an explicit
    8-byte [0xff,0x00]*4 block (fills the gap to the next marker).

Scope: only handles the "all columns N_i=1, identical lz" case. Varying N_i
or lz per column for Ncols>=3 is not yet characterized.
"""

import base64
import lz4.block

from h3_k2_generator import mvf, mvf_neg, n1_first, pair_block, decode_blob


def generate_n_adjacent_scan(lx1, ly1, lz, Ncols, mat_counter):
    pos1 = 2 * n1_first(lx1, ly1, lz) + 7
    scan_len = 723 + 17 * (Ncols - 2)
    last_marker_end = pos1 + 13 * Ncols - 8

    scan = bytearray(scan_len)
    # background before pos1: always normal phase
    for i in range(0, pos1):
        scan[i] = 0x00 if i % 2 == 0 else 0xff
    # background after last marker: normal if Ncols even, inverted if Ncols odd
    for i in range(last_marker_end, scan_len):
        if Ncols % 2 == 1:
            scan[i] = 0xff if i % 2 == 0 else 0x00
        else:
            scan[i] = 0x00 if i % 2 == 0 else 0xff

    correction = 0 if Ncols == 2 else 1

    marker1_val = mvf(lx1, ly1, lz)
    marker_other_val = (mvf_neg(lx1, ly1, lz) + 0xa4 + correction) % 256

    for k in range(1, Ncols + 1):
        p = pos1 + 13 * (k - 1)
        val = marker1_val if k == 1 else marker_other_val
        scan[p:p + 5] = bytes([val, 0x01, 0x02, 0x00, 0x00])
        if k < Ncols:
            # explicit 8-byte inverted block fills the gap to the next marker
            scan[p + 5:p + 13] = bytes([0xff, 0x00] * 4)

    PAIR1_pos = 511 + 3 * (Ncols - 2)
    p1_val_a = (marker1_val + 19) % 256
    scan[PAIR1_pos:PAIR1_pos + 16] = pair_block(p1_val_a, 0x20, 1)

    p_other_val_a = (mvf_neg(lx1, ly1, lz) + 128 + correction) % 256
    for k in range(2, Ncols + 2):
        p = PAIR1_pos + 24 * (k - 1)
        scan[p:p + 16] = pair_block(p_other_val_a, 0x20, 1)

    mat_byte_pos = PAIR1_pos - 168
    scan[mat_byte_pos] = mat_counter & 0xff

    return bytes(scan)


if __name__ == "__main__":
    tests = {
        "1433 (Ncols=3, hcAlLiPa)": (
            "+bYU+0wDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzAB/HDQAGDwIAbxWopgAPAgCLk1EBAX5+fgEAIAgABK4AE6MQAA8YAC0PAgBvgKgCAAAAx2hpIAPwDQBEZWJ1ZzEAAAHGD7Z0AAAAAGhjQWxMaVBhAgE=",
            3,
        ),
        "1435 (Ncols=3, hcCarbon)": (
            "+bYU+0wDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzAB/HDQAGDwIAbxWopgAPAgCLk1EBAX5+fgEAIAgABK4AE6MQAA8YAC0PAgBvgKgCAAAAx2hpIAPwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=",
            3,
        ),
        "1437 (Ncols=4, hcCarbon)": (
            "+bYU+10DAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzAB/HDQATDwIAZRXfqQAPAgCLk1EBAX5+fgEAIAgABK4AE6MQAA8YAEUPAgBlgN8CAAAAx2hpMQPwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=",
            4,
        ),
    }

    for name, (b64, Ncols) in tests.items():
        dec = decode_blob(b64)
        idx = dec.find(b'Debug1')
        mat_start = idx - 13
        header = dec[:64]
        real_scan = dec[64:mat_start]
        mat = dec[mat_start:]
        mat_counter = int.from_bytes(mat[:4], 'little')

        gen_scan = generate_n_adjacent_scan(16, 13, 14, Ncols, mat_counter)

        scan_match = gen_scan == real_scan
        full_match = (header + gen_scan + mat) == dec
        print(f"{name}: scan MATCH={scan_match}  full_dec MATCH={full_match}")
        if not scan_match:
            for i, (a, b) in enumerate(zip(real_scan, gen_scan)):
                if a != b:
                    print(f"  diff at {i}: real={a:02x} gen={b:02x}")
