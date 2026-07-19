"""du_tiling.py -- core-size selection + multi-core tiling for the .obj pipeline.

Three output modes (user-chosen), all on top of the deploy-proven single-core
build_blueprint_sem:

  'scale' : scale the mesh to a SPECIFIED core size (fill_fraction). One construct.
  'auto'  : pick the SMALLEST core that holds the mesh at the requested voxel resolution.
            One construct.
  'tile'  : keep the resolution and split the voxel set across an NxNxN grid of same-size
            core constructs (one blueprint each), positioned to abut. Large builds.

A blueprint is exactly one core/construct, so 'tile' emits several files plus a manifest of
their integer grid offsets (in cores) so they can be placed adjacent in-game.
"""
from du_envelope import CORE_SIZES

SIZE_ORDER = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL', 'XXXXL', 'XXXXXL']


def smallest_core_for(extent_vox):
    """Smallest core name whose per-axis voxel size >= the largest mesh extent (voxels)."""
    for name in SIZE_ORDER:
        if CORE_SIZES[name][1] >= extent_vox:
            return name
    return SIZE_ORDER[-1]


def tile_voxels(voxels, core_vox):
    """Split a GLOBAL voxel set into per-core tiles. Returns {tile_ijk: local_voxel_set}
    where local coords are within [0, core_vox). Tiling is by floor-division on each axis.
    `voxels` may be a compact (N,3) array or a Python set/iterable of triples -- the
    min/floordiv/modulo are vectorized numpy either way; only the final per-tile grouping
    (inherently a dict of sets) is a Python-level pass."""
    import numpy as np
    arr = voxels if isinstance(voxels, np.ndarray) else np.asarray(list(voxels), dtype=np.int64)
    g = arr - arr.min(0)
    t = g // core_vox
    local = g % core_vox
    tiles = {}
    for k, loc in zip(map(tuple, t.tolist()), local.tolist()):
        tiles.setdefault(k, set()).add(tuple(loc))
    return tiles


def plan(extent_vox, mode='auto', size=None):
    """Decide (per-core size, tiling grid). Returns dict(mode, size, note).
      scale: size REQUIRED; mesh will be scaled to fit it (caller uses fill_fraction).
      auto : size = smallest core that fits extent_vox; grid 1x1x1.
      tile : size REQUIRED; grid = ceil(extent/core_vox) per axis.
    """
    if mode == 'scale':
        if size is None:
            raise ValueError("mode 'scale' needs an explicit core size")
        return dict(mode='scale', size=size.upper(),
                    note=f'mesh scaled to fit {size.upper()} core')
    if mode == 'auto':
        s = smallest_core_for(extent_vox)
        return dict(mode='auto', size=s,
                    note=f'{extent_vox}-vox mesh -> smallest fitting core {s} '
                         f'({CORE_SIZES[s][1]} vox)')
    if mode == 'tile':
        if size is None:
            raise ValueError("mode 'tile' needs an explicit core size")
        cv = CORE_SIZES[size.upper()][1]
        n = -(-extent_vox // cv)                      # ceil
        return dict(mode='tile', size=size.upper(), grid=n, core_vox=cv,
                    note=f'{extent_vox}-vox mesh -> {n}x{n}x{n} grid of {size.upper()} cores')
    raise ValueError(f'unknown mode {mode!r}')
