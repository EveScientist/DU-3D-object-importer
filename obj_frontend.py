"""obj_frontend.py -- .obj mesh -> DU blueprint, on the SEMANTIC pipeline (2026-07-18).

The full front-to-back path: load a triangle mesh, voxelize its surface, fill to a solid,
place it at the core origin, and emit a blueprint via obj_pipeline.build_blueprint_sem
(du_semantic core -- no empirical grammar). This is what the web UI at
objtodu.evescientist.net calls.

    from obj_frontend import obj_to_blueprint
    obj_to_blueprint('ship.obj', 'ship.blueprint', grid=48, name='Ship')
"""
import numpy as np

from obj_to_du_voxels import load_obj, fit_to_grid, voxelize
import obj_pipeline as P

# Default template = a real game export whose Model skeleton + one VoxelData prototype we
# clone (only the voxel bodies are replaced). Any h3-bearing export works; 3187 is an M core.
DEFAULT_TEMPLATE = '/home/du/exports/archive/3187_export.blueprint'

# Core build volume starts at voxel 8 (the (8,8,8) chunk-0 origin in construct-local coords).
CORE_ORIGIN = 8


def voxelize_obj(obj_path, grid=48, margin=2, fill='z'):
    """.obj -> solid voxel set in construct-local coords (min corner at CORE_ORIGIN).
    fill: 'z' (span per column, z-convex shapes) or 'parity' (even-odd, handles hollows)
    or 'none' (surface only). grid = voxel resolution of the longest mesh axis."""
    verts, faces = load_obj(obj_path)
    verts, _ = fit_to_grid(verts, grid, margin)
    surf = voxelize(verts, faces, grid)
    if not surf:
        raise ValueError('voxelization produced no voxels (empty/degenerate mesh)')
    if fill == 'z':
        solid = P.solid_fill_z(surf)
    elif fill == 'parity':
        solid = P.solid_fill_parity(surf)
    elif fill == 'none':
        solid = surf
    else:
        raise ValueError(f'unknown fill mode {fill!r}')
    # translate so the shape's min corner sits at the core origin (all axes)
    lo = [min(v[i] for v in solid) for i in range(3)]
    d = tuple(CORE_ORIGIN - lo[i] for i in range(3))
    return {(x + d[0], y + d[1], z + d[2]) for (x, y, z) in solid}


def obj_to_blueprint(obj_path, out_path, grid=48, margin=2, fill='z', name=None,
                     template=DEFAULT_TEMPLATE, material=None, smooth_fn=None):
    """Full pipeline: .obj file -> .blueprint file. Returns (voxel_count, lod_record_set)."""
    voxels = voxelize_obj(obj_path, grid=grid, margin=margin, fill=fill)
    if name is None:
        import os
        name = os.path.splitext(os.path.basename(obj_path))[0]
    want = P.build_blueprint_sem(template, out_path, voxels, name,
                                 smooth_fn=smooth_fn, material=material)
    return len(voxels), want


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Convert an .obj mesh to a DU blueprint.')
    ap.add_argument('obj')
    ap.add_argument('out')
    ap.add_argument('--grid', type=int, default=48, help='voxel resolution (default 48)')
    ap.add_argument('--margin', type=int, default=2)
    ap.add_argument('--fill', choices=('z', 'parity', 'none'), default='z')
    ap.add_argument('--name', default=None)
    ap.add_argument('--material', default=None, help='material short name (default hcCarbon)')
    args = ap.parse_args()
    mat = None
    if args.material:
        # look the short name up against the known palette (extend as needed)
        import du_semantic
        if args.material.strip() == du_semantic.MAT_HCCARBON[1]:
            mat = du_semantic.MAT_HCCARBON
    n, want = obj_to_blueprint(args.obj, args.out, grid=args.grid, margin=args.margin,
                               fill=args.fill, name=args.name, material=mat)
    print(f'{args.obj} -> {args.out}: {n} voxels, {len(want)} records')
