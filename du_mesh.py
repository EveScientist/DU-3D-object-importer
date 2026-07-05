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


def gen_terrain_from_mesh(obj_path_or_geom, nx, ny, gx, gy, x0=0.0, y0=0.0,
                          zbase=0.0, h=1, lz0=10):
    """Mesh -> displaced MULTI-CHUNK terrain via gen_terrain (splits across
    positive chunk-grid boundaries, <=1 per axis; uniform blocky height h).
    Returns {(cx,cy,cz): scan}. The mesh's cell-center heights must all round
    to h (asserted) -- varying blocky H across grid seams is a later increment."""
    if isinstance(obj_path_or_geom, tuple):
        verts, faces = obj_path_or_geom
    else:
        verts, faces = load_obj(obj_path_or_geom)
    corner_z = []
    for i in range(nx + 1):
        line = []
        for j in range(ny + 1):
            z = top_z(verts, faces, x0 + i, y0 + j)
            line.append(0 if z is None else round((z - zbase - h) * 84))
        corner_z.append(line)
    for i in range(nx):
        for j in range(ny):
            zc = top_z(verts, faces, x0 + i + 0.5, y0 + j + 0.5)
            assert zc is not None and max(1, round(zc - zbase)) == h, \
                f"cell ({i},{j}) blocky height != h (increment-2 scope)"
    return D.gen_terrain(corner_z, gx, gy, lz0=lz0, h=h)


def gen_x0_from_mesh(obj_path_or_geom, n_low=2, n_high=2, ny=2, xoff=0.0,
                     y0=0.0, zbase=0.0, ly0=10, lz0=10):
    """Mesh -> displaced x=0 OCTANT-SEAM chunk pair {(8,8,8), (7,8,8)}.
    Samples the mesh at mesh-x = xoff + global-x (the seam sits at mesh-x =
    xoff; columns -n_low..-1 real on the LOW side, 0..n_high-1 on the HIGH). Blocky per-column
    heights from cell centers feed gen_seam_x0_*_varying; per-corner vertical
    offsets ride apply_seam_displacement's per-group vlist (seam chunks' FG
    groups correspond 1:1 to plate corner lines: cluster ci <-> x-line
    lx0+i, groups within <-> y-lines). Increment-3 scope: single top surface,
    vertical offsets only."""
    if isinstance(obj_path_or_geom, tuple):
        verts, faces = obj_path_or_geom
    else:
        verts, faces = load_obj(obj_path_or_geom)

    def colh(x):                                  # blocky height of column [x, x+1)
        zc = top_z(verts, faces, xoff + x + 0.5, y0 + ny / 2.0)
        assert zc is not None, f"column {x} not covered"
        return max(1, round(zc - zbase))

    high = [colh(i) for i in range(n_high)]       # boundary-first == plate order
    low = [colh(-1 - i) for i in range(n_low)]
    gh = D.gen_seam_x0_high_varying(high, low, ny=ny, ly0=ly0, lz0=lz0)
    gl = D.gen_seam_x0_low_varying(low, high, ny=ny, ly0=ly0, lz0=lz0)

    def vline(x, h_ref):
        out = []
        for j in range(ny + 1):
            z = top_z(verts, faces, xoff + x, y0 + j)
            dz = 0 if z is None else round((z - zbase - h_ref) * 84)
            out.append(None if dz == 0 else (0, 0, dz))
        return out

    # HIGH plate x-lines: -1..n_high (cluster ci <-> line -1+i); h_ref per
    # line = max adjacent plate column height (pair-max convention)
    hplate = [low[0]] + high
    vh = []
    for i in range(len(hplate) + 1):
        adj = [hplate[c] for c in (i - 1, i) if 0 <= c < len(hplate)]
        vh += vline(-1 + i, max(adj))
    lplate = list(reversed(low)) + [high[0]]
    vl = []
    for i in range(len(lplate) + 1):
        adj = [lplate[c] for c in (i - 1, i) if 0 <= c < len(lplate)]
        vl += vline(-n_low + i, max(adj))
    return {(8, 8, 8): D.apply_seam_displacement(gh, vlist=vh),
            (7, 8, 8): D.apply_seam_displacement(gl, vlist=vl)}


def gen_y0_from_mesh(obj_path_or_geom, n_low=2, n_high=2, nx=2, xoff=0.0,
                     yoff=0.0, zbase=0.0, lx0=10, lz0=10):
    """Mesh -> displaced y=0 OCTANT-SEAM chunk pair {(8,8,8), (8,7,8)}.
    Transpose of gen_x0_from_mesh: rows -n_low..-1 real on the LOW side,
    0..n_high-1 on the HIGH side; nx columns at world x = lx0..lx0+nx.
    Sampling at mesh (xoff + world_x, yoff + world_y). y0 chunk group order:
    clusters = x-lines (lx0+i), groups within = y-lines ascending from the
    plate's ly0 (opener = first y-line). Blocky heights may vary along y only
    (the y0 varying generators are x-uniform); vertical offsets only."""
    if isinstance(obj_path_or_geom, tuple):
        verts, faces = obj_path_or_geom
    else:
        verts, faces = load_obj(obj_path_or_geom)

    def rowh(y):                                  # blocky height of row [y, y+1)
        zc = top_z(verts, faces, xoff + lx0 + nx / 2.0, yoff + y + 0.5)
        assert zc is not None, f"row {y} not covered"
        return max(1, round(zc - zbase))

    high = [rowh(j) for j in range(n_high)]       # boundary-first
    low = [rowh(-1 - j) for j in range(n_low)]
    gh = D.gen_seam_y0_high_varying(high, low, nx=nx, lx0=lx0, lz0=lz0)
    gl = D.gen_seam_y0_low_varying(low, high, nx=nx, lx0=lx0, lz0=lz0)

    def build_vlist(prof, yline0):
        vl = []
        for i in range(nx + 1):                   # x-lines (cluster-major)
            for j in range(len(prof) + 1):        # y-lines within
                adj = [prof[c] for c in (j - 1, j) if 0 <= c < len(prof)]
                z = top_z(verts, faces, xoff + lx0 + i, yoff + yline0 + j)
                dz = 0 if z is None else round((z - zbase - max(adj)) * 84)
                vl.append(None if dz == 0 else (0, 0, dz))
        return vl

    hprof = [low[0]] + high                       # HIGH plate rows @ly0=-1
    lprof = list(reversed(low)) + [high[0]]       # LOW plate rows @ly0=32-n_low
    return {(8, 8, 8): D.apply_seam_displacement(gh, vlist=build_vlist(hprof, -1)),
            (8, 7, 8): D.apply_seam_displacement(gl, vlist=build_vlist(lprof, -n_low))}


def gen_z0_from_mesh(obj_path_or_geom, nx, ny, floor, xoff=0.0, yoff=0.0,
                     lx0=10, ly0=10, displace=True):
    """Mesh -> z=0 crossing chunk pair {(8,8,8), (8,8,7)}: terrain whose
    solid runs from a floor below z=0 up to the mesh's top surface.
    floor < 0 (integer voxel plane). Per-column HIGH depths = surface voxels
    above 0 (+1 boundary ghost) from cell-center sampling; LOW depths =
    |floor| (+1). Encodes via the z0 representation chooser (pinned 3022/
    3024/3026): per-column LOW extras = low_real - min(low_real); max extra
    0 -> LOW uniform; 1 -> variation FOLDS INTO HIGH (+extra on its depth);
    >=2 -> LOW carries ALL variation, HIGH plain at uniform-min.
    displace=True adds per-corner vertical offsets: Build AW (3095 vs 2986)
    pinned that z-seam chunks use the SAME carrier grammar as x0/y0 (12B
    expansion s=run-1, fillers in-place carrying their row's corner value,
    run-0 rows neutral) and that BOTH chunks carry the same surface offsets
    (LOW mirrors HIGH -- the ghost layer includes the surface)."""
    if isinstance(obj_path_or_geom, tuple):
        verts, faces = obj_path_or_geom
    else:
        verts, faces = load_obj(obj_path_or_geom)
    assert floor < 0
    Hdep = []                                     # HIGH depths [x][y]
    for i in range(nx):
        col = []
        for j in range(ny):
            zc = top_z(verts, faces, xoff + i + 0.5, yoff + j + 0.5)
            assert zc is not None, f"cell ({i},{j}) not covered"
            col.append(max(1, round(zc)) + 1)
        Hdep.append(col)
    low_real = [[-floor] * ny for _ in range(nx)]  # flat floor (per-col ready)
    minlow = min(min(c) for c in low_real)
    extras = [[c - minlow for c in col] for col in low_real]
    mx = max(max(c) for c in extras)
    uniform_high = all(c == Hdep[0][0] for col in Hdep for c in col)
    if mx == 0:
        if minlow <= 1:                            # low_real 1 -> DEGENERATE high form
            assert uniform_high, "degenerate-varying z0 form underived (3002)"
            high = D.gen_seam_z_high(nx, ny, lx0=lx0, ly0=ly0,
                                     depth=Hdep[0][0], opp_depth=minlow + 1)
        else:
            high = D.gen_seam_z_high_varying(Hdep, lx0=lx0, ly0=ly0)
        low = D.gen_seam_z_low(nx, ny, lx0=lx0, ly0=ly0, depth=minlow + 1)
    elif mx == 1:
        Hfold = [[Hdep[i][j] + extras[i][j] for j in range(ny)] for i in range(nx)]
        high = D.gen_seam_z_high_varying(Hfold, lx0=lx0, ly0=ly0)
        low = D.gen_seam_z_low(nx, ny, lx0=lx0, ly0=ly0, depth=minlow + 1)
    else:
        high = D.gen_seam_z_high_varying(Hdep, lx0=lx0, ly0=ly0)
        low = D.gen_seam_z_low_varying([[lr + 1 for lr in col] for col in low_real],
                                       lx0=lx0, ly0=ly0)
    if displace:
        vl = []
        for i in range(nx + 1):                   # x-lines (cluster-major)
            for j in range(ny + 1):               # y-lines within
                adj = [Hdep[ci][cj] - 1 for ci in (i - 1, i) for cj in (j - 1, j)
                       if 0 <= ci < nx and 0 <= cj < ny]
                z = top_z(verts, faces, xoff + i, yoff + j)
                dz = 0 if z is None else round((z - max(adj)) * 84)
                vl.append(None if dz == 0 else (0, 0, dz))
        high = D.apply_seam_displacement(high, vlist=vl)
        low = D.apply_seam_displacement(low, vlist=vl)
    return {(8, 8, 8): high, (8, 8, 7): low}


def gen_xy_from_mesh(obj_path_or_geom, rx=2, ry=2, xoff=0.0, yoff=0.0,
                     zbase=0.0, lz0=10):
    """Mesh -> displaced x=0+y=0 SURFACE-CORNER chunk set (4 chunks, h1
    blocky, rx/ry real cols/rows per side -- the 3079 shape). Displacement
    rides the plain-plate carriers per chunk recipe (gen_corner_xy):
      (8,8,8) gen_corner_hh(verts=)          grid x,y-lines -1..r
      (7,7,8) gen_surface_displaced          grid lines -r..1
      (7,8,8) y0 decl splice over displaced FG plate (lines x -r..1, y -1..r)
      (8,7,8) displaced plate + x0-head      (lines x -1..r, y -r..1)
    Sampling at mesh (xoff + global_x, yoff + global_y); h_ref = 1 (h1 scope).
    Column-major (x outer, y inner) vert order throughout."""
    if isinstance(obj_path_or_geom, tuple):
        verts, faces = obj_path_or_geom
    else:
        verts, faces = load_obj(obj_path_or_geom)

    def V(xl, yl):
        z = top_z(verts, faces, xoff + xl, yoff + yl)
        dz = 0 if z is None else round((z - zbase - 1) * 84)
        return (D.ORIGIN, D.ORIGIN) if dz == 0 else (D.ORIGIN, (0, 0, dz))

    def grid(xlines, ylines):
        return [V(xl, yl) for xl in xlines for yl in ylines]

    from du_solid import gen_heightmap_unified, _fg0, _first_decl
    ny = ry + 1
    out = {(8, 8, 8): D.gen_corner_hh(rx, ry, lz0=lz0,
                                      verts=grid(range(-1, rx + 1), range(-1, ry + 1)))}
    out[(7, 7, 8)] = D.gen_surface_displaced(
        [[1] * ny] * (rx + 1), grid(range(-rx, 2), range(-ry, 2)),
        lx0=32 - rx, ly0=32 - ry, lz0=lz0)
    gB = gen_heightmap_unified([[1] * (ry + 2)] * (rx + 1), lx0=32 - rx, ly0=-2, lz0=lz0)
    gA = D.gen_surface_displaced([[1] * ny] * (rx + 1),
                                 grid(range(-rx, 2), range(-1, ry + 1)),
                                 lx0=32 - rx, ly0=-1, lz0=lz0)
    fA = _fg0(gen_heightmap_unified([[1] * ny] * (rx + 1), lx0=32 - rx, ly0=-1, lz0=lz0))
    out[(7, 8, 8)] = gB[:_fg0(gB)] + gA[fA:]
    g = D.gen_surface_displaced([[1] * ny] * (rx + 1),
                                grid(range(-1, rx + 1), range(-ry, 2)),
                                lx0=-1, ly0=32 - ry, lz0=lz0)
    cvm2 = (217 - 55 * (-2) + 35 * (32 - ry) + lz0) % 256
    ins = bytes([cvm2, 1, 2, 0, 0]) + bytes([33, 1, 2, 0, 0]) * (ny - 1)
    fd = _first_decl(g)
    g2 = bytearray(g)
    g2[fd] = (200 - 1 - 35 * (ny - 1)) % 256
    g2[fd - 10:fd - 10] = ins
    del g2[fd - 10 + len(ins):fd - 8 + len(ins)]
    out[(8, 7, 8)] = bytes(g2)
    return out


def gen_xz_from_mesh(obj_path_or_geom, ny, xoff=0.0, yoff=0.0, ly0=10):
    """Mesh -> displaced x=0+z=0 SURFACE CORNER (4 chunks, the 2945/2947
    shape: 1 real col each side of x=0, ny rows, 1 real z layer each side of
    z=0). Top-surface corner offsets vs the z=+1 blocky top ride the pinned
    carrier grammar via apply_seam_displacement per chunk; the -z chunks
    MIRROR the +z chunks' offsets (3095 rule: the ghost layer includes the
    surface). Corner grid per chunk: x-lines -1..1, y-lines ly0..ly0+ny."""
    if isinstance(obj_path_or_geom, tuple):
        verts, faces = obj_path_or_geom
    else:
        verts, faces = load_obj(obj_path_or_geom)
    vl = []
    for xl in (-1, 0, 1):
        for yl in range(ly0, ly0 + ny + 1):
            z = top_z(verts, faces, xoff + xl, yoff + yl)
            dz = 0 if z is None else round((z - 1.0) * 84)
            vl.append(None if dz == 0 else (0, 0, dz))
    return {k: D.apply_seam_displacement(g, vlist=vl)
            for k, g in D.gen_corner_xz(ny).items()}


def gen_yz_from_mesh(obj_path_or_geom, nx, xoff=0.0, yoff=0.0, lx0=10):
    """Mesh -> displaced y=0+z=0 SURFACE CORNER (4 chunks, the 3077 shape:
    nx x-cols, 1 real row each side of y=0, 1 real z layer each side of z=0).
    Same carrier/mirror rules as gen_xz_from_mesh. Corner grid per chunk:
    x-lines lx0..lx0+nx, y-lines -1..1 (y0 group order: clusters = x-lines,
    rows within = y-lines)."""
    if isinstance(obj_path_or_geom, tuple):
        verts, faces = obj_path_or_geom
    else:
        verts, faces = load_obj(obj_path_or_geom)
    vl = []
    for xl in range(lx0, lx0 + nx + 1):
        for yl in (-1, 0, 1):
            z = top_z(verts, faces, xoff + xl, yoff + yl)
            dz = 0 if z is None else round((z - 1.0) * 84)
            vl.append(None if dz == 0 else (0, 0, dz))
    return {k: D.apply_seam_displacement(g, vlist=vl)
            for k, g in D.gen_corner_yz(nx).items()}


def gen_grid_from_mesh(obj_path_or_geom, nx, ny, gx, gy, x0=0.0, y0=0.0,
                       zbase=0.0, h=1, lz0=10):
    """Mesh -> displaced MULTI-BOUNDARY grid via gen_terrain_grid (any number of
    chunk-grid boundaries per axis; uniform blocky height h, amplitude <=+-1.5
    vox). Samples the global (nx+1)x(ny+1) corner grid; per-corner dz84 =
    (surface_z - zbase - h)*84. Continuity across all chunk seams is automatic
    (shared corner lines sampled once). Returns {(cx,cy,cz): scan}."""
    if isinstance(obj_path_or_geom, tuple):
        verts, faces = obj_path_or_geom
    else:
        verts, faces = load_obj(obj_path_or_geom)
    corner_z = []
    for i in range(nx + 1):
        line = []
        for j in range(ny + 1):
            z = top_z(verts, faces, x0 + i, y0 + j)
            line.append(0 if z is None else round((z - zbase - h) * 84))
        corner_z.append(line)
    return D.gen_terrain_grid(corner_z, gx, gy, lz0=lz0, h=h)


# ── OBJ -> blueprint driver (heightfield meshes, proven region types) ────────
# Envelopes are never hand-rolled (import-test guidance): the driver picks a
# donor export whose h3 chunk set matches the target region, keyed here.
# Donor exports are found in exports/ or exports/archive (user shuffles them).
DONORS = {
    'single':  (2700, {(8, 8, 8): 514}),
    'xgrid':   (2669, {(8, 8, 8): 756, (9, 8, 8): 587}),
    'x0':      (3032, {(8, 8, 8): 587, (7, 8, 8): 756}),
    'y0':      (3038, {(8, 8, 8): 719, (8, 7, 8): 658}),
    'z0':      (2986, {(8, 8, 8): 635, (8, 8, 7): 603}),
    'xy':      (3079, {(8, 8, 8): 681, (8, 7, 8): 620,
                       (7, 8, 8): 594, (7, 7, 8): 533}),
}


def _find_export(num):
    import os
    for d in ('exports', 'exports/archive'):
        p = f'/home/du/{d}/{num}_export.blueprint'
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f'{num}_export.blueprint')


def build_heightfield_blueprint(obj_path_or_geom, out_path, region, **kw):
    """Mesh -> importable blueprint for one of the proven region types:
      region='single': kw nx, ny, x0, y0 (patch in one chunk, lx0/ly0 def 10)
      region='xgrid':  kw nx, ny, gx, gy (spans a chunk-grid boundary)
      region='x0':     kw n_low, n_high, ny, xoff (across the x=0 octant seam)
      region='y0':     kw n_low, n_high, nx, xoff, yoff (across y=0)
    Donor envelope/mc from DONORS (mc is displacement-invariant, so any mesh
    whose BLOCKY occupancy matches the donor's is assemblable). Returns the
    number of substituted chunks."""
    import du_assemble as A
    donor, mcs = DONORS[region]
    template = _find_export(donor)
    if region == 'single':
        scan = gen_from_mesh(obj_path_or_geom, kw['nx'], kw['ny'],
                             x0=kw.get('x0', 0.0), y0=kw.get('y0', 0.0),
                             zbase=kw.get('zbase', 0.0))
        scans = {(8, 8, 8): scan}
    elif region == 'xgrid':
        scans = gen_terrain_from_mesh(obj_path_or_geom, kw['nx'], kw['ny'],
                                      kw['gx'], kw['gy'],
                                      x0=kw.get('x0', 0.0), y0=kw.get('y0', 0.0),
                                      zbase=kw.get('zbase', 0.0))
    elif region == 'x0':
        scans = gen_x0_from_mesh(obj_path_or_geom, kw['n_low'], kw['n_high'],
                                 ny=kw['ny'], xoff=kw.get('xoff', 0.0),
                                 y0=kw.get('y0', 0.0), zbase=kw.get('zbase', 0.0))
    elif region == 'y0':
        scans = gen_y0_from_mesh(obj_path_or_geom, kw['n_low'], kw['n_high'],
                                 nx=kw['nx'], xoff=kw.get('xoff', 0.0),
                                 yoff=kw.get('yoff', 0.0), zbase=kw.get('zbase', 0.0))
    elif region == 'z0':
        scans = gen_z0_from_mesh(obj_path_or_geom, kw['nx'], kw['ny'],
                                 floor=kw['floor'], xoff=kw.get('xoff', 0.0),
                                 yoff=kw.get('yoff', 0.0))
    elif region == 'xy':
        scans = gen_xy_from_mesh(obj_path_or_geom, kw.get('rx', 2), kw.get('ry', 2),
                                 xoff=kw.get('xoff', 0.0), yoff=kw.get('yoff', 0.0),
                                 zbase=kw.get('zbase', 0.0))
    else:
        raise ValueError(region)
    assert set(scans) == set(mcs), (sorted(scans), sorted(mcs))
    return A.rebuild_h3(template, out_path,
                        lambda cx, cy, cz: (scans[(cx, cy, cz)], mcs[(cx, cy, cz)])
                        if (cx, cy, cz) in scans else None)


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
    # 4) multi-chunk: boundary-spanning ramp == gen_terrain with the same grid
    geom = plane_mesh(4, 2, lambda x, y: 1.0 - x / 8.0)
    got = gen_terrain_from_mesh(geom, 4, 2, gx=30, gy=10)
    cz = [[round((-x / 8.0) * 84)] * 3 for x in range(5)]
    want = D.gen_terrain(cz, 30, 10)
    assert set(got) == set(want) and all(got[k] == want[k] for k in got), \
        "terrain mismatch"
    # 5) per-group vlist mode reconstructs 3081 (equivalent to its cluster map)
    try:
        from tests.archive.test_du_solid_seams import chunks
        c81 = chunks(3081)
        gh = D.gen_seam_x0_high_varying([2, 1], [2, 1])
        # cluster V's expanded per-group: c0 TRI x3, c1 x3(+filler inherits), etc.
        vh = ([(28, 0, -40)] * 3 + [(0, 0, -16)] * 3
              + [(-28, 0, -40)] * 3 + [None] * 3)
        assert D.apply_seam_displacement(gh, vlist=vh) == c81[(8, 8, 8)], \
            "3081 vlist HIGH mismatch"
    except FileNotFoundError:
        pass
    # 6) flat mesh across x=0 == undisplaced varying pair (no offsets emitted)
    geom = plane_mesh(4, 2, lambda x, y: 1.0)
    scans = gen_x0_from_mesh(geom, 2, 2, ny=2, xoff=2.0)
    assert scans[(8, 8, 8)] == D.gen_seam_x0_high_varying([1, 1], [1, 1]), "x0 flat HIGH"
    assert scans[(7, 8, 8)] == D.gen_seam_x0_low_varying([1, 1], [1, 1]), "x0 flat LOW"
    # 7) flat mesh across y=0 == undisplaced varying pair
    geom = plane_mesh(2, 4, lambda x, y: 1.0)
    scans = gen_y0_from_mesh(geom, 2, 2, nx=2, xoff=-10.0, yoff=2.0)
    assert scans[(8, 8, 8)] == D.gen_seam_y0_high_varying([1, 1], [1, 1]), "y0 flat HIGH"
    assert scans[(8, 7, 8)] == D.gen_seam_y0_low_varying([1, 1], [1, 1]), "y0 flat LOW"
    # 8) z=0 crossing (blocky): step mesh == the 3004 family
    geom = plane_mesh(2, 2, lambda x, y: 2.0 if x < 1 else 1.0)
    scans = gen_z0_from_mesh(geom, 2, 2, floor=-2, displace=False)
    assert scans[(8, 8, 8)] == D.gen_seam_z_high_varying([[3, 3], [2, 2]]), "z0 HIGH"
    assert scans[(8, 8, 7)] == D.gen_seam_z_low(2, 2, depth=3), "z0 LOW"
    # 9) z=0 displaced: flat mesh at z=1 -> no offsets == blocky 2986 form
    geom = plane_mesh(2, 2, lambda x, y: 1.0)
    scans = gen_z0_from_mesh(geom, 2, 2, floor=-1)
    assert scans[(8, 8, 8)] == D.gen_seam_z_high(2, 2, depth=2), "z0 disp flat HIGH"
    assert scans[(8, 8, 7)] == D.gen_seam_z_low(2, 2, depth=2), "z0 disp flat LOW"
    # 10) xy corner: flat mesh -> all 4 chunks == blocky gen_corner_xy
    geom = plane_mesh(4, 4, lambda x, y: 1.0)
    scans = gen_xy_from_mesh(geom, 2, 2, xoff=2.0, yoff=2.0)
    want = D.gen_corner_xy(2, 2)
    assert set(scans) == set(want)
    for k in want:
        assert scans[k] == want[k], f"xy flat {k}"
    # 11) xz / yz corners: flat mesh -> blocky gen_corner_xz / gen_corner_yz
    geom = plane_mesh(2, 5, lambda x, y: 1.0)
    scans = gen_xz_from_mesh(geom, 4, xoff=1.0, yoff=-9.0, ly0=10)
    want = D.gen_corner_xz(4)
    for k in want:
        assert scans[k] == want[k], f"xz flat {k}"
    geom = plane_mesh(4, 2, lambda x, y: 1.0)
    scans = gen_yz_from_mesh(geom, 3, xoff=-9.0, yoff=1.0, lx0=10)
    want = D.gen_corner_yz(3)
    for k in want:
        assert scans[k] == want[k], f"yz flat {k}"
    # 12: grid flat reduction (multi-boundary w/ a middle) == gen_terrain_flat_grid
    geom = plane_mesh(40, 40, lambda x, y: 1.0)          # gx=30,nx=40 -> cx 8..10, one x-middle
    scans = gen_grid_from_mesh(geom, 40, 40, gx=30, gy=30)
    want = D.gen_terrain_flat_grid(30, 30, 40, 40)
    assert set(scans) == set(want) and all(scans[k] == want[k] for k in want), "grid flat"
    print("du_mesh selftest: 12/12 OK")


if __name__ == "__main__":
    _selftest()
