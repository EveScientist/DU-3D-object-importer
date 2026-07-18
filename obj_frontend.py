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
import du_voxelize as VX
import obj_pipeline as P
import du_envelope as E

# Core build volume starts at voxel 8 (the (8,8,8) chunk-0 origin in construct-local coords).
CORE_ORIGIN = 8


def voxelize_obj(obj_path, size='M', fill_fraction=0.9, hollow=False, margin=None,
                 grid=None, want_anchors=False):
    """.obj -> (voxels, smooth_fn) in construct-local coords (min corner near CORE_ORIGIN).

    size           core size name (XS..XXXXXL); sets the voxel resolution unless `grid`.
    fill_fraction  fraction of the core edge the longest mesh axis fills (0<f<=1) --
                   the SCALING control the user picks.
    grid           override: absolute voxel resolution of the longest mesh axis.
    hollow         False = watertight solid (caves/holds preserved as modeled voids);
                   True = surface shell only.
    want_anchors   also return a smooth_fn projecting each surface vertex to the nearest
                   mesh point (the "forcibly smooth a jagged edge" deflection), else None.
    """
    core_vox = E.core_voxel_size(size)
    if grid is None:
        grid = max(1, int(round(core_vox * fill_fraction)))
    if grid > core_vox:
        raise ValueError(f"grid {grid} exceeds {size} core voxel size {core_vox}")
    verts, faces = VX.load_obj(obj_path)
    verts, _ = VX.fit_to_grid(verts, grid, margin=0)
    solid, anchors = VX.voxelize(verts, faces, grid, hollow=hollow,
                                 want_anchors=want_anchors)
    # translate so the shape's min corner sits at CORE_ORIGIN, centred in the core
    lo = [min(v[i] for v in solid) for i in range(3)]
    ex = [max(v[i] for v in solid) - lo[i] + 1 for i in range(3)]
    d = tuple(CORE_ORIGIN + max(0, (core_vox - 2 * CORE_ORIGIN - ex[i]) // 2) - lo[i]
              for i in range(3))
    voxels = {(x + d[0], y + d[1], z + d[2]) for (x, y, z) in solid}
    smooth_fn = None
    if want_anchors and anchors:
        smooth_fn = VX.anchor_smooth_fn(anchors, delta=d)   # shifts key AND target by d
    return voxels, smooth_fn


def obj_to_blueprint(obj_path, out_path, size='M', core_type='static', fill_fraction=0.9,
                     hollow=False, smooth=False, grid=None, name=None, material=None):
    """Full pipeline: .obj file -> .blueprint file. smooth=True deflects surface vertices
    onto the mesh (sub-voxel, +-1.19 vox cap). Returns (voxel_count, lod_record_set)."""
    voxels, smooth_fn = voxelize_obj(obj_path, size=size, fill_fraction=fill_fraction,
                                     hollow=hollow, grid=grid, want_anchors=smooth)
    if name is None:
        import os
        name = os.path.splitext(os.path.basename(obj_path))[0]
    want = P.build_blueprint_sem(out_path, voxels, name, smooth_fn=smooth_fn if smooth else None,
                                 material=material, size=size, core_type=core_type)
    return len(voxels), want


def obj_to_blueprints(obj_path, out_base, mode='auto', size=None, core_type='static',
                      resolution=None, fill_fraction=0.9, hollow=False, smooth=False,
                      name=None, material=None):
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
                                   hollow=hollow, smooth=smooth, name=name, material=material)
        return dict(mode='scale', size=size, files=[out_base + '.blueprint'],
                    voxels=n, note=f'mesh scaled into {size} core')

    # auto / tile: voxelize once at the requested absolute resolution, in a neutral grid
    verts, faces = VX.load_obj(obj_path)
    grid = resolution or int(round(E.core_voxel_size('M') * fill_fraction))
    verts, _ = VX.fit_to_grid(verts, grid, margin=0)
    solid, anchors = VX.voxelize(verts, faces, grid, hollow=hollow, want_anchors=smooth)
    lo = [min(v[i] for v in solid) for i in range(3)]
    solid = {(x - lo[0], y - lo[1], z - lo[2]) for (x, y, z) in solid}
    if smooth:
        anchors = {(k[0] - lo[0], k[1] - lo[1], k[2] - lo[2]): v for k, v in anchors.items()}
    extent = max(max(v[i] for v in solid) for i in range(3)) + 1

    if mode == 'auto':
        s = T.smallest_core_for(extent)
        voxels, d = _place_in_core(solid, s)
        sm = VX.anchor_smooth_fn(anchors, delta=d) if smooth else None
        want = P.build_blueprint_sem(out_base + '.blueprint', voxels, name,
                                     smooth_fn=sm, material=material, size=s, core_type=core_type)
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
            P.build_blueprint_sem(fn, voxels, f'{name} [{tijk[0]},{tijk[1]},{tijk[2]}]',
                                  smooth_fn=sm, material=material, size=size, core_type=core_type)
            files.append(fn); offsets.append(tijk)
        return dict(mode='tile', size=size, grid=T.plan(extent, 'tile', size)['grid'],
                    files=files, offsets=offsets,
                    note=f'{extent}-vox mesh -> {len(files)} {size} cores; place each at its '
                         f'core offset (x,y,z)*{cv} voxels')
    raise ValueError(f'unknown mode {mode!r}')


def _place_in_core(local, size, center=True):
    """Place a shape/tile's local voxels in the core build volume. Returns (voxels, delta).
    center=True centres the shape (single-construct default). center=False anchors the min
    corner at 0 so full tiles fit and adjacent core constructs abut seamlessly."""
    import du_envelope as E
    core_vox = E.core_voxel_size(size)
    ex = [max(v[i] for v in local) - min(v[i] for v in local) + 1 for i in range(3)]
    lo = [min(v[i] for v in local) for i in range(3)]
    if center:
        import obj_pipeline as P
        _, chunk0, _ = P.core_octree_params(size)
        d = tuple(chunk0 + max(0, (core_vox - 2 * chunk0 - ex[i]) // 2) - lo[i] for i in range(3))
    else:
        d = tuple(-lo[i] for i in range(3))          # min corner -> 0; tiles abut
    return {(x + d[0], y + d[1], z + d[2]) for (x, y, z) in local}, d


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
