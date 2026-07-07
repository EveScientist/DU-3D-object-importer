"""du_dense.py — dense-lineage closed-shape generator (top+bottom surfaces).

Decoded 2026-07-07 from probes 3156/3157 (two-surface), 3160 (sides),
3162 (4x4x4 walk order). See memory closed_shapes_kickoff PROBE 1/2/3.

DENSE SURFACE SCAN WALK ORDER (validated vs 3162):
  scan = (Ncols_x + 1) SECTIONS = X-planes (x = xlo .. xlo+Ncols_x),
         separated by empty-pair gaps.  X = slow/outer, Y = fast/inner.
  - BOUNDARY planes (x=xlo, x=xhi): run-N groups only (side faces).
  - INTERIOR planes: [y=ylo edge run-N] [ for interior y: Bottom(run0),Top(run0) ] [y=yhi edge run-N]
  Each interior (x,y) column has exactly two surface vertices:
      Bottom (emitted first) then Top (adjacent, +8 bytes), both run-0,
      8-byte IN-PLACE, displacement in the z-slot (group_start+5).
  enc(d) = (d + 126) & 0xff, 84 steps/voxel, d in signed steps.

This module reads a plain donor scan, locates the interior Bottom/Top
z-slots, and writes per-column top/bottom surface displacements to carve a
closed shape (lens/capsule: domed top + domed bottom, flat sides).
Side (vertical-face) rounding via the run-N groups is a later increment.
"""
import json, base64, lz4.block, copy, struct
import du_hash, du_assemble

DEFAULT = 0x7e  # 126 = no displacement


def load_scan(path):
    bp = json.load(open(path))
    for e in bp['VoxelData']:
        if e['h'] != 3:
            continue
        raw = base64.b64decode(e['records']['voxel']['data']['$binary'])
        size = int.from_bytes(raw[4:8], 'little')
        dec = lz4.block.decompress(raw[12:], uncompressed_size=size)
        return bytearray(dec[64:-40])
    raise ValueError('no h3 chunk')


def _is_group(scan, i):
    """Return ('run0'|'runN', run) if an 8-byte halfblock starts at i, else None."""
    if i + 8 > len(scan):
        return None
    if scan[i + 1] != 0x01:
        return None
    run = scan[i + 2]
    if scan[i + 6] != run:
        return None            # expanded (12/16B) or not a plain halfblock
    if scan[i + 7] != 0x00:
        return None
    return ('run0' if run == 0 else 'runN', run)


def parse_columns(scan, xlo, ylo):
    """Walk the surface scan; return {(x,y): (bottom_off, top_off)} for every
    interior column, using section index -> x = xlo + s and column index ->
    y = ylo + 1 + c. Sections are separated by empty-pair gaps."""
    # First, tokenize groups with their start offsets, tracking gaps.
    groups = []          # (offset, kind, run)
    i = 0
    last_end = None
    gap_before = []      # parallel: bytes of empty gap immediately before this group
    while i < len(scan):
        g = _is_group(scan, i)
        if g:
            gb = 0 if last_end is None else (i - last_end)
            groups.append((i, g[0], g[1], gb))
            last_end = i + 8
            i += 8
            continue
        i += 1
    # Split into sections at empty gaps (gap_before > 0 after the first group).
    sections = []
    cur = []
    for idx, (off, kind, run, gb) in enumerate(groups):
        if idx > 0 and gb > 0:
            sections.append(cur)
            cur = []
        cur.append((off, kind, run))
    if cur:
        sections.append(cur)
    # Map interior sections/columns to coords.
    cols = {}
    for s, sec in enumerate(sections):
        x = xlo + s
        # interior section iff it contains run-0 groups
        run0 = [g for g in sec if g[1] == 'run0']
        if not run0:
            continue  # boundary plane (all run-N) -> side face, skip
        # run-0 groups come in Bottom,Top pairs in order
        assert len(run0) % 2 == 0, f'section {s} odd run0 count {len(run0)}'
        for c in range(len(run0) // 2):
            bottom_off = run0[2 * c][0]
            top_off = run0[2 * c + 1][0]
            y = ylo + 1 + c
            cols[(x, y)] = (bottom_off, top_off)
    return cols, sections


def enc(d):
    return (int(round(d)) + 126) & 0xff


def _sections(scan):
    """Return list of sections; each = list of (offset, kind, run). Sections split
    on empty-pair gaps between groups (see parse_columns)."""
    groups = []
    i = 0
    last_end = None
    while i < len(scan):
        g = _is_group(scan, i)
        if g:
            gb = 0 if last_end is None else (i - last_end)
            groups.append((i, g[0], g[1], gb))
            last_end = i + 8
            i += 8
            continue
        i += 1
    sections, cur = [], []
    for idx, (off, kind, run, gb) in enumerate(groups):
        if idx > 0 and gb > 0:
            sections.append(cur)
            cur = []
        cur.append((off, kind, run))
    if cur:
        sections.append(cur)
    return sections


def parse_sides(scan, xlo, ylo, zlo):
    """Map side-face run-N groups to geometry.
    Returns {('-X'|'+X', y): (offset, run), ('-Y'|'+Y', x): (offset, run)}.
    Boundary X-planes (all run-N) are the +/-X faces indexed by y=ylo+i;
    interior planes' first/last run-N edge groups are the -/+Y faces indexed by x."""
    secs = _sections(scan)
    sides = {}
    n = len(secs)
    for s, sec in enumerate(secs):
        x = xlo + s
        has_run0 = any(k == 'run0' for (_, k, _) in sec)
        if not has_run0:
            face = '-X' if s == 0 else ('+X' if s == n - 1 else None)
            if face is None:
                continue
            for i, (off, kind, run) in enumerate(sec):
                sides[(face, ylo + i)] = (off, run)
        else:
            # interior plane: first group = -Y edge, last = +Y edge (both run-N)
            first, last = sec[0], sec[-1]
            if first[1] == 'runN':
                sides[('-Y', x)] = (first[0], first[2])
            if last[1] == 'runN':
                sides[('+Y', x)] = (last[0], last[2])
    return sides


def _expand_side(val, run, level_disp):
    """Full per-z-level side group (validated vs 3166 y=9/y=11):
    [val,01,run] + (enc(dx),enc(dy),enc(dz),00)*(run+1) + 00.
    level_disp: dict k(0..run) -> (dx,dy,dz) steps; missing = (0,0,0)."""
    out = bytearray([val & 0xff, 0x01, run & 0xff])
    for k in range(run + 1):
        dx, dy, dz = level_disp.get(k, (0, 0, 0))
        out += bytes([enc(dx), enc(dy), enc(dz), 0x00])
    out += b'\x00'
    return bytes(out)


def apply_sides(scan, xlo, ylo, zlo, side_fn):
    """Rebuild scan, expanding side groups per side_fn(face, tangential, z_level)->
    perpendicular displacement in steps (X for +/-X faces, Y for +/-Y faces).
    z_level is the absolute z grid-line (zlo..zlo+run). Returns new scan bytes."""
    sides = parse_sides(scan, xlo, ylo, zlo)
    # build offset -> expanded-bytes replacements
    repl = {}
    for (face, tang), (off, run) in sides.items():
        val = scan[off]
        level_disp = {}
        for k in range(run + 1):
            z = zlo + k
            d = side_fn(face, tang, z)
            if d:
                if face in ('-X', '+X'):
                    level_disp[k] = (d, 0, 0)
                else:
                    level_disp[k] = (0, d, 0)
        if level_disp:
            repl[off] = (_expand_side(val, run, level_disp), 8)
    if not repl:
        return bytes(scan)
    # rebuild: copy through, substituting 8-byte groups at repl offsets
    out = bytearray()
    i = 0
    while i < len(scan):
        if i in repl:
            newbytes, oldlen = repl[i]
            out += newbytes
            i += oldlen
        else:
            out.append(scan[i])
            i += 1
    return bytes(out)


def apply_surfaces(scan, cols, top_fn=None, bottom_fn=None):
    """Write z-slot displacements. top_fn/bottom_fn: (x,y)->steps (signed) or None.
    Returns a new scan (in-place 8-byte, no length change)."""
    out = bytearray(scan)
    for (x, y), (b_off, t_off) in cols.items():
        if top_fn is not None:
            out[t_off + 5] = enc(top_fn(x, y))
        if bottom_fn is not None:
            out[b_off + 5] = enc(bottom_fn(x, y))
    return out


def apply_shape(scan, disp_fn, xlo, ylo, zlo, ncx, ncy, ncz):
    """Drive EVERY surface vertex from one field. disp_fn(gx,gy,gz)->(dx,dy,dz) steps.
    Interior (x,y) top/bottom -> run-0 in-place (all 3 slots); side faces -> expanded
    per-z-level triples. One consistent field keeps shared edges continuous.
    Grid lines span xlo..xlo+ncx etc.; interior columns at (xlo+1..xhi-1)."""
    xhi, yhi, zhi = xlo + ncx, ylo + ncy, zlo + ncz
    scan = bytearray(scan)
    cols, _ = parse_columns(scan, xlo, ylo)
    for (x, y), (b, t) in cols.items():
        dxb, dyb, dzb = disp_fn(x, y, zlo)
        dxt, dyt, dzt = disp_fn(x, y, zhi)
        scan[b + 3], scan[b + 4], scan[b + 5] = enc(dxb), enc(dyb), enc(dzb)
        scan[t + 3], scan[t + 4], scan[t + 5] = enc(dxt), enc(dyt), enc(dzt)
    sides = parse_sides(scan, xlo, ylo, zlo)
    repl = {}
    for (face, tang), (off, run) in sides.items():
        val = scan[off]
        level_disp = {}
        for k in range(run + 1):
            z = zlo + k
            if face in ('-X', '+X'):
                gx = xlo if face == '-X' else xhi
                gy, gz = tang, z
            else:
                gy = ylo if face == '-Y' else yhi
                gx, gz = tang, z
            d = disp_fn(gx, gy, gz)
            if any(d):
                level_disp[k] = d
        if level_disp:
            repl[off] = (_expand_side(val, run, level_disp), 8)
    if not repl:
        return bytes(scan)
    out = bytearray()
    i = 0
    while i < len(scan):
        if i in repl:
            nb, ol = repl[i]
            out += nb
            i += ol
        else:
            out.append(scan[i])
            i += 1
    return bytes(out)


def build_blueprint(donor_path, out_path, scan, cx=8, cy=8, cz=8):
    """Clone donor envelope, substitute the (single) h3 chunk's scan+hash."""
    bp = json.load(open(donor_path))
    out = copy.deepcopy(bp)
    for e in out['VoxelData']:
        if e['h'] != 3:
            continue
        # recover mc from donor decoded blob
        raw = base64.b64decode(e['records']['voxel']['data']['$binary'])
        size = int.from_bytes(raw[4:8], 'little')
        dec = lz4.block.decompress(raw[12:], uncompressed_size=size)
        mc = struct.unpack('<I', dec[-40:-36])[0]
        b64, h = du_assemble.encode_voxel_b64(cx, cy, cz, bytes(scan), mc)
        e['records']['voxel']['data']['$binary'] = b64
        e['records']['voxel']['hash']['$numberLong'] = h
        break
    json.dump(out, open(out_path, 'w'))
    return out_path


# --------------------------------------------------------------------------
def _selftest():
    scan = load_scan('exports/3162_export.blueprint')
    # reconstruct plain by zeroing the 7 known z-slots
    disp = {(9, 9): (-24, 18), (10, 10): (-42, 34), (11, 11): (-60, 50),
            (9, 11): (None, 70)}
    plain = bytearray(scan)
    cols, _ = parse_columns(plain, xlo=8, ylo=8)
    # zero every interior z-slot -> plain
    for (x, y), (b, t) in cols.items():
        plain[b + 5] = DEFAULT
        plain[t + 5] = DEFAULT
    assert bytes(plain) != bytes(scan)
    # re-inject the 7 -> must byte-match 3162
    def tf(x, y):
        return disp.get((x, y), (None, None))[1]
    def bf(x, y):
        v = disp.get((x, y), (None, None))[0]
        return v

    recon = bytearray(plain)
    for (x, y), (b, t) in cols.items():
        tv = tf(x, y)
        bv = bf(x, y)
        if tv is not None:
            recon[t + 5] = enc(tv)
        if bv is not None:
            recon[b + 5] = enc(bv)
    ok = bytes(recon) == bytes(scan)
    print(f'selftest reconstruct 3162: {"OK" if ok else "FAIL"}')
    print(f'parsed interior columns: {sorted(cols)}')
    return ok


if __name__ == '__main__':
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    _selftest()
