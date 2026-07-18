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


def _triangulate(poly):
    """Fan-triangulate a polygon (list of vertex indices) -> list of index triples."""
    return [[poly[0], poly[i], poly[i + 1]] for i in range(1, len(poly) - 1)]


def load_stl(path):
    """STL (binary or ASCII) -> (verts, faces). Binary is parsed with a numpy record dtype."""
    with open(path, 'rb') as f:
        data = f.read()
    if len(data) >= 84:
        ntri = int.from_bytes(data[80:84], 'little')
        if len(data) == 84 + 50 * ntri and ntri > 0:            # binary STL
            dt = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
            arr = np.frombuffer(data, dtype=dt, count=ntri, offset=84)
            verts = arr['v'].reshape(-1, 3).astype(np.float64)
            faces = np.arange(3 * ntri, dtype=np.int32).reshape(-1, 3)
            return verts, faces
    verts, faces, cur = [], [], []                              # ASCII STL
    for line in data.decode('utf-8', 'replace').splitlines():
        p = line.split()
        if len(p) >= 4 and p[0] == 'vertex':
            cur.append([float(p[1]), float(p[2]), float(p[3])])
            if len(cur) == 3:
                i = len(verts); verts += cur; faces.append([i, i + 1, i + 2]); cur = []
    if not faces:
        raise ValueError(f'{path}: no triangles found in STL')
    return np.asarray(verts, np.float64), np.asarray(faces, np.int32)


_PLY_T = {'char': '<i1', 'uchar': '<u1', 'int8': '<i1', 'uint8': '<u1',
          'short': '<i2', 'ushort': '<u2', 'int16': '<i2', 'uint16': '<u2',
          'int': '<i4', 'uint': '<u4', 'int32': '<i4', 'uint32': '<u4',
          'float': '<f4', 'float32': '<f4', 'double': '<f8', 'float64': '<f8'}


def load_ply(path):
    """PLY (ascii / binary little- or big-endian) -> (verts, faces). Reads x,y,z + the face
    vertex-index list, skipping any other properties (normals, colours, ...)."""
    with open(path, 'rb') as f:
        raw = f.read()
    he = raw.find(b'end_header')
    if he < 0:
        raise ValueError(f'{path}: not a PLY (no end_header)')
    nl = raw.find(b'\n', he)
    header = raw[:he].decode('ascii', 'replace')
    body = raw[nl + 1:]
    fmt = 'ascii'; elements = []          # [(name, count, [(kind, ...)])]
    for line in header.splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] == 'format':
            fmt = t[1]
        elif t[0] == 'element':
            elements.append([t[1], int(t[2]), []])
        elif t[0] == 'property' and elements:
            if t[1] == 'list':
                elements[-1][2].append(('list', t[2], t[3], t[4]))
            else:
                elements[-1][2].append(('scalar', t[1], t[2]))

    verts = []; faces = []
    if fmt == 'ascii':
        toks = body.split()
        pos = 0
        for name, count, props in elements:
            for _ in range(count):
                if name == 'vertex':
                    vals = {}
                    for pr in props:
                        v = toks[pos]; pos += 1
                        vals[pr[2] if pr[0] == 'scalar' else pr[3]] = v
                    verts.append([float(vals['x']), float(vals['y']), float(vals['z'])])
                elif name == 'face':
                    for pr in props:
                        if pr[0] == 'list':
                            n = int(toks[pos]); pos += 1
                            poly = [int(toks[pos + k]) for k in range(n)]; pos += n
                            faces += _triangulate(poly)
                        else:
                            pos += 1
                else:
                    pos += sum(1 for _ in props)     # skip other elements' scalars (approx)
    else:
        endian = '<' if 'little' in fmt else '>'
        off = 0
        import struct as _st
        def rd(t):
            nonlocal off
            d = _PLY_T[t]; sz = np.dtype(d).itemsize
            val = np.frombuffer(body, dtype=endian + d[1:], count=1, offset=off)[0]
            off += sz; return val
        for name, count, props in elements:
            for _ in range(count):
                if name == 'vertex':
                    vals = {}
                    for pr in props:
                        vals[pr[2]] = rd(pr[1])
                    verts.append([float(vals['x']), float(vals['y']), float(vals['z'])])
                elif name == 'face':
                    for pr in props:
                        if pr[0] == 'list':
                            n = int(rd(pr[1]))
                            poly = [int(rd(pr[2])) for _ in range(n)]
                            faces += _triangulate(poly)
                        else:
                            rd(pr[1])
                else:
                    for pr in props:
                        rd(pr[1]) if pr[0] == 'scalar' else None
    if not faces:
        raise ValueError(f'{path}: no faces in PLY')
    return np.asarray(verts, np.float64), np.asarray(faces, np.int32)


def _quat_mat(x, y, z, w):
    n = (x * x + y * y + z * z + w * w) ** 0.5 or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def load_gltf(path):
    """glTF (.gltf + external/embedded buffers) or GLB (.glb) -> (verts, faces). Walks the
    node hierarchy applying transforms, and merges every mesh primitive (TRIANGLES)."""
    import json, base64, os, struct as _st
    if path.lower().endswith('.glb'):
        data = open(path, 'rb').read()
        _, _, length = _st.unpack_from('<III', data, 0)
        off = 12; gltf = None; buffers = [b'']
        while off < length:
            clen, ctype = _st.unpack_from('<II', data, off); off += 8
            chunk = data[off:off + clen]; off += clen
            if ctype == 0x4E4F534A:
                gltf = json.loads(chunk)
            elif ctype == 0x004E4942:
                buffers = [chunk]
    else:
        gltf = json.load(open(path))
        base = os.path.dirname(os.path.abspath(path))
        buffers = []
        for b in gltf.get('buffers', []):
            uri = b.get('uri', '')
            if uri.startswith('data:'):
                buffers.append(base64.b64decode(uri.split(',', 1)[1]))
            else:
                buffers.append(open(os.path.join(base, uri), 'rb').read())

    DT = {5120: '<i1', 5121: '<u1', 5122: '<i2', 5123: '<u2', 5125: '<u4', 5126: '<f4'}
    NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}

    def accessor(ai):
        acc = gltf['accessors'][ai]; bv = gltf['bufferViews'][acc['bufferView']]
        buf = buffers[bv.get('buffer', 0)]
        off = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
        nc = NC[acc['type']]; dt = DT[acc['componentType']]
        stride = bv.get('byteStride')
        if stride:
            isz = np.dtype(dt).itemsize
            out = np.empty((acc['count'], nc), np.dtype(dt))
            for i in range(acc['count']):
                out[i] = np.frombuffer(buf, dtype=dt, count=nc, offset=off + i * stride)
            return out
        return np.frombuffer(buf, dtype=dt, count=acc['count'] * nc,
                             offset=off).reshape(acc['count'], nc)

    def node_mat(node):
        if 'matrix' in node:
            return np.array(node['matrix'], float).reshape(4, 4).T
        M = np.eye(4)
        if 'scale' in node:
            M[:3, :3] = M[:3, :3] @ np.diag(node['scale'])
        if 'rotation' in node:
            R = np.eye(4); R[:3, :3] = _quat_mat(*node['rotation'])
            M = R @ M
        if 'translation' in node:
            T = np.eye(4); T[:3, 3] = node['translation']
            M = T @ M
        return M

    all_v = []; all_f = []; base_i = [0]

    def emit_mesh(mi, world):
        for prim in gltf['meshes'][mi].get('primitives', []):
            if prim.get('mode', 4) != 4 or 'POSITION' not in prim.get('attributes', {}):
                continue
            pos = accessor(prim['attributes']['POSITION']).astype(np.float64)
            ph = np.concatenate([pos, np.ones((len(pos), 1))], 1) @ world.T
            v = ph[:, :3]
            if 'indices' in prim:
                idx = accessor(prim['indices']).reshape(-1).astype(np.int64)
            else:
                idx = np.arange(len(v), dtype=np.int64)
            f = idx.reshape(-1, 3) + base_i[0]
            all_v.append(v); all_f.append(f); base_i[0] += len(v)

    def walk(ni, parent):
        node = gltf['nodes'][ni]
        world = parent @ node_mat(node)
        if 'mesh' in node:
            emit_mesh(node['mesh'], world)
        for ch in node.get('children', []):
            walk(ch, world)

    scenes = gltf.get('scenes'); nodes = gltf.get('nodes')
    if scenes and nodes:
        roots = scenes[gltf.get('scene', 0)].get('nodes', range(len(nodes)))
        for r in roots:
            walk(r, np.eye(4))
    else:                                     # no scene graph: dump all meshes untransformed
        for mi in range(len(gltf.get('meshes', []))):
            emit_mesh(mi, np.eye(4))
    if not all_v:
        raise ValueError(f'{path}: no triangle meshes found in glTF')
    return np.concatenate(all_v), np.concatenate(all_f).astype(np.int32)


_LOADERS = {'.obj': load_obj, '.stl': load_stl, '.ply': load_ply,
            '.gltf': load_gltf, '.glb': load_gltf}


def load_mesh(path):
    """Load a mesh by file extension -> (verts Nx3 float64, faces Mx3 int32).
    Supports .obj / .stl / .ply / .gltf / .glb."""
    import os
    ext = os.path.splitext(path)[1].lower()
    if ext not in _LOADERS:
        raise ValueError(f'unsupported mesh format {ext!r} (use .obj/.stl/.ply/.gltf/.glb)')
    return _LOADERS[ext](path)


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


def _erode(occ, n):
    """Erode a 3D boolean occupancy array by n layers (6-connectivity): a voxel survives
    iff it and all 6 face-neighbours were solid, repeated n times. numpy shift-and-AND."""
    for _ in range(n):
        e = occ.copy()
        e[1:, :, :] &= occ[:-1, :, :]; e[:-1, :, :] &= occ[1:, :, :]
        e[:, 1:, :] &= occ[:, :-1, :]; e[:, :-1, :] &= occ[:, 1:, :]
        e[:, :, 1:] &= occ[:, :, :-1]; e[:, :, :-1] &= occ[:, :, 1:]
        occ = e
    return occ


def hollow_shell(solid, grid, thickness):
    """Hollow a solid voxel set to a shell `thickness` voxels thick: shell = solid minus
    (solid eroded by `thickness`). Where the shape is thinner than 2*thickness (sharp edges,
    thin features) erosion clears it, so those regions stay SOLID -- the minimum never
    over-thins genuine detail. thickness<=0 returns the solid unchanged."""
    if thickness <= 0 or not solid:
        return solid
    lo = [min(v[i] for v in solid) for i in range(3)]
    hi = [max(v[i] for v in solid) for i in range(3)]
    p = 1                                          # False border so the outer surface erodes
    dim = [hi[i] - lo[i] + 1 + 2 * p for i in range(3)]
    occ = np.zeros(dim, bool)
    for (x, y, z) in solid:
        occ[x - lo[0] + p, y - lo[1] + p, z - lo[2] + p] = True
    inner = _erode(occ, thickness)
    shell = occ & ~inner
    xs, ys, zs = np.nonzero(shell)
    return {(int(xs[k]) + lo[0] - p, int(ys[k]) + lo[1] - p, int(zs[k]) + lo[2] - p)
            for k in range(len(xs))}


def voxelize(verts, faces, grid, hollow=False, want_anchors=True, solid_mode='contain',
             smooth_normals=True, min_thickness=0):
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
    min_thickness: for hollow shapes, the shell is at least this many voxels thick (>=1);
        regions genuinely thinner than 2x this (sharp edges) stay solid, never over-thinned.

    Anchors ({surface corner -> nearest mesh point}) always come from the SAT surface pass
    so the smoothing layer has a projection target for every boundary vertex."""
    normals = vertex_normals(verts, faces) if (want_anchors and smooth_normals) else None
    surface, anchors = voxelize_surface(verts, faces, grid, want_anchors=want_anchors,
                                        normals=normals)
    if not surface:
        raise ValueError('voxelization produced no voxels (empty/degenerate mesh)')
    if solid_mode == 'contain':
        solid = solid_by_containment(verts, faces, grid) or fill_solid(surface, grid)
    else:
        solid = fill_solid(surface, grid)
    if hollow:
        # shell of at least min_thickness voxels (>=1). Thin features stay solid because
        # erosion clears them, so the minimum never over-thins sharp edges.
        voxels = hollow_shell(solid, grid, max(1, min_thickness))
    else:
        voxels = solid
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
