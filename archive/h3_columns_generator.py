"""
UNIFIED h3 scan generator: Ncols adjacent columns along lx, starting at
(lx1, ly1), each column i a single contiguous lz-run (lz_min_i .. lz_max_i,
height N_i = lz_max_i - lz_min_i + 1).

This SUPERSEDES h3_k2_generator.generate_k2_scan and
h3_n_adjacent_generator.generate_n_adjacent_scan.

Validated 14/14 byte-exact (scan AND full dec = header+scan+mat):
  - 1390, 1356, 1354, 1352  (Ncols=2, varying N1/N2 -- the original K=2 set)
  - 1433, 1435             (Ncols=3, all N_i=1, same lz -- hcAlLiPa & hcCarbon,
                             identical scans -> material-independent)
  - 1437                   (Ncols=4, all N_i=1, same lz)
  - 1439                   (Ncols=3, col3 N=2 -- last column taller)
  - 1441                   (Ncols=3, col2 N=2 -- middle column taller)
  - 1443                   (Ncols=4, col2 N=2 -- 2nd column taller)
  - 1445                   (Ncols=4, col3 N=2 -- 3rd/penultimate column taller)
  - 1450                   (Ncols=5, all N_i=1, same lz -- baseline)
  - 1447                   (Ncols=5, col2 N=2 -- 2nd column taller)
  - 1452                   (Ncols=6, all N_i=1, same lz -- baseline)

### The model

Let lz_min[i], lz_max[i], N[i] = lz_max[i]-lz_min[i]+1 for i=0..Ncols-1
(0-indexed columns 1..Ncols). correction = 0 if Ncols==2 else 1.

Layout:
  pos1 = 2*n1_first(lx1,ly1,lz_max[0]) + 7   (anchor-dependent, col1's lz_max)

  jump = 4 if Ncols >= 5 else 0   (PAIR1_pos jump = 2 if Ncols >= 5 else 0)
  scan_len  = 689 + 17*Ncols + jump
  PAIR1_pos = 505 + 3*Ncols  + jump // 2
  -- For Ncols<=4 these reduce to the old "723 + 17*(Ncols-2)" /
     "511 + 3*(Ncols-2)" formulas exactly. At Ncols=5 BOTH jump by an extra
     +4 / +2 respectively (778/522, confirmed by both 1447 and 1450 -- the
     jump is INTRINSIC to Ncols=5, independent of sum(N)). 1452 (Ncols=6,
     baseline) confirms this is a ONE-TIME step (795/525 = 778+17/522+3,
     i.e. the +4/+2 offset is a constant added once for Ncols>=5, NOT a
     permanent slope change to +21/+5 -- the earlier max(0,Ncols-4) guess
     is REJECTED). Ncols=7+ untested -- there could be ANOTHER one-time jump
     further out, but the simple "+4/+2 once, for Ncols>=5" step function is
     now confirmed across two consecutive Ncols values (5,6).

  marker_1 @ pos1            = [mvf(lz_min[0]), 0x01, 0x02, N[0]-1, 0x00]
  marker_k @ pos1+13*(k-1)    = [mvf_neg(lz_max[k-2])+0xa4+correction, 0x01,
                                  0x02, N[k-1]-1, 0x00]    for k=2..Ncols
  -- marker_k's VALUE depends only on the PRECEDING column's lz_max; its 4th
     byte is always that column's own (N_k - 1). Confirmed for k up to Ncols=5
     (all 5 markers in 1447/1450 match exactly, unaffected by the Ncols=5
     scan_len/PAIR1_pos jump).
  Each marker_k for k<Ncols is followed by an explicit 8-byte [0xff,0x00]*4
  block (fills the 13-byte stride to the next marker).

  PAIR_1    = pair_block(mvf(lz_min[0])+19, 0x20-(N[0]-1), N[0])      -- col1 own span

  -- "interior" PAIRs k=2,3 (FIXED at exactly these two slots for Ncols>=4 --
     confirmed by 1447/1450: even at Ncols=5 there are only 2 interior pairs,
     NOT k=2..Ncols-1={2,3,4}):
  PAIR_k    = pair_block(mvf_neg(lz_max[k-2])+128+correction,
                          0x20-(span_k-1), span_k)    for k=2,3
              where span_k = prefix_span(k) = combined lz-range span of
              columns 1..k (running/cumulative union of [lz_min_i,lz_max_i]).

  -- "trailing" PAIRs PAIR_4 .. PAIR_{Ncols+1} (count = Ncols-2, for
     Ncols<=3 this group is handled by the separate branch below):
  PAIR_4 = pair_block(mvf_neg(GLOBAL_lz_max)+128+correction,
                       0x20-(last_two_span-1), last_two_span)
           -- GLOBAL_lz_max = prefix_lz_max(Ncols) = max over ALL columns.
           -- last_two_span = combined lz-range span of JUST columns
              (Ncols-1, Ncols) (the last two), i.e.
              max(lz_max[Ncols-2],lz_max[Ncols-1]) -
              min(lz_min[Ncols-2],lz_min[Ncols-1]) + 1.
  PAIR_{4+j} for j=1..(Ncols-3) =
      pair_block(mvf_neg(lz_max[1+j])+128+correction,
                 0x20-(N[2+j]-1), N[2+j])
           -- a "sliding window": val_a keyed off column (j+2)'s lz_max,
              span = column (j+3)'s OWN height (not a prefix span).
           -- For Ncols=4 this is just j=1 -> PAIR_5 = lz_max[2]-based +
              N[3] (= old "PAIR_{Ncols+1}" formula).
           -- For Ncols=5, j=1,2 -> PAIR_5 (lz_max[2]+N[3]), PAIR_6
              (lz_max[3]+N[4]). Both confirmed in 1447 and 1450.
           -- For Ncols>=6 this is EXTRAPOLATED/untested.

  PAIR_k_pos = PAIR1_pos + 24*(k-1)  for k=1..Ncols+1  (16B block + 8B gap)
  -- stride of +24 confirmed for all 6 pairs at Ncols=5.

  mat_byte_pos = PAIR1_pos - 168  (cross-reference: scan[mat_byte_pos] =
  mat[0:4] (the material section's leading u32 LE counter) & 0xff)
  -- confirmed still holds at Ncols=5 (354 = 522-168, matches low byte of
  mat_counter in both 1447 and 1450).

Background fill:
  [0, pos1): normal phase (even=0x00, odd=0xff)
  [last_marker_end, scan_len) where last_marker_end = pos1 + 13*Ncols - 8:
    inverted phase (even=0xff, odd=0x00) if Ncols odd, normal if Ncols even.
  -- confirmed pure (no hidden structure besides mat_byte) across the entire
     234..778 range of 1447's scan.

### NOTE on Ncols<=3 (degenerate cases of the same formula)
For Ncols=2: "interior k=2,3" only has k=2 (k=3 doesn't exist). last_two_span
= span of cols (1,2) = ALL columns = prefix_span(2) = GLOBAL_span. For
Ncols<=3 there isn't enough variation in the tested cases to separate
"GLOBAL" vs "lz_max[Ncols-2]" vs "prefix_span(Ncols)" vs "last_two_span" --
they all numerically coincide for 1390/1356/1354/1352/1439/1441. The code
below branches explicitly: Ncols<=3 uses the ORIGINAL (lz_max[Ncols-2]-based
PAIR_Ncols + GLOBAL-based PAIR_{Ncols+1}) formula; Ncols>=4 uses the NEW
(GLOBAL-based PAIR_4 w/ last_two_span + sliding lz_max[1+j]-based PAIRs w/
N[2+j] own-height) formula described above.

Scope: each column must be a single contiguous lz-run (no gaps within a
column). Gaps BETWEEN columns not yet integrated into this model. Ncols=2..5
tested; Ncols>=6 untested (scan_len/PAIR1_pos formula for Ncols>=6 is a
guess -- see above).
"""

from h3_k2_generator import mvf, mvf_neg, n1_first, pair_block, decode_blob


def generate_columns_scan(lx1, ly1, columns, mat_counter):
    """
    columns: list of (lz_min_i, N_i) for i=1..Ncols (each a contiguous run,
    lz_max_i = lz_min_i + N_i - 1). Column i sits at lx = lx1 + (i-1), ly=ly1.
    """
    Ncols = len(columns)
    lz_min = [c[0] for c in columns]
    N = [c[1] for c in columns]
    lz_max = [lz_min[i] + N[i] - 1 for i in range(Ncols)]

    correction = 0 if Ncols == 2 else 1

    jump = 4 if Ncols >= 5 else 0

    pos1 = 2 * n1_first(lx1, ly1, lz_max[0]) + 7
    scan_len = 689 + 17 * Ncols + jump
    last_marker_end = pos1 + 13 * Ncols - 8

    scan = bytearray(scan_len)
    for i in range(0, pos1):
        scan[i] = 0x00 if i % 2 == 0 else 0xff
    for i in range(last_marker_end, scan_len):
        if Ncols % 2 == 1:
            scan[i] = 0xff if i % 2 == 0 else 0x00
        else:
            scan[i] = 0x00 if i % 2 == 0 else 0xff

    # markers
    marker1_val = mvf(lx1, ly1, lz_min[0])
    scan[pos1:pos1 + 5] = bytes([marker1_val, 0x01, 0x02, N[0] - 1, 0x00])
    if Ncols > 1:
        scan[pos1 + 5:pos1 + 13] = bytes([0xff, 0x00] * 4)

    for k in range(2, Ncols + 1):
        p = pos1 + 13 * (k - 1)
        val = (mvf_neg(lx1, ly1, lz_max[k - 2]) + 0xa4 + correction) % 256
        scan[p:p + 5] = bytes([val, 0x01, 0x02, N[k - 1] - 1, 0x00])
        if k < Ncols:
            scan[p + 5:p + 13] = bytes([0xff, 0x00] * 4)

    # PAIRs
    PAIR1_pos = 505 + 3 * Ncols + jump // 2
    p1_val_a = (mvf(lx1, ly1, lz_min[0]) + 19) % 256
    scan[PAIR1_pos:PAIR1_pos + 16] = pair_block(p1_val_a, 0x20 - (N[0] - 1), N[0])

    prefix_lz_min = [lz_min[0]]
    prefix_lz_max = [lz_max[0]]
    for k in range(2, Ncols + 1):
        prefix_lz_min.append(min(prefix_lz_min[-1], lz_min[k - 1]))
        prefix_lz_max.append(max(prefix_lz_max[-1], lz_max[k - 1]))
    GLOBAL_lz_max = prefix_lz_max[-1]
    Nlast = N[Ncols - 1]
    last_two_min = min(lz_min[Ncols - 2], lz_min[Ncols - 1])
    last_two_max = max(lz_max[Ncols - 2], lz_max[Ncols - 1])
    last_two_span = last_two_max - last_two_min + 1

    if Ncols <= 3:
        for k in range(2, Ncols + 1):
            span = prefix_lz_max[k - 1] - prefix_lz_min[k - 1] + 1
            val_a = (mvf_neg(lx1, ly1, lz_max[k - 2]) + 128 + correction) % 256
            p = PAIR1_pos + 24 * (k - 1)
            scan[p:p + 16] = pair_block(val_a, 0x20 - (span - 1), span)
        val_a = (mvf_neg(lx1, ly1, GLOBAL_lz_max) + 128 + correction) % 256
        p = PAIR1_pos + 24 * Ncols
        scan[p:p + 16] = pair_block(val_a, 0x20 - (Nlast - 1), Nlast)
    else:
        # interior k=2,3 (fixed slots, regardless of Ncols)
        for k in (2, 3):
            span = prefix_lz_max[k - 1] - prefix_lz_min[k - 1] + 1
            val_a = (mvf_neg(lx1, ly1, lz_max[k - 2]) + 128 + correction) % 256
            p = PAIR1_pos + 24 * (k - 1)
            scan[p:p + 16] = pair_block(val_a, 0x20 - (span - 1), span)

        # PAIR_4 = GLOBAL-based + last_two_span
        val_a = (mvf_neg(lx1, ly1, GLOBAL_lz_max) + 128 + correction) % 256
        p = PAIR1_pos + 24 * 3
        scan[p:p + 16] = pair_block(val_a, 0x20 - (last_two_span - 1), last_two_span)

        # sliding PAIR_{4+j} for j=1..(Ncols-3): lz_max[1+j]-based + N[2+j]
        for j in range(1, Ncols - 2):
            val_a = (mvf_neg(lx1, ly1, lz_max[1 + j]) + 128 + correction) % 256
            span = N[2 + j]
            p = PAIR1_pos + 24 * (3 + j)
            scan[p:p + 16] = pair_block(val_a, 0x20 - (span - 1), span)

    mat_byte_pos = PAIR1_pos - 168
    scan[mat_byte_pos] = mat_counter & 0xff

    return bytes(scan)


if __name__ == "__main__":
    tests = {
        "1390 (K=2)": ("+bYU+zsDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgGzAEXFAQ"
                       "IADQAPAgB5H3KWAIIOAgCTUQECfn5+AgAfCAAEIgCToQEDfn5+AwAeCAAGGABzAX5+fgEAIAgABBgADwIA"
                       "eYByAgAAAMdoaQ8D8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB", [(14, 2), (13, 1)]),
        "1356 (K=2)": ("+bYU+zsDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT0BAgCzAEXHAQ"
                       "IBDQAPAgB5H3GWAIIOAgCTUAEBfn5+AQAgCAAEIgCTowECfn5+AgAfCAAEGAATohAADBgADwIAeYBxAgAA"
                       "AMdoaQ8D8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB", [(13, 1), (13, 2)]),
        "1354 (K=2)": ("+bYU+zsDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT0BAgGzABjGDQ"
                       "APAgB5FXGjAA8CAIuTUAECfn5+AgAfCAAErgATohAADxgAFQ8CAHmAcQIAAADHaGkPA/ANAERlYnVnMQAA"
                       "AaUCsMsAAAAAaGNDYXJib24CAQ==", [(13, 2), (13, 2)]),
        "1352 (K=2)": ("+bYU+zsDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT0BAgSzAEXDAQ"
                       "IADQAPAgB5H3KWAIIOAgCTUAEFfn5+BQAcCAAEIgATnxAADhgAcwF+fn4BACAIAAQwAA8CAHmAcgIAAADH"
                       "aGkPA/ANAERlYnVnMQAAAaUCsMsAAAAAaGNDYXJib24CAQ==", [(13, 5), (13, 1)]),
        "1433 (N=3)": ("+bYU+0wDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzAB/HDQAGDwIAbxWopgAPAgCLk1EBAX5+fgEAIAgABK4AE6MQAA8YAC0PAgBvgKgCAAAAx2hpIAPwDQBEZWJ1ZzEAAAHGD7Z0AAAAAGhjQWxMaVBhAgE=", [(14, 1), (14, 1), (14, 1)]),
        "1435 (N=3)": ("+bYU+0wDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzAB/HDQAGDwIAbxWopgAPAgCLk1EBAX5+fgEAIAgABK4AE6MQAA8YAC0PAgBvgKgCAAAAx2hpIAPwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=", [(14, 1), (14, 1), (14, 1)]),
        "1437 (N=4)": ("+bYU+10DAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzAB/HDQATDwIAZRXfqQAPAgCLk1EBAX5+fgEAIAgABK4AE6MQAA8YAEUPAgBlgN8CAAAAx2hpMQPwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=", [(14, 1), (14, 1), (14, 1), (14, 1)]),
        "1439 (N=3,col3 N=2)": ("+bYU+0wDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzABvHDQAVARoADwIAbx+njAB4DwIACZNRAQF+fn4BACAIAAQsABOjEAAOGABzAn5+fgIAHwgABDAAE6IQAAwYAA8CAG+ApwIAAADHaGkgA/ANAERlYnVnMQAAAaUCsMsAAAAAaGNDYXJib24CAQ==", [(14, 1), (14, 1), (14, 2)]),
        "1441 (N=3,col2 N=2)": ("+bYU+0wDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzAEXHAQIBDQAYxhoADwIAbxWomQAPAgCLk1EBAX5+fgEAIAgABK4Ak6MBAn5+fgIAHwgABBgAE6IQAA4YAA9IAAMPAgBvgKgCAAAAx2hpIAPwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=", [(14, 1), (14, 2), (14, 1)]),
        "1443 (N=4,col2 N=2)": ("+bYU+10DAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzAEXHAQIBDQAbxhoABicADwIAZRXfnAAPAgCLk1EBAX5+fgEAIAgABK4Ak6MBAn5+fgIAHwgABBgAE6IQAA4YAA9IAAUPGAADDwIAZYDfAgAAAMdoaTED8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB", [(14, 1), (14, 2), (14, 1), (14, 1)]),
        "1445 (N=4,col3 N=2)": ("+bYU+10DAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzABvHDQAVARoAGMYaAA8CAGUV348ADwIAi5NRAQF+fn4BACAIAASuABOjEAAOGABzAn5+fgIAHwgABDAAE6IQAA4YAA9gAAMPAgBlgN8CAAAAx2hpMQPwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=", [(14, 1), (14, 1), (14, 2), (14, 1)]),
        "1450 (Ncols=5 baseline)": ("+bYU+3IDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzAB/HDQAgDwIAXRUWrgAPAgCLk1EBAX5+fgEAIAgABK4AE6MQAA8YAF0PAgBdgBYCAAAAx2hpRgPwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=", [(14, 1), (14, 1), (14, 1), (14, 1), (14, 1)]),
        "1447 (Ncols=5,col2 N=2)": ("+bYU+3IDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzAEXHAQIBDQAbxhoACScABg0ADwIAXRUWoQAPAgCLk1EBAX5+fgEAIAgABK4Ak6MBAn5+fgIAHwgABBgAE6IQAA4YAA9IAAUPGAAbDwIAXYAWAgAAAMdoaUYD8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB", [(14, 1), (14, 2), (14, 1), (14, 1), (14, 1)]),
        "1452 (Ncols=6 baseline)": ("+bYU+4MDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcRT4BAgCzAB/HDQAtDwIAUxVNsQAPAgCLk1EBAX5+fgEAIAgABK4AE6MQAA8YAHUPAgBTgE0CAAAAx2hpVwPwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=", [(14, 1)] * 6),
    }

    for name, (b64, columns) in tests.items():
        dec = decode_blob(b64)
        idx = dec.find(b'Debug1')
        mat_start = idx - 13
        header = dec[:64]
        real_scan = dec[64:mat_start]
        mat = dec[mat_start:]
        mat_counter = int.from_bytes(mat[:4], 'little')

        gen_scan = generate_columns_scan(16, 13, columns, mat_counter)

        scan_match = gen_scan == real_scan
        full_match = (header + gen_scan + mat) == dec
        print(f"{name}: scan MATCH={scan_match}  full_dec MATCH={full_match}")
        if not scan_match:
            for i, (a, b) in enumerate(zip(real_scan, gen_scan)):
                if a != b:
                    print(f"  diff at {i}: real={a:02x} gen={b:02x}")
            if len(real_scan) != len(gen_scan):
                print(f"  len real={len(real_scan)} gen={len(gen_scan)}")
