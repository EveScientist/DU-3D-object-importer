"""Mesh -> displaced-voxel solver (END-GOAL arc).

Computes, for every placed surface voxel, where the encoding's vertex slots
must sit to recreate an .obj shape as accurately as possible -- per the
2026-07-04 decision there is NO DU-smoother value function to reverse: we
choose displacement values straight from the mesh.

Increment 1 (this file): single-chunk heightmap-style (single top surface)
patches. The byte layer underneath is already proven: gen_surface_displaced /
gen_smooth_surface (byte-exact vs ramps 2689/2691/2700 + tilt), and mc is
displacement-invariant (3048 == 3081), so a displaced blueprint can reuse its
blocky shape's mc/envelope.

Solver conventions:
  * Grid: voxel columns (cell (i,j) spans [i,i+1)x[j,j+1) in local units, z
    from a base plane). Corners are the (nx+1)x(ny+1) lattice points.
  * Blocky height H[i][j] = surface z at the CELL CENTER rounded to the
    nearest voxel (keeps vertex offsets small and centered; the slot range
    is +-1.5 voxels; DU units: 84 steps per voxel). Callers may override H
    when a specific blocky occupancy is required (e.g. donor-envelope reuse).
  * Corner vertex offset dz = (surface_z(corner) - h_ref) * 84, where h_ref =
    the max blocky height among the corner's adjacent cells (the encoding's
    pair-max convention: a shared corner-group belongs to the tallest
    neighbor's top face).
Validated offline: a planar ramp mesh reproduces gen_linear_ramp byte-exactly
and a tilted plane reproduces gen_smooth_surface (see tests in __main__ /
tests/archive/test_du_solid_seams.py).
"""
import sys

sys.path.insert(0, "/home/du")
import du_solid as D
from obj_to_du_voxels import load_obj


def top_z(verts, faces, x, y):
    """Highest surface z of the mesh at vertical line (x, y); None if the
    mesh doesn't cover that point in xy-projection."""
    best = None
    for f in faces:
        for k in range(1, len(f) - 1):          # fan-triangulate
            a, b, c = verts[f[0]], verts[f[k]], verts[f[k + 1]]
            d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(d) < 1e-12:
                continue
            w0 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
            w1 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
            w2 = 1.0 - w0 - w1
            eps = -1e-9
            if w0 >= eps and w1 >= eps and w2 >= eps:
                z = w0 * a[2] + w1 * b[2] + w2 * c[2]
                if best is None or z > best:
                    best = z
    return best


def solve_patch(verts, faces, nx, ny, x0=0.0, y0=0.0, zbase=0.0, H=None):
    """Solve an nx x ny column patch against the mesh's top surface.
    Returns (H, vlist) for gen_surface_displaced: H = blocky heightmap
    (voxels above zbase per cell; center-rounded unless overridden), vlist =
    per-corner (V0, V1) in emit order (column-major x-outer), V1 = (0,0,dz84)
    top-vertex offset."""
    cz = [[None] * (ny + 1) for _ in range(nx + 1)]
    for i in range(nx + 1):
        for j in range(ny + 1):
            z = top_z(verts, faces, x0 + i, y0 + j)
            cz[i][j] = None if z is None else z - zbase
    if H is None:
        H = []
        for i in range(nx):
            col = []
            for j in range(ny):
                zc = top_z(verts, faces, x0 + i + 0.5, y0 + j + 0.5)
                assert zc is not None, f"cell ({i},{j}) not covered by mesh"
                col.append(max(1, round(zc - zbase)))
            H.append(col)
    vlist = []
    for i in range(nx + 1):
        for j in range(ny + 1):
            adj = [H[ci][cj] for ci in (i - 1, i) for cj in (j - 1, j)
                   if 0 <= ci < nx and 0 <= cj < ny]
            h_ref = max(adj)
            z = cz[i][j]
            dz = 0 if z is None else round((z - h_ref) * 84)
            vlist.append((D.ORIGIN, D.ORIGIN) if dz == 0
                         else (D.ORIGIN, (0, 0, dz)))
    return H, vlist


def gen_from_mesh(obj_path_or_geom, nx, ny, x0=0.0, y0=0.0, zbase=0.0,
                  lx0=10, ly0=10, lz0=10):
    """Mesh -> displaced single-chunk scan. obj_path_or_geom = path to an .obj
    or a (verts, faces) tuple."""
    if isinstance(obj_path_or_geom, tuple):
        verts, faces = obj_path_or_geom
    else:
        verts, faces = load_obj(obj_path_or_geom)
    H, vlist = solve_patch(verts, faces, nx, ny, x0=x0, y0=y0, zbase=zbase)
    return D.gen_surface_displaced(H, vlist, lx0=lx0, ly0=ly0, lz0=lz0)


# ── synthetic test geometry ──────────────────────────────────────────────────
def plane_mesh(nx, ny, zfn, pad=1.0):
    """Triangulated graph surface z = zfn(x, y) over [-pad, nx+pad] x
    [-pad, ny+pad], sampled at unit resolution (exact for piecewise-planar
    zfn; fine enough for the solver's lattice sampling either way)."""
    xs = [x - pad for x in range(int(nx + 2 * pad) + 1)]
    ys = [y - pad for y in range(int(ny + 2 * pad) + 1)]
    verts = []
    idx = {}
    for x in xs:
        for y in ys:
            idx[(x, y)] = len(verts)
            verts.append((float(x), float(y), float(zfn(x, y))))
    faces = []
    for a in range(len(xs) - 1):
        for b in range(len(ys) - 1):
            p = idx[(xs[a], ys[b])]; q = idx[(xs[a + 1], ys[b])]
            r = idx[(xs[a + 1], ys[b + 1])]; s = idx[(xs[a], ys[b + 1])]
            faces.append((p, q, r))
            faces.append((p, r, s))
    return verts, faces


def _selftest():
    # 1) linear x-ramp: z = 1 - x/4 over 4x2 cells == gen_linear_ramp(4,1,ny=2)
    geom = plane_mesh(4, 2, lambda x, y: 1.0 - x / 4.0)
    got = gen_from_mesh(geom, 4, 2)
    want = D.gen_linear_ramp(4, 1, ny=2)
    assert got == want, "ramp mismatch"
    # 2) diagonal tilt: z = 1 - x/8 - y/8 over 3x3 == gen_smooth_surface grid
    geom = plane_mesh(3, 3, lambda x, y: 1.0 - x / 8.0 - y / 8.0)
    got = gen_from_mesh(geom, 3, 3)
    cz = [[round((-x / 8.0 - y / 8.0) * 84) for y in range(4)] for x in range(4)]
    want = D.gen_smooth_surface(cz)
    assert got == want, "tilt mismatch"
    # 3) flat plane at z=1 == plain heightmap (no displacement emitted)
    geom = plane_mesh(3, 2, lambda x, y: 1.0)
    got = gen_from_mesh(geom, 3, 2)
    want = D.gen_heightmap_unified([[1] * 2] * 3)
    assert got == want, "flat mismatch"
    print("du_mesh selftest: 3/3 OK")


if __name__ == "__main__":
    _selftest()
