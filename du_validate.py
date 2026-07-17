"""du_validate.py -- pre-deploy self-check for a generated h3 scan.

Turns the two client-crash classes into CAUGHT errors before a blueprint is written:
  * "Deserializing invalid vertex"  -> out-of-range marker/vertex bytes (the h=1 Top=0xff bug)
  * structural corruption           -> misaligned / incomplete / overrunning tokens

SCOPE / HONEST LIMITS:
  It CANNOT detect the +/-2 positional-offset bug (premat/grp_off vs DU's private layout
  math). That error leaves the scan internally self-consistent (mat_off, grp_off, trailing
  all shift together), so nothing in the bytes reveals it -- only a donor or the exact
  layout law can. For that, gate emission with in_confidence_region().

Structure recap (h3 scan, between the 64B header and the 40B material tail):
  lead(bg) | marker-planes (5B each, bg gaps between planes) | mat byte | group-lines
  (8B plain tokens or expanded tokens, bg gaps between lines) | trailing(bg)
  bg byte = 0x00 or 0xff (parity alternates, may flip after a written token).
"""

BG = (0x00, 0xff)


def _skip_bg(D, i):
    while i < len(D) and D[i] in BG:
        i += 1
    return i


def _is_marker(D, i):
    # marker vals 0x00 AND 0xff are LEGAL (H6 3588: val-0 ig=1 extra; C3 3594: val-0xff
    # wrapped opener at wide planes). Structure alone identifies a marker: bg bytes never
    # have 0x01 next (bg alternates 00/ff, so bg is followed by 00 or ff, or by a marker
    # whose SECOND byte is the 0x01).
    return (i + 5 <= len(D) and D[i + 1] == 1 and 2 <= D[i + 2] <= 17
            and D[i + 3] < 32 and D[i + 4] == 0)


def _read_token(D, i):
    """Parse one group token starting at i. Returns (length, kind, issue|None).
    plain  = [v,1,r,7e,7e,7e,r,0]                              (8B)
    inplace= [v,1,0,dx,dy,dz,0,0]                              (8B, run-0 displaced)
    expand = [v,1,r] + (r+1)*[dx,dy,dz,0] + [0]                (3 + 4*(r+1) + 1 B)"""
    if i + 8 > len(D):
        return 0, None, "token truncated at end of scan"
    v, one, r = D[i], D[i + 1], D[i + 2]
    if one != 1:
        return 0, None, f"token[{i}] second byte {one} != 1"
    if D[i + 3] == 0x7e and D[i + 4] == 0x7e and D[i + 5] == 0x7e and D[i + 6] == r and D[i + 7] == 0:
        return 8, "plain", None
    if r == 0 and D[i + 6] == 0 and D[i + 7] == 0:
        return 8, "inplace", None          # run-0 displaced token
    # expanded: 3 + 4*(r+1) + 1 bytes, quads end in 0, final byte 0
    ln = 3 + 4 * (r + 1) + 1
    if i + ln > len(D):
        return 0, None, f"expanded token[{i}] run {r} overruns scan"
    for q in range(r + 1):
        if D[i + 3 + 4 * q + 3] != 0:
            return 0, None, f"expanded token[{i}] quad {q} not 0-terminated"
    if D[i + ln - 1] != 0:
        return 0, None, f"expanded token[{i}] missing final 0"
    return ln, "expand", None


def parse_scan(scan):
    """Segment a scan; returns dict(lead, markers[], mat, groups[[toks]], trailing, issues[])."""
    D = scan
    issues = []
    def _skip_bg_m(i):
        # skip background but STOP at a marker start -- a marker's value byte can be 0x00 or
        # 0xff (H6/C3), so plain bg-membership would eat it.
        while i < len(D) and D[i] in BG and not _is_marker(D, i):
            i += 1
        return i
    i = _skip_bg_m(0)
    lead = i
    # marker planes (bg gaps between planes)
    markers = []
    while _is_marker(D, i):
        while _is_marker(D, i):
            markers.append(tuple(D[i:i + 5])); i += 5
        j = _skip_bg_m(i)
        if _is_marker(D, j):
            i = j
        else:
            i = j; break
    else:
        i = _skip_bg_m(i)
    mat_off = i
    if i >= len(D):
        issues.append("no mat byte / group region"); return dict(lead=lead, markers=markers,
            mat=None, mat_off=None, groups=[], trailing=0, issues=issues)
    mat = D[i]; i += 1
    mat_hidden = False
    if i < len(D) and D[i] == 0x01:
        ln, kind, iss = _read_token(D, i - 1)
        if iss is None:
            # the byte we grabbed is the VALUE byte of a well-formed group token -> the real
            # mat byte is bg-valued (0x00/0xff, invisible inside the pre-mat background run;
            # WNC13 exposed this). Its value is UNRECOVERABLE from scan bytes alone.
            mat = None; mat_hidden = True; i -= 1
    # group lines: tokens are CONTIGUOUS within a line and marked by the 0x01 second byte
    # (a token value byte can itself be 0x00, so 'non-bg' cannot delimit tokens -- background
    # is only 00/ff and never has 0x01 as its next byte). bg RUNS separate lines.
    def _tok_start(k):
        if k + 1 >= len(D) or D[k + 1] != 0x01:
            return False
        if D[k] != 0xff:
            return True
        # 0xff-VALUED tokens are legal (e.g. 33-h wall vals mod 256; WNC13 exposed this) but a
        # bg 0xff followed by a token whose VALUE is 0x01 would alias -- accept the 0xff start
        # only if a token parses cleanly here.
        ln, kind, iss = _read_token(D, k)
        return iss is None
    groups = []
    end = len(D)
    while end > 0 and D[end - 1] in BG:
        end -= 1

    def _skip_gap(i):
        # advance over a bg gap to the next token start; a true gap is pure background, so an
        # orphan non-bg byte here is corruption (e.g. a token whose 0x01 marker got clobbered).
        while i < end and not _tok_start(i):
            if D[i] not in BG:
                issues.append(f"orphan non-bg byte {D[i]:#x} at {i} (corrupt/misaligned token)")
            i += 1
        return i

    i = _skip_gap(i)
    while i < end:
        line = []
        while i < end and _tok_start(i):
            ln, kind, iss = _read_token(D, i)
            if iss:
                issues.append(iss); i = end; break
            line.append((kind, tuple(D[i:i + ln]))); i += ln
        if line:
            groups.append(line)
        i = _skip_gap(i)
    trailing = len(D) - end
    return dict(lead=lead, markers=markers, mat=mat, mat_off=mat_off, mat_hidden=mat_hidden,
                groups=groups, trailing=trailing, issues=issues)


def validate_scan(scan, expect_planes=None):
    """Return (ok, issues). Structural + vertex-range checks (see module docstring for scope)."""
    P = parse_scan(scan)
    issues = list(P["issues"])
    if not P["markers"]:
        issues.append("no marker planes found")
    for m in P["markers"]:
        v, one, b2, hm1, z = m
        if one != 1 or z != 0:
            issues.append(f"marker {m} not [v,1,b2,h-1,0]")
        if hm1 >= 32:
            issues.append(f"marker height-1 {hm1} >= 32 (invalid vertex risk)")
        # NOTE: marker VALUES 0x00 and 0xff are LEGAL (donor-proven: H6 3588 val-0 ig=1
        # extra; C3 3594 val-0xff wrapped wide-plane opener) -- no value-range check.
    if P["mat"] is None and not P.get("mat_hidden"):
        issues.append("missing material byte")
    ntok = sum(len(l) for l in P["groups"])
    if ntok == 0:
        issues.append("no group tokens (empty surface)")
    if expect_planes is not None and len(P["markers"]) not in (expect_planes, expect_planes - 1):
        issues.append(f"marker-plane count {len(P['markers'])} != expected {expect_planes}(±1)")
    return (len(issues) == 0), issues


def has_enclosed_cavity(cols):
    """True if the shape has empty voxels fully ENCLOSED (unreachable from outside the bounding
    box) -- a SEALED cavity (SB 3548). DU encodes such a void with a compact inner surface that
    our per-column overhang machinery does NOT reproduce (it over-emits ~2x tokens -> a too-long
    scan that crashes DU, which the structural validator cannot detect). Z-through holes/tubes
    and OPEN overhangs stay reachable from outside -> not flagged. Not yet decoded."""
    from collections import deque
    vox = set()
    for (x, y), ivs in cols.items():
        if isinstance(ivs, tuple) and len(ivs) == 2 and isinstance(ivs[0], int):
            ivs = [ivs]                       # bare (zlo,zhi) -> single-interval list
        for a, b in ivs:
            for z in range(a, b + 1):
                vox.add((x, y, z))
    if not vox:
        return False
    xs = [p[0] for p in vox]; ys = [p[1] for p in vox]; zs = [p[2] for p in vox]
    lo = (min(xs) - 1, min(ys) - 1, min(zs) - 1); hi = (max(xs) + 1, max(ys) + 1, max(zs) + 1)
    seen = {lo}; dq = deque([lo])
    while dq:
        x, y, z = dq.popleft()
        for dx, dy, dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            n = (x+dx, y+dy, z+dz)
            if all(lo[i] <= n[i] <= hi[i] for i in range(3)) and n not in seen and n not in vox:
                seen.add(n); dq.append(n)
    for x in range(min(xs), max(xs)+1):
        for y in range(min(ys), max(ys)+1):
            for z in range(min(zs), max(zs)+1):
                if (x, y, z) not in vox and (x, y, z) not in seen:
                    return True
    return False


def has_capped_wall_void(cols):
    """True only for the h=1 FAMILY in gapped columns -- the one unsupported void case:
    (a) 1-voxel-TALL z-gap (ig-1=0 marker bg-ambiguous: PW2), or (b) 1-voxel-THICK interval
    in a multi-interval column (chain val h-2 = 0xff invalid: 3548's 1-thick shell).
    Windows/doors AND sealed cavities are otherwise FULLY SUPPORTED (2026-07-14, 14 donors:
    1/2/3-wide, stacked, multi, diff-z, thick walls, sealed cubic/non-cubic/two-cavity) --
    region WVOID + direction-symmetric interval-chain in du_general."""
    for (x, y), ivs in cols.items():
        if isinstance(ivs, tuple) and len(ivs) == 2 and isinstance(ivs[0], int):
            continue
        ivs = sorted(ivs)
        for i in range(1, len(ivs)):
            if ivs[i][0] - ivs[i-1][1] - 1 == 1:
                return True                       # 1-tall gap
        if any(b - a + 1 < 2 for a, b in ivs):
            return True                           # 1-thick interval in a gapped col
    return False


def in_confidence_region(cols, xseam_lo=False, xopen_hi=False, yseam=False, zseam=False):
    """Guard for the KNOWN-UNMAPPED single-chunk +/-2 layout pocket (2026-07-14 grid).
    Returns (safe, reason). Multi-chunk / seam chunks use the proven path -> safe.
    Single-chunk with nx>=6 sits in the unmapped nx*x0*z interaction -> flag."""
    # windows + sealed cavities + the FULL h=1 family SUPPORTED (2026-07-14: H1-H4/H6 + 3548;
    # flat/stepped h=1 incl 1-thick shells and 1-tall gaps -- val-0 markers are legal).
    # CAUTION not flagged here: CURVED h=1 (dome rims) has no donor yet -- pipeline keeps
    # to_columns(min_thickness=2) as its default for curved shapes.
    if xseam_lo or xopen_hi or yseam or zseam:
        if yseam:
            # curved-Y crossings are only PARTIALLY decoded (item 14: yseam high-chunk
            # boundary restructure + plateau/descending yopen tails + layout cells) --
            # flag CURVED shapes; flat Y-crossings are proven (3187/3380).
            ys_all = sorted(y for _, y in cols)
            tops = {tuple(v[-1]) if isinstance(v, list) else tuple(v) for v in cols.values()}
            if len({t[1] for t in tops}) > 1:
                return False, "curved shape crossing a Y chunk boundary: item-14 sub-decodes open"
        return True, "seam/multi-chunk path (proven)"
    xs = sorted({x for x, _ in cols})
    nx = len(xs)
    y0 = min(y for _, y in cols)
    # Single-chunk layout +/-2 pockets, NARROWED 2026-07-14 (late): nx==6 ONLY -- the E/G/3497
    # grid anomaly (premat/grp_off +2, x0*z-dependent; H corner clean). nx7/8/10 single-chunks
    # all byte-exact (SC2/SC3/3500/3508/SC4-6 + pad-kink law for nx>=10). nx<=3 = shifted
    # lead-y transitions (nx3 y13/y21). Lead-y transition rows partly probed at nx>=4.
    if nx == 6:
        # 2026-07-16 P6A-F sweep: hooks live at the LEAD SHORT-STEP cells xp%5==1 (x0 9/14/19:
        # pad+2 / grp+2&lead+2(z20) / grp+2(z20)), attenuating with x0 (x0 24 clean); x0 11/24
        # proven clean BOTH z (donors 3734/3736/3742/3744). Everything else unswept.
        x0 = xs[0]
        if x0 in (11, 24):
            pass                                  # proven-clean cells
        else:
            return False, (f"single-chunk nx=6 x0={x0}: lead-short-step pocket "
                           "(pad/lead/grp +2 hooks at xp%5==1, unmapped in between)")
    # nx<=3: RESOLVED 2026-07-16 (items 6+7) -- 7-period lead y-law + %7 pad y-band, donors
    # 3520-3534 reclaimed byte-exact. No flag.
    maxnc = max(len([1 for (xx, y) in cols if xx == x]) for x in xs)
    if maxnc >= 18:
        return False, f"curved maxnc={maxnc} (>=18): pad base extrapolated (donors stop at 17)"
    yp = y0 - 8
    xs0 = xs[0]
    if nx <= 4 and xs0 > 8 and y0 > 8:
        # off-origin small-nx positional-hook pocket (2026-07-16, C315 family): x20*y10 ->
        # grp_off+2; +z18 -> also pad-2. Single-axis moves are CLEAN (donors 3770-3780);
        # the interaction cells are unmapped beyond (20,10,18).
        return False, (f"single-chunk nx={nx} at x0={xs0},y0={y0} (both off-origin): "
                       "positional grp/pad hook pocket (C315 family), unmapped")
    if 5 <= nx <= 7 and (2*((yp+1)//7) != 2*((yp+4)//9)):
        # the ONLY remaining lead-y unknown: the nx5-7 boundary between the 7-period (nx<=4)
        # and 9-period (nx>=8) y-laws, at rows where they DISAGREE (items 6/7, 2026-07-16).
        return False, f"single-chunk nx={nx}, y0={y0}: 7- vs 9-period lead-y laws disagree here"
    return True, f"single-chunk nx={nx} y0={y0} in confirmed band"
