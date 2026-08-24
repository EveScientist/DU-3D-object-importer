"""obj_frontend.py -- .obj mesh -> DU blueprint, on the SEMANTIC pipeline (2026-07-18).

Full path: load a triangle mesh, voxelize its surface, fill to a solid, place it in the
chosen core, and emit a blueprint via obj_pipeline.build_blueprint_sem (du_semantic core,
no empirical grammar; du_envelope for arbitrary core sizes). This is what the web UI at
objtodu.evescientist.net calls.

    from obj_frontend import obj_to_blueprint
    obj_to_blueprint('ship.obj', 'ship.blueprint', size='L', fill_fraction=0.9)

The voxelizer (obj_to_du_voxels.voxelize, surface SAT) is intentionally SWAPPABLE -- pass
your own voxelize_fn(verts, faces, grid)->set to try a different algorithm.
"""
import os

import numpy as np

import du_voxelize as VX
import du_semantic
import obj_pipeline as P
import du_envelope as E

# Core build volume starts at voxel 8 (the (8,8,8) chunk-0 origin in construct-local coords).
CORE_ORIGIN = 8

# Peak-RAM guard: a solid shape is up to grid^3 voxels held as a set of tuples + numpy grids
# (~64 B/voxel plus the grids), so grid^3 is the peak RAM. Cap the grid so the worst case
# stays within budget and avoids the OOM that killed max-res on the shared server.
#   - shared server (default): 5M voxels (grid ~171) ~= 0.5 GB, safe alongside the DU server.
#   - local PC / Docker: raise it via OBJTODU_MAX_VOXELS (e.g. 134_217_728 for grid 512,
#     the largest the web UI's max_grid field will ever request) once you have the RAM --
#     the code is identical, only this ceiling changes.
MAX_SOLID_VOXELS = int(os.environ.get('OBJTODU_MAX_VOXELS') or 5_000_000)


def voxelize_obj(obj_path, size='M', fill_fraction=0.9, hollow=False, margin=None,
                 grid=None, want_anchors=False, max_grid=256, min_thickness=2,
                 rotate_to_z_up=True, crease_deg=35.0):
    """.obj -> (voxels, smooth_fn, labels) in construct-local coords (min corner near CORE_ORIGIN).

    size           core size name (XS..XXL); sets the voxel resolution unless `grid`.
    fill_fraction  fraction of the core edge the longest mesh axis fills (0<f<=1) --
                   the SCALING control the user picks.
    grid           override: absolute voxel resolution of the longest mesh axis.
    hollow         False = watertight solid (caves/holds preserved as modeled voids);
                   True = surface shell only.
    want_anchors   also return a smooth_fn projecting each surface vertex to the nearest
                   mesh point (the "forcibly smooth a jagged edge" deflection), else None.
    rotate_to_z_up rotate the mesh 90° about X-axis (most OBJ/STL are Y-up, DU is Z-up);
                   applied before voxelizing so all downstream logic is consistent.
    crease_deg    edge-sharpness threshold: faces diverging > this angle are crease-snapped
                  (lower = catches gentler edges, 10-60 range typical; default 35).
    labels        (N,) uint8 array: 1=base material, 2=crease-face material.
    """
    core_vox = E.core_build_voxels(size)          # true voxel resolution (4x world size)
    if grid is None:
        grid = max(1, int(round(core_vox * fill_fraction)))
    if grid > core_vox:
        raise ValueError(f"grid {grid} exceeds {size} core build resolution {core_vox}")
    if grid > max_grid:
        # perf guard: a solid grid^3 shape is ~grid^3 voxels; beyond ~256 the pure-Python
        # emitter/voxelizer get slow and blueprints large. Cap unless the caller lifts it.
        print(f"[obj] grid {grid} capped to {max_grid} for performance "
              f"(pass max_grid= to raise; fills {100*max_grid//core_vox}% of the {size} core)")
        grid = max_grid
    # MEMORY guard: a solid shape holds up to grid^3 voxels; stored as a Python set of
    # tuples (~64 B each) plus numpy grids, this is the peak RAM. Cap the grid so the
    # worst case stays within a server-safe budget (avoids the OOM that killed max-res).
    if grid ** 3 > MAX_SOLID_VOXELS:
        safe = int(MAX_SOLID_VOXELS ** (1.0 / 3))
        print(f"[obj] grid {grid} capped to {safe} to stay within the memory budget "
              f"(~{MAX_SOLID_VOXELS // 1_000_000}M voxels)")
        grid = safe
    verts, faces = VX.load_mesh(obj_path)
    # rotate Y-up (OBJ/STL convention) to Z-up (DU convention): 90° about X-axis.
    # R = [[1, 0, 0], [0, 0, -1], [0, 1, 0]] maps (x,y,z) -> (x,-z,y) -- stands up Y-tall
    # shapes and doesn't mirror (180° rotation avoids handedness flip vs naive swap).
    if rotate_to_z_up:
        verts = verts @ np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)
    verts, _ = VX.fit_to_grid(verts, grid, margin=0)
    solid, anchors, labels = VX.voxelize(verts, faces, grid, hollow=hollow,
                                 want_anchors=want_anchors, min_thickness=min_thickness,
                                 crease_deg=crease_deg)
    # translate so the shape's min corner sits at CORE_ORIGIN, centred in the core.
    # `solid` is already a compact (N,3) int64 coordinate array (VX.voxelize returns
    # np.argwhere of a dense occupancy array, not a Python set -- see du_voxelize.voxelize
    # for why: a solid shape can be ~all of grid^3, and materialising that as a Python set
    # of tuples costs ~190B/entry vs ~24B/entry for a numpy row, a 100x+ blowup at grid 512+
    # that was OOM-killing max-resolution conversions). Stays a compact array end to end --
    # no set reconstruction here either.
    sarr = solid.astype(np.int64, copy=False)
    lo = sarr.min(0); ex = sarr.max(0) - lo + 1
    d = tuple(int(CORE_ORIGIN + max(0, (core_vox - 2 * CORE_ORIGIN - ex[i]) // 2) - lo[i])
              for i in range(3))
    voxels = sarr + np.array(d, np.int64)
    smooth_fn = None
    if want_anchors and anchors:
        smooth_fn = VX.anchor_smooth_fn(anchors, delta=d)   # shifts key AND target by d
    return voxels, smooth_fn, labels


def obj_to_blueprint(obj_path, out_path, size='M', core_type='static', fill_fraction=0.9,
                     hollow=False, smooth=False, grid=None, name=None, material=None,
                     max_grid=256, min_thickness=2, rotate_to_z_up=True, crease_deg=35.0,
                     second_material=False):
    """Full pipeline: .obj file -> .blueprint file. smooth=True deflects surface vertices
    onto the mesh (sub-voxel, +-1.19 vox cap). second_material=True uses angle-based
    material tagging (sharp edges get a second material). Returns (voxel_count, lod_record_set)."""
    voxels, smooth_fn, labels = voxelize_obj(obj_path, size=size, fill_fraction=fill_fraction,
                                     hollow=hollow, grid=grid, want_anchors=smooth,
                                     max_grid=max_grid, min_thickness=min_thickness,
                                     rotate_to_z_up=rotate_to_z_up, crease_deg=crease_deg)
    if name is None:
        import os
        name = os.path.splitext(os.path.basename(obj_path))[0]
    mat_base = material or du_semantic.MAT_HCCARBON
    materials = [mat_base, du_semantic.MAT_HCCARBON_B] if second_material else None
    want = P.build_blueprint_sem(out_path, voxels, name, smooth_fn=smooth_fn if smooth else None,
                                 material=material, size=size, core_type=core_type,
                                 labels=labels if second_material else None, materials=materials)
    return len(voxels), want


_FACES = [
    ((-1, 0, 0), [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
    ((1, 0, 0),  [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
    ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
    ((0, 1, 0),  [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),
    ((0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),
    ((0, 0, 1),  [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
]


def preview_mesh(voxels, smooth_fn=None, deflect_cap=100 / 84.0):
    """Boundary-face surface mesh of a voxel set, with the smoothing deflection applied to
    shared corners -- a faithful preview of what DU renders (its surface passes through the
    deflected voxel-corner vertices). Returns (flat_verts[x,y,z,...], flat_tris[i,j,k,...]),
    corners deduped so normals blend smoothly."""
    if isinstance(voxels, set):
        V = voxels
    elif isinstance(voxels, np.ndarray):
        V = set(map(tuple, voxels.tolist()))    # rows aren't hashable -- tuple-ify first
    else:
        V = set(voxels)
    cidx = {}
    verts = []
    tris = []

    def ci(c):
        i = cidx.get(c)
        if i is None:
            i = len(verts) // 3
            cidx[c] = i
            px, py, pz = float(c[0]), float(c[1]), float(c[2])
            if smooth_fn is not None:
                t = smooth_fn(*c)
                px += max(-deflect_cap, min(deflect_cap, t[0] - c[0]))
                py += max(-deflect_cap, min(deflect_cap, t[1] - c[1]))
                pz += max(-deflect_cap, min(deflect_cap, t[2] - c[2]))
            verts.extend((px, py, pz))
        return i

    for (x, y, z) in V:
        for off, corners in _FACES:
            if (x + off[0], y + off[1], z + off[2]) not in V:
                a, b, c, d = (ci((x + cx, y + cy, z + cz)) for cx, cy, cz in corners)
                tris.extend((a, b, c, a, c, d))
    return verts, tris


def obj_to_blueprints(obj_path, out_base, mode='auto', size=None, core_type='static',
                      resolution=None, fill_fraction=0.9, hollow=False, smooth=False,
                      name=None, material=None, rotate_to_z_up=True, crease_deg=35.0,
                      second_material=False):
    """Unified entry: .obj -> one or many blueprints, by mode.

      mode='scale' : scale the mesh to fit the SPECIFIED `size` core (fill_fraction). One
                     construct -> writes <out_base>.blueprint.
      mode='auto'  : voxelize at `resolution` (default 0.9*M) and pick the SMALLEST core
                     that holds it. One construct.
      mode='tile'  : voxelize at `resolution` and split across an NxNxN grid of `size`
                     cores. Writes <out_base>_ix_iy_iz.blueprint per non-empty tile plus a
                     manifest listing each tile's integer core offset (place adjacent
                     in-game). Seam smoothing is per-core (constructs are independent).

    Returns a manifest dict.
    """
    import os
    import du_tiling as T
    import du_envelope as E
    if name is None:
        name = os.path.splitext(os.path.basename(obj_path))[0]

    if mode in ('scale',):
        if size is None:
            size = 'M'
        n, want = obj_to_blueprint(obj_path, out_base + '.blueprint', size=size,
                                   core_type=core_type, fill_fraction=fill_fraction,
                                   hollow=hollow, smooth=smooth, name=name, material=material,
                                   rotate_to_z_up=rotate_to_z_up, crease_deg=crease_deg,
                                   second_material=second_material)
        return dict(mode='scale', size=size, files=[out_base + '.blueprint'],
                    voxels=n, note=f'mesh scaled into {size} core')

    # auto / tile: voxelize once at the requested absolute resolution, in a neutral grid
    verts, faces = VX.load_mesh(obj_path)
    if rotate_to_z_up:
        verts = verts @ np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)
    grid = resolution or int(round(E.core_voxel_size('M') * fill_fraction))
    verts, _ = VX.fit_to_grid(verts, grid, margin=0)
    solid, anchors, labels = VX.voxelize(verts, faces, grid, hollow=hollow, want_anchors=smooth,
                                 crease_deg=crease_deg)
    # solid is a compact (N,3) int64 array (see voxelize_obj) -- shift with vectorized numpy,
    # not a per-voxel Python loop/set-rebuild (this path can carry the same near-grid^3
    # voxel counts as 'scale' mode, so the same blowup/slowdown applies here too).
    lo = solid.min(0)
    solid = solid - lo
    if smooth:
        anchors = {(k[0] - int(lo[0]), k[1] - int(lo[1]), k[2] - int(lo[2])): v
                   for k, v in anchors.items()}
    extent = int(solid.max()) + 1 if len(solid) else 1

    if mode == 'auto':
        s = T.smallest_core_for(extent)
        voxels, d = _place_in_core(solid, s)
        sm = VX.anchor_smooth_fn(anchors, delta=d) if smooth else None
        mat_base = material or du_semantic.MAT_HCCARBON
        materials = [mat_base, du_semantic.MAT_HCCARBON_B] if second_material else None
        want = P.build_blueprint_sem(out_base + '.blueprint', voxels, name,
                                     smooth_fn=sm, material=material, size=s, core_type=core_type,
                                     labels=labels if second_material else None, materials=materials)
        return dict(mode='auto', size=s, files=[out_base + '.blueprint'],
                    voxels=len(voxels), note=f'{extent}-vox mesh -> smallest fitting core {s}')

    if mode == 'tile':
        if size is None:
            raise ValueError("mode 'tile' needs an explicit core size")
        cv = E.core_voxel_size(size)
        tiles = T.tile_voxels(solid, cv)
        files = []; offsets = []
        for tijk, local in sorted(tiles.items()):
            voxels, d = _place_in_core(local, size, center=False)
            sm = None
            if smooth:
                base = tuple(tijk[i] * cv for i in range(3))
                # anchors for this tile, re-based to the tile's local frame, then placed
                tanch = {tuple(k[i] - base[i] for i in range(3)):
                         (tuple(v[0][i] - base[i] for i in range(3)), v[1])
                         for k, v in anchors.items()
                         if all(0 <= k[i] - base[i] < cv for i in range(3))}
                sm = VX.anchor_smooth_fn(tanch, delta=d)
            fn = f'{out_base}_{tijk[0]}_{tijk[1]}_{tijk[2]}.blueprint'
            mat_base = material or du_semantic.MAT_HCCARBON
            materials = [mat_base, du_semantic.MAT_HCCARBON_B] if second_material else None
            P.build_blueprint_sem(fn, voxels, f'{name} [{tijk[0]},{tijk[1]},{tijk[2]}]',
                                  smooth_fn=sm, material=material, size=size, core_type=core_type,
                                  labels=labels if second_material else None, materials=materials)
            files.append(fn); offsets.append(tijk)
        return dict(mode='tile', size=size, grid=T.plan(extent, 'tile', size)['grid'],
                    files=files, offsets=offsets,
                    note=f'{extent}-vox mesh -> {len(files)} {size} cores; place each at its '
                         f'core offset (x,y,z)*{cv} voxels')
    raise ValueError(f'unknown mode {mode!r}')


def _place_in_core(local, size, center=True):
    """Place a shape/tile's local voxels in the core build volume. Returns (voxels, delta).
    center=True centres the shape (single-construct default). center=False anchors the min
    corner at 0 so full tiles fit and adjacent core constructs abut seamlessly. `local` may
    be a compact (N,3) array (the 'auto' path's full solid) or a Python set (per-tile, already
    core-bounded) -- either way the placement math is vectorized numpy, not a per-voxel loop."""
    import du_envelope as E
    arr = local if isinstance(local, np.ndarray) else np.asarray(list(local), dtype=np.int64)
    core_vox = E.core_voxel_size(size)
    lo = arr.min(0); ex = arr.max(0) - lo + 1
    if center:
        import obj_pipeline as P
        _, chunk0, _ = P.core_octree_params(size)
        d = tuple(int(chunk0 + max(0, (core_vox - 2 * chunk0 - int(ex[i])) // 2) - lo[i])
                  for i in range(3))
    else:
        d = tuple(int(-lo[i]) for i in range(3))      # min corner -> 0; tiles abut
    return arr + np.array(d, np.int64), d


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Convert an .obj mesh to a DU blueprint.')
    ap.add_argument('obj')
    ap.add_argument('out')
    ap.add_argument('--size', default='M', choices=list(E.CORE_SIZES),
                    help='core size (default M)')
    ap.add_argument('--type', dest='core_type', default='static',
                    choices=list(E.CORE_KIND), help='core type (default static)')
    ap.add_argument('--fill-fraction', type=float, default=0.9,
                    help='fraction of the core the mesh fills (0<f<=1, default 0.9)')
    ap.add_argument('--grid', type=int, default=None, help='absolute voxel resolution override')
    ap.add_argument('--hollow', action='store_true', help='surface shell only (no solid fill)')
    ap.add_argument('--smooth', action='store_true', help='deflect vertices onto the mesh')
    ap.add_argument('--mode', choices=('scale', 'auto', 'tile'), default='scale',
                    help="scale: fit the --size core; auto: smallest fitting core; "
                         "tile: split across a grid of --size cores (default scale)")
    ap.add_argument('--resolution', type=int, default=None,
                    help='absolute voxel resolution for auto/tile (longest axis)')
    ap.add_argument('--name', default=None)
    args = ap.parse_args()
    if args.mode == 'scale':
        n, want = obj_to_blueprint(args.obj, args.out, size=args.size, core_type=args.core_type,
                                   fill_fraction=args.fill_fraction, grid=args.grid,
                                   hollow=args.hollow, smooth=args.smooth, name=args.name)
        print(f'{args.obj} -> {args.out}: {n} voxels, {len(want)} records, {args.size} '
              f'{args.core_type} core')
    else:
        out_base = args.out[:-10] if args.out.endswith('.blueprint') else args.out
        m = obj_to_blueprints(args.obj, out_base, mode=args.mode, size=args.size,
                              core_type=args.core_type, resolution=args.resolution,
                              fill_fraction=args.fill_fraction, hollow=args.hollow,
                              smooth=args.smooth, name=args.name)
        print(f'{args.obj} -> {m["note"]}')
        for f in m['files']:
            print(f'  {f}')
