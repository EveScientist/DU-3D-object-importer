"""
h3 scan generator for a column-major NxM RECTANGLE of cells, all N=1
(each cell a single voxel at the same lz, i.e. a flat face on the
ly-lz... no wait: lx varies across "columns" (Ncols), ly varies within
each column ("Yextent" rows), all cells at the same lz.

Visit order: for col in 0..Ncols-1 (lx = lx1+col): for row in 0..Yextent-1
(ly = ly1+row), at fixed lz. anchor = (lx1, ly1, lz) = cell (col=0,row=0).

Validated 9/9 byte-exact (scan AND full dec = header+scan+mat):
  1456 (1x2), 1458 (1x3), 1454 (2x2), 1460 (2x3), 1462 (3x2), 1464 (3x3),
  1466 (5x2), 1468 (2x5), 1470 (4x4)
1470 (4x4 square) is the first square grid >3x3 tested -- byte-exact on
first try, NO new corrections needed. This is the first realistic
hollow-cube-face-sized grid validated.
1466 (Ncols=5, Yextent=2) confirms the bilinear formula needs NO "jump"
correction for Ncols>=5 at Yextent>=2 -- the jump=4 term in the single-row
(Yextent=1) model appears to be specific to Yextent==1.

1468 (Ncols=2, Yextent=5) revealed a SECOND correction, generalizing the
old Ncols==1-specific -2/-4 hack:
  if Yextent > 2*Ncols: PAIR1_pos -= 2; scan_len -= 4
This is a pure positional shift -- the PAIR-region content (groups+gaps)
is byte-identical, just starting 2 bytes earlier, and trailing background
is 2 bytes shorter. Consistent with ALL 8 data points: (1,2)no, (1,3)yes,
(2,2)no, (2,3)no, (2,5)yes, (3,2)no, (3,3)no, (5,2)no.

### The model

Let anchor = (lx1,ly1,lz). pos1 = 2*n1_first(lx1,ly1,lz) + 7 (same formula
as the single-row model, using the anchor cell -- col1's only lz value
since N=1 everywhere here).

scan_len(Ncols,Yextent)  = 681 + 13*Ncols*Yextent + 4*Ncols + 8*Yextent
PAIR1_pos(Ncols,Yextent) = 505 + Ncols*(5*Yextent - 2)
  [Ncols >= 2; both reduce EXACTLY to the single-row formulas
   (689+17*Ncols, 505+3*Ncols) at Yextent=1. Ncols==1 has a small,
   poorly-understood -2/-4 correction at Yextent>=3 -- see NOTE below.]

mat_byte_pos = PAIR1_pos - 168  (unchanged from single-row)

MARKERS: Ncols groups of Yextent markers (5 bytes each: [val,0x01,0x02,
0x00,0x00], N-1=0 since N=1), with an 8-byte [0xff,0x00]*4 gap between
consecutive column-groups (none for Ncols==1). Starting at pos1:
  col 0 group:  marker[0] = mvf(anchor)                         (own)
                 marker[1..Yextent-1] = mvf_neg(lx1,ly1,lz+1)     (Y-step,
                 CONSTANT, repeated -- confirmed up to Yextent=3)
  col i>=1 group: marker[0] = (234 - 35*Yextent) % 256           (X-step,
                 CONSTANT regardless of which column-transition or Ncols --
                 confirmed for Ncols=2,3 x Yextent=2,3)
                 marker[1..Yextent-1] = mvf_neg(lx1,ly1,lz+1)     (Y-step,
                 same as col0)

GROUPS: Ncols+1 groups of (Yextent+1) halfblocks (8 bytes each:
[val,0x01,0x01,0x7e,0x7e,0x7e,0x01,0x00]), with an 8-byte [0xff,0x00]*4
gap between consecutive groups. Starting at PAIR1_pos:
  GroupA = [mvf(anchor)+19] + [0x20]*Yextent
  GroupB = [(mvf_neg(anchor)+164-35*Yextent) % 256] + [0x20]*Yextent
  groups = [GroupA] + [GroupB]*Ncols   (G[1..Ncols] all == GroupB, for ALL
  Ncols>=1 -- no special case needed; confirmed for Ncols=1,2,3)

BACKGROUND:
  [0, pos1):                 even=0x00, odd=0xff  (position-0 baseline, ALWAYS)
  [last_marker_end, scan_len): depends on parity of Ncols*Yextent --
    if even: same as position-0 baseline (even=0x00, odd=0xff)
    if odd:  flipped (even=0xff, odd=0x00)
  where last_marker_end = pos1 + 5*Ncols*Yextent + 8*(Ncols-1)
  Inter-group gaps (both marker-groups and PAIR-groups) are the literal
  8-byte sequence [0xff,0x00,0xff,0x00,0xff,0x00,0xff,0x00], independent
  of absolute position parity (same as the single-row model's explicit
  marker gaps).

NOTE on Ncols==1: the scan_len/PAIR1_pos formulas above are exact at
Yextent==2 (727/513) but for Yextent==3 the REAL values (744/516) are
each 2 less than the formula predicts for PAIR1_pos (518) and 4 less for
scan_len (748) -- i.e. PAIR1_pos is -2 and trailing-background is ALSO -2.
Patched empirically below for Ncols==1,Yextent>=3 (untested beyond
Yextent==3; Ncols==1 is a degenerate "1-wide face" unlikely to matter for
hollow-cube generation).

Scope: Ncols,Yextent >= 1, all cells N=1 (single voxel), same lz for every
cell. Non-uniform N (per-cell height>1) and Ncols>=5/Yextent>=4 combinations
are UNTESTED.

### N>1 generalization (test 1474: Ncols=1, Yextent=2, N=2)

1474 is the "left/right face" case: Ncols=1 (single column), Yextent=2
(repeated markers), N=2 (each marker covers a run of 2 voxels along lz).
Confirmed byte-exact. All N-dependence is confined to VALUES -- scan_len,
PAIR1_pos, marker_region_span, last_marker_end are all UNCHANGED by N
(same formulas as N=1).

  marker: [val, 0x01, 0x02, N-1, 0x00]   (N-1 byte, was hardcoded 0 for N=1)
  own_val   = mvf(anchor)                          UNCHANGED by N
  ystep_val = mvf_neg(lx1,ly1,lz+N) = (mvf_neg(anchor) - N) % 256
  xstep_val = (234 - 35*Yextent - (N-1)) % 256     N-1 term is a GUESS,
              untested since 1474 has Ncols=1 (no X-step marker exercised)
  groupA_val = (mvf(anchor) + 19) % 256            UNCHANGED by N
  groupB_val = (mvf_neg(anchor) + 164 - 35*Yextent - (N-1)) % 256
  halfblock(val) = [val, 0x01, N, 0x7e, 0x7e, 0x7e, N, 0x00]   (c=N, was
                   hardcoded c=1 for N=1)
  default halfblock value = (0x20 - (N-1)) % 256   (0x20 for N=1, 0x1f for N=2)

For N=1 all of the above reduce exactly to the original formulas.

### "Extra block" in intermediate groups when Ncols>=2 AND N>=2
(tests 1476: Ncols=2,Yextent=2,N=2 and 1478: Ncols=2,Yextent=2,N=3)

groups = [GroupA] + [GroupB]*Ncols (Ncols+1 groups total, as before).
GroupA (index 0) and the LAST GroupB (index Ncols) are NEVER extra:
  group = halfblock(first_val) + halfblock(default_val)*Yextent
Every INTERMEDIATE GroupB (1 <= index <= Ncols-1) gets an EXTRA 16-byte
block inserted (replacing one default halfblock, net +8 bytes) when N>=2:
  group = halfblock(groupB_val) + EXTRA + halfblock(default_val)*(Yextent-1)
  EXTRA = [default_val,0x01,0x00,0x7e,0x7e,0x7e,0x00,0x00]
        + [(N-2)&0xff,0x01,0x00,0x7e,0x7e,0x7e,0x00,0x00]
For Ncols==1 there are no intermediate groups (matches 1474: no extra even
at N=2). extra_scan_len = 8*(Ncols-1) if N>=2 else 0 -- confirmed identical
for N=2 and N=3 (does not scale further with N). UNTESTED for Ncols>=3
(predicts multiple intermediate groups, each +8) and for combos with the
"Yextent > 2*Ncols" PAIR1_pos correction.
"""

from h3_k2_generator import mvf, mvf_neg, n1_first, decode_blob


def generate_rectangle_scan(lx1, ly1, lz, Ncols, Yextent, N, mat_counter):
    pos1 = 2 * n1_first(lx1, ly1, lz) + 7

    extra_scan_len = 8 * (Ncols - 1) if N >= 2 else 0
    scan_len = 681 + 13 * Ncols * Yextent + 4 * Ncols + 8 * Yextent + extra_scan_len
    PAIR1_pos = 505 + Ncols * (5 * Yextent - 2)
    if Yextent > 2 * Ncols:
        PAIR1_pos -= 2
        scan_len -= 4

    marker_region_span = 5 * Ncols * Yextent + 8 * (Ncols - 1)
    last_marker_end = pos1 + marker_region_span

    scan = bytearray(scan_len)

    # background
    for i in range(0, pos1):
        scan[i] = 0x00 if i % 2 == 0 else 0xff
    flip = (Ncols * Yextent) % 2 == 1
    for i in range(last_marker_end, scan_len):
        if flip:
            scan[i] = 0xff if i % 2 == 0 else 0x00
        else:
            scan[i] = 0x00 if i % 2 == 0 else 0xff

    # markers
    own_val = mvf(lx1, ly1, lz)
    ystep_val = mvf_neg(lx1, ly1, lz + N)
    xstep_val = (234 - 35 * Yextent - (N - 1)) % 256
    nminus1 = (N - 1) & 0xff

    p = pos1
    for col in range(Ncols):
        first_val = own_val if col == 0 else xstep_val
        scan[p:p + 5] = bytes([first_val, 0x01, 0x02, nminus1, 0x00])
        p += 5
        for _ in range(Yextent - 1):
            scan[p:p + 5] = bytes([ystep_val, 0x01, 0x02, nminus1, 0x00])
            p += 5
        if col < Ncols - 1:
            scan[p:p + 8] = bytes([0xff, 0x00] * 4)
            p += 8

    # groups
    groupA_val = (mvf(lx1, ly1, lz) + 19) % 256
    groupB_val = (mvf_neg(lx1, ly1, lz) + 164 - 35 * Yextent - (N - 1)) % 256
    default_val = (0x20 - (N - 1)) % 256

    def halfblock(val):
        return bytes([val, 0x01, N & 0xff, 0x7e, 0x7e, 0x7e, N & 0xff, 0x00])

    def group_bytes(first_val):
        return halfblock(first_val) + halfblock(default_val) * Yextent

    def group_bytes_extra(first_val):
        extra = bytes([default_val, 0x01, 0x00, 0x7e, 0x7e, 0x7e, 0x00, 0x00,
                        (N - 2) & 0xff, 0x01, 0x00, 0x7e, 0x7e, 0x7e, 0x00, 0x00])
        return halfblock(first_val) + extra + halfblock(default_val) * (Yextent - 1)

    groups = [group_bytes(groupA_val)]
    for i in range(1, Ncols + 1):
        if N >= 2 and i != Ncols:
            groups.append(group_bytes_extra(groupB_val))
        else:
            groups.append(group_bytes(groupB_val))

    p = PAIR1_pos
    for i, g in enumerate(groups):
        scan[p:p + len(g)] = g
        p += len(g)
        if i < len(groups) - 1:
            scan[p:p + 8] = bytes([0xff, 0x00] * 4)
            p += 8

    mat_byte_pos = PAIR1_pos - 168
    scan[mat_byte_pos] = mat_counter & 0xff

    return bytes(scan)


if __name__ == "__main__":
    tests = {
        "1456 (1x2)": ("+bYU+z8DAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcYD4BAgAAIQUAD7oAix8XWAGUm1EBAX5+fgEAIAgABF4BG4AYAAQoAAQgAA8CAIOAFwIAAADHaGkTA/ANAERlYnVnMQAAAaUCsMsAAAAAaGNDYXJib24CAQ==", 16, 13, 14, 1, 2, 1),
        "1458 (1x3)": ("+bYU+1ADAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcZT4BAgAAIQUAD78AiR/0WwGUn1EBAX5+fgEAIAgABARkAR9dIAAEBDgABCgADwIAgYD0AgAAAMdoaSQD8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB", 16, 13, 14, 1, 3, 1),
        "1454 (2x2)": ("+bYU+10DAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcYD4BAgAAIQUABLoAEKQNAAkSAA8CAHkfTmABlJtRAQF+fn4BACAIAARMARuAGAAEKAAPIAAVDwIAeYBOAgAAAMdoaTED8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB", 16, 13, 14, 2, 2, 1),
        "1460 (2x3)": ("+bYU+38DAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcZT4BAgAAIQUABL8AFYESAAEcAAQXAA8CAHkfK2oBlJ9RAQF+fn4BACAIAAQEVAEfXSAABAQ4AA8oAB0PAgB5gCsCAAAAx2hpUwPwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=", 16, 13, 14, 2, 3, 1),
        "1462 (3x2)": ("+bYU+3sDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcYD4BAgAAIQUABLoAEKQNAA8SAAwPAgBvH4VoAZSbUQEBfn5+AQAgCAAEQgEbgBgABCgADyAANQ8CAG+AhQIAAADHaGlPA/ANAERlYnVnMQAAAaUCsMsAAAAAaGNDYXJib24CAQ==", 16, 13, 14, 3, 2, 1),
        "1464 (3x3)": ("+bYU+6oDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcZT4BAgAAIQUABL8AFYESAAEcAA8XAAwPAgBvH2J3AZSfUQEBfn5+AQAgCAAEBEoBH10gAAQEOAAPKABFDwIAb4BiAgAAAMdoaX4D8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB", 16, 13, 14, 3, 3, 1),
        "1466 (5x2)": ("+bYU+7cDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcYD4BAgAAIQUABLoAEKQNAA8SADAPAgBbH/N4AZSbUQEBfn5+AQAgCAAELgEbgBgABCgADyAAdQ8CAFuA8wIAAADHaGmLA/ANAERlYnVnMQAAAaUCsMsAAAAAaGNDYXJib24CAQ==", 16, 13, 14, 5, 2, 1),
        "1468 (2x5)": ("+bYU+78DAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcbz4BAgAAIQUAAATJAB87HAAAATAABCEADwIAdx/lfAGUn1EBAX5+fgEAIAgAFARiAR8XMAAUBFgADzgALQ8CAHeA5QIAAADHaGmTA/ANAERlYnVnMQAAAaUCsMsAAAAAaGNDYXJib24CAQ==", 16, 13, 14, 2, 5, 1),
        "1470 (4x4)": ("+bYU+xEEAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcaj4BAgAAIQUABMQAGl4XAAEmAA8cAC0PAgBlH3aYAZSfUQEBfn5+AQAgCAAMBEgBHzooAAwESAAPMACFDwIAZYB2AgAAAMdoaeUD8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB", 16, 13, 14, 4, 4, 1),
        "1474 (1x2,N=2)": ("+bYU+z8DAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcYD4BAgEAIAUAD7oAix8WWAGUm1EBAn5+fgIAHwgABF4BG38YAAQoAAQgAA8CAIOAFgIAAADHaGkTA/ANAERlYnVnMQAAAaUCsMsAAAAAaGNDYXJib24CAQ==", 16, 13, 14, 1, 2, 2),
        "1476 (2x2,N=2)": ("+bYU+2UDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcYD4BAgEAIAUABLoAEKMNAAkSAA8CAHkfTWABlJtRAQJ+fn4CAB8IAARMARV/GABzAH5+fgAAAAgABDAADigAClAABCAADwIAeYBNAgAAAMdoaTkD8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB", 16, 13, 14, 2, 2, 2),
        "1478 (2x2,N=3)": ("+bYU+2UDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcYD4BAgIAHwUABLoAEKINAAkSAA8CAHkfTGABlJtRAQN+fn4DAB4IAARMARV+GABzAH5+fgAAAQgABDAADigAClAABCAADwIAeYBMAgAAAMdoaTkD8A0ARGVidWcxAAABpQKwywAAAABoY0NhcmJvbgIB", 16, 13, 14, 2, 2, 3),
        "1480 (3x2,N=2)": ("+bYU+4sDAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCcYD4BAgEAIAUABLoAEKMNAA8SAAwPAgBvH4RoAZSbUQECfn5+AgAfCAAEQgEVfxgAcwB+fn4AAAAIAAQwAA8oACcKeAAESAAPAgBvgIQCAAAAx2hpXwPwDQBEZWJ1ZzEAAAGlArDLAAAAAGhjQ2FyYm9uAgE=", 16, 13, 14, 3, 2, 2),
    }

    for name, (b64, lx1, ly1, lz, Ncols, Yextent, N) in tests.items():
        dec = decode_blob(b64)
        idx = dec.find(b'Debug1')
        mat_start = idx - 13
        header = dec[:64]
        real_scan = dec[64:mat_start]
        mat = dec[mat_start:]
        mat_counter = int.from_bytes(mat[:4], 'little')

        gen_scan = generate_rectangle_scan(lx1, ly1, lz, Ncols, Yextent, N, mat_counter)

        scan_match = gen_scan == real_scan
        full_match = (header + gen_scan + mat) == dec
        print(f"{name}: scan MATCH={scan_match}  full_dec MATCH={full_match}")
        if not scan_match:
            if len(real_scan) != len(gen_scan):
                print(f"  len real={len(real_scan)} gen={len(gen_scan)}")
            for i, (a, b) in enumerate(zip(real_scan, gen_scan)):
                if a != b:
                    print(f"  diff at {i}: real={a:02x} gen={b:02x}")
