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


def voxelize_surface(verts, faces, grid, want_anchors=True):
    """Surface voxel set (SAT-exact) + optional anchor map {corner -> nearest surface pt}.
    Numpy-batched per triangle over its candidate voxel slab."""
    surface = set()
    anchors = {} if want_anchors else None
    for f in faces:
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
            _accumulate_anchors(anchors, v0, v1, v2, ix[mask], iy[mask], iz[mask])
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


def _accumulate_anchors(anchors, v0, v1, v2, ix, iy, iz):
    """For each of the 8 corners of every intersected voxel, keep the closest mesh point
    across all triangles (nearest-surface projection target for smoothing)."""
    for x, y, z in zip(ix, iy, iz):
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    corner = (int(x) + dx, int(y) + dy, int(z) + dz)
                    p = np.array(corner, float)
                    q = _closest_on_triangle(p, v0, v1, v2)
                    d2 = float((q - p) @ (q - p))
                    prev = anchors.get(corner)
                    if prev is None or d2 < prev[1]:
                        anchors[corner] = (tuple(q), d2)


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


def voxelize(verts, faces, grid, hollow=False, want_anchors=True):
    """Full voxelization -> (voxels, anchors). hollow=False fills the watertight interior
    (caves/holds preserved as modeled voids); hollow=True keeps the surface shell only."""
    surface, anchors = voxelize_surface(verts, faces, grid, want_anchors=want_anchors)
    if not surface:
        raise ValueError('voxelization produced no voxels (empty/degenerate mesh)')
    voxels = surface if hollow else fill_solid(surface, grid)
    return voxels, anchors


def anchor_smooth_fn(anchors, offset=0):
    """Build a smooth_fn(x,y,z)->target from an anchor map for du_semantic's pos_fn. offset
    shifts grid coords into construct-local space if the shape was translated after
    voxelization (pass the same delta used to place the shape)."""
    def smooth_fn(x, y, z):
        key = (x - offset, y - offset, z - offset) if offset else (x, y, z)
        a = anchors.get(key)
        return a[0] if a is not None else (x, y, z)
    return smooth_fn
