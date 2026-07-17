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
from obj_to_du_voxels import load_obj, fit_to_grid, voxelize as _default_voxelize
import obj_pipeline as P
import du_envelope as E

# Core build volume starts at voxel 8 (the (8,8,8) chunk-0 origin in construct-local coords).
CORE_ORIGIN = 8


def voxelize_obj(obj_path, size='M', fill_fraction=0.9, fill='z', margin=None,
                 grid=None, voxelize_fn=None):
    """.obj -> solid voxel set in construct-local coords (min corner at CORE_ORIGIN).

    size           core size name (XS..XXXXXL); sets the voxel resolution unless `grid`.
    fill_fraction  fraction of the core edge the longest mesh axis fills (0<f<=1) --
                   this is the SCALING control the user picks.
    grid           override: absolute voxel resolution of the longest mesh axis.
    fill           'z' (span per column), 'parity' (even-odd, hollows), 'none' (surface).
    voxelize_fn    optional custom voxelizer(verts, faces, grid)->set of (x,y,z).
    """
    core_vox = E.core_voxel_size(size)
    if grid is None:
        grid = max(1, int(round(core_vox * fill_fraction)))
    if grid > core_vox:
        raise ValueError(f"grid {grid} exceeds {size} core voxel size {core_vox}")
    if margin is None:
        margin = max(1, (core_vox - grid) // 2)   # centre the shape in the core
    verts, faces = load_obj(obj_path)
    # fit into a `grid`-sized cube (the mesh's own bounding box maps to [margin, grid-margin])
    verts, _ = fit_to_grid(verts, grid, margin=0)
    vox = (voxelize_fn or _default_voxelize)(verts, faces, grid)
    if not vox:
        raise ValueError('voxelization produced no voxels (empty/degenerate mesh)')
    if fill == 'z':
        solid = P.solid_fill_z(vox)
    elif fill == 'parity':
        solid = P.solid_fill_parity(vox)
    elif fill == 'none':
        solid = vox
    else:
        raise ValueError(f'unknown fill mode {fill!r}')
    # translate so the shape's min corner sits at CORE_ORIGIN, centred within the core
    lo = [min(v[i] for v in solid) for i in range(3)]
    ex = [max(v[i] for v in solid) - lo[i] + 1 for i in range(3)]
    d = tuple(CORE_ORIGIN + max(0, (core_vox - 2 * CORE_ORIGIN - ex[i]) // 2) - lo[i]
              for i in range(3))
    return {(x + d[0], y + d[1], z + d[2]) for (x, y, z) in solid}


def obj_to_blueprint(obj_path, out_path, size='M', core_type='static', fill_fraction=0.9,
                     fill='z', grid=None, name=None, material=None, smooth_fn=None,
                     voxelize_fn=None):
    """Full pipeline: .obj file -> .blueprint file for a chosen core size.
    Returns (voxel_count, lod_record_set)."""
    voxels = voxelize_obj(obj_path, size=size, fill_fraction=fill_fraction, fill=fill,
                          grid=grid, voxelize_fn=voxelize_fn)
    if name is None:
        import os
        name = os.path.splitext(os.path.basename(obj_path))[0]
    want = P.build_blueprint_sem(out_path, voxels, name, smooth_fn=smooth_fn,
                                 material=material, size=size, core_type=core_type)
    return len(voxels), want


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
    ap.add_argument('--fill', choices=('z', 'parity', 'none'), default='z')
    ap.add_argument('--name', default=None)
    args = ap.parse_args()
    n, want = obj_to_blueprint(args.obj, args.out, size=args.size, core_type=args.core_type,
                               fill_fraction=args.fill_fraction, grid=args.grid,
                               fill=args.fill, name=args.name)
    print(f'{args.obj} -> {args.out}: {n} voxels, {len(want)} records, {args.size} '
          f'{args.core_type} core')
