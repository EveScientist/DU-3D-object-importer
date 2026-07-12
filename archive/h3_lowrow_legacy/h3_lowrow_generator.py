"""
h3 scan generator for a flat (Ncols x Yextent) rectangular plate at fixed lz,
anchored at (lx1=1, ly1=1) -- touching the LOW-Y boundary (ly=1), with
Yextent=29 spanning the FULL y-range (ly=1..29). Each cell is a single voxel
(N=1).

Validated byte-exact against:
  1496(Ncols=1), 1502(2), 1504(3), 1506(4), 1508(5) -- real in-game exports
  1517(Ncols=6) -- real in-game export (6x29 plate, separately confirmed)
  1528_export (Ncols=7) -- real in-game export: scan structure confirmed
    byte-exact (all bytes identical after correcting gap1/gap2; mat_counter=539)

mat_counter formula (Ncols>=2): 512 + (410 + 55*Ncols) % 256
  This wraps mod 256 in the low byte while mat[1] stays fixed at 2 (=0x200).
  Ncols=1 special case: mat_counter=721 (unrelated to the formula).
  Wrap events (low byte decreases going Ncols-1→Ncols) at Ncols=7,12,16,21,26...

Header (64B) and mat-tail (36B = mat[4:]) are CONSTANT across all tests
(same h3 chunk position (2,2,2)); only mat[0:4] (mat_counter) varies.

Layout (lx1=1,ly1=1,lz=14,Yextent=29):
  pos1 = 29                                  (= 2*n1_first(1,1,14)+7+4)
  marker_span     = 145*Ncols                (= 5*Ncols*Yextent)
  last_marker_end = pos1 + marker_span
  groups_total    = (Ncols+1)*240            (= (Ncols+1)*(Yextent+1)*8)
  gap1 = 316, gap2 = 296                     if Ncols == 1
  gap1 = 328-10*Ncols+2*W, gap2 = 308-10*Ncols+2*W   if Ncols >= 2
    where W = number of mat_counter wrap events in range Ncols=3..Ncols
    (Ncols=2 counted as baseline; W=0 for Ncols=2..6, W=1 for Ncols=7..11, etc.)
  groups_start = last_marker_end + gap1
  mat_byte_pos = groups_start - 20
  scan_len     = groups_start + groups_total + gap2

Background:
  [0,pos1): even=0x00, odd=0xff
  [last_marker_end, scan_len): "flip" if (Ncols*Yextent) odd (even=0xff,
    odd=0x00), else same as [0,pos1) pattern. Both parities validated
    (Ncols in {1,2,3,4,5,6,7} all byte-exact).
  scan[mat_byte_pos] = mat_counter & 0xff  (overrides whatever background
    byte would otherwise be there)

Markers (5 bytes each: [val,0x01,0x02,N-1,0x00]), starting at pos1, NO gaps
between columns:
  col 0:          own_val,   then (Yextent-1) x ystep_val
  col 1..Ncols-1: xstep_val, then (Yextent-1) x ystep_val

Groups (8-byte halfblocks: [val,0x01,N,0x7e,0x7e,0x7e,N,0x00]), starting at
groups_start, NO gaps between groups:
  GroupA:        groupA_val, then Yextent x default_val
  GroupB x Ncols (all identical): groupB_val, then Yextent x default_val

FULL-FACE PREDICTION (Ncols=29, the entire bottom Z=14 layer, 841 voxels):
  W=5 (wraps at Ncols=7,12,16,21,26), gap1=38+10=48, gap2=18+10=28
  marker_span=4205, last_marker_end=4234, groups_total=7200,
  groups_start=4282, mat_byte_pos=4262, scan_len=11510.
  Ncols*Yextent=841 (odd) -- same parity regime as the validated Ncols=1,3,5,7.
  NOTE: full-face prediction UNVERIFIED; needs real in-game export to confirm.
"""

from h3_k2_generator import mvf, mvf_neg, n1_first, decode_blob

HEADER_222 = bytes.fromhex(
    "13a0b827060000009e3381e8090000003f0000003f0000003f000000"
    "230000002300000023000000400000004000000040000000200000002000000020000000"
)
MAT_TAIL = bytes.fromhex(
    "00c768690900000000446562756731000001a502b0cb000000006863436172626f6e0201"
)
assert len(HEADER_222) == 64
assert len(MAT_TAIL) == 36


def generate_lowrow_scan(Ncols, mat_counter, lx1=1, ly1=1, lz=14, Yextent=29, N=1):
    assert (lx1, ly1, lz, Yextent, N) == (1, 1, 14, 29, 1), \
        "only the validated (1,1,14,Yextent=29,N=1) anchor family is implemented"

    pos1 = 2 * n1_first(lx1, ly1, lz) + 7 + 4  # +4 = lx1==1 correction
    marker_span = 5 * Ncols * Yextent
    last_marker_end = pos1 + marker_span
    groups_total = (Ncols + 1) * (Yextent + 1) * 8

    if Ncols == 1:
        gap1, gap2 = 316, 296
    else:
        # Count mat_counter wrap events in Ncols range [3..Ncols]; each adds +2
        # to gap1 and gap2.  Wraps happen when the low byte of (410+55*k)
        # decreases going from k-1 to k (i.e. crosses a 256 boundary).
        # Ncols=2 is the baseline (W=0); first wrap is at Ncols=7 (W=1).
        W = sum(
            1 for k in range(3, Ncols + 1)
            if (410 + 55 * k) % 256 < (410 + 55 * (k - 1)) % 256
        )
        gap1 = 328 - 10 * Ncols + 2 * W
        gap2 = 308 - 10 * Ncols + 2 * W

    groups_start = last_marker_end + gap1
    mat_byte_pos = groups_start - 20
    scan_len = groups_start + groups_total + gap2

    own_val = mvf(lx1, ly1, lz)
    groupA_val = (own_val + 19) % 256
    groupB_val = (212 - lz - 35 * Yextent - (N - 1)) % 256
    ystep_val = (304 - lz - N) % 256
    xstep_val = (234 - 35 * Yextent - (N - 1)) % 256

    scan = bytearray(scan_len)

    for i in range(pos1):
        scan[i] = 0x00 if i % 2 == 0 else 0xff

    flip = (Ncols * Yextent) % 2 == 1
    for i in range(last_marker_end, scan_len):
        if flip:
            scan[i] = 0xff if i % 2 == 0 else 0x00
        else:
            scan[i] = 0x00 if i % 2 == 0 else 0xff

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
    assert p == last_marker_end

    def halfblock(val):
        return bytes([val, 0x01, N & 0xff, 0x7e, 0x7e, 0x7e, N & 0xff, 0x00])

    default_val = (0x20 - (N - 1)) % 256

    def group_bytes(first_val):
        return halfblock(first_val) + halfblock(default_val) * Yextent

    p = groups_start
    g = group_bytes(groupA_val)
    scan[p:p + len(g)] = g
    p += len(g)
    for _ in range(Ncols):
        g = group_bytes(groupB_val)
        scan[p:p + len(g)] = g
        p += len(g)
    assert p == groups_start + groups_total

    scan[mat_byte_pos] = mat_counter & 0xff

    return bytes(scan)


def generate_lowrow_blob(Ncols, mat_counter, **kw):
    """Returns (header64, scan, mat40) ready for LZ4 packing."""
    scan = generate_lowrow_scan(Ncols, mat_counter, **kw)
    mat = mat_counter.to_bytes(4, 'little') + MAT_TAIL
    return HEADER_222, scan, mat


if __name__ == "__main__":
    import base64
    import lz4.block

    def get_scan(dec):
        idx = dec.find(b'Debug1')
        mat_start = idx - 13
        header = dec[:64]
        scan = dec[64:mat_start]
        mat = dec[mat_start:]
        mat_counter = int.from_bytes(mat[:4], 'little')
        return header, scan, mat, mat_counter

    tests = {
        1: "+bYU+1oFAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeA+tAAkPAgD5H9HVAQCf5gEBfn5+AQAgCADUH8/oANQE0AEPAAP5DwIACYDRAgAAAMdoaS4F8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB",
        2: "+bYU+8sGAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeB/zjAB4ARgBDz4BCQ8CAPEfCF4CAJ/mAQF+fn4BACAIANQfz+gA1ATQAQ/wAN0P6APxDwIACYAIAgAAAMdoaZ8G8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB",
        3: "+bYU+zgIAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeB/zjAB4ARgBD5EAfg/PAQkPAgDnHz/lAgCf5gEBfn5+AQAgCADUH8/oANQE0AEP8AD/zg/OBOcPAgAJgD8CAAAAx2hpDAjwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=",
        4: "+bYU+6UJAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeB/zjAB4ARgBD5EA/xAPYAIJDwIA3R92bAMAn+YBAX5+fgEAIAgA1B/P6ADUBNABD/AA//+/D7QF3Q8CAAmAdgIAAADHaGl5CfANAERlYnVnMQAAAaUCsMsAAAAAaGNDYXJib24CAQ==",
        5: "+bYU+xILAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgAIb9MBAgAAIQUAeB/zjAB4ARgBD5EA/6EP8QIJDwIA0x+t8wMAn+YBAX5+fgEAIAgA1B/P6ADUBNABD/AA////sA+aBtMPAgAJgK0CAAAAx2hp5grwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=",
    }

    for Ncols, b64 in tests.items():
        raw = base64.b64decode(b64)
        size = int.from_bytes(raw[4:8], 'little')
        dec = lz4.block.decompress(raw[12:], uncompressed_size=size)
        header, real_scan, mat, mat_counter = get_scan(dec)

        gen_scan = generate_lowrow_scan(Ncols, mat_counter)
        gen_header, _, gen_mat = generate_lowrow_blob(Ncols, mat_counter)

        scan_match = gen_scan == real_scan
        full_match = (gen_header + gen_scan + gen_mat) == dec
        print(f"Ncols={Ncols}: scan_len={len(real_scan)} scan MATCH={scan_match}  full_dec MATCH={full_match}")
        if not scan_match:
            if len(real_scan) != len(gen_scan):
                print(f"  len real={len(real_scan)} gen={len(gen_scan)}")
            for i, (a, b) in enumerate(zip(real_scan, gen_scan)):
                if a != b:
                    print(f"  diff at {i}: real={a:02x} gen={b:02x}")
