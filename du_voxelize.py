"""du_voxelize.py -- fast, feature-preserving mesh voxelizer for the DU pipeline.

Replaces the pure-Python SAT voxelizer (obj_to_du_voxels) which is O(tri x candidate) and
times out at grid>=128. This one is numpy-batched over each triangle's candidate slab and
scales to L+ cores. It produces, in one pass:

  surface  : set of (x,y,z) voxels the mesh surface passes through (SAT-exact)
  solid    : surface + watertight interior (ray-parity flood along z, robust to the
             conservative surface shell), OR just the surface when hollow=True
  anchors  : {voxel_corner -> nearest mesh-surface point} for the whole surface, so the
             smoothing layer (du_semantic pos_fn) can deflect blocky edges onto the true
             mesh without re-querying the mesh (the anchor is the projection target).

Design notes:
  * Watertight fill uses even-odd parity of surface crossings per z-column, which handles
    caves / cargo holds / internal voids correctly when hollow=True is NOT set: interior
    voxels are filled, enclosed voids stay empty only if hollow=True keeps them.
  * hollow=True returns the surface shell only (+ optional thickness) -- for hulls where
    the mesh is a single outer surface and you want an empty interior.
  * The anchor map is what makes "forcibly smooth a jagged curve" cheap and exact.
"""
import math
import numpy as np


def load_obj(path):
    """(vertices Nx3 float64, faces Mx3 int32). Handles v/f with v/vt/vn and polygons."""
    verts, faces = [], []
    with open(path) as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            if p[0] == 'v':
                verts.append([float(p[1]), float(p[2]), float(p[3])])
            elif p[0] == 'f':
                idx = [int(t.split('/')[0]) - 1 for t in p[1:]]
                for i in range(1, len(idx) - 1):
                    faces.append([idx[0], idx[i], idx[i + 1]])
    if not verts or not faces:
        raise ValueError(f'{path}: need vertices and faces (got {len(verts)}/{len(faces)})')
    return np.asarray(verts, np.float64), np.asarray(faces, np.int32)


def fit_to_grid(verts, grid, margin=0):
    """Uniformly scale+centre the mesh into [margin, grid-margin]^3 voxel space."""
    lo = verts.min(0)
    hi = verts.max(0)
    extent = float((hi - lo).max())
    if extent == 0:
        raise ValueError('mesh has zero extent')
    scale = (grid - 2 * margin) / extent
    centred = (verts - lo) * scale
    span = (hi - lo) * scale
    offset = margin + (grid - 2 * margin - span) / 2.0
    return centred + offset, scale


def _tri_aabb_overlap(v0, v1, v2, cx, cy, cz, hs=0.5):
    """Vectorized Moller SAT over arrays of voxel centres (cx,cy,cz are 1-D arrays).
    Returns a boolean mask of which centres the triangle overlaps."""
    n = cx.shape[0]
    C = np.stack([cx, cy, cz], 1)                       # (n,3)
    t0 = v0 - C; t1 = v1 - C; t2 = v2 - C               # (n,3) each
    e0 = v1 - v0; e1 = v2 - v1; e2 = v0 - v2            # (3,)
    ok = np.ones(n, bool)
    # 3 AABB face normals
    for i in range(3):
        col = np.stack([t0[:, i], t1[:, i], t2[:, i]], 1)
        ok &= ~((col.min(1) > hs) | (col.max(1) < -hs))
    # 9 edge x axis cross products
    for e in (e0, e1, e2):
        for ai in range(3):
            ax = np.zeros(3); ax[ai] = 1.0
            a = np.cross(e, ax)
            if a @ a < 1e-12:
                continue
            p0 = t0 @ a; p1 = t1 @ a; p2 = t2 @ a
            r = hs * (abs(a[0]) + abs(a[1]) + abs(a[2]))
            pmin = np.minimum(np.minimum(p0, p1), p2)
            pmax = np.maximum(np.maximum(p0, p1), p2)
            ok &= ~((pmin > r) | (pmax < -r))
    # 1 triangle face normal
    nrm = np.cross(e0, e1)
    if nrm @ nrm > 1e-12:
        d = t0 @ nrm
        r = hs * (abs(nrm[0]) + abs(nrm[1]) + abs(nrm[2]))
        ok &= ~((d > r) | (d < -r))
    return ok


def vertex_normals(verts, faces):
    """Area-weighted per-vertex normals (N,3), for smooth (PN-triangle) projection."""
    vn = np.zeros_like(verts)
    fn = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]],
                  verts[faces[:, 2]] - verts[faces[:, 0]])      # area-weighted face normals
    for k in range(3):
        np.add.at(vn, faces[:, k], fn)
    ln = np.linalg.norm(vn, axis=1, keepdims=True)
    return vn / np.where(ln < 1e-20, 1.0, ln)


def voxelize_surface(verts, faces, grid, want_anchors=True, normals=None):
    """Surface voxel set (SAT-exact) + optional anchor map {corner -> nearest surface pt}.
    Numpy-batched per triangle over its candidate voxel slab. If `normals` (per-vertex) are
    given, anchor targets are projected onto the smooth PN-triangle surface (rounds facets of
    low-poly meshes) instead of the flat triangle."""
    surface = set()
    anchors = {} if want_anchors else None
    for fi, f in enumerate(faces):
        v0, v1, v2 = verts[f[0]], verts[f[1]], verts[f[2]]
        tri = np.stack([v0, v1, v2])
        lo = np.clip(np.floor(tri.min(0)).astype(int), 0, grid - 1)
        hi = np.clip(np.floor(tri.max(0)).astype(int) + 1, 0, grid - 1)
        gx, gy, gz = (np.arange(lo[i], hi[i] + 1) for i in range(3))
        if not (len(gx) and len(gy) and len(gz)):
            continue
        X, Y, Z = np.meshgrid(gx, gy, gz, indexing='ij')
        ix = X.ravel(); iy = Y.ravel(); iz = Z.ravel()
        mask = _tri_aabb_overlap(v0, v1, v2, ix + 0.5, iy + 0.5, iz + 0.5)
        for x, y, z in zip(ix[mask], iy[mask], iz[mask]):
            surface.add((int(x), int(y), int(z)))
        if want_anchors:
            tn = None if normals is None else (normals[f[0]], normals[f[1]], normals[f[2]])
            _accumulate_anchors(anchors, v0, v1, v2, ix[mask], iy[mask], iz[mask], tn)
    return surface, anchors


def _closest_on_triangle(p, a, b, c):
    """Closest point to p on triangle abc (Ericson, Real-Time Collision Detection)."""
    ab = b - a; ac = c - a; ap = p - a
    d1 = ab @ ap; d2 = ac @ ap
    if d1 <= 0 and d2 <= 0:
        return a
    bp = p - b; d3 = ab @ bp; d4 = ac @ bp
    if d3 >= 0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        return a + (d1 / (d1 - d3)) * ab
    cp = p - c; d5 = ab @ cp; d6 = ac @ cp
    if d6 >= 0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        return a + (d2 / (d2 - d6)) * ac
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        return b + ((d4 - d3) / ((d4 - d3) + (d5 - d6))) * (c - b)
    denom = 1.0 / (va + vb + vc)
    v = vb * denom; w = vc * denom
    return a + ab * v + ac * w


def _closest_on_triangle_batch(P, a, b, c):
    """Closest points on triangle abc for an (N,3) array of query points P -- vectorized
    Ericson region test. Returns (N,3)."""
    ab = b - a; ac = c - a
    ap = P - a
    d1 = ap @ ab; d2 = ap @ ac
    bp = P - b; d3 = bp @ ab; d4 = bp @ ac
    cp = P - c; d5 = cp @ ab; d6 = cp @ ac
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    out = np.empty_like(P)
    # default: interior (barycentric)
    denom = va + vb + vc
    denom = np.where(np.abs(denom) < 1e-20, 1e-20, denom)
    v = (vb / denom)[:, None]; w = (vc / denom)[:, None]
    out[:] = a + ab * v + ac * w
    # vertex/edge regions (later assignments win; order matches the scalar cascade priority)
    eab = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    t = np.where((d1 - d3) == 0, 0, d1 / np.where((d1 - d3) == 0, 1, d1 - d3))
    out[eab] = (a + t[:, None] * ab)[eab]
    ebc = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    dd = (d4 - d3) + (d5 - d6)
    t = np.where(dd == 0, 0, (d4 - d3) / np.where(dd == 0, 1, dd))
    out[ebc] = (b + t[:, None] * (c - b))[ebc]
    eca = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    t = np.where((d2 - d6) == 0, 0, d2 / np.where((d2 - d6) == 0, 1, d2 - d6))
    out[eca] = (a + t[:, None] * ac)[eca]
    out[(d1 <= 0) & (d2 <= 0)] = a
    out[(d3 >= 0) & (d4 <= d3)] = b
    out[(d6 >= 0) & (d5 <= d6)] = c
    return out


def _barycentric(Q, a, b, c):
    """Barycentric coords (w0,w1,w2) of points Q (N,3) w.r.t. triangle a,b,c."""
    v0 = b - a; v1 = c - a; v2 = Q - a
    d00 = v0 @ v0; d01 = v0 @ v1; d11 = v1 @ v1
    d20 = v2 @ v0; d21 = v2 @ v1
    den = d00 * d11 - d01 * d01
    den = den if abs(den) > 1e-20 else 1e-20
    w1 = (d11 * d20 - d01 * d21) / den
    w2 = (d00 * d21 - d01 * d20) / den
    return 1 - w1 - w2, w1, w2


def _pn_surface(w0, w1, w2, P1, P2, P3, N1, N2, N3):
    """PN-triangle (Vlachos) cubic surface point at barycentric (w0,w1,w2). Rounds the flat
    facets of a low-poly mesh toward the smooth surface implied by the vertex normals."""
    def wij(Pi, Pj, Ni):
        return (2 * Pi + Pj - ((Pj - Pi) @ Ni) * Ni) / 3.0
    b210 = wij(P1, P2, N1); b120 = wij(P2, P1, N2)
    b021 = wij(P2, P3, N2); b012 = wij(P3, P2, N3)
    b102 = wij(P3, P1, N3); b201 = wij(P1, P3, N1)
    E = (b210 + b120 + b021 + b012 + b102 + b201) / 6.0
    V = (P1 + P2 + P3) / 3.0
    b111 = E + (E - V) / 2.0
    u, v, w = w0[:, None], w1[:, None], w2[:, None]        # u->P1, v->P2, w->P3
    return (P1 * u**3 + P2 * v**3 + P3 * w**3
            + 3 * b210 * u**2 * v + 3 * b120 * u * v**2
            + 3 * b021 * v**2 * w + 3 * b012 * v * w**2
            + 3 * b102 * w**2 * u + 3 * b201 * w * u**2
            + 6 * b111 * u * v * w)


def _accumulate_anchors(anchors, v0, v1, v2, ix, iy, iz, tn=None):
    """Keep, per voxel corner, the closest mesh point across all triangles (the smoothing
    projection target). Vectorized over all 8 corners of every intersected voxel. When tn
    (the three vertex normals) is given, the stored target is the PN-triangle surface point
    (smooth) rather than the flat closest point -- the nearest-triangle metric still uses the
    flat distance."""
    if len(ix) == 0:
        return
    base = np.stack([ix, iy, iz], 1)                       # (M,3)
    offs = np.array([(dx, dy, dz) for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)])
    corners = (base[:, None, :] + offs[None, :, :]).reshape(-1, 3)   # (8M,3)
    corners = np.unique(corners, axis=0)
    P = corners.astype(float)
    Q = _closest_on_triangle_batch(P, v0, v1, v2)
    d2 = np.einsum('ij,ij->i', Q - P, Q - P)
    if tn is not None:
        w0, w1, w2 = _barycentric(Q, v0, v1, v2)
        T = _pn_surface(w0, w1, w2, v0, v1, v2, tn[0], tn[1], tn[2])
    else:
        T = Q
    for k in range(len(corners)):
        key = (int(corners[k, 0]), int(corners[k, 1]), int(corners[k, 2]))
        prev = anchors.get(key)
        dk = float(d2[k])
        if prev is None or dk < prev[1]:
            anchors[key] = ((float(T[k, 0]), float(T[k, 1]), float(T[k, 2])), dk)


def _scan_axis(verts, faces, grid, axis):
    """Inside-voxel set by casting rays ALONG `axis` (0=x,1=y,2=z) through each cell centre
    of the other two axes, even-odd parity. Permute so the ray axis is last, run the z-scan,
    permute back."""
    p = [i for i in range(3) if i != axis] + [axis]     # ray axis last
    inv = [p.index(i) for i in range(3)]
    V = verts[:, p]
    v0 = V[faces[:, 0]]; v1 = V[faces[:, 1]]; v2 = V[faces[:, 2]]
    amin = np.minimum(np.minimum(v0, v1), v2)
    amax = np.maximum(np.maximum(v0, v1), v2)
    # Perturb the ray sample point by tiny INCOMMENSURATE irrationals so rays never pass
    # exactly through a shared edge / vertex / coplanar ring (the equatorial "knife cut":
    # a UV sphere's parallel of latitude is a full ring of coplanar edges that the two
    # perpendicular-axis rays graze simultaneously -> majority vote can't save it). An
    # off-grid nudge makes such grazes measure-zero. Sub-voxel so classification is unmoved.
    EA = 1e-3 * math.sqrt(2)
    EB = 1e-3 * math.sqrt(3)
    inside = set()
    for a in range(grid):
        pa = a + 0.5 + EA
        ma = (amin[:, 0] <= pa) & (pa <= amax[:, 0])
        if not ma.any():
            continue
        b0, b1, b2 = v0[ma], v1[ma], v2[ma]
        bmn = amin[ma]; bmx = amax[ma]
        for b in range(grid):
            pb = b + 0.5 + EB
            mb = (bmn[:, 1] <= pb) & (pb <= bmx[:, 1])
            if not mb.any():
                continue
            cs = _ray_z_hits(b0[mb], b1[mb], b2[mb], pa, pb)
            if len(cs) < 2:
                continue
            cs.sort()
            for i in range(0, len(cs) - 1, 2):
                c0 = int(math.ceil(cs[i] - 0.5)); c1 = int(math.floor(cs[i + 1] - 0.5))
                for c in range(max(0, c0), min(grid - 1, c1) + 1):
                    cell = (a, b, c)                        # in permuted frame
                    inside.add((cell[inv[0]], cell[inv[1]], cell[inv[2]]))
    return inside


def solid_by_containment(verts, faces, grid, robust=True):
    """Mesh-tight solid: a voxel is filled iff its CENTRE is inside the mesh. The boundary
    sits ON the surface (unlike the conservative SAT band), so surface-vertex corners are
    within +-0.5 vox of the mesh and smoothing deflections stay sub-voxel like the game's
    own smooth exports. Watertight meshes required for a correct interior.

    robust=True casts rays along ALL THREE axes and MAJORITY-votes (>=2 of 3) -- this fixes
    the single-axis degeneracies (rays grazing shared triangle edges/vertices) that leave
    'knife-cut' missing columns on grid-aligned meshes like a UV sphere (dep19d). robust=
    False is the fast single z-scan (fine for meshes without axis-aligned edges)."""
    if not robust:
        return _scan_axis(verts, faces, grid, 2)
    from collections import Counter
    votes = Counter()
    for axis in (0, 1, 2):
        for v in _scan_axis(verts, faces, grid, axis):
            votes[v] += 1
    return {v for v, n in votes.items() if n >= 2}


def _ray_z_hits(v0, v1, v2, px, py):
    """z of intersections of the +z ray through (px,py) with triangles (barycentric)."""
    # solve px,py in triangle -> bary (u,v); z = w0*z0+... Vectorized Cramer.
    x0, y0 = v0[:, 0], v0[:, 1]
    e1x, e1y = v1[:, 0] - x0, v1[:, 1] - y0
    e2x, e2y = v2[:, 0] - x0, v2[:, 1] - y0
    det = e1x * e2y - e2x * e1y
    ok = np.abs(det) > 1e-12
    rx, ry = px - x0, py - y0
    u = np.where(ok, (rx * e2y - e2x * ry) / np.where(ok, det, 1), -1)
    v = np.where(ok, (e1x * ry - rx * e1y) / np.where(ok, det, 1), -1)
    inside = ok & (u >= 0) & (v >= 0) & (u + v <= 1)
    z = v0[:, 2] + u * (v1[:, 2] - v0[:, 2]) + v * (v2[:, 2] - v0[:, 2])
    return list(z[inside])


def fill_solid(surface, grid):
    """Watertight interior via even-odd z-parity of surface crossings per (x,y) column.
    Robust to the conservative surface shell (collapses runs of adjacent surface voxels to
    single crossings). Returns surface | interior."""
    cols = {}
    for (x, y, z) in surface:
        cols.setdefault((x, y), []).append(z)
    out = set(surface)
    for (x, y), zs in cols.items():
        zs = sorted(set(zs))
        # collapse contiguous runs -> crossing z-levels
        runs = []
        s = zs[0]; p = zs[0]
        for z in zs[1:]:
            if z == p + 1:
                p = z
            else:
                runs.append((s, p)); s = z; p = z
        runs.append((s, p))
        # fill gaps between successive run PAIRS (inside/outside toggles at each run)
        for i in range(0, len(runs) - 1, 2):
            for z in range(runs[i][1] + 1, runs[i + 1][0]):
                out.add((x, y, z))
    return out


def voxelize(verts, faces, grid, hollow=False, want_anchors=True, solid_mode='contain',
             smooth_normals=True):
    """Full voxelization -> (voxels, anchors).

    solid_mode='contain' (default): mesh-tight solid by center-in-mesh z-parity -- the
        boundary sits on the surface so smoothing deflections stay sub-voxel (like the
        game's exports). Best for smoothing; needs a watertight mesh.
    solid_mode='band': conservative SAT surface + span fill -- robust to non-manifold
        meshes but the boundary sits ~1 vox proud (blockier, larger smoothing offsets).
    hollow=True: surface shell only (no interior), for hulls with a modeled outer skin.
    smooth_normals=True: anchor targets projected onto the smooth PN-triangle surface
        (vertex-normal Phong tessellation) so LOW-POLY meshes round out instead of showing
        flat facets at high voxel resolution; False projects onto the flat triangles.

    Anchors ({surface corner -> nearest mesh point}) always come from the SAT surface pass
    so the smoothing layer has a projection target for every boundary vertex."""
    normals = vertex_normals(verts, faces) if (want_anchors and smooth_normals) else None
    surface, anchors = voxelize_surface(verts, faces, grid, want_anchors=want_anchors,
                                        normals=normals)
    if not surface:
        raise ValueError('voxelization produced no voxels (empty/degenerate mesh)')
    if hollow:
        voxels = surface
    elif solid_mode == 'contain':
        voxels = solid_by_containment(verts, faces, grid)
        if not voxels:              # degenerate/open mesh: fall back to the band fill
            voxels = fill_solid(surface, grid)
    else:
        voxels = fill_solid(surface, grid)
    return voxels, anchors


def anchor_smooth_fn(anchors, delta=(0, 0, 0)):
    """Build a smooth_fn(x,y,z)->target from an anchor map for du_semantic's pos_fn.
    `delta` is the per-axis translation applied to place the shape AFTER voxelization --
    it must be applied to BOTH the lookup key AND the returned mesh point, so the target
    is expressed in the same (placed) frame as the query. (Shifting only the key is the
    dep19b bug: targets landed in the pre-placement frame and every deflection saturated
    at the +-100 clamp -> spiky, not smooth.)"""
    dx, dy, dz = delta
    shifted = {(k[0] + dx, k[1] + dy, k[2] + dz):
               (v[0][0] + dx, v[0][1] + dy, v[0][2] + dz)
               for k, v in anchors.items()}

    def smooth_fn(x, y, z):
        t = shifted.get((x, y, z))
        return t if t is not None else (x, y, z)
    return smooth_fn
