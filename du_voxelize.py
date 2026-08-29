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
import os
import multiprocessing
import numpy as np

# Optional: scipy for faster erosion on large grids
try:
    from scipy.ndimage import binary_erosion as scipy_binary_erosion
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

# Parallelism for _scan_axis's outer `a` loop (see below) -- same env var / default cap as
# obj_pipeline.py's emitter pool, so one knob controls both.
_SCAN_PARALLEL_MIN_A = 64
_DEFAULT_MAX_WORKERS = 12   # see obj_pipeline._DEFAULT_MAX_WORKERS; one knob via OBJTODU_WORKERS


def _n_workers():
    n = os.environ.get('OBJTODU_WORKERS')
    if n:
        try:
            return max(1, int(n))
        except ValueError:
            pass
    return max(1, min(_DEFAULT_MAX_WORKERS, (os.cpu_count() or 2) - 1))


# Set by _scan_axis in the PARENT process before Pool() creation, so fork()'d workers inherit
# it via copy-on-write instead of needing it pickled. Unlike obj_pipeline's _WORKER_CTX, the
# shared data here (v0/v1/v2/amin/amax) is proportional to face count, not grid^3, so it's
# small even for complex meshes -- no del/gc.collect() dance needed before forking.
_SCAN_CTX = None


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


def corner_normals(verts, faces, crease_deg=35.0):
    """Per-(face, corner) normals, CREASE-LIMITED: a corner averages only the incident faces
    whose normal is within `crease_deg` of this face's normal. So a flat face keeps its face
    normal (PN stays flat) and a sharp edge keeps each side's own normal (PN stays sharp) --
    only genuinely-curved neighbourhoods blend and round. Returns (M, 3, 3)."""
    import math
    from collections import defaultdict
    fn = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]],
                  verts[faces[:, 2]] - verts[faces[:, 0]])       # area-weighted (|fn| = 2*area)
    ln = np.linalg.norm(fn, axis=1, keepdims=True)
    unit = fn / np.where(ln < 1e-20, 1.0, ln)
    incident = defaultdict(list)
    for fi in range(len(faces)):
        for c in range(3):
            incident[int(faces[fi, c])].append(fi)
    cos_c = math.cos(math.radians(crease_deg))
    out = np.empty((len(faces), 3, 3))
    for fi in range(len(faces)):
        ni = unit[fi]
        for c in range(3):
            acc = np.zeros(3)
            for j in incident[int(faces[fi, c])]:
                if unit[j] @ ni >= cos_c:
                    acc += fn[j]                                # area-weighted blend
            m = np.linalg.norm(acc)
            out[fi, c] = acc / m if m > 1e-20 else ni
    return out


def _voxelize_surface_faces(verts, faces, grid, want_anchors, normals, cnormals, face_idx,
                             crease_face=None):
    """Core per-triangle loop, over just `face_idx` (an iterable of face indices into
    `faces`). Shared by the serial path and each parallel worker's chunk -- see
    voxelize_surface for why splitting by triangle can be parallelized (surface is a plain
    union across triangles/workers; anchors keeps whichever triangle gave the closest point,
    which is an associative per-key min, so partial per-worker dicts merge correctly too).
    crease_face: optional (len(faces),) bool array; when given, tracks which surface voxels
    came from a crease-angle face for material tagging."""
    surface = set()
    crease_surface = set() if crease_face is not None else None
    anchors = {} if want_anchors else None
    for fi in face_idx:
        f = faces[fi]
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
            if crease_surface is not None and crease_face[fi]:
                crease_surface.add((int(x), int(y), int(z)))
        if want_anchors:
            if cnormals is not None:
                tn = (cnormals[fi, 0], cnormals[fi, 1], cnormals[fi, 2])
            elif normals is not None:
                tn = (normals[f[0]], normals[f[1]], normals[f[2]])
            else:
                tn = None
            _accumulate_anchors(anchors, v0, v1, v2, ix[mask], iy[mask], iz[mask], tn, fi)
    return surface, anchors, crease_surface


_SURFACE_PARALLEL_MIN_WORK = 8 * 64   # faces * grid; skip pool overhead below this
_SURF_CTX = None


def _voxelize_surface_chunk(worker_i):
    """Process faces[worker_i::n_workers] (round-robin, not contiguous -- spreads triangles
    of very different candidate-voxel cost evenly across workers instead of risking one
    worker getting a run of expensive large triangles). Reads shared inputs from _SURF_CTX
    (fork/copy-on-write, same reasoning as _scan_axis/_emit_chunk)."""
    ctx = _SURF_CTX
    face_idx = range(worker_i, len(ctx['faces']), ctx['n_workers'])
    return _voxelize_surface_faces(ctx['verts'], ctx['faces'], ctx['grid'], ctx['want_anchors'],
                                   ctx['normals'], ctx['cnormals'], face_idx, crease_face=ctx.get('crease_face'))


def voxelize_surface(verts, faces, grid, want_anchors=True, normals=None, cnormals=None, crease_face=None):
    """Surface voxel set (SAT-exact) + optional anchor map {corner -> nearest surface pt}
    + optional crease_surface (voxels on high-dihedral-angle faces).
    Numpy-batched per triangle over its candidate voxel slab. `cnormals` (M,3,3 crease-limited
    corner normals) projects anchor targets onto the PN-triangle surface, rounding curved
    regions while keeping flats/sharp edges; `normals` (per-vertex) is the legacy blend.
    crease_face: optional (len(faces),) bool array marking crease faces for material tagging.

    Split across a process pool (round-robin by triangle) when there's enough total work and
    fork() is available -- large flat triangles (a cube's 12 faces, say) dominate at high
    grid resolution the same way _scan_axis's outer loop does."""
    def _strip_fi(anch):
        # (target, d2, fi) internal form -> public (target, d2); fi only matters during the
        # per-corner argmin accumulation/merge above.
        return {k: (v[0], v[1]) for k, v in anch.items()} if anch is not None else anch

    n_workers = _n_workers()
    use_pool = (len(faces) * grid >= _SURFACE_PARALLEL_MIN_WORK and n_workers > 1
                and 'fork' in multiprocessing.get_all_start_methods())
    if not use_pool:
        surface, anchors, crease_surface = _voxelize_surface_faces(verts, faces, grid, want_anchors,
                                                   normals, cnormals, range(len(faces)), crease_face=crease_face)
        return surface, _strip_fi(anchors), crease_surface
    n = min(n_workers, len(faces))
    global _SURF_CTX
    _SURF_CTX = dict(verts=verts, faces=faces, grid=grid, want_anchors=want_anchors,
                     normals=normals, cnormals=cnormals, n_workers=n, crease_face=crease_face)
    try:
        ctx = multiprocessing.get_context('fork')
        with ctx.Pool(n) as pool:
            parts = pool.map(_voxelize_surface_chunk, range(n))
    finally:
        _SURF_CTX = None
    surface = set()
    crease_surface = set() if crease_face is not None else None
    anchors = {} if want_anchors else None
    for psurf, panch, pcrease in parts:
        surface |= psurf
        if crease_surface is not None:
            crease_surface |= pcrease
        if want_anchors:
            for k, v in panch.items():
                prev = anchors.get(k)
                # same (d2, fi) argmin as _accumulate_anchors, so the merged result is
                # independent of how faces were partitioned across workers.
                if prev is None or v[1] < prev[1] or (v[1] == prev[1] and v[2] < prev[2]):
                    anchors[k] = v
    return surface, _strip_fi(anchors), crease_surface


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


def _accumulate_anchors(anchors, v0, v1, v2, ix, iy, iz, tn=None, fi=0):
    """Keep, per voxel corner, the closest mesh point across all triangles (the smoothing
    projection target). Vectorized over all 8 corners of every intersected voxel. When tn
    (the three vertex normals) is given, the stored target is the PN-triangle surface point
    (smooth) rather than the flat closest point -- the nearest-triangle metric still uses the
    flat distance.

    Stored value is (target, d2, fi). `fi` (the source face index) is the TIE-BREAKER: on an
    exact d2 tie between two triangles (common at a shared edge, where a corner is equidistant
    to both adjacent faces but their PN targets differ), the lower face index wins. This makes
    the winner a function of (d2, fi) only -- associative, so splitting the triangle loop
    across workers (voxelize_surface) yields byte-identical anchors regardless of the split,
    matching the original serial "process faces 0..M in order, first-closest wins" semantics.
    voxelize_surface strips fi from the final dict, so the public value stays (target, d2)."""
    if len(ix) == 0:
        return
    base = np.stack([ix, iy, iz], 1)                       # (M,3)
    offs = np.array([(dx, dy, dz) for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)])
    corners = (base[:, None, :] + offs[None, :, :]).reshape(-1, 3)   # (8M,3)
    # dedup via 1-D integer key (far faster than np.unique axis=0 sort)
    mn = corners.min(0)
    c = corners - mn
    K = int(c.max()) + 1
    key = (c[:, 0] * K + c[:, 1]) * K + c[:, 2]
    _, idx = np.unique(key, return_index=True)
    corners = corners[idx]
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
        # (dk, fi) < (prev_d2, prev_fi): min distance, ties broken by lower face index
        if prev is None or dk < prev[1] or (dk == prev[1] and fi < prev[2]):
            anchors[key] = ((float(T[k, 0]), float(T[k, 1]), float(T[k, 2])), dk, fi)


def _scan_a_range(a_range):
    """Compute occ[a_lo:a_hi, :, :] (relative-indexed, shape (a_hi-a_lo, grid, grid)) for one
    contiguous slice of _scan_axis's outer `a` loop. Module-level (picklable by reference) so
    a multiprocessing.Pool can dispatch it; the actual mesh data comes from _SCAN_CTX, not
    arguments -- see _scan_axis for why (fork/copy-on-write sharing, not pickling)."""
    a_lo, a_hi = a_range
    ctx = _SCAN_CTX
    v0, v1, v2, amin, amax = ctx['v0'], ctx['v1'], ctx['v2'], ctx['amin'], ctx['amax']
    grid, EA, EB = ctx['grid'], ctx['EA'], ctx['EB']
    occ = np.zeros((a_hi - a_lo, grid, grid), bool)
    for a in range(a_lo, a_hi):
        pa = a + 0.5 + EA
        ma = (amin[:, 0] <= pa) & (pa <= amax[:, 0])
        if not ma.any():
            continue
        b0, b1, b2 = v0[ma], v1[ma], v2[ma]
        bmn = amin[ma]; bmx = amax[ma]
        b_lo = max(0, int(math.floor(bmn[:, 1].min())))
        b_hi = min(grid, int(math.ceil(bmx[:, 1].max())) + 1)
        for b in range(b_lo, b_hi):
            pb = b + 0.5 + EB
            mb = (bmn[:, 1] <= pb) & (pb <= bmx[:, 1])
            if not mb.any():
                continue
            cs = _ray_z_hits(b0[mb], b1[mb], b2[mb], pa, pb)
            if len(cs) < 2:
                continue
            cs.sort()
            for i in range(0, len(cs) - 1, 2):
                c0 = max(0, int(math.ceil(cs[i] - 0.5)))
                c1 = min(grid - 1, int(math.floor(cs[i + 1] - 0.5)))
                if c1 >= c0:
                    occ[a - a_lo, b, c0:c1 + 1] = True
    return occ


def _scan_axis(verts, faces, grid, axis):
    """Inside-voxel occupancy (bool grid^3, ORIGINAL frame) by casting rays ALONG `axis`
    through each cell centre of the other two axes, even-odd parity. Fills each inside run
    with a numpy SLICE (no per-voxel Python).

    The outer `a` loop is embarrassingly parallel -- each `a` only ever writes its own
    occ[a,:,:] slice -- and is the dominant cost at high resolution (measured ~70% of total
    voxelize() time at grid 512, almost entirely in the per-(a,b) ray-triangle intersection).
    Split across a process pool when there's enough work and fork() is available; falls back
    to the plain loop otherwise (small shapes, or Windows/macOS-spawn hosts)."""
    p = [i for i in range(3) if i != axis] + [axis]     # ray axis last
    inv = [p.index(i) for i in range(3)]
    V = verts[:, p]
    v0 = V[faces[:, 0]]; v1 = V[faces[:, 1]]; v2 = V[faces[:, 2]]
    amin = np.minimum(np.minimum(v0, v1), v2)
    amax = np.maximum(np.maximum(v0, v1), v2)
    # Perturb the ray by tiny INCOMMENSURATE irrationals so it never passes exactly through a
    # shared edge / vertex / coplanar ring (the equatorial "knife cut"). Sub-voxel -> the
    # inside/outside classification is unchanged, but grazes become measure-zero, which makes
    # a SINGLE axis robust (the old 3-axis majority vote is no longer needed).
    EA = 1e-3 * math.sqrt(2)
    EB = 1e-3 * math.sqrt(3)
    occ = np.zeros((grid, grid, grid), bool)            # permuted [a, b, c]
    a_lo = max(0, int(math.floor(amin[:, 0].min())))
    a_hi = min(grid, int(math.ceil(amax[:, 0].max())) + 1)
    total_a = a_hi - a_lo
    n_workers = _n_workers()
    use_pool = (total_a >= _SCAN_PARALLEL_MIN_A and n_workers > 1
                and 'fork' in multiprocessing.get_all_start_methods())
    global _SCAN_CTX
    _SCAN_CTX = dict(v0=v0, v1=v1, v2=v2, amin=amin, amax=amax, grid=grid, EA=EA, EB=EB)
    try:
        if use_pool:
            n = min(n_workers, total_a)
            bounds = np.linspace(a_lo, a_hi, n + 1).round().astype(int)
            ranges = [(int(bounds[i]), int(bounds[i + 1]))
                      for i in range(n) if bounds[i] < bounds[i + 1]]
            ctx = multiprocessing.get_context('fork')
            with ctx.Pool(len(ranges)) as pool:
                parts = pool.map(_scan_a_range, ranges)
            for (rlo, rhi), part in zip(ranges, parts):
                occ[rlo:rhi] = part
        else:
            occ[a_lo:a_hi] = _scan_a_range((a_lo, a_hi))
    finally:
        _SCAN_CTX = None
    return np.transpose(occ, inv)                        # back to original frame


def solid_by_containment(verts, faces, grid, robust=False):
    """Mesh-tight solid occupancy: a voxel is filled iff its CENTRE is inside the mesh (ray
    even-odd parity). The boundary sits ON the surface so smoothing deflections stay
    sub-voxel. Watertight meshes required for a correct interior.

    Returns a DENSE (grid,grid,grid) bool array, not a coordinate set. A solid shape can
    occupy close to 100% of grid^3; a Python set of int-tuples costs ~190 B/entry (measured)
    vs 1 B/entry for a bool array, so materialising the set form at high resolution is what
    was blowing memory past the guard's grid^3*64B estimate (grid 512 solid: ~22 GB as a
    set vs ~134 MB dense -- and voxelize() below was building TWO such sets, doubling it).

    Ray perturbation makes a SINGLE z-scan robust (default). robust=True casts all 3 axes and
    majority-votes (>=2) -- kept as a fallback for pathological non-manifold meshes."""
    if robust:
        occ = (_scan_axis(verts, faces, grid, 0).astype(np.int8)
               + _scan_axis(verts, faces, grid, 1)
               + _scan_axis(verts, faces, grid, 2)) >= 2
    else:
        occ = _scan_axis(verts, faces, grid, 2)
    return occ


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
    single crossings). Returns a DENSE (grid,grid,grid) bool array of surface | interior --
    same representation as solid_by_containment, so voxelize() can merge either branch
    uniformly without materialising a grid^3-scale Python set (see solid_by_containment)."""
    occ = np.zeros((grid, grid, grid), bool)
    cols = {}
    for (x, y, z) in surface:
        cols.setdefault((x, y), []).append(z)
        occ[x, y, z] = True
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
            lo_z, hi_z = runs[i][1] + 1, runs[i + 1][0]
            if hi_z > lo_z:
                occ[x, y, lo_z:hi_z] = True
    return occ


def _erode(occ, n):
    """Erode a 3D boolean occupancy array by n layers (6-connectivity): a voxel survives
    iff it and all 6 face-neighbours were solid, repeated n times.
    Uses scipy.ndimage.binary_erosion if available (C implementation, 5-10x faster);
    falls back to vectorized numpy."""
    if n <= 0:
        return occ
    occ = occ.astype(bool)
    if _SCIPY_AVAILABLE:
        # scipy's binary_erosion is much faster (implemented in C)
        structure = np.ones((3, 3, 3), bool)
        structure[0, 0, 0] = False; structure[0, 0, 2] = False
        structure[0, 2, 0] = False; structure[0, 2, 2] = False
        structure[2, 0, 0] = False; structure[2, 0, 2] = False
        structure[2, 2, 0] = False; structure[2, 2, 2] = False  # 6-connectivity
        return scipy_binary_erosion(occ, structure=structure, iterations=n)
    # Fallback: pure numpy vectorized
    for _ in range(n):
        result = np.zeros_like(occ)
        # Combine all neighbor checks at once (avoids intermediate copies)
        result[1:-1, 1:-1, 1:-1] = (
            occ[1:-1, 1:-1, 1:-1] &
            occ[:-2, 1:-1, 1:-1] &  # i-1 neighbor
            occ[2:, 1:-1, 1:-1] &   # i+1 neighbor
            occ[1:-1, :-2, 1:-1] &  # j-1 neighbor
            occ[1:-1, 2:, 1:-1] &   # j+1 neighbor
            occ[1:-1, 1:-1, :-2] &  # k-1 neighbor
            occ[1:-1, 1:-1, 2:]     # k+1 neighbor
        )
        occ = result
    return occ


def _inner_boundary_anchors(shell, grid, verts, faces, want_anchors, cnormals=None, normals=None):
    """For a HOLLOW shell, compute anchor targets for voxel corners on the INNER boundary
    (boundary between shell and the eroded-away interior). Returns a dict of anchors on the
    inner surface, or None if not wanted. Uses spatial bucketing to avoid O(corners*triangles)
    projection checks."""
    if not want_anchors or not shell.any():
        return None
    import time
    t0 = time.time()
    # Fast detection: the inner surface is where the shell meets the eroded void.
    eroded = _erode(shell, 1)
    is_boundary = shell & ~eroded
    boundary_voxels = np.argwhere(is_boundary)
    if len(boundary_voxels) == 0:
        return None
    print(f"[_inner_boundary_anchors] {len(boundary_voxels)} boundary voxels, "
          f"projecting ~{len(boundary_voxels)*8} corners onto {len(faces)} triangles...")

    # Spatial bucketing: divide grid into buckets, assign triangles to buckets they overlap.
    # Each bucket covers BUCKET_SIZE voxels; corners query nearby buckets only.
    BUCKET_SIZE = 16
    buckets = {}
    for fi in range(len(faces)):
        f = faces[fi]
        v0, v1, v2 = verts[f[0]], verts[f[1]], verts[f[2]]
        lo = np.floor(np.minimum(np.minimum(v0, v1), v2)).astype(int)
        hi = np.ceil(np.maximum(np.maximum(v0, v1), v2)).astype(int)
        lo = np.clip(lo, 0, grid - 1); hi = np.clip(hi, 0, grid - 1)
        for bx in range(lo[0] // BUCKET_SIZE, (hi[0] // BUCKET_SIZE) + 1):
            for by in range(lo[1] // BUCKET_SIZE, (hi[1] // BUCKET_SIZE) + 1):
                for bz in range(lo[2] // BUCKET_SIZE, (hi[2] // BUCKET_SIZE) + 1):
                    key = (bx, by, bz)
                    if key not in buckets:
                        buckets[key] = []
                    buckets[key].append(fi)

    anchors = {}
    for x, y, z in boundary_voxels:
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    cx, cy, cz = x + dx, y + dy, z + dz
                    key = (int(cx), int(cy), int(cz))
                    if key in anchors:
                        continue
                    corner = np.array([cx + 0.5, cy + 0.5, cz + 0.5], dtype=np.float64)
                    # Query nearby buckets (corner bucket + adjacent buckets)
                    bx, by, bz = cx // BUCKET_SIZE, cy // BUCKET_SIZE, cz // BUCKET_SIZE
                    candidate_faces = set()
                    for dbx in (-1, 0, 1):
                        for dby in (-1, 0, 1):
                            for dbz in (-1, 0, 1):
                                bkey = (bx + dbx, by + dby, bz + dbz)
                                candidate_faces.update(buckets.get(bkey, []))

                    best_d2 = float('inf')
                    best_target = None
                    for fi in candidate_faces:
                        f = faces[fi]
                        v0, v1, v2 = verts[f[0]], verts[f[1]], verts[f[2]]
                        e0 = v1 - v0; e1 = v2 - v0; c = corner - v0
                        d00 = float(e0 @ e0); d01 = float(e0 @ e1); d11 = float(e1 @ e1)
                        denom = d00 * d11 - d01 * d01
                        if abs(denom) < 1e-20:
                            continue
                        c_dot_e0 = float(c @ e0); c_dot_e1 = float(c @ e1)
                        s = (d11 * c_dot_e0 - d01 * c_dot_e1) / denom
                        t = (d00 * c_dot_e1 - d01 * c_dot_e0) / denom
                        s_clipped = np.clip(s, 0.0, 1.0)
                        t_clipped = np.clip(t, 0.0, 1.0)
                        if s_clipped + t_clipped > 1.0:
                            sum_st = s_clipped + t_clipped
                            s_clipped /= sum_st
                            t_clipped = 1.0 - s_clipped
                        pt = v0 + s_clipped * e0 + t_clipped * e1
                        d2 = float(np.sum((pt - corner) ** 2))
                        if d2 < best_d2:
                            best_d2 = d2
                            best_target = tuple(pt)
                    if best_target is not None:
                        anchors[key] = (best_target, best_d2)
    elapsed = time.time() - t0
    print(f"[_inner_boundary_anchors] Complete: {len(anchors)} anchors in {elapsed:.1f}s")
    return anchors if anchors else None


def hollow_shell(solid, grid, thickness):
    """Hollow a DENSE (grid,grid,grid) solid occupancy array to a shell `thickness` voxels
    thick: shell = solid minus (solid eroded by `thickness`). Where the shape is thinner than
    2*thickness (sharp edges, thin features) erosion clears it, so those regions stay SOLID --
    the minimum never over-thins genuine detail. thickness<=0 returns the solid unchanged.
    Returns a dense array of the same (grid,grid,grid) shape as `solid`."""
    if thickness <= 0 or not solid.any():
        return solid
    padded = np.pad(solid, 1, mode='constant', constant_values=False)   # False border so
    inner = _erode(padded, thickness)                                  # the outer surface erodes
    shell = padded & ~inner
    return shell[1:-1, 1:-1, 1:-1]


def _closest_on_segment_pt(p, a, b):
    """Closest point on segment [a,b] to point p (all (3,) arrays)."""
    ab = b - a
    denom = float(ab @ ab)
    if denom < 1e-20:
        return a
    t = min(1.0, max(0.0, float((p - a) @ ab) / denom))
    return a + t * ab


def crease_faces(verts, faces, crease_deg=35.0):
    """Per-face crease classification: (len(faces),) bool array where True means the face has
    at least one edge diverging >crease_deg from a neighbor. Used to tag surface voxels for
    material assignment. Uses the same edge-adjacency logic as mesh_crease_features but
    returns a boolean per face, not the edge/corner geometry."""
    from collections import defaultdict
    if len(faces) == 0:
        return np.zeros(0, bool)
    q = max(1e-9, 1e-5 * float(np.ptp(verts, axis=0).max()))
    vkeys = np.round(verts / q).astype(np.int64)
    canon = {}
    vid_of = np.empty(len(verts), np.int64)
    for i, k in enumerate(map(tuple, vkeys.tolist())):
        vid_of[i] = canon.setdefault(k, len(canon))
    fn = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]],
                  verts[faces[:, 2]] - verts[faces[:, 0]])
    ln = np.linalg.norm(fn, axis=1)
    unit = fn / np.where(ln[:, None] < 1e-20, 1.0, ln[:, None])
    degenerate = ln < 1e-9
    e2f = defaultdict(list)
    for fi in range(len(faces)):
        if degenerate[fi]:
            continue
        a, b, c = int(vid_of[faces[fi, 0]]), int(vid_of[faces[fi, 1]]), int(vid_of[faces[fi, 2]])
        for u, v in ((a, b), (b, c), (c, a)):
            if u != v:
                e2f[(u, v) if u < v else (v, u)].append(fi)
    cos_c = math.cos(math.radians(crease_deg))
    is_crease = np.zeros(len(faces), bool)
    for (u, v), fis in e2f.items():
        if len(fis) == 2 and float(unit[fis[0]] @ unit[fis[1]]) < cos_c:
            is_crease[fis[0]] = True
            is_crease[fis[1]] = True
    return is_crease


def mesh_crease_features(verts, faces, crease_deg=35.0):
    """Extract sharp FEATURES from mesh topology, in the SAME coord space as `verts`:
      edges   -- (E,2,3) endpoints of crease edges: an edge shared by two faces whose normals
                 diverge by more than crease_deg.
      corners -- (C,3) feature points: welded vertices where >=3 crease edges meet, or where
                 two crease edges bend (non-collinear).
    These drive feature_snap_anchors so sharp non-axis-aligned edges/corners survive smoothing.

    Robust to real exports: vertices are WELDED by position (coincident-but-duplicated
    vertices -- a common exporter artifact -- otherwise break edge adjacency and fabricate
    creases across a smooth surface, e.g. 120 phantom creases on a clean sphere), and
    DEGENERATE (near-zero-area) faces are skipped (garbage normals). A boundary edge (one
    incident face after welding) is NOT a crease -- a watertight solid has none, and a gap in
    an imperfect mesh must not fabricate a sharp edge."""
    from collections import defaultdict
    if len(faces) == 0:
        return np.zeros((0, 2, 3)), np.zeros((0, 3))
    q = max(1e-9, 1e-5 * float(np.ptp(verts, axis=0).max()))
    vkeys = np.round(verts / q).astype(np.int64)
    canon = {}
    vid_of = np.empty(len(verts), np.int64)
    for i, k in enumerate(map(tuple, vkeys.tolist())):
        vid_of[i] = canon.setdefault(k, len(canon))
    fn = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]],
                  verts[faces[:, 2]] - verts[faces[:, 0]])
    ln = np.linalg.norm(fn, axis=1)
    unit = fn / np.where(ln[:, None] < 1e-20, 1.0, ln[:, None])
    degenerate = ln < 1e-9
    e2f = defaultdict(list)                            # welded undirected edge -> face indices
    for fi in range(len(faces)):
        if degenerate[fi]:
            continue
        a, b, c = int(vid_of[faces[fi, 0]]), int(vid_of[faces[fi, 1]]), int(vid_of[faces[fi, 2]])
        for u, v in ((a, b), (b, c), (c, a)):
            if u != v:
                e2f[(u, v) if u < v else (v, u)].append(fi)
    pos_of = {}                                        # welded vid -> a representative position
    for i in range(len(verts)):
        pos_of.setdefault(int(vid_of[i]), verts[i])
    cos_c = math.cos(math.radians(crease_deg))
    crease_edges = []
    vce = defaultdict(list)
    for (u, v), fis in e2f.items():
        if len(fis) == 2 and float(unit[fis[0]] @ unit[fis[1]]) < cos_c:
            crease_edges.append((u, v))
            vce[u].append(v); vce[v].append(u)
    edges = (np.array([(pos_of[u], pos_of[v]) for u, v in crease_edges], float)
             if crease_edges else np.zeros((0, 2, 3)))
    corner_vids = []
    for vid, others in vce.items():
        if len(others) >= 3:
            corner_vids.append(vid); continue
        if len(others) == 2:
            d0 = pos_of[others[0]] - pos_of[vid]; d1 = pos_of[others[1]] - pos_of[vid]
            n0 = float(np.linalg.norm(d0)) or 1.0; n1 = float(np.linalg.norm(d1)) or 1.0
            if abs(float((d0 / n0) @ (d1 / n1))) < 0.999:      # bend -> corner
                corner_vids.append(vid)
    corners = (np.array([pos_of[i] for i in corner_vids], float)
               if corner_vids else np.zeros((0, 3)))
    return edges, corners


def feature_snap_anchors(anchors, edges, corners, radius):
    """Override each surface-corner anchor whose nearest crease FEATURE is within `radius`:
    snap its smoothing target to the crease CORNER point (priority) or the nearest point on a
    crease EDGE segment. Without this, the anchor target is nearest-point-on-nearest-triangle,
    which lands on a single FACE -- so a sharp non-axis-aligned edge is reconstructed as a
    rounded, jagged band across the two faces (axis-aligned edges are immune: they already lie
    on voxel-corner lines with zero deflection). Snapping the ~1-voxel ring of corners around
    the feature onto the feature itself restores the crease within the +-1.19 vox clamp.

    Spatially indexed (creases are sparse, radius ~1 vox) and DETERMINISTIC (nearest feature,
    ties by kind then index) so it doesn't depend on the parallelized surface pass's ordering.
    anchors keys are integer voxel corners, values (target, d2); returns a new dict."""
    if not anchors or (len(edges) == 0 and len(corners) == 0):
        return anchors
    r2 = radius * radius
    # Coarse spatial hash of anchor corners so each feature only tests nearby anchors -- a
    # dense-crease mesh (thousands of long edges) otherwise spends all its time on empty-cell
    # lookups along the edges (grid-512-scale: minutes). Bucket size 2 ~ the radius.
    from collections import defaultdict
    B = 2
    buckets = defaultdict(list)
    for key in anchors:
        buckets[(key[0] // B, key[1] // B, key[2] // B)].append(key)
    # a corner within `radius` of a feature is at most ceil(radius) voxels away -> +-1 bucket
    # (bucket=2 vox covers that), so Rb = ceil(radius/B) buckets each side is exact coverage.
    Rb = int(math.ceil(radius / B))
    boff = tuple(range(-Rb, Rb + 1))
    best = {}                                         # key -> (d2, kind, idx, target)

    def consider(key, d2, kind, idx, target):
        if d2 <= r2:
            cur = best.get(key)
            if cur is None or (d2, kind, idx) < (cur[0], cur[1], cur[2]):
                best[key] = (d2, kind, idx, target)

    for ci in range(len(corners)):                    # crease CORNER points (kind 0, priority)
        px, py, pz = float(corners[ci][0]), float(corners[ci][1]), float(corners[ci][2])
        cb = (int(math.floor(px)) // B, int(math.floor(py)) // B, int(math.floor(pz)) // B)
        tgt = (px, py, pz)
        for dx in boff:
            for dy in boff:
                for dz in boff:
                    for key in buckets.get((cb[0]+dx, cb[1]+dy, cb[2]+dz), ()):
                        d2 = (px-key[0])**2 + (py-key[1])**2 + (pz-key[2])**2
                        consider(key, d2, 0, ci, tgt)
    for ei in range(len(edges)):                      # crease EDGE segments (kind 1)
        ax, ay, az = float(edges[ei,0,0]), float(edges[ei,0,1]), float(edges[ei,0,2])
        abx, aby, abz = float(edges[ei,1,0])-ax, float(edges[ei,1,1])-ay, float(edges[ei,1,2])-az
        denom = abx*abx + aby*aby + abz*abz or 1.0
        steps = max(1, int(math.ceil(math.sqrt(denom) / B)))
        seen = set()                                  # per-edge bucket dedup (steps overlap)
        for s in range(steps + 1):
            t = s / steps
            cb = (int(math.floor(ax+abx*t)) // B, int(math.floor(ay+aby*t)) // B,
                  int(math.floor(az+abz*t)) // B)
            for dx in boff:
                for dy in boff:
                    for dz in boff:
                        bk = (cb[0]+dx, cb[1]+dy, cb[2]+dz)
                        if bk in seen:
                            continue
                        seen.add(bk)
                        for key in buckets.get(bk, ()):
                            if key in best and best[key][1] == 0:
                                continue              # already claimed by a corner (priority)
                            tt = ((key[0]-ax)*abx + (key[1]-ay)*aby + (key[2]-az)*abz) / denom
                            tt = 0.0 if tt < 0.0 else (1.0 if tt > 1.0 else tt)
                            qx, qy, qz = ax+abx*tt, ay+aby*tt, az+abz*tt
                            d2 = (qx-key[0])**2 + (qy-key[1])**2 + (qz-key[2])**2
                            consider(key, d2, 1, ei, (qx, qy, qz))
    if not best:
        return anchors
    out = dict(anchors)
    for key, (d2, kind, idx, target) in best.items():
        out[key] = (target, d2)
    return out


def _flood_fill_exterior(grid, surface_set):
    """Flood-fill from boundary to mark external space. Surface voxels act as barriers.
    Returns a bool array where True=external, False=interior."""
    external = np.zeros((grid, grid, grid), bool)
    surface_grid = np.zeros((grid, grid, grid), bool)
    for (x, y, z) in surface_set:
        if 0 <= x < grid and 0 <= y < grid and 0 <= z < grid:
            surface_grid[x, y, z] = True

    # Start flood-fill from boundary voxels
    queue = []
    visited = np.zeros((grid, grid, grid), bool)

    # Add all boundary-adjacent voxels to queue (they're definitely external)
    for i in range(grid):
        for j in range(grid):
            for k in [0, grid - 1]:
                if not visited[i, j, k]:
                    queue.append((i, j, k))
                    visited[i, j, k] = True
                    external[i, j, k] = True
            for k in [0, grid - 1]:
                if not visited[i, k, j]:
                    queue.append((i, k, j))
                    visited[i, k, j] = True
                    external[i, k, j] = True
            for k in [0, grid - 1]:
                if not visited[k, i, j]:
                    queue.append((k, i, j))
                    visited[k, i, j] = True
                    external[k, i, j] = True

    # BFS: expand external region, stopped by surface voxels
    idx = 0
    while idx < len(queue):
        x, y, z = queue[idx]
        idx += 1

        for dx, dy, dz in [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]:
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < grid and 0 <= ny < grid and 0 <= nz < grid:
                if not visited[nx, ny, nz]:
                    visited[nx, ny, nz] = True
                    if not surface_grid[nx, ny, nz]:
                        external[nx, ny, nz] = True
                        queue.append((nx, ny, nz))

    return external


def voxelize_flood_fill(verts, faces, grid, hollow=False, want_anchors=True,
                        smooth_normals=True, min_thickness=0, crease_deg=35.0, preserve_features=True):
    """Voxelization via flood-fill from outside (alternative to SAT-based contain/fill).

    Flood-fills from the boundary to identify external space, treating surface voxels as
    barriers. Interior = everything not marked external. Can be more robust on complex,
    non-convex, or non-manifold geometry compared to ray-parity containment tests."""
    cn = corner_normals(verts, faces, crease_deg) if (want_anchors and smooth_normals) else None
    surface, anchors, _ = voxelize_surface(verts, faces, grid, want_anchors=want_anchors,
                                        cnormals=cn, crease_face=None)
    if not surface:
        raise ValueError('voxelization produced no voxels (empty/degenerate mesh)')

    # Flood-fill from outside to find external space
    external = _flood_fill_exterior(grid, surface)
    solid = ~external  # Interior = NOT external

    if want_anchors and preserve_features and anchors:
        edges, corners = mesh_crease_features(verts, faces, crease_deg)
        anchors = feature_snap_anchors(anchors, edges, corners, radius=100.0 / 84.0)

    if hollow:
        import time
        t_hollow = time.time()
        print(f"[voxelize_flood_fill] Creating hollow shell (thickness={max(1, min_thickness)}, grid={grid}^3={grid**3//1_000_000}M)...")
        occ = hollow_shell(solid, grid, max(1, min_thickness))
        print(f"[voxelize_flood_fill] Hollow shell complete in {time.time()-t_hollow:.1f}s ({np.sum(occ)} voxels)")
    else:
        occ = solid

    voxels = np.argwhere(occ)
    print(f"[voxelize_flood_fill] FINAL: {len(voxels)} voxels extracted from occupancy grid")
    return voxels, anchors


def voxelize(verts, faces, grid, hollow=False, want_anchors=True, solid_mode='contain',
             smooth_normals=True, min_thickness=0, crease_deg=35.0, preserve_features=True,
             voxelization_method='sat'):
    """Full voxelization -> (voxels, anchors, labels).

    voxelization_method='sat' (default): SAT-based surface detection + containment/fill.
    voxelization_method='flood': flood-fill from outside (more robust on complex geometry).

    solid_mode='contain' (default): mesh-tight interior (center-in-mesh z-parity) UNIONED
        with the conservative SAT surface, so THIN features (< the interior sampling can
        catch) are still represented; smoothing then pulls the surface layer onto the mesh.
        (Ignored when voxelization_method='flood')
    solid_mode='band': conservative SAT surface + span fill only.
    hollow=True: surface shell only (no interior), for hulls with a modeled outer skin.
    smooth_normals=True: anchor targets projected onto the PN-triangle surface using
        CREASE-LIMITED corner normals (crease_deg) -- curved regions round out, but flat
        faces stay flat and sharp edges stay sharp (no rounding of straight lines).
    min_thickness: for hollow shapes, the shell is at least this many voxels thick (>=1);
        regions genuinely thinner than 2x this (sharp edges) stay solid, never over-thinned.

    Anchors ({surface corner -> nearest mesh point}) always come from the SAT surface pass
    so the smoothing layer has a projection target for every boundary vertex.

    labels: (N,) uint8 array, 1=base material, 2=crease-face material. Interior fill voxels
    are always label 1 (only surface voxels can be crease-tagged).

    Internally the solid/interior occupancy stays a DENSE (grid,grid,grid) bool array end to
    end (see solid_by_containment) -- only the sparse SURFACE shell (bounded by mesh area,
    not grid^3) is ever a Python set of tuples. The final return converts the dense result to
    a compact (N,3) int64 coordinate array via np.argwhere (vectorized, no per-voxel Python
    object churn), not a Python set -- for a solid shape N can be ~all of grid^3, and a
    coordinate array costs ~24 B/entry vs ~190 B/entry for a set of tuples."""

    if voxelization_method == 'flood':
        return voxelize_flood_fill(verts, faces, grid, hollow=hollow, want_anchors=want_anchors,
                                   smooth_normals=smooth_normals, min_thickness=min_thickness,
                                   crease_deg=crease_deg, preserve_features=preserve_features)

    cn = corner_normals(verts, faces, crease_deg) if (want_anchors and smooth_normals) else None
    surface, anchors, _ = voxelize_surface(verts, faces, grid, want_anchors=want_anchors,
                                        cnormals=cn, crease_face=None)
    if not surface:
        raise ValueError('voxelization produced no voxels (empty/degenerate mesh)')
    if want_anchors and preserve_features and anchors:
        # Feature preservation: snap the anchor ring around each sharp crease onto the crease
        # itself, so non-axis-aligned edges/corners stay sharp instead of rounding onto a face
        # (see feature_snap_anchors). radius = the +-1.19 vox deflection clamp (100/84).
        edges, corners = mesh_crease_features(verts, faces, crease_deg)
        anchors = feature_snap_anchors(anchors, edges, corners, radius=100.0 / 84.0)
    if solid_mode == 'contain':
        contain = solid_by_containment(verts, faces, grid)
        if contain.any():
            # add ONLY surface voxels with NO containment voxel nearby -- i.e. thin sheets/
            # fins the interior sampler dropped. Surface voxels hugging a thick boundary have
            # a containment neighbour and are skipped, so thick solids keep their TIGHT
            # boundary (sharp edges reachable within the +-1.19 vox deflection clamp).
            # Padded so neighbour lookups never need per-voxel bounds checks; the check is
            # against the PRISTINE contain array (collect first, apply after, matching the
            # old contain | thin set-union semantics -- must not see its own additions).
            padded = np.pad(contain, 1, mode='constant', constant_values=False)
            thin = []
            for (x, y, z) in surface:
                px, py, pz = x + 1, y + 1, z + 1
                if not padded[px, py, pz] and not (
                        padded[px + 1, py, pz] or padded[px - 1, py, pz] or
                        padded[px, py + 1, pz] or padded[px, py - 1, pz] or
                        padded[px, py, pz + 1] or padded[px, py, pz - 1]):
                    thin.append((x, y, z))
            for (x, y, z) in thin:
                contain[x, y, z] = True
            solid = contain
        else:
            solid = fill_solid(surface, grid)
    else:
        solid = fill_solid(surface, grid)
    if hollow:
        # shell of at least min_thickness voxels (>=1). Thin features stay solid because
        # erosion clears them, so the minimum never over-thins sharp edges.
        import time
        t_hollow = time.time()
        print(f"[voxelize] Creating hollow shell (thickness={max(1, min_thickness)}, grid={grid}^3={grid**3//1_000_000}M)...")
        occ = hollow_shell(solid, grid, max(1, min_thickness))
        print(f"[voxelize] Hollow shell complete in {time.time()-t_hollow:.1f}s ({np.sum(occ)} voxels)")
        # NOTE: Skipping inner boundary anchors for hollow shapes by default.
        # Computing anchors for the inner surface is expensive (projects 1M+ corners)
        # and mostly cosmetic. Outer surface anchors are sufficient for most use cases.
        # To enable, set want_anchors_inner=True (not exposed in UI).
    else:
        occ = solid
    voxels = np.argwhere(occ)                     # compact (N,3) int64, C-order sorted
    print(f"[voxelize] FINAL: {len(voxels)} voxels extracted from {occ.dtype} occupancy grid")
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
