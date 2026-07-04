"""PREDICTION harness for the y=0+z=0 SURFACE corner (Build AT), transposing
the pinned xz-corner rules (2945/2947) with y in x's role. Run against the
export the moment it lands:

    python3 tests/predict_yz_corner_0704.py <export_num>

Build AT (12 vox, hcCarbon):
    X in {10.5, 11.5, 12.5}  x  Y in {-0.5, +0.5}  x  Z in {-0.5, +0.5}
Chunks: (8,8,8) +y+z, (8,7,8) -y+z, (8,8,7) +y-z, (8,7,7) -y-z.

Transposed hypotheses (each may be wrong -- that's the point of the harness):
  H1 +y chunks = gen_seam_z_high/low at ly0=-1 (ghost row first).
  H2 -y chunks = same at ly0=31 with the fwd-ghost rule's Y-ANALOG: the z-seam
     interior transform extends to ALL rows of each interior cluster (k <=
     ny-1), not just k < ny-1 -- mirroring how x_fwd_ghost extended the
     special range over clusters.
  H3 jitter: the x0 corner jitter (-4: pad pair before preval + trailing pair)
     applies to +y+z, +y-z, -y+z but NOT the double-negative -y-z. The x0
     jitter is a base-position effect; y may have a different/no analog, so
     each chunk is ALSO diffed against its no-jitter variant.
For every chunk the harness prints which candidate (if any) is byte-exact,
else the closest candidate's first-diff context.
"""
import sys
sys.path.insert(0, "/home/du")
import du_solid as D
from du_solid import (gen_heightmap_unified, _fg0, _flat_groups, _zgrp,
                      _seam_nx_step, _seam_z_value_nudge, _x0_corner_jitter)
from tests.archive.test_du_solid_seams import chunks


def z_high_yfwd(nx, ny, ly0, depth=2, all_rows=False):
    """Degenerate-form z-high with optional Y-analog of the fwd-ghost rule:
    interior clusters' special treatment covers ALL content rows."""
    inner = depth - 2
    g = gen_heightmap_unified([[depth] * ny] * nx, lx0=10, ly0=ly0, lz0=-1)
    gs = _flat_groups(g); f0 = _fg0(g)
    gvals = [(g[i], g[i+2]) for i in gs]
    clgap = bytes([255, 0]) * (4 - (ny >= 6))
    fg = bytearray(); idx = 0
    for c in range(nx + 1):
        ov, orr = gvals[idx]; idx += 1; fg += _zgrp(ov, orr)
        content = gvals[idx:idx + ny]; idx += ny
        if 1 <= c <= nx - 1:
            hi = ny if all_rows else ny - 1
            for k in range(hi):
                fg += _zgrp(content[k][0], 0) + _zgrp(inner, 0)
            for k in range(hi, ny):
                fg += _zgrp(*content[k])
        else:
            for v, r in content:
                fg += _zgrp(v, r)
        if c < nx:
            fg += clgap
    return _seam_nx_step(bytes(g[:f0]) + bytes(fg) + bytes(g[gs[-1] + 8:]), nx)


def z_low_yfwd(nx, ny, ly0, depth=2, all_rows=False):
    g = bytearray(gen_heightmap_unified([[depth] * ny] * nx, lx0=10, ly0=ly0,
                                        lz0=31, cz_neg=True))
    gs = _flat_groups(g); per = 1 + ny
    for c in range(1, nx):
        b = c * per
        for k in range(ny):
            gi = gs[b + 1 + k]
            if k == 0:
                if ny > 1:
                    g[gi+2] = 0; g[gi+6] = 0
            else:
                g[gi] = 33
                if k < ny - 1 or all_rows:
                    g[gi+2] = 0; g[gi+6] = 0
    _seam_z_value_nudge(g, gs, 2)
    return _seam_nx_step(bytes(g), nx)


def diff(ref, got, label):
    if got == ref:
        return f"  BYTE-EXACT: {label}"
    n = min(len(ref), len(got))
    i = next((j for j in range(n) if ref[j] != got[j]), n)
    return (f"  {label}: len ref={len(ref)} got={len(got)} first@{i}\n"
            f"    ref: {ref[max(0,i-8):i+24].hex(' ')}\n"
            f"    got: {got[max(0,i-8):i+24].hex(' ')}")


def main(num):
    c = chunks(num)
    NX = 3  # 3 x-cols
    cands = {
        (8, 8, 8): [('zhigh@ly-1 +jit', _x0_corner_jitter(D.gen_seam_z_high(NX, 2, ly0=-1))),
                    ('zhigh@ly-1', D.gen_seam_z_high(NX, 2, ly0=-1))],
        (8, 8, 7): [('zlow@ly-1 +jit', _x0_corner_jitter(D.gen_seam_z_low(NX, 2, ly0=-1))),
                    ('zlow@ly-1', D.gen_seam_z_low(NX, 2, ly0=-1))],
        (8, 7, 8): [('zhigh@ly31 allrows +jit', _x0_corner_jitter(z_high_yfwd(NX, 2, 31, all_rows=True))),
                    ('zhigh@ly31 allrows', z_high_yfwd(NX, 2, 31, all_rows=True)),
                    ('zhigh@ly31 plain', D.gen_seam_z_high(NX, 2, ly0=31)),
                    ('zhigh@ly31 plain +jit', _x0_corner_jitter(D.gen_seam_z_high(NX, 2, ly0=31)))],
        (8, 7, 7): [('zlow@ly31 allrows', z_low_yfwd(NX, 2, 31, all_rows=True)),
                    ('zlow@ly31 plain', D.gen_seam_z_low(NX, 2, ly0=31)),
                    ('zlow@ly31 allrows +jit', _x0_corner_jitter(z_low_yfwd(NX, 2, 31, all_rows=True)))],
    }
    for key in sorted(cands):
        ref = c.get(key)
        print(f"### chunk {key}" + ("" if ref is not None else "  -- MISSING IN EXPORT"))
        if ref is None:
            continue
        hits = [lab for lab, got in cands[key] if got == ref]
        if hits:
            print(f"  BYTE-EXACT: {hits}")
        else:
            for lab, got in cands[key]:
                print(diff(ref, got, lab))


if __name__ == '__main__':
    main(int(sys.argv[1]))
