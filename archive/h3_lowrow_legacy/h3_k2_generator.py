"""
First real h3 scan generator: K=2 (adjacent, no-gap) 2-column case.

Target shape (test 1390): anchor lx1=16,ly1=13
  col1: lx=16, N1=2, lz=14-15
  col2: lx=17 (=lx1+1), N2=1, lz=13

This module builds the 723-byte scan body byte-for-byte for the
(lx1=16, ly1=13), N1+N2=3 family of K=2 tests, and verifies it against
1390's actual decoded blob.
"""

import base64
import lz4.block


def decode_blob(b64):
    raw = base64.b64decode(b64)
    size = int.from_bytes(raw[4:8], 'little')
    return lz4.block.decompress(raw[12:], uncompressed_size=size)


def mvf(lx, ly, lz):
    return (201 * lx + 35 * ly + lz + 217) % 256


def mvf_neg(lx, ly, lz):
    return (201 * lx + 35 * ly - lz + 217) % 256


def n1_first(lx, ly, lz):
    return 4 + (153 * lx + 4 * ly + lz) // 31


def pair_block(val_a, val_b, c):
    """16-byte opener+closer block: [val,01,C,7e,7e,7e,C,00] x2"""
    opener = bytes([val_a, 0x01, c, 0x7e, 0x7e, 0x7e, c, 0x00])
    closer = bytes([val_b, 0x01, c, 0x7e, 0x7e, 0x7e, c, 0x00])
    return opener + closer


def generate_k2_scan(lx1, ly1, N1, lz_min1, lz_max1, N2, lz_min2, lz_max2, mat_counter):
    """
    K=2 (adjacent column pair) h3 scan body, anchor (lx1,ly1), scan_len=723.
    lx2 = lx1 + 1 (col2 is adjacent to col1).
    Confirmed byte-exact for 1390, 1356, 1354 (3/3) and 722/723 for 1352 (5-voxel column).

    mat_counter: the 4-byte little-endian counter that goes in mat[0:4] of the
    material section. Its low byte is independently duplicated into the scan at
    position 343 (confirmed 8/8 across all available tests, K=2 and K=3 alike).
    """
    GLOBAL_lz_min = min(lz_min1, lz_min2)
    GLOBAL_lz_max = max(lz_max1, lz_max2)
    GLOBAL_lz_span = GLOBAL_lz_max - GLOBAL_lz_min + 1

    scan_len = 723
    scan = bytearray(scan_len)
    for i in range(scan_len):
        scan[i] = 0x00 if i % 2 == 0 else 0xff

    # marker1 @ pos1
    pos1 = 2 * n1_first(lx1, ly1, lz_max1) + 7
    marker1_val = mvf(lx1, ly1, lz_min1)
    scan[pos1:pos1 + 5] = bytes([marker1_val, 0x01, 0x02, N1 - 1, 0x00])

    # 8-byte phase-inverted block immediately after marker1 (N1+N2=3 family)
    inv_start = pos1 + 5
    scan[inv_start:inv_start + 8] = bytes([0xff, 0x00] * 4)

    # marker2 @ pos2 = pos1 + 13
    pos2 = pos1 + 13
    marker2_val = (mvf_neg(lx1, ly1, lz_min1) + 0xa4 - (N1 - 1)) % 256
    scan[pos2:pos2 + 5] = bytes([marker2_val, 0x01, 0x02, N2 - 1, 0x00])

    # byte @343 is just a copy of mat[0:4]'s low byte (cross-reference, not geometric)
    scan[343] = mat_counter & 0xff

    # PAIR1 @ 511-526
    p1_val_a = (marker1_val + 19) % 256
    p1_val_b = 0x20 - (N1 - 1)
    scan[511:527] = pair_block(p1_val_a, p1_val_b, N1)

    # PAIR2 @ 535-550
    p2_val_a = (mvf_neg(lx1, ly1, lz_max1) + 128) % 256
    p2_val_b = 0x20 - (GLOBAL_lz_span - 1)
    scan[535:551] = pair_block(p2_val_a, p2_val_b, GLOBAL_lz_span)

    # PAIR3 @ 559-574
    p3_val_a = (mvf_neg(lx1, ly1, GLOBAL_lz_max) + 128) % 256
    p3_val_b = 0x20 - (N2 - 1)
    scan[559:575] = pair_block(p3_val_a, p3_val_b, N2)

    return bytes(scan)


if __name__ == "__main__":
    tests = {
        "1390": ("+bYU+zsDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgGzAEXFAQ"
                 "IADQAPAgB5H3KWAIIOAgCTUQECfn5+AgAfCAAEIgCToQEDfn5+AwAeCAAGGABzAX5+fgEAIAgABBgADwIA"
                 "eYByAgAAAMdoaQ8D8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB",
                 dict(lx1=16, ly1=13, N1=2, lz_min1=14, lz_max1=15, N2=1, lz_min2=13, lz_max2=13)),
        "1356": ("+bYU+zsDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT0BAgCzAEXHAQ"
                 "IBDQAPAgB5H3GWAIIOAgCTUAEBfn5+AQAgCAAEIgCTowECfn5+AgAfCAAEGAATohAADBgADwIAeYBxAgAA"
                 "AMdoaQ8D8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB",
                 dict(lx1=16, ly1=13, N1=1, lz_min1=13, lz_max1=13, N2=2, lz_min2=13, lz_max2=14)),
        "1354": ("+bYU+zsDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT0BAgGzABjGDQ"
                 "APAgB5FXGjAA8CAIuTUAECfn5+AgAfCAAErgATohAADxgAFQ8CAHmAcQIAAADHaGkPA/ANAERlYnVnMQAA"
                 "AaUCsMsAAAAAaGNDYXJib24CAQ==",
                 dict(lx1=16, ly1=13, N1=2, lz_min1=13, lz_max1=14, N2=2, lz_min2=13, lz_max2=14)),
        "1352": ("+bYU+zsDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT0BAgSzAEXDAQ"
                 "IADQAPAgB5H3KWAIIOAgCTUAEFfn5+BQAcCAAEIgATnxAADhgAcwF+fn4BACAIAAQwAA8CAHmAcgIAAADH"
                 "aGkPA/ANAERlYnVnMQAAAaUCsMsAAAAAaGNDYXJib24CAQ==",
                 dict(lx1=16, ly1=13, N1=5, lz_min1=13, lz_max1=17, N2=1, lz_min2=13, lz_max2=13)),
    }

    for name, (b64, params) in tests.items():
        dec = decode_blob(b64)
        idx = dec.find(b'Debug1')
        mat_start = idx - 13
        header = dec[:64]
        real_scan = dec[64:mat_start]
        mat = dec[mat_start:]
        mat_counter = int.from_bytes(mat[:4], 'little')

        gen_scan = generate_k2_scan(**params, mat_counter=mat_counter)

        scan_match = gen_scan == real_scan
        full_match = (header + gen_scan + mat) == dec
        print(f"{name}: scan MATCH={scan_match}  full_dec MATCH={full_match}")
        if not scan_match:
            for i, (a, b) in enumerate(zip(real_scan, gen_scan)):
                if a != b:
                    print(f"  diff at {i}: real={a:02x} gen={b:02x}")
