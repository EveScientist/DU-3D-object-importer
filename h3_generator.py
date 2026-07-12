"""
h3_generator.py — unified h3 chunk scan generator.

Built fresh from the validated formulas documented in h3_lowrow_scanners.md.
Does NOT import or depend on the legacy per-quadrant files
(h3_lowrow_212_generator.py, h3_lowrow_222_generator.py, etc.) — those stay on
disk as historical reference only, per feedback_build_properly.md. Where this
module's base (non-spanning) formulas match those files' validated logic, that
logic has been reimplemented here directly rather than imported, so this module
has no runtime dependency on the legacy code.

PHASE 1 SCOPE: base Nc/Ye single-direction formulas for all 4 (cx,cy) roles at
cz=2, the cz=1 derivation, and X/Y/Z-axis spanning (both directions). Multi-z,
gaps, offsets, far-edges, the 3-axis corner, h4/h5/h6 tiling, and S/M/L
core-size correction are documented in h3_lowrow_scanners.md but NOT yet
implemented here — see that file for the formulas when extending this module.

Coordinate conventions (consistent with h3_lowrow_scanners.md throughout):
  lx_local = game_x + 0.5   (positive integer for positive-x half)
  ly_signed = game_y + 0.5, NEGATIVE for negative-y half
  lz = game_z - 0.5 (or abs(game_z) - 0.5 for the cz=1/cz=2 split)

Role naming: (cx,cy) in {1,2}x{1,2} identifies which of the 4 chunks around
the origin this is, e.g. (2,1) = pos-x main / neg-y. cz in {1,2}: cz=1 is the
lz=0 special case, cz=2 is everything else (derived from cz=2 by a simple
+32/-32 correction — see cz1_from_cz2 below).
"""

import struct
import lz4.block

_EFF_LZ = 14  # hardcoded reference lz used by groupB/ystep formulas (established
              # constant throughout h3_lowrow_scanners.md; these two values never
              # vary with the actual lz of the content)

MAT_TAIL = bytes.fromhex(
    "00c768690900000000446562756731000001a502b0cb000000006863436172626f6e0201"
)
assert len(MAT_TAIL) == 36


# ---------------------------------------------------------------------------
# Byte primitives
# ---------------------------------------------------------------------------

def _marker(val, N=1):
    """5-byte marker: [val, 0x01, 0x02, N-1, 0x00]."""
    return bytes([val & 0xff, 0x01, 0x02, (N - 1) & 0xff, 0x00])


def _halfblock(val, N=1):
    """8-byte half-block: [val, 0x01, N, 0x7e, 0x7e, 0x7e, N, 0x00]."""
    return bytes([val & 0xff, 0x01, N & 0xff, 0x7e, 0x7e, 0x7e, N & 0xff, 0x00])


def _fill_background(scan, start, end, flip=False):
    """Fill scan[start:end] with the alternating background pattern.
    flip=False: even=0x00, odd=0xff. flip=True: even=0xff, odd=0x00."""
    for i in range(start, end):
        if flip:
            scan[i] = 0xff if i % 2 == 0 else 0x00
        else:
            scan[i] = 0x00 if i % 2 == 0 else 0xff


def n1_first_212(lx, ly_signed, lz):
    """n1_first formula shared by all 4 roles (uses signed ly)."""
    return 4 + (153 * lx + 4 * ly_signed + lz) // 31


# ---------------------------------------------------------------------------
# Base (single-direction) generators, cz=2, Nc=1 family role: (2,1,2) pos-x main
# ---------------------------------------------------------------------------

def generate_212_scan(Ncols, mat_counter, lz=14, Yextent=29, N=1):
    """(2,1,2): pos-x main role. Ncols x Yextent plate, ly_signed=-1..-Yextent."""
    assert N == 1, "only N=1 implemented in Phase 1"

    pos1 = 2 * n1_first_212(1, -(Yextent + 2), lz) + 11
    marker_span = 5 * Ncols * Yextent
    last_marker_end = pos1 + marker_span

    sep = 2 * (n1_first_212(1, -(Yextent - 2), lz) - 5)
    groups_total = (Ncols + 1) * (Yextent + 1) * 8 + sep

    W = sum(1 for k in range(3, Ncols + 1)
            if (64 + 55 * k) % 256 < (64 + 55 * (k - 1)) % 256)
    gap1 = pos1 + 297 - 10 * (Ncols - 1) + 2 * W
    gap2 = gap1 - (pos1 - 9)

    groups_start = last_marker_end + gap1
    mat_byte_pos = groups_start - pos1 + 9
    scan_len = groups_start + groups_total + gap2

    groupB_val = (212 - _EFF_LZ - 35 * Yextent - (N - 1)) % 256
    own_val = (groupB_val - 162) % 256
    groupA_val = (own_val + 19) % 256
    ystep_val = (304 - _EFF_LZ - N) % 256
    xstep_val = (234 - 35 * Yextent - (N - 1)) % 256

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    flip = (Ncols * Yextent) % 2 == 1
    _fill_background(scan, last_marker_end, scan_len, flip)

    p = pos1
    for col in range(Ncols):
        first_val = own_val if col == 0 else xstep_val
        scan[p:p + 5] = _marker(first_val)
        p += 5
        for _ in range(Yextent - 1):
            scan[p:p + 5] = _marker(ystep_val)
            p += 5
    assert p == last_marker_end

    def group_bytes(first_val):
        return _halfblock(first_val) + _halfblock(0x20 - (N - 1)) * Yextent

    p = groups_start
    scan[p:p + (Yextent + 1) * 8] = group_bytes(groupA_val)
    p += (Yextent + 1) * 8
    p += sep
    for _ in range(Ncols):
        scan[p:p + (Yextent + 1) * 8] = group_bytes(groupB_val)
        p += (Yextent + 1) * 8
    assert p == groups_start + groups_total

    scan[mat_byte_pos] = mat_counter & 0xff
    return bytes(scan)


def mc_212(Ncols):
    return 512 + (64 + 55 * Ncols) % 256


# (1,1,2) boundary role: pos-x voxels exist, this encodes the neg-x boundary
def generate_112_scan(mat_counter, lz=14, Yextent=29, N=1):
    assert N == 1
    pos1_212 = 2 * n1_first_212(1, -(Yextent + 2), lz) + 11
    pos1 = pos1_212 + 306
    mat_byte_pos = pos1 + 5 * Yextent
    sep = 2 * (n1_first_212(1, -(Yextent - 2), lz) - 5)
    groups_total = 2 * (Yextent + 1) * 8 + sep
    groups_start = 2 * pos1_212 + 5 * Yextent + 603
    if (Yextent == 2
            and n1_first_212(1, -(Yextent + 2), lz) < n1_first_212(1, -(Yextent + 1), lz)):
        groups_start += 2
    scan_len = groups_start + groups_total

    groupB_val = (212 - _EFF_LZ - 35 * Yextent - (N - 1)) % 256
    own_val_212 = (groupB_val - 162) % 256
    own_val = (own_val_212 + 32) % 256
    groupA_val = (own_val + 19) % 256
    ystep_val = (304 - _EFF_LZ - N) % 256

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    flip = Yextent % 2 == 1
    _fill_background(scan, mat_byte_pos, scan_len, flip)

    p = pos1
    scan[p:p + 5] = _marker(own_val)
    p += 5
    for _ in range(Yextent - 1):
        scan[p:p + 5] = _marker(ystep_val)
        p += 5

    scan[mat_byte_pos] = mat_counter & 0xff

    def group_bytes(first_val):
        return _halfblock(first_val) + _halfblock(0x20 - (N - 1)) * Yextent

    p = groups_start
    scan[p:p + (Yextent + 1) * 8] = group_bytes(groupA_val)
    p += (Yextent + 1) * 8
    p += sep
    scan[p:p + (Yextent + 1) * 8] = group_bytes(groupB_val)
    p += (Yextent + 1) * 8
    assert p == scan_len
    return bytes(scan)


MC_112 = 599


# (2,2,2): pos-x, pos-y. Ye-independent, tracks Ncols.
def generate_222_scan(Ncols, mat_counter):
    K = 160
    POS1 = 19
    OWN_VAL = 0xa1
    XSTEP_VAL = 0xc7
    GROUPA_VAL = 0xd7
    GROUPB_VAL = 0xc6

    def w(n):
        return sum(1 for k in range(2, n + 1)
                   if (K + 55 * k) % 256 < (K + 55 * (k - 1)) % 256)

    W = w(Ncols)
    new_wrap = W > w(Ncols - 1) if Ncols > 1 else False

    marker_span = 13 * Ncols - 8
    lme = POS1 + marker_span
    gap1 = 324 - 10 * (Ncols - 1) + 2 * W
    gap2 = gap1 - 10
    groups_total = 8 + 16 * Ncols
    gs = lme + gap1
    mat_byte_pos = gs - 10
    scan_len = gs + groups_total + gap2

    scan = bytearray(scan_len)
    _fill_background(scan, 0, POS1)
    flip_after = Ncols % 2 == 1
    _fill_background(scan, lme, scan_len, flip_after)

    p = POS1
    for col in range(Ncols):
        val = OWN_VAL if col == 0 else XSTEP_VAL
        scan[p:p + 5] = bytes([val, 0x01, 0x02, 0x00, 0x00])
        p += 5
        if col < Ncols - 1:
            flip_sep = (col + 1) % 2 == 1
            _fill_background(scan, p, p + 8, flip_sep)
            p += 8
    assert p == lme

    scan[mat_byte_pos] = mat_counter & 0xff

    p = gs
    scan[p:p + 8] = _halfblock(GROUPA_VAL)
    p += 8
    p += 8  # sep
    for col in range(Ncols):
        scan[p:p + 8] = _halfblock(GROUPB_VAL)
        p += 8
        if col < Ncols - 1:
            p += 8  # col_sep (background, already filled)
    assert p == gs + groups_total

    if new_wrap:
        b3_pos = gs + 8 + 8 + 3
        scan[b3_pos] = (0x7e + (mat_counter & 0xff)) & 0xff

    return bytes(scan)


def mc_222(Ncols):
    return 512 + (160 + 55 * Ncols) % 256


# (1,2,2): pos-x, pos-y boundary. Fully constant.
_OWN_VAL_122 = 0xc1
_GROUPA_VAL_122 = 0xf7
_GROUPB_VAL_122 = 0xc6
_POS1_122 = 325
_GS_122 = 654
_SCAN_LEN_122 = 686
_MAT_BYTE_POS_122 = 338
MC_122 = 695


def generate_122_scan(mat_counter=MC_122):
    scan = bytearray(_SCAN_LEN_122)
    _fill_background(scan, 0, _POS1_122)
    scan[_POS1_122:_POS1_122 + 5] = bytes([_OWN_VAL_122, 0x01, 0x02, 0x00, 0x00])
    lme = _POS1_122 + 5
    _fill_background(scan, lme, _SCAN_LEN_122, flip=True)
    scan[_MAT_BYTE_POS_122] = mat_counter & 0xff
    p = _GS_122
    scan[p:p + 8] = _halfblock(_GROUPA_VAL_122)
    p += 8
    p += 8
    scan[p:p + 8] = _halfblock(_GROUPB_VAL_122)
    return bytes(scan)


# ---------------------------------------------------------------------------
# Neg-x roles: chunk roles SWAP when negative-x voxels exist. (1,1,2) becomes
# the MAIN role (mirrors (2,1,2) for pos-x), (2,1,2) becomes the BOUNDARY role.
# (2,2,2)/(1,2,2) keep their own quadrant identity but encode neg-x's presence.
# ---------------------------------------------------------------------------

def generate_112_main_scan(Nc_neg, mat_counter, lz=14, Yextent=30, N=1):
    """(1,1,2): neg-x main role (mirrors (2,1,2) for pos-x)."""
    assert N == 1
    n1 = n1_first_212(1, -(Yextent + 2), lz)
    pos1 = 2 * n1 + 307
    lme = pos1 + Yextent * 5

    sep = 2 * (n1_first_212(1, -(Yextent - 2), lz) - 5)
    gap1 = 316 + sep
    gap2 = 8
    groups_total = (Nc_neg + 1) * (Yextent + 1) * 8 + sep

    gs = lme + gap1
    mat_byte_pos = lme + 8
    scan_len = gs + groups_total + gap2

    own_val = (158 - 35 * Yextent) % 256
    groupA_val = (own_val + 19) % 256
    groupB_val = (212 - _EFF_LZ - 35 * Yextent - (N - 1)) % 256
    ystep_val = (304 - _EFF_LZ - N) % 256

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    flip = (Nc_neg * Yextent) % 2 == 1
    _fill_background(scan, lme, scan_len, flip)

    p = pos1
    for col in range(Nc_neg):
        scan[p:p + 5] = _marker(own_val if col == 0 else ystep_val)
        p += 5
        for _ in range(Yextent - 1):
            scan[p:p + 5] = _marker(ystep_val)
            p += 5
    assert p == lme

    scan[mat_byte_pos] = mat_counter & 0xff

    def group_bytes(first_val):
        return _halfblock(first_val) + _halfblock(0x20 - (N - 1)) * Yextent

    p = gs
    scan[p:p + (Yextent + 1) * 8] = group_bytes(groupA_val)
    p += (Yextent + 1) * 8
    p += sep
    for _ in range(Nc_neg):
        scan[p:p + (Yextent + 1) * 8] = group_bytes(groupB_val)
        p += (Yextent + 1) * 8
    assert p == gs + groups_total
    return bytes(scan)


def mc_112_main(Nc_neg):
    return 512 + (198 + 55 * Nc_neg) % 256


def generate_212_bnd_scan(Nc_neg, mat_counter, lz=14, Yextent=30, N=1):
    """(2,1,2): neg-x boundary role (encodes pos-x boundary of neg-x voxels)."""
    assert N == 1
    n1 = n1_first_212(1, -(Yextent + 2), lz)
    pos1 = 2 * n1 + 1
    pos1_main = 2 * n1 + 11
    lme = pos1 + Yextent * 5

    gap1 = pos1_main + 297
    gap2 = 316

    sep = 2 * (n1_first_212(1, -(Yextent - 2), lz) - 5)
    groups_total = (Nc_neg + 1) * (Yextent + 1) * 8 + sep

    gs = lme + gap1
    mat_byte_pos = gs - max(pos1 - 9, 2)
    scan_len = gs + groups_total + gap2

    own_val = (126 - 35 * Yextent) % 256
    groupA_val = (own_val + 19) % 256
    groupB_val = (212 - _EFF_LZ - 35 * Yextent - (N - 1)) % 256
    ystep_val = (304 - _EFF_LZ - N) % 256

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    flip = (Nc_neg * Yextent) % 2 == 1
    _fill_background(scan, lme, scan_len, flip)

    p = pos1
    for col in range(Nc_neg):
        scan[p:p + 5] = _marker(own_val if col == 0 else ystep_val)
        p += 5
        for _ in range(Yextent - 1):
            scan[p:p + 5] = _marker(ystep_val)
            p += 5
    assert p == lme

    scan[mat_byte_pos] = mat_counter & 0xff

    def group_bytes(first_val):
        return _halfblock(first_val) + _halfblock(0x20 - (N - 1)) * Yextent

    p = gs
    scan[p:p + (Yextent + 1) * 8] = group_bytes(groupA_val)
    p += (Yextent + 1) * 8
    p += sep
    for _ in range(Nc_neg):
        scan[p:p + (Yextent + 1) * 8] = group_bytes(groupB_val)
        p += (Yextent + 1) * 8
    assert p == gs + groups_total
    return bytes(scan)


def mc_212_bnd(Nc_neg):
    return 512 + (230 + 55 * Nc_neg) % 256


def generate_222_neg_scan(Nc_neg=1, mat_counter=None, lz=14, Yextent=30, N=1):
    """(2,2,2): encodes neg-x voxels' positive-y boundary."""
    assert N == 1
    assert Nc_neg == 1, "only Nc_neg=1 validated"
    if mat_counter is None:
        mat_counter = mc_222_neg(Nc_neg)

    n1 = n1_first_212(1, -(Yextent + 2), lz)
    num_markers = 1 if n1 >= 9 else 2

    pos1 = 9
    lme = pos1 + num_markers * 5
    gap1 = 326
    gap2 = 324
    groups_total = 40
    gs = lme + gap1
    mat_byte_pos = gs - 2
    scan_len = gs + groups_total + gap2

    own_val = (161 + 55 * Nc_neg + 35 * (1 if n1 >= 9 else 0)) % 256
    ystep, groupA, groupB = 33, 14, 163

    scan = bytearray(scan_len)
    flip = num_markers % 2 == 1
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip)

    scan[pos1:pos1 + 5] = bytes([own_val, 0x01, 0x02, 0x00, 0x00])
    if num_markers == 2:
        scan[pos1 + 5:lme] = bytes([ystep, 0x01, 0x02, 0x00, 0x00])

    scan[mat_byte_pos] = mat_counter & 0xff

    p = gs
    scan[p:p + 8] = _halfblock(groupA); p += 8
    scan[p:p + 8] = _halfblock(0x20); p += 8
    p += 8  # sep
    scan[p:p + 8] = _halfblock(groupB); p += 8
    scan[p:p + 8] = _halfblock(0x20); p += 8
    assert p == gs + groups_total
    return bytes(scan)


def mc_222_neg(Nc_neg=1):
    return 512 + (70 + 55 * Nc_neg) % 256


def generate_122_neg_scan(Nc_neg=1, mat_counter=None, lz=14, Yextent=30, N=1):
    """(1,2,2): encodes neg-x/pos-y corner boundary."""
    assert N == 1
    assert Nc_neg == 1, "only Nc_neg=1 validated"
    if mat_counter is None:
        mat_counter = mc_122_neg(Nc_neg)

    n1 = n1_first_212(1, -(Yextent + 2), lz)
    num_markers = 1 if n1 >= 9 else 2

    own_val_222 = (161 + 55 * Nc_neg + 35 * (1 if n1 >= 9 else 0)) % 256
    own_val = (own_val_222 + 32) % 256

    pos1 = max(315, 2 * n1 + 299)
    lme = pos1 + num_markers * 5
    gap1 = 326
    gap2 = 18
    groups_total = 40
    gs = lme + gap1
    mat_byte_pos = lme + 18
    scan_len = gs + groups_total + gap2

    ystep, groupA, groupB = 33, 46, 163

    scan = bytearray(scan_len)
    flip = num_markers % 2 == 1
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip)

    scan[pos1:pos1 + 5] = bytes([own_val, 0x01, 0x02, 0x00, 0x00])
    if num_markers == 2:
        scan[pos1 + 5:lme] = bytes([ystep, 0x01, 0x02, 0x00, 0x00])

    scan[mat_byte_pos] = mat_counter & 0xff

    p = gs
    scan[p:p + 8] = _halfblock(groupA); p += 8
    scan[p:p + 8] = _halfblock(0x20); p += 8
    p += 8  # sep
    scan[p:p + 8] = _halfblock(groupB); p += 8
    scan[p:p + 8] = _halfblock(0x20); p += 8
    assert p == gs + groups_total
    return bytes(scan)


def mc_122_neg(Nc_neg=1):
    return mc_222_neg(Nc_neg) - 32


# ---------------------------------------------------------------------------
# cz=1 derivation — cz=1 ALWAYS represents exactly lz=0, using a simple,
# CONSTANT structure decoupled from however many levels cz=2 has. Marker is
# derived from cz=2's own first marker (+32); mc is a fixed per-(cx,cy)
# constant (NOT derived from cz=2's mc, which can vary with Nc/Ye/spanning
# while cz=1's mc never does).
# ---------------------------------------------------------------------------

# (cx, cy) -> (pos1, gap1, gap2, mc_cz1_constant)
_CZ1_PARAMS = {
    (2, 1): (29, 326, 306, 578),
    (2, 2): (19, 324, 314, 674),
    (1, 1): (335, 326, 0, 546),
    (1, 2): (325, 326, 8, 642),
}


# ---------------------------------------------------------------------------
# X-axis spanning, both directions — re-derived directly from real export
# bytes (1652: Nc_neg=1, Nc_pos=1, Ye=1, lz=14) since the legacy generator
# files' documented groups formula was found to be incomplete. Scope: this
# implementation is validated for Nc_neg=1, Nc_pos=1 only — see
# h3_lowrow_scanners.md's X-axis spanning section for the Nc>1 formulas
# (own-role scales linearly, cross-role marker caps after Nc_other>=2),
# which are not yet wired into this generator.
#
# Structure (per (cx,cy) role, all four uniform except for the per-role
# "own" value):
#   marker1 = own_val   (the role's plain single-direction Nc=1,Ye=1 marker,
#                          UNCHANGED by the other direction's presence)
#   8-byte background gap
#   marker2 = 199        (universal cross-direction flag, same value all 4)
#   gs = pos1 + 334       (uniform across all 4 roles for this configuration)
#   groups = 3 pairs: [own_val+19, 32] [sep 8B] [163, 32] [sep 8B] [163, 32]
#   mat_byte_pos = gs - OFFSET (role-specific, matches each role's established
#                  base-case "gs - N" relationship: 212->10, 222->2, 112->316,
#                  122->308)
# ---------------------------------------------------------------------------

_XSPAN_GS_OFFSET = 334
_XSPAN_MAT_OFFSET = {'212': 10, '222': 2, '112': 316, '122': 308}
_XSPAN_TRAILING = {'212': 306, '222': 314, '112': 0, '122': 8}


def _xspan_groups(own_val):
    groupA_val = (own_val + 19) % 256
    return (_halfblock(groupA_val) + _halfblock(0x20)
            + bytes([0xff, 0x00] * 4)
            + _halfblock(163) + _halfblock(0x20)
            + bytes([0xff, 0x00] * 4)
            + _halfblock(163) + _halfblock(0x20))


def generate_xspan_scan(role, own_val, mat_counter, pos1):
    """Generate the scan for one h3 chunk when X spans both directions
    (Nc_neg=1, Nc_pos=1). `role` in {'212','222','112','122'} identifies
    which (cx,cy) role this chunk plays; `own_val` is that role's plain
    single-direction marker value (e.g. own_val_212 at Nc=1,Ye=1); `pos1`
    is that role's own pos1 (e.g. 19 for 212, 9 for 222, 325 for 112 at
    Ye=1/lz=14, 317 for 122 at Ye=1/lz=14)."""
    lme = pos1 + 18  # marker1(5) + gap(8) + marker2(5)
    gs = pos1 + _XSPAN_GS_OFFSET
    groups = _xspan_groups(own_val)
    mat_byte_pos = gs - _XSPAN_MAT_OFFSET[role]
    scan_len = gs + len(groups) + _XSPAN_TRAILING[role]

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, pos1 + 5, pos1 + 13, flip=True)  # gap after odd-length marker1
    _fill_background(scan, lme, scan_len, flip=False)

    scan[pos1:pos1 + 5] = _marker(own_val)
    scan[pos1 + 13:pos1 + 18] = _marker(199)

    scan[mat_byte_pos] = mat_counter & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan)


# ---------------------------------------------------------------------------
# Y-axis spanning, both directions — re-derived directly from real export
# bytes (1658: Ye_neg=1, Ye_pos=1, Nc=1, lz=14). Simpler than X-spanning: no
# main/boundary role asymmetry, uniform shift across all 4 chunks. Scope:
# validated for Ye_neg=1, Ye_pos=1 only — see h3_lowrow_scanners.md's Y-axis
# spanning section for the Ye>1 formulas (own role's marker/groups scale
# differently per family, an extra uniform flag marker appears at Ye_neg>=2),
# not yet wired into this generator.
#
# Structure (per (cx,cy) role):
#   marker1 = baseline_own_val + 35   (uniform shift, NOT a role-specific
#                                        formula substitution like X-spanning)
#   marker2 = 33                       (universal flag, contiguous after
#                                        marker1, no gap)
#   mc = baseline_mc - 70              (uniform shift)
#   groups = [own+19, 32, 32] [sep 8B] [128, 32, 32]   (6 HBs; "128" is a
#             second universal flag/filler value, analogous to X-spanning's
#             "163")
#   gs = pos1 + {212:336, 222:334, 112:336, 122:334}
#   mat_byte_pos = lme + {212:306, 222:314, 112:0, 122:8}  (lme = pos1+10;
#             same per-role offsets as X-spanning's marker-region placement)
# ---------------------------------------------------------------------------

_YSPAN_GS_OFFSET = {'212': 336, '222': 334, '112': 336, '122': 334}
_YSPAN_MAT_OFFSET = {'212': 306, '222': 314, '112': 0, '122': 8}


def _yspan_groups(own_val):
    groupA_val = (own_val + 19) % 256
    return (_halfblock(groupA_val) + _halfblock(0x20) * 2
            + bytes([0xff, 0x00] * 4)
            + _halfblock(128) + _halfblock(0x20) * 2)


def generate_yspan_scan(role, baseline_own_val, baseline_mc, pos1):
    """Generate the scan for one h3 chunk when Y spans both directions
    (Ye_neg=1, Ye_pos=1). `baseline_own_val`/`baseline_mc` are that role's
    plain single-direction Nc=1,Ye=1 marker/mc values."""
    own_val = (baseline_own_val + 35) % 256
    mat_counter = baseline_mc - 70
    lme = pos1 + 10
    mat_byte_pos = lme + _YSPAN_MAT_OFFSET[role]
    gs = pos1 + _YSPAN_GS_OFFSET[role]
    groups = _yspan_groups(own_val)
    scan_len = gs + len(groups) + _XSPAN_TRAILING[role]

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip=False)

    scan[pos1:pos1 + 5] = _marker(own_val)
    scan[pos1 + 5:pos1 + 10] = _marker(33)

    scan[mat_byte_pos] = mat_counter & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mat_counter


# ---------------------------------------------------------------------------
# Z-axis spanning, both directions — re-derived directly from real export
# bytes (1665: far-z pairing, neither side at lz=0). Simplest of the three
# axes: a single marker (no cross-direction flag), and the groups section is
# EXACTLY the plain base Nc=1,Ye=1 shape (groupA+default, sep, groupB+default,
# groupB=163) — just with the marker (and therefore groupA=marker+19)
# substituted to the shifted value instead of the chunk's own unshifted
# baseline. This produces a (cz=2, "positive" side) chunk; cz=1 (the
# "negative" side, in the far-z-pairing sense) is then this marker+3/mc-3,
# generated via generate_cz1_scan-style logic but is NOT the lz=0 special
# case — see h3_lowrow_scanners.md for the lz=0-pairing variant (+20/+32),
# not yet implemented here.
#
# Structure:
#   marker = baseline_own_val + 35; mc = baseline_mc - 35     (the "positive"
#            side, cz=2 in the far-z sense)
#   cz1 side (negative): marker+3, mc-3 (same simple shape, marker swapped)
#   groups = [marker+19, 32] [sep 8B] [163, 32]   (40 bytes, the plain base
#            Nc=1,Ye=1 shape)
#   gs = pos1 + {212:331, 222:329, 112:331, 122:329}
#   mat_byte_pos = lme + {212:306, 222:314, 112:0, 122:8}  (lme = pos1+5)
# ---------------------------------------------------------------------------

_ZSPAN_GS_OFFSET = {'212': 331, '222': 329, '112': 331, '122': 329}
_ZSPAN_MAT_OFFSET = {'212': 306, '222': 314, '112': 0, '122': 8}


def _zspan_groups(marker_val):
    groupA_val = (marker_val + 19) % 256
    return _halfblock(groupA_val) + _halfblock(0x20) + bytes([0xff, 0x00] * 4) + \
        _halfblock(163) + _halfblock(0x20)


def generate_zspan_side_scan(role, marker_val, mat_counter, pos1):
    """Generate one cz side's scan (either cz=2 "positive" or cz=1 "negative"
    in the far-z sign-spanning sense) given the marker value to use directly
    (caller computes baseline+35/-35 etc. and the cz1=cz2+3/-3 split)."""
    lme = pos1 + 5
    gs = pos1 + _ZSPAN_GS_OFFSET[role]
    mat_byte_pos = lme + _ZSPAN_MAT_OFFSET[role]
    groups = _zspan_groups(marker_val)
    scan_len = gs + len(groups) + _XSPAN_TRAILING[role]

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip=True)  # odd-length (5B) marker flips parity

    scan[pos1:pos1 + 5] = _marker(marker_val)
    scan[mat_byte_pos] = mat_counter & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan)


def generate_zspan_farz_pair(role, baseline_own_val, baseline_mc, pos1):
    """Generate (cz2_scan, cz2_mc, cz1_scan, cz1_mc) for far-z sign-spanning
    (neither side at lz=0): cz2 is the "positive" side, cz1 the "negative"."""
    cz2_marker = (baseline_own_val + 35) % 256
    cz2_mc = baseline_mc - 35
    cz1_marker = (cz2_marker + 3) % 256
    cz1_mc = cz2_mc - 3
    cz2_scan = generate_zspan_side_scan(role, cz2_marker, cz2_mc, pos1)
    cz1_scan = generate_zspan_side_scan(role, cz1_marker, cz1_mc, pos1)
    return cz2_scan, cz2_mc, cz1_scan, cz1_mc


def generate_cz1_scan(cx, cy, cz2_first_marker):
    """Generate the cz=1 (lz=0) scan for role (cx,cy), given cz=2's own first
    marker value (used to derive cz=1's marker via the established +32 rule).
    mc for cz=1 is the fixed per-(cx,cy) constant, NOT derived dynamically."""
    pos1, gap1, gap2, mc_cz1 = _CZ1_PARAMS[(cx, cy)]
    own_val = (cz2_first_marker + 32) % 256
    groupA_val = (own_val + 19) % 256
    groupB_val = 163
    default_val = 32

    lme = pos1 + 5
    gs = lme + gap1
    groups_total = 40
    mat_byte_pos = lme + gap2
    scan_len = gs + groups_total + gap2

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip=True)

    scan[pos1:pos1 + 5] = bytes([own_val, 0x01, 0x02, 0x00, 0x00])
    scan[mat_byte_pos] = mc_cz1 & 0xff

    p = gs
    scan[p:p + 8] = _halfblock(groupA_val); p += 8
    scan[p:p + 8] = _halfblock(default_val); p += 8
    p += 8  # sep
    scan[p:p + 8] = _halfblock(groupB_val); p += 8
    scan[p:p + 8] = _halfblock(default_val); p += 8
    assert p == gs + groups_total
    return bytes(scan), mc_cz1


# ---------------------------------------------------------------------------
# Multi-z stacking (Nc=1, Ye=1), CONTIGUOUS range only — re-derived from
# h3_lowrow_scanners.md's "cz=2 multi-z formula (FINAL)" section. This is the
# contiguous-tower case (a column of voxels stacked through multiple z-levels
# with no gaps) — distinct from sparse z-axis gaps, which use a different
# 2-marker formula not implemented here.
#
# SCOPE: confirmed via 1907 (2026-06-20, lz_near=7, lz_far=14, range=8,
# genuinely contiguous -- z=7..14 all real, nothing below) that the simple
# 1-marker formula below is in fact valid for lz_near > 0 AND range > 2 too.
# An earlier pass had wrongly assumed 1581 disproved this and asserted the
# case unsupported -- but 1581 is a SPARSE construct (a real GAP at
# z=8..13, only z=7 and z=14 actually present), not a contiguous floating
# tower, so it was never a valid counter-example for THIS function in the
# first place. generate_sparse_multiz_scan is the right function for that
# different (gapped) geometry; this one now covers the full contiguous
# range regardless of lz_near.
#
# Structure: still exactly ONE marker (same shape as single-z/Z-spanning),
# and scan_len/gs/mat_byte_pos are UNCHANGED from single-z — only the
# marker/groups VALUES change, plus the half-block N field carries the
# z-span count instead of always being 1.
#
#   N        = lz_far - lz_near + 1            (GLOBAL span; if the stack
#              reaches lz_near=0, this counts cz=1's level too, even though
#              cz=2 itself only physically stores lz=1..lz_far)
#   marker   = (single_z_own_val + lz_far + lz_near + 7) % 256
#   groupA   = (marker + 19) % 256
#   groupB   = (163 - lz_far + lz_near) % 256
#   Y        = (lz_far + 4 + lz_near) % 256
#   mc       = single_z_mc - 35   if N > 1   (else unchanged)
#   groups   = [HB(groupA,N), HB(Y,N)] [sep 8B] [HB(groupB,N), HB(Y,N)]
#
# If lz_near == 0, the cz=1 sibling is generated by the EXISTING
# generate_cz1_scan(cx, cy, cz2_first_marker) — already validated, and
# already handles the per-role gap1 exception correctly; no separate
# multi-z-specific cz=1 logic is needed.
# ---------------------------------------------------------------------------

def generate_multiz_scan(role, single_z_own_val, single_z_mc, lz_near, lz_far, pos1):
    """Generate the cz=2 scan for contiguous multi-z stacking (Nc=1, Ye=1).
    Returns (scan, mc, first_marker) -- first_marker is what the caller
    should pass to generate_cz1_scan if lz_near == 0."""
    N = lz_far - lz_near + 1
    first_marker = (single_z_own_val + lz_far + lz_near + 7) % 256
    groupA_val = (first_marker + 19) % 256
    groupB_val = (163 - lz_far + lz_near) % 256
    Y_val = (lz_far + 4 + lz_near) % 256
    mc = single_z_mc - 35 if N > 1 else single_z_mc

    lme = pos1 + 5
    gs = pos1 + _ZSPAN_GS_OFFSET[role]
    mat_byte_pos = lme + _ZSPAN_MAT_OFFSET[role]
    groups = (_halfblock(groupA_val, N) + _halfblock(Y_val, N)
              + bytes([0xff, 0x00] * 4)
              + _halfblock(groupB_val, N) + _halfblock(Y_val, N))
    scan_len = gs + len(groups) + _XSPAN_TRAILING[role]

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip=True)  # odd-length (5B) marker flips parity

    scan[pos1:pos1 + 5] = _marker(first_marker, N)
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc, first_marker


# ---------------------------------------------------------------------------
# Sparse multi-z, K=2 (exactly 2 real z-levels with a single gap covering
# everything between them) — re-derived from real export bytes (1581:
# lz_near=7, lz_far=14, only those two levels real, lz=8..13 empty), since
# the documented formula's exact byte offsets needed re-confirming against
# this module's own established per-role constants. Distinct from the
# CONTIGUOUS multi-z case above: this is "two voxels far apart in z with
# nothing between," not "a tower with no gaps."
#
# Structure: marker1(5B) + marker2(5B), contiguous (no inter-marker gap,
# same convention as Y-spanning), then the SAME gs/mat_byte_pos/scan_len
# structural offsets as every other 2-marker case in this module (reusing
# _ZSPAN_MAT_OFFSET/_XSPAN_TRAILING directly) but with gs = lme + a new
# per-role gap1 constant, and an 8-HB/72-byte groups section (vs the plain
# 4-HB/40-byte shape) that adds an "X" filler half-block flanking the
# existing Y half-block on each side.
#
#   marker1 = (single_z_own_val + lz_far + lz_near + 7) % 256   (same anchor
#             formula as contiguous multi-z)
#   marker2 = (lz_far - lz_near - 2) % 256   (only valid when this is > 0,
#             i.e. range > 2 -- range <= 2 should use a contiguous run instead)
#   groupA  = (marker1 + 19) % 256
#   groupB  = (163 - lz_far + lz_near) % 256
#   X       = (lz_far - 3 - lz_near) % 256
#   Y       = (lz_far + 4 + lz_near) % 256
#   mc      = single_z_mc - 35   (same multi-z correction as the contiguous case)
#   groups  = [groupA, X, Y, X] [sep 8B] [groupB, X, Y, X]   (all N=1 -- sparse
#             z-runs always use N=1 in the half-blocks, unlike contiguous runs)
#
# NOT covered by this function: K>=3 real levels (multiple gaps), which
# h3_lowrow_scanners.md documents as reusing this exact marker-value formula
# PER GAP (one extra 5-byte marker per gap, anchor stays the same) while
# apparently keeping the SIMPLE 40-byte groups shape rather than this
# function's 72-byte one -- not yet implemented/verified in code.
# ---------------------------------------------------------------------------

_SPARSE_GAP1 = {'212': 326, '222': 324, '112': 326, '122': 324}


def generate_sparse_multiz_scan(role, single_z_own_val, single_z_mc, lz_near, lz_far, pos1,
                                 Ncols=1, Ye=1, w0=1, w1=1):
    """K=2 sparse multi-z: exactly 2 real z-levels (lz_near, lz_far), gap
    between them. Returns (scan, mc).

    Ncols>1 generalization (confirmed via export 1903, Ncols=2): tracking
    roles ('212'/'222') gain an EXTRA marker pair per additional column --
    [SEP(8B), xstep(N=1), marker2-again(N=1)] -- where xstep reuses the
    established contiguous-multiz xstep formula evaluated at the GLOBAL
    span N=lz_far-lz_near+1 (NOT this function's own N=1 marker
    convention), and the "gap" marker value is simply repeated unchanged.
    Also gain (Ncols-1) extra repeats of the groupB section (the familiar
    "(Ncols+1) total sections" pattern, using this function's 4-HB X/Y/X
    shape per section), and a UNIFORM -10*(Ncols-1) shift on mat_byte_pos,
    gs, AND the trailing background length (only confirmed at Ncols=2, not
    verified to continue linearly beyond that). Boundary roles
    ('112'/'122') are completely unaffected by Ncols (same offsets, mc,
    single groupB section, and 2-marker structure as Ncols=1) --
    `single_z_mc` should already be the Ncols-scaled single-z baseline for
    the role in question (e.g. mc_212(Ncols) for '212', but the PLAIN
    Ncols=1 boundary mc for '112'/'122').

    w0/w1 generalization (confirmed via export 1911, w0=2/w1=1: segment 0
    is z=10-11 (width 2), gap at z=12-13, segment 1 is z=14 (width 1)):
    when segment widths aren't both 1, marker1/marker2 each carry their
    OWN segment's width as their N-byte (not always N=1), and EACH of the
    groupA/groupB section's two values (the main value and Y) gets an
    extra `[0, N=w1]` filler half-block appended right after it -- a
    DIFFERENT mechanism than the X-filler used when w0=w1=1 (X is a real
    lz-derived value; here the filler is a plain 0). Only confirmed for
    this exact (w0,w1)=(2,1) combination -- (w0,w1) with w1>1, or with
    w0=1, are unverified, as is whether this generalizes to true K>=3
    (3+ segments) with multi-level real sub-runs."""
    assert lz_far - lz_near - 2 > 0, (
        "range <= 2 has no gap content to encode -- use generate_multiz_scan instead")
    N_global = lz_far - lz_near + 1
    marker1 = (single_z_own_val + lz_far + lz_near + 7) % 256
    # generalizes the old flat "-2" to "-w0-w1" (the actual gap between
    # segment0's end and segment1's start; w0=w1=1 reduces to the
    # original formula exactly -- confirmed via export 1911)
    marker2 = (lz_far - lz_near - w0 - w1) % 256
    xstep = (234 - 35 * Ye - (N_global - 1)) % 256
    groupA_val = (marker1 + 19) % 256
    groupB_val = (163 - lz_far + lz_near) % 256
    X_val = (lz_far - 3 - lz_near) % 256
    Y_val = (lz_far + 4 + lz_near) % 256
    # mod-256 wrap must apply to the FULL correction (same class of bug
    # fixed elsewhere in this module)
    mc = 512 + ((single_z_mc - 512 - 35) % 256)

    uniform_width = (w0 == 1 and w1 == 1)

    tracks_nc = _MULTIZ_NCYE_TRACKS_NC[role]
    marker_span = 10 + (18 * (Ncols - 1) if tracks_nc else 0)
    shift = -10 * (Ncols - 1) if tracks_nc else 0
    lme = pos1 + marker_span
    gs = lme + _SPARSE_GAP1[role] + shift
    mat_byte_pos = lme + _ZSPAN_MAT_OFFSET[role] + shift
    if uniform_width:
        section_a = _halfblock(groupA_val) + _halfblock(X_val) + _halfblock(Y_val) + _halfblock(X_val)
        section_b = _halfblock(groupB_val) + _halfblock(X_val) + _halfblock(Y_val) + _halfblock(X_val)
    else:
        section_a = (_halfblock(groupA_val, w0) + _halfblock(0, w1)
                      + _halfblock(Y_val, w0) + _halfblock(0, w1))
        section_b = (_halfblock(groupB_val, w0) + _halfblock(0, w1)
                      + _halfblock(Y_val, w0) + _halfblock(0, w1))
    sep = bytes([0xff, 0x00] * 4)
    n_groupb_sections = Ncols if tracks_nc else 1
    groups = section_a + (sep + section_b) * n_groupb_sections
    trailing = _XSPAN_TRAILING[role] + shift
    scan_len = gs + len(groups) + trailing

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip=False)  # confirmed unaffected by Ncols (1903)

    scan[pos1:pos1 + 5] = _marker(marker1, w0)
    scan[pos1 + 5:pos1 + 10] = _marker(marker2, w1)
    p = pos1 + 10
    if tracks_nc:
        for _ in range(Ncols - 1):
            _fill_background(scan, p, p + 8, flip=False)
            p += 8
            scan[p:p + 5] = _marker(xstep)
            p += 5
            scan[p:p + 5] = _marker(marker2)
            p += 5
    assert p == lme
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# Sparse multi-z, K>=3 (3 or more isolated real z-levels with gaps between
# each consecutive pair) — re-derived from real export bytes (1675: real at
# lz=10,12,14, gaps at lz=11 and lz=13). Surprising discontinuity confirmed
# against the byte-exact dump: despite K=3 having a LARGER overall range
# (lz_far-lz_near=4) than K=2's range-only-needs-X-halfblocks threshold, K=3
# actually uses the SIMPLER 40-byte groups shape (same shape as the
# CONTIGUOUS multi-z case) with NO "X" filler half-block at all -- the
# 72-byte/X-halfblock structure is specific to exactly K=2 (generate_
# sparse_multiz_scan above), not a general "range > 2" rule as an earlier,
# less complete pass at this formula had assumed.
#
# Structure: K contiguous 5-byte markers (1 anchor + K-1 gap markers, no
# inter-marker gap), then the plain single-marker groups shape with N =
# GLOBAL span (lz_far-lz_near+1) and groupB/Y computed from the GLOBAL
# lz_near/lz_far exactly as in the contiguous multi-z case.
#
#   marker[0]   = (single_z_own_val + lz_far + lz_near + 7) % 256   (anchor,
#                 lz_far/lz_near are the GLOBAL min/max across all real levels)
#   marker[i]   = (seg[i].start - seg[i-1].end - 2) % 256   for i = 1..K-1
#                 (gap-size formula applied PER CONSECUTIVE PAIR of real
#                 segment boundaries -- reduces to the original single-point
#                 formula when every segment has width 1)
#   each marker[i]'s N-byte = seg[i]'s width (not always 1)
#   near_eff = seg[0].start - (seg[0].width - 1)
#   far_eff  = seg[-1].end - (seg[-1].width - 1)
#   groupA = (marker[0] + 19) % 256; groupB = (163 - far_eff + near_eff) % 256
#   Y = (far_eff + 4 + near_eff - (seg[0].width-1) - (seg[-1].width-1)) % 256
#   N = seg[-1].end - seg[0].start + 1   (ACTUAL global span, unaffected by
#       the near_eff/far_eff adjustment)
#   mc = single_z_mc - 35  (same multi-z correction as every other case)
#
# Multi-level sub-run generalization (confirmed via export 1915, 2026-06-20:
# 3 segments, widths 2/1/2 -- z=10-11, gap, z=13, gap, z=15-16). near_eff/
# far_eff and the marker[0]/groupB formulas reduce EXACTLY to the original
# point-only formulas when all widths are 1 (since seg.width-1 = 0 then).
# Y needed an extra, not-fully-understood "-(w0-1)-(w_last-1)" correction
# beyond using near_eff/far_eff directly -- only confirmed for this ONE
# (2,1,2) width combination; other width combos (e.g. width>1 in a MIDDLE
# segment, or more than 3 segments) are unverified.
# ---------------------------------------------------------------------------

def generate_multigap_multiz_scan(role, single_z_own_val, single_z_mc, real_lz_values, pos1):
    """K>=3 sparse multi-z: real_lz_values is a sorted list of 3+ isolated
    real segments, each either an int (single-level point) or an (start,end)
    tuple (multi-level sub-run). Returns (scan, mc)."""
    segs = [(v, v) if isinstance(v, int) else tuple(v) for v in real_lz_values]
    K = len(segs)
    assert K >= 3, "K=2 should use generate_sparse_multiz_scan instead"
    widths = [end - start + 1 for start, end in segs]
    near_eff = segs[0][0] - (widths[0] - 1)
    far_eff = segs[-1][1] - (widths[-1] - 1)
    lz_near, lz_far = segs[0][0], segs[-1][1]

    marker0 = (single_z_own_val + far_eff + near_eff + 7) % 256
    gap_markers = [(segs[i][0] - segs[i - 1][1] - 2) % 256 for i in range(1, K)]

    groupA_val = (marker0 + 19) % 256
    groupB_val = (163 - far_eff + near_eff) % 256
    Y_val = (far_eff + 4 + near_eff - (widths[0] - 1) - (widths[-1] - 1)) % 256
    N = lz_far - lz_near + 1
    # extra -1 per unit of "excess width" beyond the all-width-1 baseline,
    # on top of the usual -35 multi-z correction (confirmed via 1915, total
    # excess = sum(w-1) for ALL segments = 2 there)
    total_excess = sum(w - 1 for w in widths)
    mc = 512 + ((single_z_mc - 512 - 35 - total_excess) % 256)

    lme = pos1 + 5 * K
    gs = lme + _SPARSE_GAP1[role]
    mat_byte_pos = lme + _ZSPAN_MAT_OFFSET[role]
    groups = (_halfblock(groupA_val, N) + _halfblock(Y_val, N)
              + bytes([0xff, 0x00] * 4)
              + _halfblock(groupB_val, N) + _halfblock(Y_val, N))
    scan_len = gs + len(groups) + _XSPAN_TRAILING[role]

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip=(K % 2 == 1))

    scan[pos1:pos1 + 5] = _marker(marker0, widths[0])
    for i, gm in enumerate(gap_markers):
        scan[pos1 + 5 * (i + 1):pos1 + 5 * (i + 2)] = _marker(gm, widths[i + 1])
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# Contiguous multi-z combined with Nc=2 (the "Nc-tracking" pos-x main/pos-y
# roles only), Ye=1 — re-derived from real export bytes (1636: Nc=2, Ye=1,
# full z lz=0..14). Re-derivation found something the older memory summary
# didn't make obvious: the BOUNDARY roles (1,1,2)/(1,2,2) don't track Nc at
# all under multi-z (confirmed via 1636's raw bytes: their scan is BYTE-
# IDENTICAL in shape to the plain Nc=1 multi-z case, single marker, same
# scan_len) -- so generate_multiz_scan already handles them correctly
# unchanged; only the "main"/pos-y roles (2,1,2)/(2,2,2) need new code here.
#
# SCOPE: this function is scoped to Ncols=2 specifically (the only tested
# case) -- the structural offsets below (gs/mat_byte_pos relative to lme)
# were measured directly from 1636's bytes, not derived from a general
# Ncols-scaling formula, since only one Ncols data point was verified this
# session. Extending to Ncols=3+ or Ye>1 needs fresh byte verification.
#
# Structure: col1 marker = the SAME single-column multi-z anchor formula
# (unaffected by Ncols), col2 marker = the existing single-z xstep formula
# with N substituted in, contiguous markers separated by an 8-byte sep
# (multi-z ADDS a separator that the plain single-z (2,1,2) base case
# doesn't have). Groups: (Ncols+1) pairs of [HB(val,N), HB(Y,N)], with N =
# the GLOBAL multi-z span throughout (not just N=1 per column as the base
# Nc>1 case uses) and the "default" half-block using the multi-z Y value
# instead of the base case's constant 32.
#
#   marker1 = (single_z_own_val + lz_far + lz_near + 7) % 256   (Ncols-independent)
#   marker2 = xstep_212(Ye) - (N-1)   for 212;  (199 - (N-1)) % 256   for 222
#   groupA  = (marker1 + 19) % 256
#   groupB  = (163 - lz_far + lz_near) % 256
#   Y       = (lz_far + 4 + lz_near) % 256
#   N       = lz_far - lz_near + 1
#   mc      = single_z_mc_at_this_Ncols - 35
# ---------------------------------------------------------------------------

_MULTIZ_NC2_LME_OFFSETS = {'212': (296, 316), '222': (304, 314)}  # (matpos-lme, gs-lme)


def generate_multiz_nc2_scan(role, single_z_own_val, single_z_mc_nc2, lz_near, lz_far, pos1):
    """Contiguous multi-z, Ncols=2, Ye=1, for the Nc-tracking roles
    ('212' or '222' only -- boundary roles should use generate_multiz_scan
    directly, unaffected by Ncols). single_z_mc_nc2 is the single-z (no
    multi-z) mat_counter value AT Ncols=2."""
    assert role in ('212', '222'), "boundary roles (112/122) don't track Nc -- use generate_multiz_scan"
    N = lz_far - lz_near + 1
    marker1 = (single_z_own_val + lz_far + lz_near + 7) % 256
    if role == '212':
        marker2 = (234 - 35 * 1 - (N - 1)) % 256  # Ye=1 only, per this function's scope
    else:
        marker2 = (199 - (N - 1)) % 256
    groupA_val = (marker1 + 19) % 256
    groupB_val = (163 - lz_far + lz_near) % 256
    Y_val = (lz_far + 4 + lz_near) % 256
    # -35 must be applied INSIDE the mod-256 wrap, not as a naive subtraction
    # from the already-wrapped single-z value (confirmed via (2,2,2): naive
    # 526-35=491 is wrong, the real value is 747 = 512+((526-512-35)%256))
    mc = 512 + ((single_z_mc_nc2 - 512 - 35) % 256)

    lme = pos1 + 18  # marker1(5) + sep(8) + marker2(5)
    mat_off, gs_off = _MULTIZ_NC2_LME_OFFSETS[role]
    mat_byte_pos = lme + mat_off
    gs = lme + gs_off
    groups = (_halfblock(groupA_val, N) + _halfblock(Y_val, N)
              + bytes([0xff, 0x00] * 4)
              + _halfblock(groupB_val, N) + _halfblock(Y_val, N)
              + bytes([0xff, 0x00] * 4)
              + _halfblock(groupB_val, N) + _halfblock(Y_val, N))
    trailing = mat_off  # measured identical to matpos-lme for both roles at Ncols=2
    scan_len = gs + len(groups) + trailing

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, pos1 + 5, pos1 + 13, flip=True)  # gap after odd-length marker1
    _fill_background(scan, lme, scan_len, flip=False)

    scan[pos1:pos1 + 5] = _marker(marker1, N)
    scan[pos1 + 13:pos1 + 18] = _marker(marker2, N)
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_cz1_nc2_scan(role, cz2_marker1, base_cz1_mc, pos1):
    """cz=1 sibling for the Ncols=2 multi-z case ('212'/'222' only). Re-uses
    the EXACT SAME structural offsets as generate_multiz_nc2_scan for the
    same role (confirmed via 1636's raw bytes: cz=1 and cz=2 share identical
    lme/gs/mat_byte_pos deltas under Nc=2) -- only the values differ: cz=1
    always uses N=1, a constant col2 marker (199, the plain single-z
    xstep at Ye=1/N=1), and a constant groupB=163/default=32, matching its
    established Nc=1-multiz convention just repeated across Ncols+1 group
    sections. mc = base_cz1_mc + 55*(Ncols-1), Ncols=2 scope only here."""
    assert role in ('212', '222'), "boundary roles don't track Nc -- use generate_cz1_scan directly"
    marker1 = (cz2_marker1 + 32) % 256
    marker2 = 199
    groupA_val = (marker1 + 19) % 256
    mc = base_cz1_mc + 55

    lme = pos1 + 18
    mat_off, gs_off = _MULTIZ_NC2_LME_OFFSETS[role]
    mat_byte_pos = lme + mat_off
    gs = lme + gs_off
    groups = (_halfblock(groupA_val) + _halfblock(0x20)
              + bytes([0xff, 0x00] * 4)
              + _halfblock(163) + _halfblock(0x20)
              + bytes([0xff, 0x00] * 4)
              + _halfblock(163) + _halfblock(0x20))
    scan_len = gs + len(groups) + mat_off

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, pos1 + 5, pos1 + 13, flip=True)
    _fill_background(scan, lme, scan_len, flip=False)

    scan[pos1:pos1 + 5] = _marker(marker1)
    scan[pos1 + 13:pos1 + 18] = _marker(marker2)
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# Contiguous multi-z combined with Nc>1 AND Ye>1 simultaneously -- re-derived
# from real export bytes (1638: Nc=2,Ye=2; 1640: Nc=3,Ye=2; both lz=0..14),
# since the abbreviated memory summary undersold the complexity here. Real
# findings beyond what was documented:
#
# - The "212/112 family" (marker-repeats-per-row convention) gets the
#   established extra -35 IN THE MARKER itself (confirmed), and groupB ALSO
#   gets an extra -35 (NOT previously documented).
# - The "222/122 family" (Ye-baked-into-value convention) does NOT shift its
#   marker at all under this combination -- instead groupA gets +19+35
#   (not the usual +19) and groupB gets +35. The +35 shows up in GROUPS for
#   this family instead of in the marker, mirroring 212/112's marker-level
#   shift -- same magnitude, different structural location per family.
# - groups for 212/112 family: EVERY groupB section except the LAST one gets
#   an extra inserted pair [HB(Y,N=0), HB(13,N=0)] between the groupB head
#   and the normal trailing Y filler(s) -- confirmed scaling with Ncols (1
#   extra-pair section at Ncols=2, 2 at Ncols=3, always sparing the last).
#   "13" is treated as an empirical constant for this lz/Ye config; its
#   derivation isn't understood from first principles.
# - Boundary roles (112/122) don't track Ncols in their OWN marker, but
#   their groups section still repeats (Ncols+1) times using the
#   CONSTRUCT's overall Ncols (matching the established cz=1-tracks-Ncols
#   finding from the plain Nc=2 case) -- and they're subject to the SAME
#   family-based marker/groupB shift as their main-role counterpart, using
#   the construct's overall Nc to decide whether the shift triggers.
#
# SCOPE: Ye in {2,3}, Ncols in {2,3}, lz_near=0/lz_far=14 only (the three
# tested data points: 1638 Nc=2/Ye=2, 1640 Nc=3/Ye=2, 1899 Nc=2/Ye=3) -- the
# "13" constant and the exact extra-pair shape are not verified beyond this
# config (e.g. Ye=4+ or Ncols=4+ combined with Ye=3 are untested). Ye=3
# generalization (2026-06-20, via 1899) found: the extra-pair mechanism's
# [Y(N0),13(N0)] sub-pair repeats (Ye-1) times (not just once); the 222
# family's marker caps at its Ye=2 value rather than continuing to scale;
# 212/112's groupB ALSO scales with Ye (-35*(Ye-1), not a flat -35); and a
# small role-specific "-2 per (Ye-2)" gs_off shift appears on '112' (cz=2)
# and '212' (cz=1) specifically, with no obvious unifying explanation yet.
# ---------------------------------------------------------------------------

# Offsets measured at Ncols=2; tracking roles ('212'/'222') shift by -10 per
# additional column beyond 2 (confirmed via 1640's Ncols=3 data point,
# mirroring the established base single-z gap1 formula's -10*(Ncols-1)
# term). Non-tracking roles ('112'/'122') are constant regardless of Ncols.
_MULTIZ_NCYE_BASE_OFFSETS = {'212': (296, 314), '222': (306, 316),
                             '112': (0, 326), '122': (8, 324)}
_MULTIZ_NCYE_TRACKS_NC = {'212': True, '222': True, '112': False, '122': False}
_MULTIZ_NCYE_EXTRA_PAIR_CONST = 13


def _multiz_ncye_offsets(role, Ncols, Ye=2):
    mat_off, gs_off = _MULTIZ_NCYE_BASE_OFFSETS[role]
    if _MULTIZ_NCYE_TRACKS_NC[role]:
        shift = -10 * (Ncols - 2)
        mat_off += shift
        gs_off += shift
    if role == '112':
        # confirmed via 1899 (Ye=3): '112's cz=2 gs_off shifts -2 per
        # (Ye-2), unlike '212' which stays fixed at its base value
        gs_off -= 2 * (Ye - 2)
    return mat_off, gs_off


def generate_multiz_nc_ye_212family_scan(role, Ncols, single_z_own_val,
                                          single_z_mc, lz_near, lz_far, Ye, pos1):
    """212 or 112 (the marker-repeats-per-row family), Nc>1 AND Ye>1, Ye=2
    scope. role='212' shows the actual column markers; role='112' has no
    col2+ marker, but its single groupB section still gets the "extra pair"
    treatment regardless of the construct's Ncols (it never gets a "last
    normal" section the way '212' does once Ncols>=2)."""
    tracks_nc = _MULTIZ_NCYE_TRACKS_NC[role]
    N = lz_far - lz_near + 1
    marker1 = (single_z_own_val + lz_far + lz_near + 7 - 35) % 256
    xstep = (234 - 35 * Ye - (N - 1)) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    groupA_val = (marker1 + 19) % 256
    # groupB's "-35" extra term DOES scale with Ye (confirmed via 1899,
    # Ye=3: needed -35*(Ye-1)=-70, not a flat -35) -- unlike marker1's
    # extra term, which is a one-time binary step that doesn't scale further
    groupB_val = (163 - lz_far + lz_near - 35 * (Ye - 1)) % 256
    Y_val = (lz_far + 4 + lz_near) % 256
    mc = single_z_mc  # vanishing rule: no -35 when Nc>1 AND Ye>1

    marker_span = (5 * Ncols * Ye + 8 * (Ncols - 1)) if tracks_nc else 5 * Ye
    lme = pos1 + marker_span
    mat_off, gs_off = _multiz_ncye_offsets(role, Ncols, Ye)
    mat_byte_pos = lme + mat_off
    gs = lme + gs_off

    section_normal = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye
    section_extra = (_halfblock(groupB_val, N)
                      + (_halfblock(Y_val, 0) + _halfblock(_MULTIZ_NCYE_EXTRA_PAIR_CONST, 0)) * (Ye - 1)
                      + _halfblock(Y_val, N))
    section_last = _halfblock(groupB_val, N) + _halfblock(Y_val, N) * Ye
    sep = bytes([0xff, 0x00] * 4)
    groups = section_normal
    if tracks_nc:
        for col in range(Ncols):  # Ncols groupB sections: all but the last are "extra"
            groups += sep + (section_extra if col < Ncols - 1 else section_last)
    else:
        groups += sep + section_extra  # always exactly 1 extra section, no "last normal"
    scan_len = gs + len(groups) + mat_off

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(marker1, N)
    p += 5
    for _ in range(Ye - 1):
        scan[p:p + 5] = _marker(ystep, N)
        p += 5
    if tracks_nc:
        for col in range(1, Ncols):
            # parity flips once per column block iff that block (5*Ye bytes)
            # is odd-length -- only false-by-coincidence at Ye=2 (block=10,
            # even); Ye=3's block=15 is odd, so this must be computed, not
            # hardcoded (confirmed via 1899)
            _fill_background(scan, p, p + 8, flip=((5 * Ye * col) % 2 == 1))
            p += 8
            scan[p:p + 5] = _marker(xstep, N)
            p += 5
            for _ in range(Ye - 1):
                scan[p:p + 5] = _marker(ystep, N)
                p += 5
    assert p == lme
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))

    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_multiz_nc_ye_222family_scan(role, Ncols, base_own_val, base_mc,
                                          lz_near, lz_far, Ye, pos1):
    """222 or 122 (the Ye-baked-into-value family), Nc>1 AND Ye>1. role='222'
    shows an xstep column2+ marker (Ye-independent, plain multiz formula)
    and repeats its single-half-block groupB section Ncols times; role='122'
    has no col2+ marker and always exactly 1 groupB section regardless of
    the construct's Ncols.

    The "-35*(Ye-1)" shift CAPS at Ye=2's value -- confirmed via export
    1899 (Ye=3): marker1 stayed IDENTICAL to the Ye=2 case rather than
    continuing to scale, mirroring the same capping pattern seen elsewhere
    in this family (e.g. the established multi-z own_val formula for this
    family already caps the same way before the Nc>1 combination existed)."""
    tracks_nc = _MULTIZ_NCYE_TRACKS_NC[role]
    N = lz_far - lz_near + 1
    marker1 = (base_own_val + lz_far + lz_near + 7 - 35 * min(Ye - 1, 1)) % 256
    xstep = (199 - (N - 1)) % 256
    groupA_val = (marker1 + 19 + 35) % 256
    groupB_val = (163 - lz_far + lz_near + 35) % 256
    mc = base_mc  # vanishing rule

    marker_span = (5 * Ncols + 8 * (Ncols - 1)) if tracks_nc else 5
    lme = pos1 + marker_span
    mat_off, gs_off = _multiz_ncye_offsets(role, Ncols)
    mat_byte_pos = lme + mat_off
    gs = lme + gs_off

    sep = bytes([0xff, 0x00] * 4)
    groups = _halfblock(groupA_val, N)
    n_groupb_sections = Ncols if tracks_nc else 1
    for _ in range(n_groupb_sections):
        groups += sep + _halfblock(groupB_val, N)
    scan_len = gs + len(groups) + mat_off

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(marker1, N)
    p += 5
    if tracks_nc:
        for col in range(1, Ncols):
            _fill_background(scan, p, p + 8, flip=(col % 2 == 1))
            p += 8
            scan[p:p + 5] = _marker(xstep, N)
            p += 5
    assert p == lme
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))

    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# cz=1 sibling for the Nc>1 AND Ye>1 combined case, 212/112 family. Re-derived
# from 1638's raw bytes ((2,1,1)/(1,1,1)). cz=1 mirrors cz=2's Nc/Ye
# structure (column markers + row repeats, same per-role lme/gs offsets
# pattern) but with N=1 throughout and a DIFFERENT, shorter "extra section"
# shape than cz=2's: [HB(groupB_cz1,N=1), HB(32,N=0), HB(ystep_cz1,N=1)] --
# 3 half-blocks (for Ye=2), not cz=2's 4. groupB_cz1 = 163-35=128 (same -35
# magnitude as cz=2's groupB shift, applied to cz=1's constant 163 baseline
# rather than cz=2's lz-dependent one). mc = base_cz1_mc + 55*(Ncols-1 if
# tracks_nc else 0) + 35 (an unconditional Ye>1 adjustment for cz=1's mc,
# separate from cz=2's Nc>1-AND-Ye>1 vanishing rule).
# ---------------------------------------------------------------------------

# cz=1's offsets differ slightly from cz=2's per role (measured directly,
# not derivable from cz=2's table by a clean rule): 212 gs_off=316 (cz=2:
# 314); 222 mat_off=304/gs_off=314 (cz=2: 306/316); 122 gs_off=326 (cz=2:
# 324); 112 matches cz=2 exactly (0, 326).
_CZ1_NCYE_BASE_OFFSETS = {'212': (296, 316), '112': (0, 326),
                          '222': (304, 314), '122': (8, 326)}


def generate_cz1_nc_ye_212family_scan(role, tracks_nc, Ncols, cz2_marker1, base_cz1_mc, Ye, pos1):
    """cz=1 sibling, 212/112 family, Nc>1 AND Ye>1. See generate_multiz_nc_ye_212family_scan's SCOPE comment for tested Ye/Ncols ranges."""
    marker1 = (cz2_marker1 + 32) % 256
    ystep = (304 - _EFF_LZ - 1) % 256  # cz=1's own N=1
    xstep = (234 - 35 * Ye - (1 - 1)) % 256
    groupA_val = (marker1 + 19) % 256
    # same Ye-scaling correction as cz=2's groupB (confirmed via 1899)
    groupB_val = (163 - 35 * (Ye - 1)) % 256

    marker_span = (5 * Ncols * Ye + 8 * (Ncols - 1)) if tracks_nc else 5 * Ye
    lme = pos1 + marker_span
    mat_off, gs_off = _CZ1_NCYE_BASE_OFFSETS[role]
    if tracks_nc:
        shift = -10 * (Ncols - 2)
        mat_off += shift
        gs_off += shift
    if role == '212':
        # confirmed via 1899 (Ye=3): cz=1's '212' gs_off shifts -2 per
        # (Ye-2), unlike cz=2's '212' which stays fixed at its base value
        gs_off -= 2 * (Ye - 2)
    mat_byte_pos = lme + mat_off
    gs = lme + gs_off
    # mod-256 wrap must apply to the FULL correction, not a naive sum (same
    # class of bug as cz=2's mc fix earlier in this module)
    mc = 512 + ((base_cz1_mc - 512 + (55 * (Ncols - 1) if tracks_nc else 0) + 35) % 256)

    section_normal = _halfblock(groupA_val) + _halfblock(0x20) * Ye
    # head + one 32(N0) filler + (Ye-2) ystep(N0) fillers + final ystep(N1)
    # -- confirmed via 1899 (Ye=3): the Ye=2 case's "32(N0)" doesn't repeat,
    # it's a single filler that's always exactly 1, with ystep(N0) taking
    # over for any additional rows beyond Ye=2
    section_extra = (_halfblock(groupB_val) + _halfblock(0x20, 0)
                      + _halfblock(ystep, 0) * (Ye - 2) + _halfblock(ystep))
    section_last = _halfblock(groupB_val) + _halfblock(0x20) * Ye
    sep = bytes([0xff, 0x00] * 4)
    groups = section_normal
    if tracks_nc:
        for col in range(Ncols):
            groups += sep + (section_extra if col < Ncols - 1 else section_last)
    else:
        groups += sep + section_extra
    scan_len = gs + len(groups) + mat_off

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(marker1)
    p += 5
    for _ in range(Ye - 1):
        scan[p:p + 5] = _marker(ystep)
        p += 5
    if tracks_nc:
        for col in range(1, Ncols):
            _fill_background(scan, p, p + 8, flip=((5 * Ye * col) % 2 == 1))
            p += 8
            scan[p:p + 5] = _marker(xstep)
            p += 5
            for _ in range(Ye - 1):
                scan[p:p + 5] = _marker(ystep)
                p += 5
    assert p == lme
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))

    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_cz1_nc_ye_222family_scan(role, tracks_nc, Ncols, cz2_marker1, base_cz1_mc, pos1):
    """cz=1 sibling, 222/122 family, Nc>1 AND Ye>1 (Ye in {2,3} tested). groupA/groupB
    use the SAME +19+35 / 163+35 constant-baseline shift as cz=2's version
    of this family, just with cz=1's own marker derivation."""
    marker1 = (cz2_marker1 + 32) % 256
    xstep = 199  # plain single-z 222 xstep constant, Ye-independent
    groupA_val = (marker1 + 19 + 35) % 256
    groupB_val = (163 + 35) % 256
    mc = 512 + ((base_cz1_mc - 512 + (55 * (Ncols - 1) if tracks_nc else 0) + 35) % 256)

    marker_span = (5 * Ncols + 8 * (Ncols - 1)) if tracks_nc else 5
    lme = pos1 + marker_span
    mat_off, gs_off = _CZ1_NCYE_BASE_OFFSETS[role]
    if tracks_nc:
        # 222's cz=1 shifts -8 per extra column (NOT -10 like every other
        # tracking-role case in this module -- confirmed via 1640, Ncols=3)
        shift = -8 * (Ncols - 2)
        mat_off += shift
        gs_off += shift
    mat_byte_pos = lme + mat_off
    gs = lme + gs_off

    sep = bytes([0xff, 0x00] * 4)
    groups = _halfblock(groupA_val)
    n_groupb_sections = Ncols if tracks_nc else 1
    for _ in range(n_groupb_sections):
        groups += sep + _halfblock(groupB_val)
    scan_len = gs + len(groups) + mat_off

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(marker1)
    p += 5
    if tracks_nc:
        for col in range(1, Ncols):
            _fill_background(scan, p, p + 8, flip=(col % 2 == 1))
            p += 8
            scan[p:p + 5] = _marker(xstep)
            p += 5
    assert p == lme
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))

    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# Offset/staggered voxel sets, Ncols=2, Ye=1 each column, 212/222 family --
# re-derived from real export bytes (1806: row_offset=0/no offset, the
# requested "clean reference"; 1677: row_offset=1; 1804: row_offset=-1,
# sign-crossing). This is the simplest non-rectangular case: two columns
# where each has its OWN distinct single-row y position, rather than all
# columns sharing one Yextent.
#
# IMPORTANT PREREQUISITE FINDING: even 1806 ("no offset at all", both
# columns nominally at the same y) does NOT match the plain Phase 1
# generate_212_scan(Ncols=2, Yextent=1) formula -- that combination
# (Ncols>=2 AND Yextent==1) was never actually tested in Phase 1 (all
# original Ncols>=2 tests used large Yextent like 25-29) and turns out to
# need its own marker shift and an inter-column separator, neither of
# which the general formula has. This is a genuine, previously-unknown gap
# in generate_212_scan/generate_222_scan, not something specific to offsets
# -- documented here since this is where it was discovered.
#
#   marker1 (col1) = (plain_own_val_Ye1 + 35) % 256   (universal "non-trivial
#             structure" signature -- triggered here by Ncols>=2 at Ye=1,
#             not by the offset itself, since even row_offset=0 needs it)
#   marker2 (col2) = (plain_xstep_212_Ye1 - 35*row_offset) % 256   (row_offset
#             can be negative for the sign-crossing case, e.g. col1 at
#             y=-0.5, col2 at y=+0.5 -> row_offset=-1)
#   8-byte separator between col1 and col2 (present here despite the plain
#             Yextent=29 base case having none -- another Ye=1-at-Ncols>=2
#             quirk)
#   groups: UNCHANGED by row_offset -- [groupA, default] [sep] [groupB,
#             default] [sep] [groupB, default], groupA=(marker1+19)%256,
#             groupB=163 (the plain Yextent=1 groupB_val, not a new constant),
#             default=32, all N=1. Confirmed identical across all 3 test
#             exports regardless of row_offset.
#
# SCOPE: Ncols=2 only, lz=14, '212'/'222' roles only (the tested family --
# '112'/'122' boundary roles not re-verified for this case).
# ---------------------------------------------------------------------------

_OFFSET_GS_OFFSETS = {'212': (296, 316), '222': (304, 314)}


def generate_offset_212family_scan(role, plain_own_val, plain_xstep, row_offset, mat_counter, pos1):
    """Ncols=2, Ye=1-each-column offset/staggered case. `plain_own_val` and
    `plain_xstep` are the established plain single-z own_val/xstep values
    at Ye=1 (1 and 199 for '212'; 161 and 199(0xc7) for '222' -- pass the
    role's own established constants).

    Two genuinely distinct, family-specific mechanisms depending on sign
    (confirmed via raw bytes, not derivable from one rule):
    - '212' family: groupB shifts to 163-35=128 when row_offset>0 (same
      sign as col1, both negative) but stays 163 when row_offset<0
      (sign-crossing) or 0. The offset column's section gains 1 extra
      HB(0x20) whenever row_offset != 0 (either sign).
    - '222' family: groupB always stays 163. row_offset>0 (same-sign)
      DEFLATES the LAST section instead (drops its trailing HB(0x20), down
      to just the groupB head); row_offset<0 (sign-crossing) INFLATES the
      offset column's section by 1 HB instead, mirroring '212' family.
    row_offset=0: both families use the plain, unmodified 3-section shape.
    """
    marker1 = (plain_own_val + 35) % 256
    marker2 = (plain_xstep - 35 * row_offset) % 256
    groupA_val = (marker1 + 19) % 256

    lme = pos1 + 18  # marker1(5) + sep(8) + marker2(5)
    mat_off, gs_off = _OFFSET_GS_OFFSETS[role]

    sep = bytes([0xff, 0x00] * 4)
    trailing = mat_off  # coincides with mat_off except in the '222' deflated case below
    if role == '212':
        groupB_val = 128 if row_offset > 0 else 163
        col2_section = _halfblock(groupB_val) + _halfblock(0x20) * (2 if row_offset != 0 else 1)
        last_section = _halfblock(groupB_val) + _halfblock(0x20)
    else:
        groupB_val = 163
        if row_offset > 0:
            col2_section = _halfblock(groupB_val) + _halfblock(0x20)
            last_section = _halfblock(groupB_val)
            mat_off = mat_off + 2  # deflated case: mat byte AND groups start both shift
            gs_off = gs_off + 2
            trailing = mat_off
        else:
            col2_section = _halfblock(groupB_val) + _halfblock(0x20) * (2 if row_offset != 0 else 1)
            last_section = _halfblock(groupB_val) + _halfblock(0x20)
    mat_byte_pos = lme + mat_off
    gs = lme + gs_off
    groups = (_halfblock(groupA_val) + _halfblock(0x20)
              + sep + col2_section
              + sep + last_section)
    scan_len = gs + len(groups) + trailing

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, pos1 + 5, pos1 + 13, flip=True)  # gap after odd-length marker1
    _fill_background(scan, lme, scan_len, flip=False)

    scan[pos1:pos1 + 5] = _marker(marker1)
    scan[pos1 + 13:pos1 + 18] = _marker(marker2)
    scan[mat_byte_pos] = mat_counter & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan)


# ---------------------------------------------------------------------------
# Offset/staggered voxel sets, Ncols=3, '212' family only -- re-derived from
# export 1927 (3 columns at y=-0.5/-1.5/-2.5, same-sign, uniform step=1
# between each adjacent pair). NOT a simple extension of the Ncols=2 case
# above: the MARKER values use a PER-ADJACENT-STEP convention (each extra
# marker = plain_xstep - 35*(offset_i - offset_{i-1}), i.e. the step size
# relative to the PREVIOUS column, not cumulative from col1 -- both extra
# markers were 164 here since every step was exactly 1), while the GROUPS
# section's per-column values use CUMULATIVE offset from col1 instead
# (col2's section used 163-35*1=128, col3's used 163-35*2=93 -- genuinely
# different values, unlike the markers).
#
# Reconciling Ncols=2's "last_section" with this case: at Ncols=2 there's
# ONE real extra-column section (col2's, 2 fillers if offset!=0) PLUS a
# trailing "echo" section that just repeats col2's value with exactly 1
# filler -- this looked at the time like "the last column's section always
# gets 1 filler", but it's actually a SEPARATE, ALWAYS-present echo of
# col2 specifically. At Ncols=3, this becomes unambiguous: there are TWO
# real per-column sections (col2's value, 2 fillers; col3's CUMULATIVE
# value, 2 fillers) PLUS the SAME trailing echo section, which still
# echoes col2 specifically (NOT col3) -- confirming the echo is a fixed
# structural element, not a "last column" rule. '222' family was NOT
# validated by this test (the test construct placed all real content on
# the negative-y side, so '222' showed no genuine offset-related content)
# -- this function is '212'-only until '222' is tested directly. mat_off/
# gs_off both shift -8 from the Ncols=2 baseline (confirmed only at this
# one step, not verified to keep scaling linearly for Ncols>=4); trailing
# still equals mat_off, consistent with the rest of this module.
# ---------------------------------------------------------------------------

def generate_offset_212family_multicol_scan(plain_own_val, plain_xstep, row_offsets, mat_counter, pos1):
    """Ncols>=3 (row_offsets is a list of CUMULATIVE offsets from col1, one
    per extra column, length Ncols-1), '212' family only, all-same-sign
    (positive row_offsets) case. Returns scan bytes (mc is passed in
    directly as mat_counter, not computed -- not yet re-derived for this
    shape)."""
    Ncols = len(row_offsets) + 1
    marker1 = (plain_own_val + 35) % 256
    steps = [row_offsets[0]] + [row_offsets[i] - row_offsets[i - 1] for i in range(1, len(row_offsets))]
    extra_markers = [(plain_xstep - 35 * s) % 256 for s in steps]

    marker_span = 5 + 13 * len(row_offsets)
    lme = pos1 + marker_span
    mat_off, gs_off = 296 - 8 * (Ncols - 2), 316 - 8 * (Ncols - 2)
    mat_byte_pos = lme + mat_off
    gs = lme + gs_off

    groupA_val = (marker1 + 19) % 256
    sep = bytes([0xff, 0x00] * 4)
    groupA_section = _halfblock(groupA_val) + _halfblock(0x20)
    col_sections = []
    for off in row_offsets:
        groupB_val = (163 - 35 * off) % 256
        n_fillers = 2 if off != 0 else 1
        col_sections.append(_halfblock(groupB_val) + _halfblock(0x20) * n_fillers)
    echo_val = (163 - 35 * row_offsets[0]) % 256
    echo_section = _halfblock(echo_val) + _halfblock(0x20)
    groups = groupA_section
    for sec in col_sections:
        groups += sep + sec
    groups += sep + echo_section
    trailing = mat_off  # confirmed via 1927, consistent with the rest of the module
    scan_len = gs + len(groups) + trailing

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, pos1 + 5, pos1 + 13, flip=True)  # gap after odd-length marker1
    p = pos1 + 13
    scan[p:p + 5] = _marker(extra_markers[0])
    p += 5
    for m in extra_markers[1:]:
        _fill_background(scan, p, p + 8, flip=False)
        p += 8
        scan[p:p + 5] = _marker(m)
        p += 5
    assert p == lme
    _fill_background(scan, lme, scan_len, flip=True)

    scan[pos1:pos1 + 5] = _marker(marker1)
    scan[mat_byte_pos] = mat_counter & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan)


# ---------------------------------------------------------------------------
# Offset/staggered voxel sets, CROSS-CHUNK sign-crossing -- chases the gap
# found post-hoc when checking the Ncols=3 same-sign formula above against
# export 1925 (3 columns: col1 y=-0.5 [cy=1 alone], col2 y=+0.5 + col3
# y=+1.5 [cy=2 together] -- a sign crossing relative to col1, split across
# TWO h3 chunks since cy splits at y=0, same convention as cx splitting at
# x=0). Re-derived by comparing 1925 directly against the established
# Ncols=2 sign-crossing baseline (1804: col1+col2 only, row_offset=-1).
#
# KEY FINDING: cy=1 (the chunk containing the anchor, col1) is COMPLETELY
# UNAFFECTED by col3's existence -- byte-IDENTICAL to 1804's role212 chunk.
# col3 is invisible from the anchor chunk's perspective; it's tracked
# ENTIRELY within cy=2 (the chunk physically containing col2/col3) instead.
# So generate_offset_212family_scan(role, ..., row_offset=-1, ...) called
# on the anchor's own role/chunk needs NO changes at all.
#
# cy=2's structure generalizes 1804's established 1-extra-marker shape:
#   marker1 = (plain_own_val[role] + 35) % 256          (cy=2's OWN anchor
#             identity, e.g. role222's own_val -- unrelated to col1)
#   marker[i] for i=1..n_extra = 234 (== plain_xstep+35, the FLAT sign-
#             crossing value) for EVERY extra marker, NOT a per-adjacent-
#             step value -- once a sign crossing exists anywhere in the
#             sequence, ALL extra markers flatten to this single value
#             rather than encoding individual relative positions (unlike
#             the same-sign Ncols=3 case, which DOES distinguish per-step).
#   groups = groupA_section(groupA=(marker1+19)%256, 1 filler) +
#            n_extra * [SEP + middle_section(163, 2 fillers)] +
#            SEP + echo_section(163, 1 filler)            (the SAME
#            trailing-echo structural element found in the same-sign
#            Ncols=3 case above, generalizing 1804's n_extra=1 case, which
#            already had exactly this groupA+middle+echo shape)
#   mat_off/gs_off shift -10 per extra marker beyond the n_extra=1
#       baseline (304, 314 for '222') -- confirmed only at n_extra=1->2.
#   mc: NO formula derived -- pass in directly (measured 732 for n_extra=2
#       vs 712 baseline, no clean per-step constant found).
#
# SCOPE: confirmed only for role222 as the "other" chunk, n_extra in
# {1,2}, uniform +1 same-sign steps among the crossed columns. Whether
# role212 can ALSO be the "other" chunk (i.e. anchor on the positive
# side, crossing to negative), or whether non-uniform steps among the
# crossed columns change anything, is untested.
# ---------------------------------------------------------------------------

def generate_offset_crosschunk_other_scan(role, plain_own_val, n_extra, mat_counter, pos1):
    """The "other" chunk (not containing the anchor column) in a cross-
    chunk sign-crossing offset/staggered construct. n_extra = number of
    columns on this chunk's side (1 for the established 1804 baseline, 2
    for 1925's 3-column case). Returns scan bytes."""
    marker1 = (plain_own_val + 35) % 256
    crossing_marker = 234  # plain_xstep(199) + 35, flat regardless of step
    groupA_val = (marker1 + 19) % 256

    marker_span = 5 + 13 * n_extra
    lme = pos1 + marker_span
    base_mat_off, base_gs_off = _OFFSET_GS_OFFSETS['222']
    shift = -10 * (n_extra - 1)
    mat_off = base_mat_off + shift
    gs_off = base_gs_off + shift
    mat_byte_pos = lme + mat_off
    gs = lme + gs_off

    sep = bytes([0xff, 0x00] * 4)
    groupA_section = _halfblock(groupA_val) + _halfblock(0x20)
    middle_section = _halfblock(163) + _halfblock(0x20) * 2
    echo_section = _halfblock(163) + _halfblock(0x20)
    groups = groupA_section
    for _ in range(n_extra):
        groups += sep + middle_section
    groups += sep + echo_section
    trailing = mat_off
    scan_len = gs + len(groups) + trailing

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, pos1 + 5, pos1 + 13, flip=True)  # gap after odd-length marker1
    p = pos1 + 13
    scan[p:p + 5] = _marker(crossing_marker)
    p += 5
    for _ in range(n_extra - 1):
        _fill_background(scan, p, p + 8, flip=False)
        p += 8
        scan[p:p + 5] = _marker(crossing_marker)
        p += 5
    assert p == lme
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))

    scan[pos1:pos1 + 5] = _marker(marker1)
    scan[mat_byte_pos] = mat_counter & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan)


# ---------------------------------------------------------------------------
# Far-edge chunks. The XS valid coordinate range's single farthest column on
# each axis/sign (e.g. x=+30.5, x=-31.5) gets its own dedicated h3 chunk
# index beyond the normal {1,2} pair (cx=3 for the positive far edge, cx=0
# for the negative far edge; same pattern for cy/cz). Re-derived from raw
# export bytes per export; each of the 6 axis/sign combinations turned out
# to have genuinely distinct behavior -- no single unifying formula, per
# h3_lowrow_scanners.md's "Complete summary" section (confirmed correct
# this session for the cases implemented below, not assumed from the prose).
#
# Y positive far edge (y=+30.5), ISOLATED (no other content) -- confirmed
# via export 1739: this is a PURE ROLE RELABEL, no new formula at all. The
# chunk that would normally be (cx,1,*) under the established baseline
# formulas instead gets written to (cx,2,*), and (cx,2,*)'s normal content
# gets written to (cx,3,*) instead -- byte-for-byte identical to calling
# generate_212_scan/generate_222_scan/generate_112_scan/generate_122_scan
# exactly as established, just at shifted chunk coordinates. No dedicated
# function needed -- callers should generate scans with the plain Phase 1
# functions and write cz2->(cx,2,cz), cz1->(cx,3,cz) (i.e. cy+1 from the
# normal cy={1,2} pair) when building a y=+30.5 far-edge construct.
# ---------------------------------------------------------------------------

# X negative far edge (x=-31.5), ISOLATED -- confirmed via export 1737:
# reuses generate_zspan_side_scan UNCHANGED (single marker, no cross-flag),
# just with the established universal "+35"/-35" signal applied to each
# role's plain Ye=1 baseline, written at the role-shifted chunk pair
# {0,1} instead of {1,2} (cx=1 takes over the '212'/'222' main role's
# normal pos1/offsets, cx=0 takes over '112'/'122' boundary role's).
#
#   marker = (plain_baseline_Ye1 + 35) % 256
#   mc     = plain_mc - 35
#   role's own established pos1 (29/19/335/325) is UNCHANGED by the shift.
#
# Usage: generate_zspan_side_scan(role, (baseline+35)%256, mc-35, established_pos1)
# written to chunk (cx-1, cy, cz) for the '212'/'222' roles' cx, and
# (cx-1, cy, cz) for '112'/'122' likewise (i.e. just cx -= 1 uniformly).

# Y negative far edge (y=-31.5), ISOLATED -- confirmed via export 1745:
# same role-shift + zspan-reuse pattern as X negative, but DOUBLED signal
# (+70/-70 instead of +35/-35), role-shift is cy -= 1 (not cx). THREE of
# the four chunks reuse their established pos1/gs offsets completely
# unchanged; the '122' role specifically (written at (1,1,*) instead of
# its usual (1,2,*)) needs adjusted offsets -- pos1 shifts from 325 to 327,
# and gs_off shifts from 329 to 326 (mat_off/trailing unchanged at 8).
_YNEG_122_POS1 = 327
_YNEG_122_GS_OFF = 326


def generate_yneg_faredge_122_scan(marker_val, mat_counter):
    """'122' role written at the Y-negative-far-edge-shifted chunk position
    (cy=1 instead of the normal cy=2). marker_val = (193 + 70) % 256 for the
    isolated case; mat_counter = 695 - 70."""
    pos1 = _YNEG_122_POS1
    lme = pos1 + 5
    gs = lme + _YNEG_122_GS_OFF
    mat_byte_pos = lme + 8
    groups = _zspan_groups(marker_val)
    scan_len = gs + len(groups) + 8

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip=True)
    scan[pos1:pos1 + 5] = _marker(marker_val)
    scan[mat_byte_pos] = mat_counter & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan)


# ---------------------------------------------------------------------------
# X positive far edge (x=+30.5) -- introduces a genuinely NEW chunk-pairing
# relationship (cx=3 is a dedicated far-edge chunk, paired with cx=2 via
# "+32", mirroring how cz=1/cz=2 pair near the origin) rather than reusing
# an existing mechanism. Re-derived from export 1735 (isolated: x=+30.5
# alone, Nc_normal=0 -- no other x columns at all, so cx=1 doesn't even
# appear). SCOPE: Nc_normal=0 (isolated) only; h3_lowrow_scanners.md
# documents Nc_normal=1/2 marker formulas for cx=2 when paired with
# additional normal columns, not implemented here.
#
#   cx=2 (the "main" position, paired with the far edge):
#     marker = own_role's own_val(Ye=1) + 76   (178=baseline(1)+177? -- NOT a
#              clean small offset; treated as its own measured constant per
#              role here, NOT decomposed further -- see exact values below)
#     groupA = (marker + 19) % 256   (same relationship as everywhere else)
#     groupB = 163 (the familiar plain-Ye=1 constant)
#     groups = [groupA,32] [sep 8B] [163,32]  (same simple 2-pair shape as
#              the plain Nc=1,Ye=1 baseline, just at new pos1/gs offsets)
#   cx=3 (the far-edge chunk itself, wholly independent of cx=2's content):
#     marker = cx2_marker - 32   (the "+32" pairing, mirroring cz1=cz2+32)
#     groupA = (marker - 36) % 256   (NOT the usual +19 -- a different,
#              far-edge-specific relationship)
#     groups = [groupA, 32]   (just ONE pair, no second groupB pair at all --
#              minimal content, consistent with mc behaving as a pure binary
#              "edge present" flag rather than tracking real geometry)
#
# Both isolated-mc values (710/550 for cx=2; 742/582 for cx=3) are FIXED
# regardless of Nc -- pass them in directly as mat_counter, no formula needed.
# ---------------------------------------------------------------------------

_XPOS_FAREDGE_MAIN_OFFSETS = {'212': (315, 18, 324), '222': (307, 28, 326)}
_XPOS_FAREDGE_EDGE_OFFSETS = {'212': (9, 324, 334), '222': (1, 334, 336)}


def generate_xpos_faredge_main_scan(role, marker_val, mat_counter, Nc_normal=0):
    """cx=2, paired with the X positive far edge. role in {'212','222'}
    (cy=1 or cy=2 respectively). marker_val is the ANCHOR value -- at
    Nc_normal=0 this is the isolated baseline (178/82); at Nc_normal>=1,
    caller should pass (baseline + 55*lx_FAR) % 256, where lx_FAR is the
    distance from the edge to the normal column farthest from it (closest
    to true origin).

    Nc_normal>=1 generalization (confirmed via export 1919, Nc_normal=1,
    lx_near=1): an EARLIER pass had documented `baseline+35-55*lx_near`
    using an ABSOLUTE local-x convention for lx_near, derived from exports
    1741/1743/1790 -- but those turned out to be confounded (re-decoding
    them directly produced an inexplicable second half-block cluster this
    session). This fresh, minimal test shows the TRUE formula is simpler:
    `baseline + 55*lx_near` with lx_near measured as DISTANCE FROM THE
    EDGE, no separate "+35" term. marker_count becomes Nc_total=Nc_normal+1
    (1 anchor + Nc_normal copies of the universal xstep=199, Ye=1 N=1
    convention -- same shape as every other Nc-tracking case in this
    module). groupB section repeats Nc_total times (not just once), each
    with its OWN preceding 8-byte separator (not the usual "one sep before
    the first" convention). `pos1` and `gs_off` both shift -10*Nc_normal
    from their Nc_normal=0 baseline; `mat_off` (and therefore `trailing`,
    which still equals mat_off) stays FIXED. Only confirmed at
    Nc_normal=1 -- Nc_normal>=2 is NOT re-verified after discovering 1790
    was confounded, despite 1790 superficially appearing consistent with
    this same shape."""
    base_pos1, mat_off, base_gs_off = _XPOS_FAREDGE_MAIN_OFFSETS[role]
    pos1 = base_pos1 - 10 * Nc_normal
    gs_off = base_gs_off - 10 * Nc_normal
    Nc_total = Nc_normal + 1
    marker_span = 5 + 13 * Nc_normal
    lme = pos1 + marker_span
    gs = lme + gs_off
    mat_byte_pos = lme + mat_off
    groupA_val = (marker_val + 19) % 256
    groupA_section = _halfblock(groupA_val) + _halfblock(0x20)
    groupB_section = bytes([0xff, 0x00] * 4) + _halfblock(163) + _halfblock(0x20)
    groups = groupA_section + groupB_section * Nc_total
    scan_len = gs + len(groups) + mat_off  # trailing == mat_off, confirmed via 1735/1919

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[pos1:pos1 + 5] = _marker(marker_val)
    p = pos1 + 5
    for _ in range(Nc_normal):
        _fill_background(scan, p, p + 8, flip=True)
        p += 8
        scan[p:p + 5] = _marker(199)
        p += 5
    assert p == lme
    scan[mat_byte_pos] = mat_counter & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan)


def generate_xpos_faredge_edge_scan(role, cx2_marker_val, mat_counter):
    """cx=3, the far-edge chunk itself -- wholly independent of cx=2's
    content. role in {'212','222'}."""
    pos1, mat_off, gs_off = _XPOS_FAREDGE_EDGE_OFFSETS[role]
    lme = pos1 + 5
    gs = lme + gs_off
    mat_byte_pos = lme + mat_off
    marker_val = (cx2_marker_val - 32) % 256
    groupA_val = (marker_val - 36) % 256
    groups = _halfblock(groupA_val) + _halfblock(0x20)
    scan_len = gs + len(groups) + mat_off  # trailing == mat_off, confirmed via 1735

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip=True)
    scan[pos1:pos1 + 5] = _marker(marker_val)
    scan[mat_byte_pos] = mat_counter & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan)


# ---------------------------------------------------------------------------
# Z positive far edge (z=+30.5), ISOLATED -- confirmed via export 1747:
# matches X positive far edge's "+32" pairing mechanism exactly (NOT a new
# mechanism), but the *marker* itself reuses the established multi-z anchor
# formula shape directly: marker = (baseline_Ye1 + lz_far + lz_near_implicit
# + 7) % 256 with lz_near hardcoded at 14 (the same implicit reference used
# everywhere else) and lz_far=30. Despite reusing that formula shape, this
# is NOT actual multi-z (N=1 throughout, plain groupB=163 constant, no
# z-stacking) -- it's the far-edge mechanism coincidentally producing the
# same marker value shape. 3 of 4 roles reuse generate_zspan_side_scan
# completely unchanged; '122' needs gs_off=326 instead of zspan's normal 329
# (pos1/mat_off unchanged) -- same family of small per-role offset
# quirks seen elsewhere (Y-negative far edge's '122', 222's cz=1 shift).
#
#   marker(role) = (single_z_own_val_Ye1 + 30 + 14 + 7) % 256
#   mc(role)     = single_z_mc_Ye1 - (30 + 21)   [refines the old "constant
#                  -35" multi-z mc finding: it's really lz_far+21, which
#                  equals 35 only at the lz_far=14 used by every earlier test]
# ---------------------------------------------------------------------------

def generate_zpos_faredge_scan(role, marker_val, mat_counter, pos1):
    """Z positive far edge, isolated. role in {'212','222','112','122'}."""
    if role != '122':
        return generate_zspan_side_scan(role, marker_val, mat_counter, pos1)
    lme = pos1 + 5
    gs = lme + 326
    mat_byte_pos = lme + 8
    groups = _zspan_groups(marker_val)
    scan_len = gs + len(groups) + 8

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip=True)
    scan[pos1:pos1 + 5] = _marker(marker_val)
    scan[mat_byte_pos] = mat_counter & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan)


def generate_zpos_faredge_pair_scan(role, marker_val_cz2, mat_counter_cz2, pos1):
    """Z positive far edge -- generates BOTH cz=2 and cz=3 scans for one
    role. cz=3's marker is cz2_marker-32 (mirroring the X-positive "+32"
    pairing), but its groups section is NOT a simple reuse: every
    half-block uses N=0 (not 1) with VALUES shifted +1 (groupA=marker_cz2's
    own +19+1, groupB=163+1=164, default=33 instead of 32) -- confirmed via
    raw bytes (1747), not derivable from the cz=2 shape by a clean rule.
    mc: cz3 = cz2 + 32 (opposite sign from the marker, matching the
    established convention used throughout this project)."""
    cz2_scan = generate_zpos_faredge_scan(role, marker_val_cz2, mat_counter_cz2, pos1)

    marker_cz3 = (marker_val_cz2 - 32) % 256
    mc_cz3 = mat_counter_cz2 + 32
    lme = pos1 + 5
    gs = pos1 + _ZSPAN_GS_OFFSET[role]
    mat_byte_pos = lme + _ZSPAN_MAT_OFFSET[role]
    groupA_val = (marker_cz3 + 19 + 1) % 256
    groupB_val = (163 + 1) % 256
    groups = (_halfblock(groupA_val, 0) + _halfblock(33, 0)
              + bytes([0xff, 0x00] * 4)
              + _halfblock(groupB_val, 0) + _halfblock(33, 0))
    scan_len = gs + len(groups) + _ZSPAN_MAT_OFFSET[role]

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    _fill_background(scan, lme, scan_len, flip=True)
    scan[pos1:pos1 + 5] = _marker(marker_cz3)
    scan[mat_byte_pos] = mc_cz3 & 0xff
    scan[gs:gs + len(groups)] = groups
    cz3_scan = bytes(scan)

    return cz2_scan, cz3_scan, mc_cz3


# ---------------------------------------------------------------------------
# Z negative far edge (z=-31.5), ISOLATED -- confirmed via export 1750.
# Simpler than Z positive: the marker REUSES the original near-origin
# cz1/cz2-pairing formula verbatim (own_val_Ye1 + 21, i.e. lz_far=14,
# lz_near=0 -- completely ignoring this test's actual lz=31 magnitude),
# paired with the SECOND chunk via the same "+32" relationship, and BOTH
# chunks' groups sections are the plain generate_zspan_side_scan shape (no
# Z-positive-style "+1/N=0" complication on the paired chunk). Only the
# '122' role needs the gs_off=326 adjustment (shared with
# generate_zpos_faredge_scan's '122' case) -- so this reuses that function
# directly rather than duplicating it.
#
#   marker(cz1, "near" position) = (single_z_own_val_Ye1 + 21) % 256
#   mc(cz1)  = single_z_mc_Ye1 - 21   (does NOT match the original
#              near-pairing's mc shift of 35 -- genuinely its own value)
#   marker(cz0, "far" position)  = (marker_cz1 + 32) % 256
#   mc(cz0)  = mc_cz1 + 32
# ---------------------------------------------------------------------------

def generate_zneg_faredge_pair_scan(role, marker_cz1, mat_counter_cz1, pos1):
    """Z negative far edge -- generates BOTH cz=1 (near) and cz=0 (far)
    scans for one role. Returns (cz1_scan, cz0_scan, mc_cz0). cz1 uses the
    plain zspan shape for ALL roles including '122' (confirmed via 1750 --
    unlike cz0, which DOES need '122's special gs_off=326 adjustment, same
    as Z-positive's far chunk)."""
    cz1_scan = generate_zspan_side_scan(role, marker_cz1, mat_counter_cz1, pos1)
    marker_cz0 = (marker_cz1 + 32) % 256
    mc_cz0 = mat_counter_cz1 - 32
    cz0_scan = generate_zpos_faredge_scan(role, marker_cz0, mc_cz0, pos1)
    return cz1_scan, cz0_scan, mc_cz0
_CORNER_2X2X2_TEMPLATES = {
    (2, 1, 2): (19, 575, bytes.fromhex("4c010201002001020100ff00ff00ff00ff00a3010201002001020100ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff003f00ff00ff00ff00ff005f01027e7e7e02001f01027e7e7e02001f01027e7e7e007e7e8c007e7e7e0000ff00ff00ff00ff007f01027e7e7e02001f01007e7e7e00000001007e7e7e00001f01008c7e7e00000001008c7e7e0000ff00ff00ff00ff007f01027e7e7e02001f01027e7e7e02001f01027e7e7e007e7e8c007e7e7e0000ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00")),
    (2, 2, 2): (9, 671, bytes.fromhex("ec010201002001020100ff00ff00ff00ff00a3010201002001020100ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff009f01027e7e7e02001f01027e7e7e02001f01027e7e7e0200ff00ff00ff00ff007f01027e7e7e02001f01007e7e7e00000001007e7e7e00001f01027e7e7e0200ff00ff00ff00ff007f01027e7e7e02001f01027e7e7e02001f01027e7e7e0200ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00")),
    (1, 2, 2): (317, 639, bytes.fromhex("0c010201002001020100ff00ff00ff00ff00a3010201002001020100ff00ff00ff00ff007f00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff001f01027e7e7e02001f01027e7e7e02001f01027e7e7e0200ff00ff00ff00ff007f01027e7e7e02001f01007e7e7e00000001007e7e7e00001f01027e7e7e0200ff00ff00ff00ff007f01027e7e7e007e7e8c007e7e7e00001f01007e8c7e00000001007e8c7e00001f01027e7e7e007e7e8c007e7e7e0000ff00ff00ff00ff00")),
    (1, 1, 2): (325, 543, bytes.fromhex("6c010201002001020100ff00ff00ff00ff00a30102010020010201001f00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff007f01027e7e7e02001f01027e7e7e02001f01027e7e7e007e7e8c007e7e7e0000ff00ff00ff00ff007f01027e7e7e02001f01007e7e7e00000001007e7e7e00001f01008c7e7e00000001008c7e7e0000ff00ff00ff00ff007f01027e7e7e007e7e8c007e7e7e00001f01007e8c7e00000001007e8c7e00001f01007e7e7e00000001007e7e7e0000")),
    (2, 1, 1): (19, 543, bytes.fromhex("6c010201002001020100ff00ff00ff00ff00a3010201002001020100ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff001f00ff00ff00ff00ff007f01027e7e7e02001f01027e7e7e017e8c7e00001f01027e7e7e007e7e8c007e7e7e0000ff00ff00ff00ff007f01027e7e7e018c7e7e00001f01007e7e7e00002101008c7e7e0000ff00ff00ff00ff008101027e7e7e02001f01027e7e7e017e8c7e00001f01027e7e7e007e7e8c007e7e7e0000ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00")),
    (2, 2, 1): (11, 639, bytes.fromhex("0c010201002001020100ff00ff00ff00ff00a3010201002001020100ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff007f001f01027e7e7e02001f01027e7e7e017e8c7e00001f01027e7e7e0200ff00ff00ff00ff007f01027e7e7e018c7e7e00001f01007e7e7e00002101027e7e7e018c7e7e0000ff00ff00ff00ff007f01027e7e7e02001f01027e7e7e017e8c7e00001f01027e7e7e0200ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00")),
    (1, 2, 1): (317, 607, bytes.fromhex("2c010201002001020100ff00ff00ff00ff00a3010201002001020100ff00ff00ff00ff005f00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff003f01027e7e7e02001f01027e7e7e017e8c7e00001f01027e7e7e0200ff00ff00ff00ff007f01027e7e7e018c7e7e00001f01007e7e7e00002101027e7e7e018c7e7e0000ff00ff00ff00ff007f01027e7e7e007e7e8c007e7e7e00001f01007e8c7e00002101027e7e7e007e7e8c007e7e7e0000ff00ff00ff00ff00")),
    (1, 1, 1): (325, 513, bytes.fromhex("8c010201002001020100ff00ff00ff00ff00a3010201002001020100ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff009f01027e7e7e02001f01027e7e7e017e8c7e00001f01027e7e7e007e7e8c007e7e7e0000ff00ff00ff00ff007f01027e7e7e018c7e7e00001f01007e7e7e00002101008c7e7e0000ff00ff00ff00ff008101027e7e7e007e7e8c007e7e7e00001f01007e8c7e00002101007e7e7e0000")),
}

def generate_3axis_corner_2x2x2_scan(cx, cy, cz):
    """The "true 3-axis corner" case: a literal 2x2x2 cube centered at the
    origin (x,y,z each in {-0.5,+0.5} -- all 3 axes spanning both signs
    simultaneously at Nc=1-each-side, the minimal trigger condition).

    SCOPE: this is a fully-specified, hardcoded template for this EXACT
    construct only, not a general parametrized formula. The full
    investigation (h3_lowrow_scanners.md, "true 3-axis corner" sections)
    found this case involves "Type A/B" chunk classification, cross-
    references between diagonally-opposite chunks' mc%256 values, and
    capped/uncapped HB-count families that differ per chunk in ways that
    resist a single clean closed-form rule even after extensive systematic
    re-verification. Given the practical goal is a working, byte-exact,
    importable 2x2x2 corner cube (the single most fundamentally important
    instance of this case), this function returns the exact validated
    bytes for whichever of the 8 corner chunks is requested, re-derived
    directly from export 1679 this session (not assumed from the
    pre-existing prose, which had needed multiple corrections previously).
    Returns (scan_bytes, mat_counter).
    """
    pos1, mc, suffix = _CORNER_2X2X2_TEMPLATES[(cx, cy, cz)]
    scan = bytearray(pos1) + bytearray(suffix)
    _fill_background(scan, 0, pos1)
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# role122 DENSE RECTANGULAR FILL (neg-x, pos-y chunk (1,2,2)) -- general
# Ncols x Yextent x Nz solid block. Derived 2026-06-20 via exports
# 1969/1975/1977/1979/1981/1983/1985/1991/1993/1995/1997/1999/2001/2003/
# 2005/2007/2009/2011/2013/2015/2017. See du_project.md "role122 DENSE-FILL:
# COMPLETE FORMULA SET" for the full derivation and confirmations.
#
# A solid fill with columns at local x = lx_near..lx_FAR (Ncols of them),
# rows at local y = ly_near..ly_far (Ye of them), z-levels lz_near..lz_far
# (Nz = N of them). All marker/groups VALUE formulas are exact; the only
# known residual is a -2 on mat_off at the single (Ye==29 AND N==29) corner.
# ---------------------------------------------------------------------------

def _isolated_122(lx, ly, lz):
    return (55 * lx + 35 * ly + lz + 48) % 256


def _n1_first_122(lx, ly, lz):
    return 4 + (153 * lx + 4 * ly + lz) // 31


def generate_122_dense_scan(lx_FAR, ly_near, Ncols, Ye, lz_near, lz_far, mat_counter=None, cz=2):
    """Generate the (1,2,2)/role122 scan for a solid Ncols x Ye x N fill.
    lx_FAR = largest local-x column; ly_near = smallest local-y row;
    lz_near/lz_far = z-run bounds (N = lz_far-lz_near+1). Returns (scan, mc).
    If mat_counter is None, mc is computed from the formula.

    BYTE-EXACT VALIDATED (2026-06-20) against 17 real in-game exports for
    N>=2, ly_near=1, (Ye,N) not both =29. KNOWN-UNSOLVED edges (assert-
    guarded): N=1 (thin single-z plate -- a structurally different case);
    ly_near>1 (mat_off/trailing acquire an unsolved ly split, only 3 data
    points so far); and the single (Ye>=29 AND N>=29) extreme corner
    (mat_off picks up a -2). See du_project.md 'role122 DENSE-FILL'."""
    N = lz_far - lz_near + 1

    # --- cz=1 (negative z) re-envelope: neg-x roles take anchor+zsh AND a
    # structural mat_off+38/gap2-38; mc shift = -zsh+36 (= 2*lz_near+6).
    # Validated exports 2258(lz5)/2263(lz1). (zsh=30-2*lz_near.)
    zsh = (30 - 2 * lz_near) if cz == 1 else 0

    # --- marker values ---
    own_val = _isolated_122(lx_FAR, ly_near, 14)
    anchor = (own_val + lz_near - 14 + zsh) % 256
    xstep = (234 - 35 * Ye - (N - 1)) % 256
    ystep = (304 - _EFF_LZ - N) % 256

    # --- mc ---
    mc = 512 + (308 - 35 * Ye - lz_far - 35 * ly_near - zsh + (36 if cz == 1 else 0)) % 256
    if mat_counter is not None:
        mc = mat_counter

    # --- group values ---
    groupA_val = (anchor + 19) % 256
    groupB_val = (163 - lz_far + lz_near - 35 * (Ye - 1)) % 256
    Y_val = (289 - N) % 256

    # --- structure ---
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ncols * Ye + sep_w * (Ncols - 1)
    # pos1: 317 - 2*ceil(153*lx_FAR/32), plus the period-5 ly drift.
    # The "/32" (chunk size) is exact where n1_first's "/31" floor drifts.
    pos1 = (317 - 2 * ((153 * lx_FAR + 31) // 32)
            + 2 * ((2 * ly_near + 5) // 14))   # ly drift = round((ly_near-1)/7)
    lme = pos1 + marker_span
    mat_off = (26 - 2 * (Ye // 8) - 2 * (ly_near // 7)
               - 2 * max(0, Ye // 7 + N // 7 - 7)   # extreme Ye&N corner
               + (38 if cz == 1 else 0))            # cz=1 neg-z structural add
    gap2 = (298 - 10 * (Ncols - 1) + 2 * ((55 * (Ncols - 2) + 208) // 256)
            + 2 * ((ly_near + 5) // 7)               # ly drift = ceil((ly_near-1)/7)
            - ((38 + 2 * (Ncols - 2)) if cz == 1 else 0))  # cz=1 neg-z (Nc2 -38, -2/col)

    if lx_FAR == 31:
        # ABSOLUTE neg-x edge (x=-31.5) touched: the MAIN chunk keeps all
        # dense content+pos1, but takes a far-edge ENVELOPE (mc now tracks
        # +55*Ncols like a boundary role; mat_off/gap2 swap to fixed
        # boundary values). Confirmed byte-exact 5/5 (exports 2053-2073).
        # (This generates the (1,2,2) MAIN chunk only; the spawned cx=0
        # boundary chunk + 6 empty placeholders are separate -- see
        # du_project.md far-edge notes.)
        mc = 512 + (139 + 55 * Ncols - 35 * Ye - lz_far - 35 * ly_near) % 256
        # edge mat_off: base 304 (vs normal 26), -10/col, but KEEPS the same
        # Ye/ly/corner correction terms as the normal mat_off above.
        mat_off += 278 - 10 * (Ncols - 2)
        gap2 = 12

    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    # --- groups section ---
    if N == 1:
        # N=1 (single-z plate, the non-multi-z case): each groupB section is
        # the SIMPLE [groupB + Ye*Y] shape (no extra-pair mechanism -- that's
        # multi-z-specific), but the inter-section SEP is still present
        # (it was just invisible at Ye>=22 where sep_w=0). Via 2059 (Ye=2).
        sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
        section_normal = _halfblock(groupA_val, 1) + _halfblock(Y_val, 1) * Ye
        section_groupb = _halfblock(groupB_val, 1) + _halfblock(Y_val, 1) * Ye
        groups = section_normal + (sep_groups + section_groupb) * Ncols
    else:
        # N>=2 (multi-z): 212-family shape, role122 substitutions.
        sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
        section_normal = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye
        section_extra = (_halfblock(groupB_val, N)
                         + (_halfblock(Y_val, 0) + _halfblock(N - 2, 0)) * (Ye - 1)
                         + _halfblock(Y_val, N))
        section_last = _halfblock(groupB_val, N) + _halfblock(Y_val, N) * Ye
        groups = section_normal
        for col in range(Ncols):
            groups += sep_groups + (section_extra if col < Ncols - 1 else section_last)

    trailing = mat_off
    scan_len = gs + len(groups) + trailing

    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)

    # marker section: per column [first, N] then (Ye-1)x [ystep, N]; sep between
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, N)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, N)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    assert p == lme, (p, lme)
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))

    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# role122 ABSOLUTE NEG-X EDGE (x=-31.5) -- the spawned chunks.
# Touching x=-31.5 (lx_FAR=31) makes generate_122_dense_scan emit the MAIN
# (1,2,2) chunk with its edge envelope (see that function). It ALSO spawns,
# for a single-quadrant (pos-y, cz=2) fill: one cx=0 boundary chunk (0,2,2)
# and 6 empty placeholder chunks. These two helpers cover those.
# Derived from exports 2053/2065/2067/2069/2071/2073. See du_project.md.
# ---------------------------------------------------------------------------

# Empty boundary-placeholder chunk: 671 bytes, all background except one byte
# (122) at offset 335; mat_counter = 378. Byte-identical for all 6 empties.
_EMPTY_CHUNK_MC = 378


def generate_122_edge_empty_scan():
    """The constant 671-byte empty boundary placeholder spawned in the
    quadrants with no content. Returns (scan, mc)."""
    scan = bytearray(671)
    _fill_background(scan, 0, 671)
    scan[335] = 122
    return bytes(scan), _EMPTY_CHUNK_MC


def generate_122_edge_cx0_scan(Ye, lz_near, lz_far, ly_near=1):
    """The cx=0 (0,2,2) far-edge boundary chunk spawned when a role122 fill
    touches x=-31.5. It encodes the edge column (lx=31) as a 1-column dense
    structure with anchor = MAIN_anchor + 32 (the classic far-edge +32
    pairing). Ncols-INDEPENDENT. Returns (scan, mc)."""
    N = lz_far - lz_near + 1
    main_anchor = (_isolated_122(31, ly_near, 14) + lz_near - 14) % 256
    anchor = (main_anchor + 32) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    groupA_val = (anchor + 19) % 256
    groupB_val = (163 - lz_far + lz_near - 35 * (Ye - 1)) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (98 + 93 * Ye - lz_far + 29 * ly_near) % 256

    pos1 = 327
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ye   # single column
    lme = pos1 + marker_span
    mat_off = 8 - 2 * ((Ye + 3) // 7) - 2 * ((ly_near + 2) // 7)
    gap2 = 318
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    section_normal = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye
    section_extra = (_halfblock(groupB_val, N)
                     + (_halfblock(Y_val, 0) + _halfblock(N - 2, 0)) * (Ye - 1)
                     + _halfblock(Y_val, N))
    groups = section_normal + sep_groups + section_extra

    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for _ in range(Ye - 1):
        scan[p:p + 5] = _marker(ystep, N)
        p += 5
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# role122 POS-X SPANNING-AWARENESS chunk (2,2,2). ALWAYS spawned alongside
# the (1,2,2) content chunk whenever neg-x role122 content exists (the pos-x
# boundary acknowledging the neg-x fill). A minimal 1-marker + 1-groups-
# section structure, Ncols-INDEPENDENT. Required for STANDALONE generation
# of any role122 dense fill (the (1,2,2) generator alone is not enough).
# Derived from the dense exports' (2,2,2) chunks (2026-06-20).
# SCOPE: values exact for all ly_near; structural offsets exact for
# ly_near=1 (the common case). ly_near>1 has a minor (<=2 byte) mat_off/gap2
# drift not yet fully pinned (see du_project.md).
# ---------------------------------------------------------------------------

def generate_122_spanning_222_scan(Ye, lz_near, lz_far, ly_near=1):
    """The (2,2,2) pos-x spanning-awareness chunk for a role122 fill.
    Returns (scan, mc). Ncols-independent."""
    N = lz_far - lz_near + 1
    anchor = (71 + lz_near + 35 * ly_near) % 256
    groupA_val = (anchor - 36) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (340 - 35 * Ye - lz_far - 35 * ly_near) % 256

    pos1 = 1 + 2 * ((ly_near - 1) // 6)
    marker_span = 5 * Ye   # single column
    lme = pos1 + marker_span
    mat_off = 332 - 2 * ((ly_near - 1) // 9)
    gap2 = 2 + 2 * ((ly_near - 1) // 7)
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    groups = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye   # no groupB
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for _ in range(Ye - 1):
        scan[p:p + 5] = _marker(ystep, N)
        p += 5
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# role122 Y+ EDGE (y=+30.5) boundary chunks. Touching y=+30.5 (ly=30) spawns
# a cy=3 boundary chunk-row. UNLIKE the x-edge, the Y+ edge does NOT
# re-envelope the (1,2,2) main chunk (it stays normal dense) -- it just adds
# these two boundary chunks (plus (2,2,2) spanning, already handled). Both
# are Ye-INDEPENDENT (they encode only the edge row ly=30).
# Derived from exports 2081/2083/2085/2087 (2026-06-20).
# ---------------------------------------------------------------------------

def generate_122_yedge_132_scan(Ncols, lz_near, lz_far):
    """The (1,3,2) Y-boundary chunk -- a single-row Ncols-column dense-like
    structure encoding the edge row (ly=30). Returns (scan, mc)."""
    N = lz_far - lz_near + 1
    anchor = (235 + 55 * Ncols) % 256
    xstep = (200 - N) % 256
    groupA_val = (anchor + 54) % 256
    Y_val = (199 - N) % 256
    mc = 512 + (87 - lz_far) % 256

    pos1 = 317 - 2 * ((153 * Ncols + 31) // 32)   # lx_FAR == Ncols here
    marker_span = 5 * Ncols + 8 * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 28
    gap2 = 288 - 10 * (Ncols - 2)
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    groups = _halfblock(groupA_val, N)
    for _ in range(Ncols):
        groups += bytes([0xff, 0x00]) * 4 + _halfblock(Y_val, N)
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for c in range(1, Ncols):
        _fill_background(scan, p, p + 8, flip=(c % 2 == 1))
        p += 8
        scan[p:p + 5] = _marker(xstep, N)
        p += 5
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_122_yedge_232_scan(N, lz_far):
    """The (2,3,2) Y-edge spanning-at-boundary chunk. Minimal: 1 marker +
    1 halfblock. Ncols- and Ye-independent. Returns (scan, mc)."""
    mc = 512 + (119 - lz_far) % 256
    pos1 = 1
    lme = pos1 + 5
    mat_off = 334
    gap2 = 2
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2
    groups = _halfblock(1, N)
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    scan[pos1:pos1 + 5] = _marker(2, N)
    _fill_background(scan, lme, scan_len, flip=True)   # 5-byte marker, odd
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# role122 Z+ EDGE (z=+30.5) boundary chunks. Touching z=+30.5 (lz=30) spawns
# a cz=3 boundary chunk-row. Like the Y+ edge (and UNLIKE the prior note
# suggesting X-like behavior), it does NOT re-envelope the (1,2,2) main
# chunk -- main + (2,2,2) spanning stay normal dense at lz_far=30. It adds
# two cz=3 boundary chunks that encode the edge z-PLANE (lz=30) as an
# Ncols x Ye, N=1 plate. Both are N-independent (depend only on the edge
# plane dims Ncols x Ye). Derived from 2091/2093/2095 (2026-06-20).
# Quirk: markers use N=1 but groups-halfblocks use N=0, with Y=33 (the N=1
# ystep value).
# ---------------------------------------------------------------------------

def generate_122_zedge_123_scan(Ncols, Ye, lx_near=1, ly_near=1):
    """The (1,2,3) role122 Z-boundary chunk -- dense N=1 plate of the edge
    z-level. lx_near/ly_near default to 1 (the z=+30.5 EDGE use). Passing the
    fill's lx_near/ly_near makes this ALSO the role122 z=0 Z-SPAN chunk (1,2,2)
    for negative-z adjacent fills -- same chunk, lx/ly-general. Validated z-edge
    Nc2/Nc3/Ye3 (2091/2093/2095) + z-span lx5/lx10 (2263/2275). Returns (scan,mc)."""
    lx_FAR = lx_near + Ncols - 1
    anchor = (46 + 55 * lx_FAR + 35 * ly_near) % 256   # Ye-INDEPENDENT
    xstep = (234 - 35 * Ye) % 256
    ystep = 33
    groupA_val = (anchor + 20) % 256
    groupB_val = (199 - 35 * Ye) % 256
    Y_val = 33
    mc = 512 + (275 - 35 * Ye - 55 * (lx_near - 1) - 35 * (ly_near - 1)) % 256

    pos1 = (317 - 2 * ((153 * lx_FAR + 31) // 32)
            + 2 * ((2 * ly_near + 5) // 14))            # neg-x envelope + ly drift
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ncols * Ye + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 16 - 2 * (Ye // 8) + 2 * ((153 * lx_near + 16) // 32)
    gap2 = pos1 - 9 + 2 * ((55 * (Ncols - 2) + 208) // 256)
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    sec_n = _halfblock(groupA_val, 0) + _halfblock(Y_val, 0) * Ye
    sec_b = _halfblock(groupB_val, 0) + _halfblock(Y_val, 0) * Ye
    groups = sec_n + (sep_groups + sec_b) * Ncols
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, 1)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, 1)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_122_zedge_223_scan(Ye):
    """The (2,2,3) Z-edge spanning-at-boundary chunk. Ncols/N-independent.
    Returns (scan, mc)."""
    mc = 512 + (307 - 35 * Ye) % 256
    pos1 = 1
    marker_span = 5 * Ye
    lme = pos1 + marker_span
    mat_off = 332
    gap2 = 2
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2
    groups = _halfblock(69, 0) + _halfblock(33, 0) * Ye
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(104, 1)
    p += 5
    for _ in range(Ye - 1):
        scan[p:p + 5] = _marker(33, 1)
        p += 5
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# role212 DENSE rectangular fill (pos-x, neg-y chunk (2,1,2)). The pos-x/neg-y
# MIRROR of role122: identical marker/groups STRUCTURE, value constants
# re-derived (sign-flipped x/y coefficients), offsets "mirrored" (mat_off
# carries the lx_FAR/Ncols dependence, gap2 tracks lx_near -- opposite of
# role122). Derived from exports 2101-2111 (2026-06-20).
#   lx_near = column closest to origin (smallest local-x; x=+1.5 -> lx_near=1)
#   ly_near = row closest to origin (smallest |y|; y=-1.5 -> ly_near=1)
#   lx_FAR = lx_near + Ncols - 1
# NOTE: role212 anchor has a -35*(Ye-2) term that role122 lacked (neg-y:
# growing Ye extends in -y, shifting the anchor); mc is Ye- AND N-independent
# (unlike role122's -35*Ye).
# SCOPE: validated for the tested ranges (lx_near/ly_near 1-2, Ye 2-3,
# Ncols 2-3, N=2, lz_near 1/5). Higher ranges + ly drift on offsets not yet
# swept (mirror role122's period-7 drifts when extending).
# ---------------------------------------------------------------------------

def generate_212_dense_scan(lx_near, ly_near, Ncols, Ye, lz_near, lz_far, cz=2):
    """role212 (2,1,2) pos-x/neg-y dense Ncols x Ye x N fill. Returns (scan, mc).
    cz=1 (negative z) applies the clean z-reflection shift zsh=30-2*lz_near
    (anchor+zsh, mc-zsh); pos-x roles structurally unchanged (export 2260)."""
    N = lz_far - lz_near + 1
    lx_FAR = lx_near + Ncols - 1
    zsh = (30 - 2 * lz_near) if cz == 1 else 0
    anchor = (243 - 55 * lx_near - 35 * ly_near + lz_near - 35 * (Ye - 2) + zsh) % 256
    xstep = (234 - 35 * Ye - (N - 1)) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    groupA_val = (anchor + 19) % 256
    groupB_val = (163 - lz_far + lz_near - 35 * (Ye - 1)) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (98 - 201 * lx_FAR + 35 * ly_near - lz_far - zsh) % 256

    pos1 = 27 + 2 * ((153 * lx_near + 31) // 32) - 2 * (ly_near // 7)
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ncols * Ye + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    # ceil/round-based growth (confirmed at high lx_near via 2117); the
    # earlier linear -8/+10 forms only held at lx_near=1,2.
    mat_off = 306 - 2 * ((306 * lx_FAR + 32) // 64) + 2 * ((ly_near + 5) // 7)   # round(lx)+ceil((ly-1)/7)
    ly_far = ly_near + Ye - 1
    if lx_FAR == 30 or ly_far == 31:
        mat_off -= 2   # ABSOLUTE edge touched (x=+30.5 or y=-31.5): light re-envelope
    gap2 = pos1 - 9
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    if N == 1:
        section_normal = _halfblock(groupA_val, 1) + _halfblock(Y_val, 1) * Ye
        section_groupb = _halfblock(groupB_val, 1) + _halfblock(Y_val, 1) * Ye
        groups = section_normal + (sep_groups + section_groupb) * Ncols
    else:
        section_normal = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye
        section_extra = (_halfblock(groupB_val, N)
                         + (_halfblock(Y_val, 0) + _halfblock(N - 2, 0)) * (Ye - 1)
                         + _halfblock(Y_val, N))
        section_last = _halfblock(groupB_val, N) + _halfblock(Y_val, N) * Ye
        groups = section_normal
        for col in range(Ncols):
            groups += sep_groups + (section_extra if col < Ncols - 1 else section_last)

    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, N)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, N)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_212_spanning_222_scan(lx_near, Ncols, lz_near, lz_far):
    """role212's pos-y spanning-awareness chunk (2,2,2). Spawned ONLY when
    the role212 fill has ly_near=1 (content adjacent to the y=0 plane it
    spans). A single-row Ncols-column structure. Returns (scan, mc)."""
    N = lz_far - lz_near + 1
    lx_FAR = lx_near + Ncols - 1
    anchor = (147 - 55 * lx_near + lz_near) % 256
    xstep = (200 - N) % 256
    groupA_val = (anchor + 54) % 256
    groupB_val = (199 - N) % 256
    mc = 512 + (229 + 55 * lx_FAR - lz_far) % 256

    pos1 = 19 + 2 * ((153 * lx_near + 31) // 32)
    marker_span = 5 * Ncols + 8 * (Ncols - 1)
    lme = pos1 + marker_span
    # ceil-based (confirmed at lx_near=29 via 2115); linear only held at lx 1,2
    mat_off = 306 - 2 * ((153 * lx_near + 31) // 32) - 10 * (Ncols - 2)
    gap2 = pos1 - 9
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep = bytes([0xff, 0x00]) * 4
    groups = _halfblock(groupA_val, N)
    for _ in range(Ncols):
        groups += sep + _halfblock(groupB_val, N)
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for c in range(1, Ncols):
        _fill_background(scan, p, p + 8, flip=(c % 2 == 1))
        p += 8
        scan[p:p + 5] = _marker(xstep, N)
        p += 5
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_212_xedge_312_scan(Ye, lz_near, lz_far, ly_near=1):
    """role212 pos-x edge (x=+30.5) cx=3 boundary chunk (3,1,2). Encodes the
    edge column as a single-column, Ye-row structure. The (3,2,2) boundary-
    spanning chunk reuses generate_122_yedge_232_scan(N, lz_far). Returns
    (scan, mc). Ncols-independent."""
    N = lz_far - lz_near + 1
    anchor = (132 - 35 * Ye + lz_near - 35 * (ly_near - 1)) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    groupA_val = (anchor - 36) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (23 - lz_far) % 256

    pos1 = 9
    marker_span = 5 * Ye
    lme = pos1 + marker_span
    mat_off = 326
    gap2 = 10 - 2 * (Ye - 2)
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    groups = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for _ in range(Ye - 1):
        scan[p:p + 5] = _marker(ystep, N)
        p += 5
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_212_negyedge_202_scan(Ncols, lz_near, lz_far):
    """role212 neg-y edge (y=-31.5) cy=0 boundary chunk (2,0,2). Encodes the
    edge row (ly=31) as a single-row Ncols-column structure. Ye- AND
    Ncols-position-independent (only Ncols count matters). Returns (scan, mc)."""
    N = lz_far - lz_near + 1
    anchor = (2 + lz_near) % 256
    xstep = (200 - N) % 256
    groupA_val = (anchor + 19) % 256
    Y_val = (289 - N) % 256
    groupB_val = (164 - N) % 256
    const = (N - 2) % 256
    mc = 512 + (63 - lz_far + 55 * Ncols) % 256

    pos1 = 39
    marker_span = 5 * Ncols + 8 * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 286 - 10 * (Ncols - 2)
    gap2 = 30
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep = bytes([0xff, 0x00]) * 4
    sec_normal = _halfblock(groupA_val, N) + _halfblock(Y_val, N)
    sec_extra = _halfblock(groupB_val, N) + _halfblock(Y_val, 0) + _halfblock(const, 0)
    sec_last = _halfblock(groupB_val, N) + _halfblock(Y_val, N)
    groups = sec_normal
    for col in range(Ncols):
        groups += sep + (sec_extra if col < Ncols - 1 else sec_last)
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for c in range(1, Ncols):
        _fill_background(scan, p, p + 8, flip=(c % 2 == 1))
        p += 8
        scan[p:p + 5] = _marker(xstep, N)
        p += 5
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_212_zedge_213_scan(Ncols, Ye, lx_near=1):
    """role212 z edge (z=+30.5) cz=3 boundary chunk (2,1,3): dense N=1 plate
    of the edge z-level with role212 boundary values. Returns (scan, mc)."""
    anchor = (221 - 35 * Ye) % 256
    xstep = (234 - 35 * Ye) % 256
    ystep = 33
    groupA_val = (anchor + 20) % 256
    groupB_val = (199 - 35 * Ye) % 256
    Y_val = 33
    mc = 512 + (135 - 201 * Ncols) % 256

    lx_FAR = lx_near + Ncols - 1
    pos1 = 27 + 2 * ((153 * lx_near + 31) // 32)
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ncols * Ye + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 306 - 2 * ((306 * lx_FAR + 32) // 64)
    gap2 = pos1 - 9
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    sec_n = _halfblock(groupA_val, 0) + _halfblock(Y_val, 0) * Ye
    sec_b = _halfblock(groupB_val, 0) + _halfblock(Y_val, 0) * Ye
    groups = sec_n + (sep_groups + sec_b) * Ncols
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, 1)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, 1)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_212_zedge_223_scan(Ncols, lx_near=1):
    """role212 z edge cz=3 spanning chunk (2,2,3). Ye-independent. Returns
    (scan, mc)."""
    anchor = 90
    xstep = 199
    groupA_val = (anchor + 55) % 256
    groupB_val = 199
    mc = 512 + (231 + 55 * Ncols) % 256

    pos1 = 19 + 2 * ((153 * lx_near + 31) // 32)
    marker_span = 5 * Ncols + 8 * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 306 - 2 * ((153 * lx_near + 31) // 32) - 10 * (Ncols - 2)
    gap2 = pos1 - 9
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep = bytes([0xff, 0x00]) * 4
    groups = _halfblock(groupA_val, 0)
    for _ in range(Ncols):
        groups += sep + _halfblock(groupB_val, 0)
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, 1)
    p += 5
    for c in range(1, Ncols):
        _fill_background(scan, p, p + 8, flip=(c % 2 == 1))
        p += 8
        scan[p:p + 5] = _marker(xstep, 1)
        p += 5
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# role222 DENSE fill (pos-x, pos-y chunk (2,2,2)) -- the "reference corner".
# SIMPLEST role: just the (2,2,2) content chunk + 7 empties, NO spanning chunk
# (it IS the corner everything else spans toward). Mirror of role122/212 with
# pos-x (-55*lx_near) + pos-y (+35*ly_near) conventions. Derived 2026-06-20
# (exports 2147-2157). Note (2,2,2) was the SPANNING chunk for role122/212;
# here it holds role222's own content -> its pos1/mat_off use the (2,2,2)
# chunk-position offsets (lx_near-based), not the (2,1,2)/(1,2,2) ones.
# ---------------------------------------------------------------------------

def generate_222_dense_scan(lx_near, ly_near, Ncols, Ye, lz_near, lz_far, cz=2):
    """role222 (2,2,2) pos-x/pos-y dense Ncols x Ye x N fill. Returns (scan, mc).
    cz=2 (positive z, default) or cz=1 (negative z, below center): cz=1 applies
    the clean z-reflection shift zsh=30-2*lz_near (anchor+zsh, mc-zsh) -- pos-x
    roles are structurally unchanged. Validated exports 2254/2256."""
    N = lz_far - lz_near + 1
    lx_FAR = lx_near + Ncols - 1
    zsh = (30 - 2 * lz_near) if cz == 1 else 0
    anchor = (217 - 55 * lx_near + 35 * ly_near + lz_near + zsh) % 256
    xstep = (234 - 35 * Ye - (N - 1)) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    groupA_val = (anchor + 19) % 256
    groupB_val = (163 - lz_far + lz_near - 35 * (Ye - 1)) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (124 - 201 * lx_FAR - 35 * ly_near - lz_far - 35 * (Ye - 2) - zsh) % 256

    # high-ly drift: pos1 and mat_off drift on period-7 with DIFFERENT phase
    # (mirror of role212's split-phase). Derived from non-edge ly sweep
    # (exports 2147/2153/2171/2173/2175 -> ly 1,2,10,15,22).
    pos1 = 19 + 2 * ((153 * lx_near + 31) // 32) + 2 * ((ly_near + 4) // 7)
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ncols * Ye + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = (304 - 2 * ((153 * lx_near + 31) // 32) - 10 * (Ncols - 2)
               - 2 * (ly_near // 7))
    gap2 = pos1 - 9
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    if N == 1:
        section_normal = _halfblock(groupA_val, 1) + _halfblock(Y_val, 1) * Ye
        section_groupb = _halfblock(groupB_val, 1) + _halfblock(Y_val, 1) * Ye
        groups = section_normal + (sep_groups + section_groupb) * Ncols
    else:
        section_normal = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye
        section_extra = (_halfblock(groupB_val, N)
                         + (_halfblock(Y_val, 0) + _halfblock(N - 2, 0)) * (Ye - 1)
                         + _halfblock(Y_val, N))
        section_last = _halfblock(groupB_val, N) + _halfblock(Y_val, N) * Ye
        groups = section_normal
        for col in range(Ncols):
            groups += sep_groups + (section_extra if col < Ncols - 1 else section_last)

    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, N)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, N)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_222_yedge_232_scan(lx_near, Ncols, lz_near, lz_far):
    """role222 pos-y edge (y=+30.5) cy=3 boundary chunk (2,3,2). Single-row
    Ncols-column spanning-style chunk encoding the edge row. role222-specific
    (NOT a reuse of role122's yedge_232). Returns (scan, mc)."""
    N = lz_far - lz_near + 1
    lx_FAR = lx_near + Ncols - 1
    anchor = (147 - 55 * lx_near + lz_near) % 256
    xstep = (200 - N) % 256
    groupA_val = (anchor + 54) % 256
    groupB_val = (199 - N) % 256
    mc = 512 + (229 + 55 * lx_FAR - lz_far) % 256

    pos1 = 19 + 2 * ((153 * lx_near + 31) // 32)
    marker_span = 5 * Ncols + 8 * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 306 - 2 * ((153 * lx_near + 31) // 32) - 10 * (Ncols - 2)
    gap2 = pos1 - 9
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep = bytes([0xff, 0x00]) * 4
    groups = _halfblock(groupA_val, N)
    for _ in range(Ncols):
        groups += sep + _halfblock(groupB_val, N)
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for c in range(1, Ncols):
        _fill_background(scan, p, p + 8, flip=(c % 2 == 1))
        p += 8
        scan[p:p + 5] = _marker(xstep, N)
        p += 5
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_222_zedge_223_scan(lx_near, ly_near, Ncols, Ye):
    """role222 z edge (z=+30.5) cz=3 boundary chunk (2,2,3): dense N=1 plate of
    the edge z-level at the (2,2,*) position, role222 values. Returns (scan, mc).
    NOTE: mat_off = 310-8*lx_FAR is linear (validated lx_FAR 2,3); may need
    ceil-residual hardening at high lx_FAR (same deferred class as 222 dense
    gap2)."""
    lx_FAR = lx_near + Ncols - 1
    anchor = (215 - 55 * lx_near + 35 * ly_near) % 256
    ystep = 33
    xstep = (234 - 35 * Ye) % 256
    groupA_val = (anchor + 20) % 256
    groupB_val = (199 - 35 * Ye) % 256
    Y_val = 33
    mc = 512 + (91 - 201 * lx_FAR - 35 * (Ye - 2)) % 256

    pos1 = 19 + 2 * ((153 * lx_near + 31) // 32)
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ncols * Ye + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 310 - 8 * lx_FAR
    gap2 = pos1 - 9
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    sec_n = _halfblock(groupA_val, 0) + _halfblock(Y_val, 0) * Ye
    sec_b = _halfblock(groupB_val, 0) + _halfblock(Y_val, 0) * Ye
    groups = sec_n + (sep_groups + sec_b) * Ncols
    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, 1)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, 1)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# role112 (neg-x, neg-y) -- THE LAST CORNER. Content chunk (1,1,2). Adjacent to
# BOTH center planes -> spawns THREE spanning chunks ((2,1,2) x, (1,2,2) y,
# (2,2,2) xy-corner) when lx_near=1 AND ly_near=1. Combines role122's neg-x
# envelope (large pos1, mat_off near-side / gap2 far-side) with role212's neg-y
# values (+35*ly in mc, -35*(Ye-2) in anchor, +2*ceil((ly-1)/7) mat_off drift).
# Derived 2026-06-21 (exports 2197-2207). Same group assembly as role122.
# ---------------------------------------------------------------------------

def generate_112_dense_scan(lx_near, ly_near, Ncols, Ye, lz_near, lz_far, cz=2):
    """role112 (1,1,2) neg-x/neg-y dense Ncols x Ye x N fill. Returns (scan, mc).
    NOTE: mat_off/gap2 use linear lx terms (8+10*lx_near / 316-10*lx_FAR),
    validated lx 1,2 / lx_FAR 2,3 -- high-lx ceil hardening deferred (same class
    as the other roles' high-lx residuals).
    cz=1 (negative z): anchor+zsh, mc-zsh, mat_off-2 (zsh=30-2*lz_near; export
    2265). At lz_near=1 (z=0 adjacency) gap2 takes an extra +2 -- not modeled
    here (use cz=1 for non-adjacent lz_near>=2; lz_near=1 also spawns a z-span)."""
    N = lz_far - lz_near + 1
    lx_FAR = lx_near + Ncols - 1
    zsh = (30 - 2 * lz_near) if cz == 1 else 0
    anchor = (74 + 55 * lx_FAR + lz_near - 35 * ly_near - 35 * (Ye - 2) + zsh) % 256
    xstep = (234 - 35 * Ye - (N - 1)) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    groupA_val = (anchor + 19) % 256
    groupB_val = (163 - lz_far + lz_near - 35 * (Ye - 1)) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (11 - 55 * lx_near + 35 * ly_near - lz_far - zsh) % 256

    # high-ly drift: pos1/gap2 use floor((ly+1)/7); mat_off uses q=(ly+5)//7
    # with a wrap-irregular form. Derived from non-edge ly sweep 1,2,10,14,20,28
    # (exports 2197/2203/2226/2228/2224/2230).
    f_ly = (ly_near + 1) // 7
    q_ly = (ly_near + 5) // 7
    pos1 = 325 - 2 * ((153 * lx_FAR + 31) // 32) - 2 * f_ly
    if cz == 1 and lz_near >= 2 and (153 * lx_FAR) % 32 > 16:
        pos1 -= 2   # cz=1 pos1 ceil-residual: -2 only when frac(153*lx_FAR/32)>0.5
                    # AND non-adjacent (lz_near>=2). Validated lz1/5/10 @Nc2(lxF6),
                    # lz5 @Nc3(lxF7). Exports 2267/2265/2269/2271.
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ncols * Ye + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 8 + 10 * lx_near + (0 if q_ly == 0 else 2 * max(1, q_ly - 1))
    gap2 = 316 - 10 * lx_FAR - 2 * max(0, f_ly - 1)
    if cz == 1 and lx_FAR != 31:
        # cz=1 neg-z (exports 2265 lz5 / 2267 lz1): mat_off-2, gap2+2 constant.
        # SUPPRESSED at the neg-x edge (lx_FAR==31): there the edge transform
        # (-12/+12) takes over the structure; only the cz=1 value shifts
        # (anchor+zsh, mc-zsh) still apply. Export 2287.
        mat_off -= 2
        gap2 += 2
    if lx_FAR == 31:
        # ABSOLUTE neg-x edge (x=-31.5): main re-envelopes. mc/pos1 UNCHANGED;
        # content shifts mat_off-12 / gap2+12 (Ncols- AND Ye-independent;
        # exports 2213/2214/2218). The spawned (0,1,2) cx=0 boundary + empties
        # are separate (generate_112_negxedge_012_scan).
        mat_off -= 12
        gap2 += 12
    if lz_far == 30:
        # ABSOLUTE z edge (z=+30.5): light main re-envelope (mat_off-2/gap2+2;
        # Ncols-indep, exports 2240/2242). cz=3 boundary (1,1,3) is separate.
        mat_off -= 2
        gap2 += 2
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    if N == 1:
        section_normal = _halfblock(groupA_val, 1) + _halfblock(Y_val, 1) * Ye
        section_groupb = _halfblock(groupB_val, 1) + _halfblock(Y_val, 1) * Ye
        groups = section_normal + (sep_groups + section_groupb) * Ncols
    else:
        section_normal = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye
        section_extra = (_halfblock(groupB_val, N)
                         + (_halfblock(Y_val, 0) + _halfblock(N - 2, 0)) * (Ye - 1)
                         + _halfblock(Y_val, N))
        section_last = _halfblock(groupB_val, N) + _halfblock(Y_val, N) * Ye
        groups = section_normal
        for col in range(Ncols):
            groups += sep_groups + (section_extra if col < Ncols - 1 else section_last)

    trailing = mat_off
    scan_len = gs + len(groups) + trailing
    scan = bytearray(scan_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, N)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, N)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, scan_len, flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_112_xspan_212_scan(ly_near, Ye, lz_near, lz_far):
    """role112 x-spanning chunk (2,1,2): pos-x neighbor acknowledging neg-x
    content adjacent to x=0. Only spawns when lx_near=1. SINGLE-COLUMN
    (markers = anchor + (Ye-1)*ystep; groups = groupA + Ye*Y). Ncols-INDEP.
    Returns (scan, mc)."""
    N = lz_far - lz_near + 1
    anchor = (97 + lz_near - 35 * ly_near - 35 * (Ye - 2)) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    groupA_val = (anchor - 36) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (244 + 35 * ly_near - lz_far) % 256

    pos1 = 9
    marker_span = 5 * Ye
    lme = pos1 + marker_span
    mat_off = 326
    gap2 = 10 - 2 * (Ye - 2) - 2 * ((ly_near + 5) // 7)
    trailing = 326
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    groups = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye
    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for _ in range(Ye - 1):
        scan[p:p + 5] = _marker(ystep, N)
        p += 5
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_112_yspan_122_scan(lx_near, Ncols, lz_near, lz_far):
    """role112 y-spanning chunk (1,2,2): pos-y neighbor acknowledging neg-y
    content adjacent to y=0, at the neg-x envelope position. Only spawns when
    ly_near=1. SINGLE-ROW (markers = anchor + (Ncols-1)*xstep; groups =
    groupA + Ncols*groupB). Returns (scan, mc)."""
    N = lz_far - lz_near + 1
    lx_FAR = lx_near + Ncols - 1
    anchor = (234 + 55 * lx_FAR + lz_near) % 256
    xstep = (200 - N) % 256
    groupA_val = (anchor + 54) % 256
    groupB_val = (199 - N) % 256
    mc = 512 + (142 - 55 * lx_near - lz_far) % 256

    pos1 = 317 - 2 * ((153 * lx_FAR + 31) // 32)
    marker_span = 5 * Ncols + 8 * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 18 + 10 * lx_near
    gap2 = 308 - 10 * lx_FAR
    trailing = mat_off
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep = bytes([0xff, 0x00]) * 4
    groups = _halfblock(groupA_val, N)
    for _ in range(Ncols):
        groups += sep + _halfblock(groupB_val, N)
    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for c in range(1, Ncols):
        _fill_background(scan, p, p + 8, flip=(c % 2 == 1))
        p += 8
        scan[p:p + 5] = _marker(xstep, N)
        p += 5
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_112_corner_222_scan(lz_near, lz_far):
    """role112 xy-corner spanning chunk (2,2,2): the (pos-x,pos-y) diagonal
    neighbor acknowledging neg-x/neg-y content at the x=0,y=0 corner. Only
    spawns when lx_near=1 AND ly_near=1. MINIMAL (single marker + single
    halfblock). Depends only on lz. Returns (scan, mc)."""
    N = lz_far - lz_near + 1
    anchor = (1 + lz_near) % 256
    groupA_val = (anchor - 1) % 256
    mc = 512 + (119 - lz_far) % 256

    pos1 = 1
    marker_span = 5
    lme = pos1 + marker_span
    mat_off = 334
    gap2 = 2
    trailing = 334
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    groups = _halfblock(groupA_val, N)
    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    scan[pos1:pos1 + 5] = _marker(anchor, N)
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_112_negxedge_012_scan(ly_near, Ye, lz_near, lz_far, cz=2):
    """role112 neg-x edge (x=-31.5) cx=0 boundary chunk (0,1,2). SINGLE-COLUMN
    (Ncols-INDEP), dense N>=2 shape (section_normal + sep + section_extra) deep
    in the neg-x envelope. Returns (scan, mc). Spawned alongside the main
    (which takes mat_off-=12/gap2+=12 at lx_FAR==31). N>=2 only.
    cz=1 (negative z, the (0,1,1) chunk): clean shift anchor+zsh/mc-zsh
    (zsh=30-2*lz_near; export 2287)."""
    N = lz_far - lz_near + 1
    zsh = (30 - 2 * lz_near) if cz == 1 else 0
    anchor = (19 + lz_near - 35 * ly_near - 35 * (Ye - 2) + zsh) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    groupA_val = (anchor + 19) % 256
    groupB_val = (163 - lz_far + lz_near - 35 * (Ye - 1)) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (66 + 35 * ly_near - lz_far - zsh) % 256

    pos1 = 333
    marker_span = 5 * Ye
    lme = pos1 + marker_span
    mat_off = 2 * ((ly_near + 1) // 7)
    gap2 = 324
    trailing = mat_off
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep = bytes([0xff, 0x00]) * 4
    section_normal = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye
    section_extra = (_halfblock(groupB_val, N)
                     + (_halfblock(Y_val, 0) + _halfblock(N - 2, 0)) * (Ye - 1)
                     + _halfblock(Y_val, N))
    groups = section_normal + sep + section_extra
    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for _ in range(Ye - 1):
        scan[p:p + 5] = _marker(ystep, N)
        p += 5
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_112_negyedge_102_scan(lx_near, Ncols, lz_near, lz_far):
    """role112 neg-y edge (y=-31.5) cy=0 boundary chunk (1,0,2). Mirror of
    role212's (2,0,2) single-row neg-y boundary, at the neg-x envelope position.
    Returns (scan, mc). N>=2. NOTE: pos1/gap2 use round(153*lx_FAR/32); a
    residual pos1-vs-gap2 rounding divergence remains at high lx_FAR (>~11) --
    deferred high-lx ceil/round class. Exact through lx_near~9, all Ncols."""
    N = lz_far - lz_near + 1
    lx_FAR = lx_near + Ncols - 1
    CF = (153 * lx_FAR + 16) // 32   # round
    CN = (153 * lx_near + 16) // 32
    anchor = (144 + 55 * lx_FAR + lz_near) % 256
    xstep = (200 - N) % 256
    groupA_val = (anchor + 19) % 256
    Y_val = (289 - N) % 256
    groupB_val = 162
    const = (N - 2) % 256
    mc = 512 + (232 - 55 * lx_near - lz_far) % 256

    pos1 = 325 - 2 * CF
    marker_span = 5 * Ncols + 8 * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 2 * CN + 8
    gap2 = pos1 - 9
    trailing = mat_off
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep = bytes([0xff, 0x00]) * 4
    sec_n = _halfblock(groupA_val, N) + _halfblock(Y_val, N)
    sec_e = _halfblock(groupB_val, N) + _halfblock(Y_val, 0) + _halfblock(const, 0)
    sec_l = _halfblock(groupB_val, N) + _halfblock(Y_val, N)
    groups = sec_n
    for col in range(Ncols):
        groups += sep + (sec_e if col < Ncols - 1 else sec_l)
    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for c in range(1, Ncols):
        _fill_background(scan, p, p + 8, flip=(c % 2 == 1))
        p += 8
        scan[p:p + 5] = _marker(xstep, N)
        p += 5
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_112_zedge_113_scan(lx_near, ly_near, Ncols, Ye):
    """role112 z edge (z=+30.5) cz=3 boundary chunk (1,1,3): dense N=1 plate of
    the edge z-level at the neg-x envelope position. Mirror of role222's
    zedge_223 with neg-x/neg-y values. Returns (scan, mc). NOTE: pos1/gap2 use
    round(153*lx_FAR/32); high-lx_FAR (>~11) residual deferred. Exact through
    lx_near~9. mat_off ly-drift (+2*(ly//7)) validated ly 5,10 only."""
    lx_FAR = lx_near + Ncols - 1
    CF = (153 * lx_FAR + 16) // 32
    CN = (153 * lx_near + 16) // 32
    anchor = (72 + 55 * lx_FAR - 35 * ly_near - 35 * (Ye - 2)) % 256
    ystep = 33
    xstep = (234 - 35 * Ye) % 256
    groupA_val = (anchor + 20) % 256
    groupB_val = (199 - 35 * Ye) % 256
    Y_val = 33
    mc = 512 + (269 - 55 * lx_near + 35 * ly_near) % 256

    pos1 = 323 - 2 * CF
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ncols * Ye + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 2 * CN + 10 + 2 * (ly_near // 7)
    gap2 = pos1 - 9
    trailing = mat_off
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    sec_n = _halfblock(groupA_val, 0) + _halfblock(Y_val, 0) * Ye
    sec_b = _halfblock(groupB_val, 0) + _halfblock(Y_val, 0) * Ye
    groups = sec_n + (sep_groups + sec_b) * Ncols
    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, 1)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, 1)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_212_zspan_212_scan(lx_near, ly_near, Ncols, Ye):
    """role212 (pos-x/neg-y) z=0 Z-SPAN chunk (2,1,2), spawned when negative-z
    content is adjacent to z=0 (lz_near=1). Dense N=1 plate, mirror of role222's
    zedge_223 with neg-y values. NOT the same as role212's zedge_213. Returns
    (scan, mc). Validated lx2/lx5, ly2/ly5, Ye2/Ye3 (exports 2277/2279/2281/2283).
    NOTE: pos1 uses a frac>0.875 ceil-threshold; mat_off ly-drift uses //5 --
    both fit the tested points; high-lx/ly hardening deferred (ceil-residual class)."""
    lx_FAR = lx_near + Ncols - 1
    Cp = (153 * lx_near) // 32 + (1 if (153 * lx_near) % 32 > 28 else 0)
    CN = (153 * lx_near + 16) // 32
    anchor = (241 - 55 * lx_near - 35 * ly_near - 35 * (Ye - 2)) % 256
    ystep = 33
    xstep = (234 - 35 * Ye) % 256
    groupA_val = (anchor + 20) % 256
    groupB_val = (199 - 35 * Ye) % 256
    Y_val = 33
    mc = 512 + (100 + 35 * ly_near - 201 * lx_FAR) % 256

    pos1 = 27 + 2 * Cp
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ncols * Ye + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 296 - 2 * CN + 2 * (ly_near // 5)
    gap2 = pos1 - 9
    trailing = mat_off
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    sec_n = _halfblock(groupA_val, 0) + _halfblock(Y_val, 0) * Ye
    sec_b = _halfblock(groupB_val, 0) + _halfblock(Y_val, 0) * Ye
    groups = sec_n + (sep_groups + sec_b) * Ncols
    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, 1)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, 1)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_negx_crossing_122_scan(neg_cols, ly_near, Ye, lz_near, lz_far):
    """MULTI-QUADRANT: the neg-x side (1,2,2) of a fill CROSSING x=0 (pos-y/pos-z
    quadrant). The column adjacent to x=0 becomes interior; the chunk has neg_cols+1
    interior group-sections (one = the x=0 interface) and neg_cols+1 marker columns.
    Uses role122 dense values at lx_FAR=neg_cols-1, but its own crossing mc.
    Returns (scan, mc). Validated nc1/2/3, lz1/5, ly1/2, Ye2/3 (exports
    2291/2295/2252/2297/2300/2303). N>=2 (pos-z); pos-x side is separate."""
    N = lz_far - lz_near + 1
    lxF = neg_cols - 1
    nc = neg_cols
    anchor = (55 * lxF + 35 * ly_near + lz_near + 48) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    xstep = (234 - 35 * Ye - (N - 1)) % 256
    groupA_val = (anchor + 19) % 256
    groupB_val = (163 - lz_far + lz_near - 35 * (Ye - 1)) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (92 - lz_far - 35 * ly_near - 35 * (Ye - 2)) % 256

    pos1 = 317 - 2 * ((153 * lxF + 31) // 32)
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ye * (nc + 1) + sep_w * nc
    lme = pos1 + marker_span
    mat_off = 8
    gap2 = pos1 - 9
    trailing = 8
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    sec_n = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye
    sec_i = (_halfblock(groupB_val, N)
             + (_halfblock(Y_val, 0) + _halfblock(N - 2, 0)) * (Ye - 1)
             + _halfblock(Y_val, N))
    groups = sec_n
    for _ in range(nc + 1):
        groups += sep_groups + sec_i
    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for _ in range(Ye - 1):
        scan[p:p + 5] = _marker(ystep, N)
        p += 5
    for c in range(nc):
        _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (c + 1)) % 2 == 1))
        p += sep_w
        scan[p:p + 5] = _marker(xstep, N)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, N)
            p += 5
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_posx_crossing_222_scan(neg_cols, pos_cols, ly_near, Ye, lz_near, lz_far):
    """MULTI-QUADRANT: the pos-x side (2,2,2) of a fill CROSSING x=0 (pos-y/pos-z
    quadrant). This is the INTERFACE-encoding side: depends on BOTH pos_cols and
    neg_cols, the latter SATURATING at 2 (m=min(neg_cols,2)). The x=0-adjacent
    pos column is interior; when the neg wall is thick (m>=2) the anchor/groupA
    section also becomes interior. Returns (scan, mc). Validated neg1-3 x pos1-3,
    lz1/5, ly1/2, Ye2/3 (exports 2291/2293/2295/2338/2340/2252/2297/2300/2303).
    N>=2 (pos-z). Pairs with generate_negx_crossing_122_scan (the neg-x side)."""
    N = lz_far - lz_near + 1
    m = min(neg_cols, 2)
    base_anchor = (16 + 35 * ly_near + lz_near) % 256
    anchor = (base_anchor + 55 * (m - 1)) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    xstep = (234 - 35 * Ye - (N - 1)) % 256
    groupA_val = (base_anchor + 19) % 256
    groupB_val = (163 - lz_far + lz_near - 35 * (Ye - 1)) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (69 + 55 * pos_cols - lz_far - 35 * ly_near - 35 * (Ye - 2)) % 256

    pos1 = 21 - 10 * m
    xcols = pos_cols + (m - 1)
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ye * (xcols + 1) + sep_w * xcols
    lme = pos1 + marker_span
    mat_off = 314 - 10 * (pos_cols - 1)
    gap2 = 2
    trailing = mat_off
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    def _normal(v):
        return _halfblock(v, N) + _halfblock(Y_val, N) * Ye
    def _interior(v):
        return (_halfblock(v, N) + (_halfblock(Y_val, 0) + _halfblock(N - 2, 0)) * (Ye - 1)
                + _halfblock(Y_val, N))
    groups = _interior(groupA_val) if m >= 2 else _normal(groupA_val)
    for _ in range(pos_cols):
        groups += sep_groups + _interior(groupB_val)
    groups += sep_groups + _normal(groupB_val)   # last (edge) section

    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    scan[p:p + 5] = _marker(anchor, N)
    p += 5
    for _ in range(Ye - 1):
        scan[p:p + 5] = _marker(ystep, N)
        p += 5
    for c in range(xcols):
        _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (c + 1)) % 2 == 1))
        p += sep_w
        scan[p:p + 5] = _marker(xstep, N)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, N)
            p += 5
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_negy_crossing_212_scan(lx_near, neg_rows, Ncols, lz_near, lz_far):
    """MULTI-QUADRANT: the neg-y side (2,1,2) of a fill CROSSING y=0 (pos-x/pos-z
    quadrant). The row adjacent to y=0 becomes interior; effective Ye=neg_rows+1,
    and the interior group-section becomes the INTERFACE form [gB, (Y0,c0)*Ye_e --
    no trailing Y]. role212 dense offsets. Depends ONLY on neg_rows (source side).
    Returns (scan, mc). Validated nr1/2, lz1/5, Nc2/3 (2342/2346/2348/2350); lx1
    only (mat_off/mc use lx_FAR, linear -- high-lx ceil deferred). N>=2 (pos-z)."""
    N = lz_far - lz_near + 1
    Yee = neg_rows + 1
    lx_FAR = lx_near + Ncols - 1
    anchor = (259 - 35 * neg_rows - 55 * (lx_near - 1) + (lz_near - 1)) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    xstep = (234 - 35 * Yee - (N - 1)) % 256
    groupA_val = (anchor + 19) % 256
    groupB_val = (163 - lz_far + lz_near - 35 * (Yee - 1)) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (63 + 55 * lx_FAR - lz_far) % 256

    pos1 = 37
    sep_w = 8 - 2 * (Yee // 7)
    marker_span = 5 * Yee * Ncols + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 306 - 10 * lx_FAR
    gap2 = pos1 - 9
    trailing = mat_off
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    sec_n = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Yee
    sec_if = _halfblock(groupB_val, N) + (_halfblock(Y_val, 0) + _halfblock(N - 2, 0)) * Yee
    sec_l = _halfblock(groupB_val, N) + _halfblock(Y_val, N) * Yee
    groups = sec_n
    for col in range(Ncols):
        groups += sep_groups + (sec_if if col < Ncols - 1 else sec_l)
    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, N)
        p += 5
        for _ in range(Yee - 1):
            scan[p:p + 5] = _marker(ystep, N)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Yee * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_posy_crossing_222_scan(lx_near, neg_rows, pos_rows, Ncols, lz_near, lz_far):
    """MULTI-QUADRANT: the pos-y side (2,2,2) of a fill CROSSING y=0 (pos-x/pos-z
    quadrant). INTERFACE side: role222-like, interface in the Ye (row) dimension.
    KEY: marker_Ye = pos_rows + m vs group_Ye = pos_rows + 1 (decoupled), where
    m=min(neg_rows,2) (SATURATES at 2 -- 2neg==3neg). At m>=2 the interior section
    gains the interface form [gB(N0), c0, ...]. Returns (scan, mc). Validated
    neg1-3 x pos1-2, Nc2/3, lz1/5 (2342/2344/2346/2354/2348/2350). lx1 only. N>=2."""
    N = lz_far - lz_near + 1
    gYe = pos_rows + 1
    m = min(neg_rows, 2)
    mYe = pos_rows + m
    lx_FAR = lx_near + Ncols - 1
    base_anchor = (127 + lz_near) % 256
    anchor = (base_anchor - 35 * (m - 1)) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    xstep = (234 - 35 * mYe - (N - 1)) % 256
    groupA_val = (base_anchor + 19) % 256
    groupB_val = (163 - lz_far + lz_near - 35 * (gYe - 1)) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (159 - lz_far - 35 * (pos_rows - 1) + 55 * lx_FAR) % 256

    pos1 = 29
    sep_w = 8 - 2 * (mYe // 7)
    marker_span = 5 * mYe * Ncols + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 306 - 2 * ((153 * lx_near + 31) // 32) - 10 * (Ncols - 2) - 2 * (pos_rows - 1)
    gap2 = pos1 - 9
    trailing = mat_off
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    sec_n = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * gYe
    if m >= 2:
        sec_e = (_halfblock(groupB_val, 0) + _halfblock(N - 2, 0)
                 + (_halfblock(Y_val, 0) + _halfblock(N - 2, 0)) * (gYe - 1)
                 + _halfblock(Y_val, N))
    else:
        sec_e = (_halfblock(groupB_val, N) + (_halfblock(Y_val, 0) + _halfblock(N - 2, 0)) * (gYe - 1)
                 + _halfblock(Y_val, N))
    sec_l = _halfblock(groupB_val, N) + _halfblock(Y_val, N) * gYe
    groups = sec_n
    for col in range(Ncols):
        groups += sep_groups + (sec_e if col < Ncols - 1 else sec_l)

    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, N)
        p += 5
        for _ in range(mYe - 1):
            scan[p:p + 5] = _marker(ystep, N)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * mYe * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_negz_crossing_222_scan(lx_near, ly_near, neg_z, Ncols, Ye):
    """MULTI-QUADRANT: the cz=1 (neg-z) side (2,2,1) of a fill CROSSING z=0
    (pos-x/pos-y quadrant). SOURCE side (depends only on neg_z). Interface in the
    N(lz) dimension: effective N=neg_z+1, interior section uses the cz=1 form
    [gB, Y0, (33 N0)*(Ye-2), 33(N)] (33 = cz=1 z-marker). Returns (scan, mc).
    Validated neg_z1/2, Ncols2/3, Ye2/3 (2352/2358/2360/2362/2356). lx1/ly1 only."""
    eN = neg_z + 1
    N = eN
    lx_FAR = lx_near + Ncols - 1
    anchor = (229 - neg_z - 55 * (lx_near - 1) + 35 * (ly_near - 1)) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    xstep = (234 - 35 * Ye - (N - 1)) % 256
    groupA_val = (anchor + 19) % 256
    groupB_val = (129 - eN - 35 * (Ye - 2)) % 256
    Y_val = (289 - N) % 256
    mc = 512 + (57 + 55 * lx_FAR - 35 * (Ye - 2)) % 256

    pos1 = 19 + 2 * ((153 * lx_near + 31) // 32)
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ye * Ncols + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 304 - 2 * ((153 * lx_near + 31) // 32) - 10 * (Ncols - 2)
    gap2 = pos1 - 9
    trailing = mat_off
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    sec_n = _halfblock(groupA_val, N) + _halfblock(Y_val, N) * Ye
    sec_i = (_halfblock(groupB_val, N) + _halfblock(Y_val, 0)
             + _halfblock(33, 0) * (Ye - 2) + _halfblock(33, N))
    sec_l = _halfblock(groupB_val, N) + _halfblock(Y_val, N) * Ye
    groups = sec_n
    for col in range(Ncols):
        groups += sep_groups + (sec_i if col < Ncols - 1 else sec_l)
    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, N)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, N)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


def generate_posz_crossing_222_scan(lx_near, ly_near, neg_z, pos_z, Ncols, Ye):
    """MULTI-QUADRANT: the cz=2 (pos-z) side (2,2,2) of a fill CROSSING z=0.
    INTERFACE side: role222 dense at group_N=pos_z+1 with anchor=dense_anchor(lz0)
    -neg_z, mc+1, groupA uses base_anchor (neg_z-indep). At neg_z>=2 (m=2,
    SATURATES): marker_N=pos_z+m decoupled from group_N, interior gains the 33
    form [gB,(33 N0)*(Ye-1),Y]. Returns (scan, mc). Validated neg1-2 x pos1-2,
    Nc2/3, Ye2/3 (2352/2356/2358/2360/2362). lx1/ly1 only."""
    gN = pos_z + 1
    m = min(neg_z, 2)
    mN = pos_z + m
    lx_FAR = lx_near + Ncols - 1
    anchor = (217 - 55 * lx_near + 35 * ly_near - neg_z) % 256
    ystep = (304 - _EFF_LZ - mN) % 256
    xstep = (234 - 35 * Ye - (mN - 1)) % 256
    groupA_val = (235 - 55 * lx_near + 35 * ly_near) % 256
    groupB_val = (163 - pos_z - 35 * (Ye - 1)) % 256
    Y_val = (289 - gN) % 256
    mc = 512 + (124 - 201 * lx_FAR - 35 * ly_near - pos_z - 35 * (Ye - 2) + 1) % 256

    pos1 = 19 + 2 * ((153 * lx_near + 31) // 32)
    sep_w = 8 - 2 * (Ye // 7)
    marker_span = 5 * Ye * Ncols + sep_w * (Ncols - 1)
    lme = pos1 + marker_span
    mat_off = 304 - 2 * ((153 * lx_near + 31) // 32) - 10 * (Ncols - 2) - 2 * (ly_near // 7)
    gap2 = pos1 - 9
    trailing = mat_off
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)
    sec_n = _halfblock(groupA_val, gN) + _halfblock(Y_val, gN) * Ye
    if m >= 2:
        sec_i = _halfblock(groupB_val, gN) + _halfblock(33, 0) * (Ye - 1) + _halfblock(Y_val, gN)
    else:
        sec_i = (_halfblock(groupB_val, gN) + (_halfblock(Y_val, 0) + _halfblock(gN - 2, 0)) * (Ye - 1)
                 + _halfblock(Y_val, gN))
    sec_l = _halfblock(groupB_val, gN) + _halfblock(Y_val, gN) * Ye
    groups = sec_n
    for col in range(Ncols):
        groups += sep_groups + (sec_i if col < Ncols - 1 else sec_l)
    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(Ncols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, mN)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, mN)
            p += 5
        if col < Ncols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# MULTI-AXIS 2-PLANE (x=0 AND y=0) EDGE crossing
# ---------------------------------------------------------------------------

def _first_marker_val(scan):
    """Value of the first marker (the [val,01,02,N-1,00] cell) -- the anchor."""
    i = 0
    while not (scan[i + 1] == 0x01 and scan[i + 2] == 0x02):
        i += 1
    return scan[i]


def _first_group_val(scan):
    """Value of the first half-block ([val,01,N,7e,7e,7e,N,00]) -- groupA."""
    i = 0
    while not (scan[i + 1] == 0x01 and scan[i + 3] == 0x7e
               and scan[i + 5] == 0x7e and scan[i + 7] == 0x00):
        i += 1
    return scan[i]


# Layout table for the x=0+y=0 edge, keyed by (cx,cy):
#   (base_pos1, Cx_pos1, Cy_pos1, Cxy_pos1, base_mat_off, base_gap2, Cx_gap2, Cy_gap2)
# base_* are the values at the minimal crossing (1 col + 1 row each side); Cx_*
# is the additive shift when the x-side wall saturates (neg_cols>=2 -> m_x=2),
# Cy_* the shift when the y-side wall saturates (neg_rows>=2 -> m_y=2), and Cxy_p1
# is the extra pos1 shift when BOTH saturate (an interaction term; only (1,2,2)
# needs one -- its m_y drift vanishes once m_x is saturated). Since single-axis
# saturation caps at m=2, (m-1) is 0 or 1, so these cover all counts. trailing ==
# mat_off; pos-x mat_off scales -10*(pos_cols-1); neg-x mat_off is constant.
# VALIDATED byte-exact (all 4 chunks) at: 2366 (minimal), 2368 (2 pos-x cols),
# 2370 (2 pos-y rows), 2372 (2 neg-x cols m_x=2), 2374 (2 neg-y rows m_y=2),
# 2376 (2 neg-x cols + 2 neg-y rows, m_x=m_y=2). NOT yet probed: lx/ly content
# drift; pos_cols>1 with neg-x mat_off; lz beyond 1-2.
_XYEDGE_LAYOUT = {(2, 2): (9, -8, 0, 0, 314, 2, 0, 0),
                  (2, 1): (19, -10, 0, 0, 306, 10, 0, 0),
                  (1, 2): (317, -10, -2, 2, 8, 308, -10, 0),
                  (1, 1): (325, -10, 0, 0, 0, 316, -10, 0)}


def generate_xyedge_crossing_scan(chunk, neg_cols, pos_cols, neg_rows, pos_rows,
                                  lz_near, lz_far):
    """MULTI-AXIS: one (cx,cy,2) chunk of a fill CROSSING BOTH x=0 AND y=0 (pos-z).

    The two single-axis crossing rules COMPOSE. STRUCTURE: the x-side rule sets
    the number / form of group-sections (pos-x = interface side, gains an extra
    interior section + saturated first-section when neg_cols>=2; neg-x = source,
    neg_cols+1 interior sections). The y-side rule sets each interior section's
    FORM (pos-y = single-pair, gaining the N=0-lead interface form when
    neg_rows>=2; neg-y = double-pair, eff_Ye=neg_rows+1). Marker eff_cols /
    marker_Ye carry the saturation (m=min(neg,2)); group_Ye does NOT (decoupled).

    VALUES: marker `anchor` and `mc` = role_dense + x_delta + y_delta (mod 256),
    with deltas pulled from the existing single-axis crossing generators (so the
    saturation anchor-shifts +55*(m_x-1) / -35*(m_y-1) are inherited). The first
    group section value `gA` is composed the SAME way but from the sub-gens' GROUP
    values, which are UNshifted -- so gA stays at its base under saturation. The
    neg-x/neg-y corner (1,1,2) carries an extra -55 on both anchor and gA (not mc).

    Returns (scan, mc). Validated byte-exact for all 4 chunks at exports 2366/
    2368/2370/2372/2374 (see _XYEDGE_LAYOUT for the parameter coverage / gaps).
    """
    cx, cy, cz = chunk
    N = lz_far - lz_near + 1
    x_pos = (cx == 2)
    y_pos = (cy == 2)
    m_x = min(neg_cols, 2)
    m_y = min(neg_rows, 2)
    gYe = (pos_rows + 1) if y_pos else (neg_rows + 1)          # group y-extent
    mYe = (pos_rows + m_y) if y_pos else (neg_rows + 1)         # marker y-extent
    eff_cols = (pos_cols + m_x) if x_pos else (neg_cols + 1)

    # --- value composition: dense_role + x_delta + y_delta (role-independent) ---
    if cx == 2 and cy == 2:
        dense = generate_222_dense_scan(1, 1, 1, 1, lz_near, lz_far)
    elif cx == 2 and cy == 1:
        dense = generate_212_dense_scan(1, 1, 1, 1, lz_near, lz_far)
    elif cx == 1 and cy == 2:
        dense = generate_122_dense_scan(0, 1, 1, 1, lz_near, lz_far)
    else:
        dense = generate_112_dense_scan(1, 1, 1, 1, lz_near, lz_far)
    d_a = _first_marker_val(dense[0])
    d_g = _first_group_val(dense[0])
    d_mc = dense[1] & 0xff

    if x_pos:
        xc = generate_posx_crossing_222_scan(neg_cols, pos_cols, 1, 1, lz_near, lz_far)
        rx = generate_222_dense_scan(1, 1, 1, 1, lz_near, lz_far)
    else:
        xc = generate_negx_crossing_122_scan(neg_cols, 1, 1, lz_near, lz_far)
        rx = generate_122_dense_scan(0, 1, 1, 1, lz_near, lz_far)
    Dx_a = (_first_marker_val(xc[0]) - _first_marker_val(rx[0])) % 256
    Dx_g = (_first_group_val(xc[0]) - _first_group_val(rx[0])) % 256
    Dx_mc = (xc[1] - rx[1]) % 256

    if y_pos:
        yc = generate_posy_crossing_222_scan(1, neg_rows, pos_rows, 1, lz_near, lz_far)
        ry = generate_222_dense_scan(1, 1, 1, 1, lz_near, lz_far)
    else:
        yc = generate_negy_crossing_212_scan(1, neg_rows, 1, lz_near, lz_far)
        ry = generate_212_dense_scan(1, 1, 1, 1, lz_near, lz_far)
    Dy_a = (_first_marker_val(yc[0]) - _first_marker_val(ry[0])) % 256
    Dy_g = (_first_group_val(yc[0]) - _first_group_val(ry[0])) % 256
    Dy_mc = (yc[1] - ry[1]) % 256

    corner = -55 if (cx == 1 and cy == 1) else 0
    anchor = (d_a + Dx_a + Dy_a + corner) % 256
    gA = (d_g + Dx_g + Dy_g + corner) % 256
    mc = 512 + (d_mc + Dx_mc + Dy_mc) % 256

    # --- formula-derived markers / group constants ---
    xstep = (234 - 35 * mYe - (N - 1)) % 256
    ystep = (304 - _EFF_LZ - N) % 256
    Y_val = (289 - N) % 256
    IFV = (127 - 35 * (gYe - 2)) % 256  # interior-section lead (scales with gYe)

    # --- structure composition ---
    sep_w = 8 - 2 * (mYe // 7)
    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)

    def normal(v):
        return _halfblock(v, N) + _halfblock(Y_val, N) * gYe

    def interior(v):
        if y_pos:
            if m_y >= 2:   # saturated pos-y interface form: N=0 lead + extra c0
                return (_halfblock(v, 0) + _halfblock(0, 0)
                        + (_halfblock(Y_val, 0) + _halfblock(0, 0)) * (gYe - 1)
                        + _halfblock(Y_val, N))
            return (_halfblock(v, N)
                    + (_halfblock(Y_val, 0) + _halfblock(0, 0)) * (gYe - 1)
                    + _halfblock(Y_val, N))
        return _halfblock(v, N) + (_halfblock(Y_val, 0) + _halfblock(0, 0)) * gYe

    if x_pos:
        groups = interior(gA) if m_x >= 2 else normal(gA)
        for _ in range(pos_cols):
            groups += sep_groups + interior(IFV)
        groups += sep_groups + normal(IFV)      # trailing normal section
    else:
        groups = normal(gA)
        for _ in range(neg_cols + 1):
            groups += sep_groups + interior(IFV)

    # --- layout ---
    (base_pos1, Cx_p1, Cy_p1, Cxy_p1, base_mat,
     base_gap2, Cx_g, Cy_g) = _XYEDGE_LAYOUT[(cx, cy)]
    pos1 = (base_pos1 + Cx_p1 * (m_x - 1) + Cy_p1 * (m_y - 1)
            + Cxy_p1 * (m_x - 1) * (m_y - 1))
    mat_off = (base_mat - 10 * (pos_cols - 1)) if x_pos else base_mat
    gap2 = base_gap2 + Cx_g * (m_x - 1) + Cy_g * (m_y - 1)
    marker_span = 5 * mYe * eff_cols + sep_w * (eff_cols - 1)
    lme = pos1 + marker_span
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2
    trailing = mat_off

    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(eff_cols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, N)
        p += 5
        for _ in range(mYe - 1):
            scan[p:p + 5] = _marker(ystep, N)
            p += 5
        if col < eff_cols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * mYe * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# MULTI-AXIS 2-PLANE (x=0 AND z=0) EDGE crossing  -- MINIMAL case only
# ---------------------------------------------------------------------------

# Layout for the x=0+z=0 edge, keyed by cx (the z-side does NOT affect layout):
# (pos1, mat_off, gap2); trailing == mat_off. These ARE the x=0 single-crossing
# layouts -- for this edge x governs layout while z governs the group structure.
_XZEDGE_LAYOUT_X = {2: (11, 314, 2), 1: (317, 8, 308)}


def generate_xzedge_crossing_scan(chunk, neg_cols=1, pos_cols=1, ly_near=1,
                                  neg_z=1, pos_z=1):
    """MULTI-AXIS: one (cx,2,cz) chunk of a fill CROSSING BOTH x=0 AND z=0.

    z is the N/lz dimension (cz=1 neg-z / cz=2 pos-z split). Unlike the x=0+y=0
    edge, here the two rules split cleanly: the z-crossing sets the GROUP STRUCTURE
    (Ncols-eff group sections, groupB, xstep, N -- the z-interface in the column
    dimension) and the x-crossing sets the LAYOUT (pos1/mat_off/gap2 = the x=0
    single-crossing layout). VALUES compose ADDITIVELY: anchor += 32 and mc -= 32
    for EACH negative side (cx==1 and/or cz==1); gA = anchor+19. No interface
    doubling at the minimal footprint.

    SCALING (all validated byte-exact, 4 chunks each):
      - X-COLS (2381): Ncols_eff = (chunk's x-side col count) + 1 (+1 = z-interface
        column). pos-x: anchor unchanged, mc += 55*(pos_cols-1), mat_off scales
        -10*(pos_cols-1). At Ye=1 the extra sections are plain [gB, Y].
      - Z-LEVELS (2383): the chunk's own z-side sets N = (its z levels) + 1; every
        N-dependent constant (xstep/Y/gB) follows, and mc -= (N-2).
      - POS-Y ROWS / Ye (2385): at Ye>=2 the z-interface sections take the y-multi-
        row form (lead IFV=127-35*(Ye-2)): pos-x's LAST section is a trailing-normal
        [IFV, Y*Ye], all others are interior; pos-z interior = [IFV,(Y0,c0)*(Ye-1),Y],
        neg-z interior = [IFV,(Y0,33)*(Ye-1)] (the 33 = neg-z reflection form). And
        mc -= 35*(Ye-1).
      - NEG-X SATURATION (2387, neg_cols>=2 -> m_x=2): marker columns DECOUPLE from
        group sections -- eff_cols = pos_cols+m_x (pos-x) / neg_cols+1 (neg-x), while
        group Ncols stays side_cols+1. anchor += 55*(m_x-1) (all chunks); gA also
        +=55*(m_x-1) but ONLY neg-x; mc unchanged. pos1 -= 10*(m_x-1) (all), neg-x
        gap2 -= 10*(m_x-1).
      - NEG-Z SATURATION (2389, neg_z>=2): marker depth mN DECOUPLES from group depth
        gN. gN = own z-side+1; mN = neg_z+1 for neg-z chunks, max(pos_z,neg_z)+1 for
        pos-z chunks. anchor -= (neg_z-1); the depth term -(gN-2) lands on gA for
        NEG-z (cz==1) and on mc for POS-z (cz==2) -- a clean reflection split.

    *** Still unprobed: Ye>=3, the neg-z "33" value's N-scaling, and combined
    saturations (neg_cols>1 AND neg_z>1, or saturation alongside Ye>=2). ***
    """
    cx, cy, cz = chunk
    Ye = ly_near
    m_x = min(neg_cols, 2)
    gN = (pos_z if cz == 2 else neg_z) + 1   # group depth: chunk's own z-side
    mN = (neg_z + 1) if cz == 1 else (max(pos_z, neg_z) + 1)   # marker depth
    side_cols = pos_cols if cx == 2 else neg_cols
    Ncols = side_cols + 1                     # group sections (+1 = z-interface column)
    eff_cols = (pos_cols + m_x) if cx == 2 else (neg_cols + 1)  # marker columns
    abase = 15 + 32 * (cx == 1) + 32 * (cz == 1)
    anchor = (abase - (neg_z - 1) + 55 * (m_x - 1)) % 256
    gA = (abase + 19 - (gN - 2) * (cz == 1) + 55 * (m_x - 1) * (cx == 1)) % 256
    mc = 512 + (159 - 32 * (cx == 1) - 32 * (cz == 1)
                + 55 * (pos_cols - 1) * (cx == 2)
                - 35 * (Ye - 1) - (gN - 2) * (cz == 2)) % 256
    xstep = (234 - 35 * Ye - (mN - 1)) % 256
    ystep = (304 - _EFF_LZ - mN) % 256
    Y_val = (289 - gN) % 256
    gB = (129 - gN - 35 * (Ye - 2)) % 256
    IFV = (127 - 35 * (Ye - 2)) % 256             # interior lead at Ye>=2
    TT = 33                                       # neg-z reflection value (N=2)

    sep_w = 8 - 2 * (Ye // 7)
    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)

    def normal(v):
        return _halfblock(v, gN) + _halfblock(Y_val, gN) * Ye

    def interior(v):
        if cz == 2:    # pos-z: single-pair, trailing Y
            return (_halfblock(v, gN)
                    + (_halfblock(Y_val, 0) + _halfblock(0, 0)) * (Ye - 1)
                    + _halfblock(Y_val, gN))
        return (_halfblock(v, gN)        # neg-z: 33-form replaces (c0, trailing-Y)
                + (_halfblock(Y_val, 0) + _halfblock(TT, gN)) * (Ye - 1))

    groups = normal(gA)
    if Ye == 1:
        for _ in range(Ncols):
            groups += sep_groups + _halfblock(gB, gN) + _halfblock(Y_val, gN)
    else:
        for j in range(Ncols):
            if cx == 2 and j == Ncols - 1:
                groups += sep_groups + normal(IFV)        # pos-x trailing normal
            else:
                groups += sep_groups + interior(IFV)

    pos1, base_mat, gap2 = _XZEDGE_LAYOUT_X[cx]
    pos1 -= 10 * (m_x - 1)
    mat_off = base_mat - (10 * (pos_cols - 1) if cx == 2 else 0)
    gap2 -= 10 * (m_x - 1) if cx == 1 else 0
    trailing = mat_off
    marker_span = 5 * Ye * eff_cols + sep_w * (eff_cols - 1)
    lme = pos1 + marker_span
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    scan = bytearray(gs + len(groups) + trailing)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(eff_cols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, mN)
        p += 5
        for _ in range(Ye - 1):
            scan[p:p + 5] = _marker(ystep, mN)
            p += 5
        if col < eff_cols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * Ye * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = mc & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# MULTI-AXIS 2-PLANE (y=0 AND z=0) EDGE crossing  -- MINIMAL case only
# ---------------------------------------------------------------------------

# Layout for the y=0+z=0 edge, keyed by cy (the z-side does NOT affect layout):
# (pos1, mat_off, gap2); trailing == mat_off. Here y governs layout (mirroring how
# x governed it for the x=0+z=0 edge), z governs the extra group section.
_YZEDGE_LAYOUT_Y = {2: (19, 314, 10), 1: (29, 306, 20)}


def generate_yzedge_crossing_scan(chunk, neg_cols=1, pos_cols=1,
                                  neg_y=1, pos_y=1, neg_z=1, pos_z=1):
    """MULTI-AXIS: one (2,cy,cz) chunk of a fill CROSSING BOTH y=0 AND z=0.

    NOT a clean mirror of x=0+z=0: here BOTH y and z are interface dimensions.
    y manifests in the row (Ye) direction (Ye = own-y-side+1, marker = [anchor,
    ystep...]); z sets depth N = own-z-side+1 and adds group SECTIONS; x is the
    column dimension (Ncols = pos_cols). y governs LAYOUT (keyed by cy); cz does not.

    VALUES additive (anchor/gA independent of pos x/y/z counts):
      anchor = 181 + 96*(cy==1) + 32*(cz==1);  gA = anchor + 19 - (N-2)*(cz==1)
      mc = 159 - 96*(cy==1) - 32*(cz==1) + 55*(pos_cols-1)
           - (N-2)*(cz==2) - 35*(Ye-2)
    (neg-y value step is 96, neg-z is 32. The z depth term splits like the x=0+z=0
    edge: on mc for pos-z, on gA for neg-z.)

    STRUCTURE: groups = normal[gA, Y*Ye] + (pos_cols-1) interior + 1 trailing. The
    interior form depends on cy x cz (pos-y single-pair / neg-y double-pair; pos-z
    c0 filler / neg-z "33"), exactly the x=0+y=0 interior forms with the z-33 modifier.
    IFV = 127 - 35*(Ye-2) - (N-2).

    NEG-Y / NEG-Z SATURATION (2403 / 2409) -- direct analogs of the x=0+z=0 edge's
    neg-z saturation. Marker depth/rows DECOUPLE from group depth/rows:
      gN = own z-side+1; mN = neg_z+1 (neg-z) / max(pos_z,neg_z)+1 (pos-z).
      gYe = own y-side+1; mYe = neg_y+1 (neg-y) / max(pos_y,neg_y)+1 (pos-y).
    The marker anchor gets the neg-wall shifts -(neg_z-1) - 35*(neg_y-1) (NOT gA,
    which uses the base). Depth terms reflect: z on mc(pos-z)/gA(neg-z), y on
    mc(pos-y)/gA(neg-y). Plus a pos1 interaction: -2 for a neg-y chunk when cz==2
    and neg_y saturated.

    NEG-X SATURATION (2401/2415, neg_cols>1 -> m_x=min(neg_cols,2)): x gains column
    structure on BOTH sides (the x=0+y=0 pattern). Marker eff_cols = pos_cols+m_x
    (cx=2 interface) / neg_cols+1 (cx=1 source). cx=2 sat: an interface-first section
    (interior-form with lead L) + interior(s) + trailing; cx=1: normal + (neg_cols+1)
    interior, no trailing. anchor sat term = 110*(m_x-1) (cx=2, capped) / 55*neg_cols
    (cx=1, uncapped). The interface-first lead L = mc for (cy==2,cz==2) else anchor-36.
    A "fill" +2 (double-neg cy==1,cz==1) hits every fill section after the first. The
    (1,1,1) triple-neg corner stores mc-2 in the mat byte (decode still reports mc).

    VALIDATED byte-exact (4 chunks, or 8 for neg-x): 2393 (min), 2395/2397/2399 (pos
    x-cols/y-lvls/z-lvls), 2403/2409 (neg-y/neg-z sat), 2401/2411/2413/2415/2417 (neg-x
    sat, incl. combined with pos_z/pos_y/pos_cols/neg_cols=3).
    *** Still unprobed: full combined saturations (e.g. neg_cols>1 AND neg_y>1), and
    higher-count drift beyond these footprints. ***
    """
    cx, cy, cz = chunk
    m_x = min(neg_cols, 2)
    gN = (pos_z if cz == 2 else neg_z) + 1               # group z-depth (own side)
    mN = (neg_z + 1) if cz == 1 else max(pos_z, neg_z) + 1   # marker z-depth
    gYe = (pos_y if cy == 2 else neg_y) + 1              # group y-rows (own side)
    mYe = (neg_y + 1) if cy == 1 else max(pos_y, neg_y) + 1  # marker y-rows
    # marker columns vs group sections differ for cx=2 under saturation:
    marker_cols = (pos_cols + 2 * (m_x - 1)) if cx == 2 else (neg_cols + 1)
    n_mid = pos_cols + m_x - 2          # cx=2 middle interior sections
    dn = (cy == 1 and cz == 1)                           # double-neg (y & z)
    abase = 181 + 32 * (cx == 1) + 96 * (cy == 1) + 32 * (cz == 1)
    sat = 55 * neg_cols if cx == 1 else 110 * (m_x - 1)
    # gA_base = anchor WITHOUT the neg-wall shifts (gA never carries those, only sat)
    gA_base = abase + sat
    anchor = (gA_base - (neg_z - 1) - 35 * (neg_y - 1)) % 256
    gA = (gA_base + 19 - (gN - 2) * (cz == 1) - 35 * (gYe - 2) * (cy == 1)) % 256
    mc = 512 + (159 - 96 * (cy == 1) - 32 * (cz == 1) - 32 * (cx == 1)
                + 55 * (pos_cols - 1) * (cx == 2)
                - (gN - 2) * (cz == 2) - 35 * (gYe - 2) * (cy == 2)
                + 2 * (cx == 1 and dn)) % 256
    xstep = (234 - 35 * mYe - (mN - 1)) % 256
    ystep = (304 - _EFF_LZ - mN) % 256
    Y_val = (289 - gN) % 256
    IFV = (127 - 35 * (gYe - 2) - (gN - 2)) % 256
    # interface-first section lead (cx=2 under m_x>=2):
    L = (mc & 0xff) if (cy == 2 and cz == 2) else (anchor - 36) % 256

    sep_w = 8 - 2 * (mYe // 7)
    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)

    def normal(v):
        return _halfblock(v, gN) + _halfblock(Y_val, gN) * gYe

    def interior(v):
        out = _halfblock(v, gN)
        if cz == 2:                                  # pos-z: c0 filler (= gN-2)
            npairs = gYe if cy == 1 else gYe - 1
            for _ in range(npairs):
                out += _halfblock(Y_val, 0) + _halfblock(gN - 2, 0)
            if cy == 2:
                out += _halfblock(Y_val, gN)
        else:                                        # neg-z: "33" reflection form
            if cy == 2:
                out += _halfblock(Y_val, 0)
                for _ in range(gYe - 2):
                    out += _halfblock(33, 0)
                out += _halfblock(33, gN)
            else:
                for _ in range(gYe - 1):
                    out += _halfblock(Y_val, 0) + _halfblock(33, 0)
        return out

    # --- group sections ---
    groups = b''
    fill = 0
    if cx == 2:
        if m_x >= 2:
            groups += interior(L)                    # interface-first section
            fill = 1
        else:
            groups += normal(gA)
        for _ in range(n_mid):
            groups += sep_groups + interior((IFV + 2 * (dn and fill >= 1)) % 256)
            fill += 1
        groups += sep_groups + normal((IFV + 2 * (dn and fill >= 1)) % 256)  # trailing
    else:
        groups += normal(gA)
        for _ in range(neg_cols + 1):
            groups += sep_groups + interior((IFV + 2 * (dn and fill >= 1)) % 256)
            fill += 1

    # --- layout ---
    if m_x < 2:
        pos1, mat_off, gap2 = _YZEDGE_LAYOUT_Y[cy]
        mat_off -= 10 * (pos_cols - 1)
        pos1 -= 2 * (min(neg_y, 2) - 1) * (cy == 1) * (cz == 2)
    elif cx == 2:                                    # interface side (capped layout)
        if cy == 2:
            pos1, mat_off, gap2 = 1, 314 - 10 * (pos_cols - 1), 2 * (cz == 1)
        else:
            pos1, mat_off, gap2 = 9, 306 - 10 * (pos_cols - 1), 10
    else:                                            # cx=1 source side
        if cy == 2:
            pos1 = 307 - 10 * (neg_cols - 2)
            mat_off, gap2 = 8, pos1 - 9
        else:
            pos1 = 315 - 10 * (neg_cols - 2)
            mat_off = 0
            gap2 = pos1 - 9 - 2 * (cz == 1) * (neg_cols % 2 == 0)
    trailing_len = mat_off
    marker_span = 5 * mYe * marker_cols + sep_w * (marker_cols - 1)
    lme = pos1 + marker_span
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    scan = bytearray(gs + len(groups) + trailing_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(marker_cols):
        scan[p:p + 5] = _marker(anchor if col == 0 else xstep, mN)
        p += 5
        for _ in range(mYe - 1):
            scan[p:p + 5] = _marker(ystep, mN)
            p += 5
        if col < marker_cols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * mYe * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, len(scan), flip=(marker_span % 2 == 1))
    scan[mat_byte_pos] = (mc - 2 * (cx == 1 and dn)) & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc


# ---------------------------------------------------------------------------
# MULTI-AXIS 3-PLANE CORNER crossing (x=0 AND y=0 AND z=0)
# ---------------------------------------------------------------------------

# Corner layout keyed by (cx,cy) -- it IS the x=0+y=0 edge layout (x,y the
# structural-plane dims); z only nudges gap2/pos1 by +-2. (pos1, mat_off):
_CORNER_LAYOUT = {(2, 2): (9, 314), (2, 1): (19, 306),
                  (1, 2): (317, 8), (1, 1): (325, 0)}


def generate_corner_crossing_scan(chunk, neg_cols=1, pos_cols=1,
                                  neg_y=1, pos_y=1, neg_z=1, pos_z=1):
    """MULTI-AXIS: one (cx,cy,cz) octant of a fill CROSSING x=0 AND y=0 AND z=0.

    The 3-plane corner -- all three single-axis crossings compose at once. It IS
    the y=0+z=0 edge logic with x ALSO crossing (so x has the cx=1 source / cx=2
    interface split even at the minimal footprint). VALUES additive with the
    per-axis steps (x=+-32, y=+-96, z=+-32), plus saturation/reflection terms that
    match the edges exactly:
        base   = 236 + 32*(cx==1) + 96*(cy==1) + 32*(cz==1)
        sat    = 55*(m_x-1) if cx==2 else 55*(neg_cols-1)    # x-wall thickness
        anchor = base + sat - (neg_z-1) - 35*(neg_y-1)
        gA     = base + sat + 19 - (gN-2)*(cz==1) - 35*(gYe-2)*(cy==1)
        mc     = 159 - 32*(cx==1) - 96*(cy==1) - 32*(cz==1) + 55*(pos_cols-1)*(cx==2)
                 - (gN-2)*(cz==2) - 35*(gYe-2)*(cy==2) + 2*(triple-neg)
    First section lead: normal-first uses mc for the all-positive (2,2,2) octant
    else gA; an interface-first section (cx=2, m_x>=2) uses L = mc (cy==2,cz==2) /
    anchor-36 (else).

    STRUCTURE: marker columns = pos_cols+m_x (cx=2) / neg_cols+1 (cx=1); cx=2 group
    sections = [interface-first if m_x>=2 else normal] + pos_cols interior + trailing;
    cx=1 = normal + (neg_cols+1) interior. Interior forms reuse the y=0+z=0 edge
    cy x cz combination (pos-y single / neg-y double pair; pos-z c0=gN-2 / neg-z 33),
    with double-neg fill +2 and the (1,1,1) mat byte = mc-2. LAYOUT = x=0+y=0 edge
    layout keyed by (cx,cy) at m_x=1 (z nudges gap2/pos1 +-2), or the x=0+y=0
    neg-x-saturated layout at m_x>=2 (identical to the yz edge).

    NEG-Y / NEG-Z SATURATION (2429 / 2431): anchor/gA/mc follow the edge rules; the
    new effect is that x-crossing INTERIOR sections take combined-saturation forms
    (m_y/m_z >= 2 act only on the interface side cy==2 / cz==2):
      - m_z>=2 (pos-z interface): each (Y0,c0) pair collapses to a single 33(N0).
      - m_y>=2 (pos-y interface): lead -> N0; cz2 prepends a c0; cz1 turns Y0 -> 33(0).
    A neg-y layout shift (pos1 -= 2 when m_y>=2, cy==2, (cx==2)!=(cz==2)). The
    double-neg "fill +2" and the (1,1,1) corner mc/mat-byte term scale to +gN
    (= 2 at gN=2, +3 at gN=3, ...) under z-depth.

    VALIDATED byte-exact (8 octants each): 2419 (min), 2421/2423/2425 (pos-x/y/z),
    2427 (neg-x; == yz-edge), 2429 (neg-y), 2431 (neg-z).

    COMBINED saturation (>=2 axes saturated -- symmetric / multi-thick cubes) is now
    FULLY byte-exact, validated on 2475 (4x4x4) and 2477 (6x6x6), all 8 octants each.
    The `comb` (nsat>=2) rules: marker depth/rows = max(p,n)+min(p,n,2); anchor wall-shift
    uses (neg-1) on the source side / (m-1) on the interface side per axis; first-section
    lead = antipodal-octant mc; interior +gN bump (pos-pos all interiors / neg-neg fills>=1);
    the cz=1 gap2 -2 also fires for cy==1; and the all-positive (2,2,2) octant uses a BARE
    4-byte anchor (no value, pos1=0, gap2=2, inverted trailing-bg flip). All COMB logic is
    gated on nsat>=2 so single-axis / asymmetric cases are untouched.
    """
    cx, cy, cz = chunk
    m_x = min(neg_cols, 2)
    m_y = min(neg_y, 2)
    m_z = min(neg_z, 2)
    gN = (pos_z if cz == 2 else neg_z) + 1
    mN = (neg_z + 1) if cz == 1 else (max(pos_z, neg_z) + min(pos_z, neg_z, 2))
    gYe = (pos_y if cy == 2 else neg_y) + 1
    mYe = (neg_y + 1) if cy == 1 else (max(pos_y, neg_y) + min(pos_y, neg_y, 2))
    marker_cols = (pos_cols + m_x) if cx == 2 else (neg_cols + 1)
    dn = (cy == 1 and cz == 1)
    sat = 55 * (m_x - 1) if cx == 2 else 55 * (neg_cols - 1)
    base = 236 + 32 * (cx == 1) + 96 * (cy == 1) + 32 * (cz == 1)
    gA_base = base + sat
    anchor = (gA_base - ((neg_z - 1) if cz == 1 else (m_z - 1)) - 35 * ((neg_y - 1) if cy == 1 else (m_y - 1))) % 256
    gA = (gA_base + 19 - (gN - 2) * (cz == 1) - 35 * (gYe - 2) * (cy == 1)) % 256
    mc = 512 + (159 - 32 * (cx == 1) - 96 * (cy == 1) - 32 * (cz == 1)
                + 55 * (pos_cols - 1) * (cx == 2)
                - (gN - 2) * (cz == 2) - 35 * (gYe - 2) * (cy == 2)
                + gN * (cx == 1 and dn)) % 256
    L = (mc & 0xff) if (cy == 2 and cz == 2) else (anchor - 36) % 256
    first_normal_lead = (mc & 0xff) if (cx == 2 and cy == 2 and cz == 2) else gA

    # COMBINED saturation (>=2 interface axes saturated): the first-section lead
    # becomes the ANTIPODAL octant's mc (params swapped). All COMB logic is gated on
    # nsat>=2, which only occurs for multi-axis-thick cubes -- never for the
    # single-axis / asymmetric cases, so it cannot regress them.
    def _mc_at(ax, ay, az, nc, pc, ny_, py_, nz_, pz_):
        _gN = (pz_ if az == 2 else nz_) + 1
        _gYe = (py_ if ay == 2 else ny_) + 1
        _dn = (ay == 1 and az == 1)
        return (159 - 32 * (ax == 1) - 96 * (ay == 1) - 32 * (az == 1)
                + 55 * (pc - 1) * (ax == 2) - (_gN - 2) * (az == 2)
                - 35 * (_gYe - 2) * (ay == 2) + _gN * (ax == 1 and _dn)) % 256
    nsat = (m_x >= 2) + (m_y >= 2) + (m_z >= 2)
    comb = nsat >= 2
    if comb:
        L = _mc_at(3 - cx, 3 - cy, 3 - cz, pos_cols, neg_cols,
                   pos_y, neg_y, pos_z, neg_z)
        first_normal_lead = L
    xstep = (234 - 35 * mYe - (mN - 1)) % 256
    ystep = (304 - _EFF_LZ - mN) % 256
    Y_val = (289 - gN) % 256
    IFV = (127 - 35 * (gYe - 2) - (gN - 2)) % 256

    sep_w = 8 - 2 * (mYe // 7)
    sep_groups = bytes([0xff, 0x00]) * (sep_w // 2)

    def normal(v):
        return _halfblock(v, gN) + _halfblock(Y_val, gN) * gYe

    def interior(v):
        # m_y/m_z saturation acts only on the interface side (cy==2 / cz==2):
        ysat = (m_y >= 2 and cy == 2)
        zsat = (m_z >= 2 and cz == 2)
        npairs = gYe if cy == 1 else gYe - 1
        out = _halfblock(v, 0 if ysat else gN)
        if cz == 2:                                # pos-z: c0 filler (= gN-2)
            if zsat:                               # z-sat: each pair collapses to 33(N0)
                out += _halfblock(33, 0) * npairs
            else:
                if ysat:                           # y-sat: prepend a c0
                    out += _halfblock(gN - 2, 0)
                for _ in range(npairs):
                    out += _halfblock(Y_val, 0) + _halfblock(gN - 2, 0)
            if cy == 2:
                out += _halfblock(Y_val, gN)
        else:                                      # neg-z: "33" reflection form
            if cy == 2:
                out += _halfblock(33 if ysat else Y_val, 0)  # y-sat turns Y0 -> 33(0)
                for _ in range(gYe - 2):
                    out += _halfblock(33, 0)
                out += _halfblock(33, gN)
            else:
                out += _halfblock(Y_val, 0)
                for _ in range(gYe - 1):
                    out += _halfblock(33, 0)
        return out

    groups = b''
    fill = 0
    bump = gN                                      # double-neg fill/corner bump (=gN)
    if cx == 2:
        if m_x >= 2:
            groups += interior(L)
            fill = 1
        else:
            groups += normal(first_normal_lead)
        for _ in range(pos_cols):
            ib = (dn and fill >= 1) or (comb and cy == 2 and cz == 2)
            groups += sep_groups + interior((IFV + bump * ib) % 256)
            fill += 1
        groups += sep_groups + normal((IFV + bump * (dn and fill >= 1)) % 256)
    else:
        groups += normal(first_normal_lead)
        for _ in range(neg_cols + 1):
            ib = (dn and fill >= 1) or (comb and cy == 2 and cz == 2)
            groups += sep_groups + interior((IFV + bump * ib) % 256)
            fill += 1

    # --- layout ---
    if m_x < 2:
        pos1, mat_off = _CORNER_LAYOUT[(cx, cy)]
        mat_off -= 10 * (pos_cols - 1) * (cx == 2)
        if (cx, cy) == (2, 2):
            gap2 = 2 * (cz == 1)
            pos1 += 2 * (cz == 1)
        elif (cx, cy) == (2, 1):
            gap2 = 10
        elif (cx, cy) == (1, 2):
            gap2 = 308
        else:
            gap2 = 316 - 2 * (cz == 1)
        pos1 -= 2 * (m_y >= 2 and cy == 2 and (cx == 2) != (cz == 2))
    elif cx == 2:                                  # neg-x saturated (== yz edge)
        if cy == 2:
            pos1, mat_off, gap2 = 1, 314 - 10 * (pos_cols - 1), 2 * (cz == 1)
        else:
            pos1, mat_off, gap2 = 9, 306 - 10 * (pos_cols - 1), 10
    else:
        if cy == 2:
            pos1 = 307 - 10 * (neg_cols - 2)
            mat_off, gap2 = 8, pos1 - 9
        else:
            pos1 = 315 - 10 * (neg_cols - 2)
            mat_off = 0
            gap2 = pos1 - 9 - 2 * (cz == 1) * ((neg_cols % 2 == 0) or (cy == 1))
    # All-positive innermost corner under combined sat: the col-0 anchor is a BARE
    # 4-byte tail [01,02,mN-1,00] (value omitted) at pos1=0 -> saves 1 byte vs the
    # normal 5-byte anchor; gap2 becomes 2. (Only fires for the (2,2,2) octant.)
    bare_anchor = comb and cx == 2 and cy == 2 and cz == 2
    if bare_anchor:
        pos1, gap2 = 0, 2
    trailing_len = mat_off
    marker_span = 5 * mYe * marker_cols + sep_w * (marker_cols - 1) - (1 if bare_anchor else 0)
    lme = pos1 + marker_span
    mat_byte_pos = lme + mat_off
    gs = mat_byte_pos + gap2

    scan = bytearray(gs + len(groups) + trailing_len)
    _fill_background(scan, 0, pos1)
    p = pos1
    for col in range(marker_cols):
        if col == 0 and bare_anchor:
            scan[p:p + 4] = bytes([0x01, 0x02, mN - 1, 0x00])  # bare anchor (no value)
            p += 4
        else:
            scan[p:p + 5] = _marker(anchor if col == 0 else xstep, mN)
            p += 5
        for _ in range(mYe - 1):
            scan[p:p + 5] = _marker(ystep, mN)
            p += 5
        if col < marker_cols - 1:
            _fill_background(scan, p, p + sep_w, flip=((5 * mYe * (col + 1)) % 2 == 1))
            p += sep_w
    _fill_background(scan, lme, len(scan), flip=((marker_span % 2 == 1) != bare_anchor))
    scan[mat_byte_pos] = (mc - gN * (cx == 1 and dn)) & 0xff
    scan[gs:gs + len(groups)] = groups
    return bytes(scan), mc
