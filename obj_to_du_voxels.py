#!/usr/bin/env python3
"""
obj_to_du_voxels.py
Convert a triangulated OBJ mesh to Dual Universe voxel coordinates.
Outputs a CSV list and a Lua script for in-game voxel placement via construct.setVoxel().

Usage:
    python obj_to_du_voxels.py ship.obj
    python obj_to_du_voxels.py ship.obj --grid 64 --material 7 --out my_ship
"""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# OBJ loader
# ---------------------------------------------------------------------------

def load_obj(path):
    """Return (vertices Nx3 float64, faces Mx3 int32). Handles v/vt/vn notation."""
    verts, faces = [], []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            if parts[0] == 'v':
                verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif parts[0] == 'f':
                indices = [int(p.split('/')[0]) - 1 for p in parts[1:]]
                # Fan-triangulate polys
                for i in range(1, len(indices) - 1):
                    faces.append([indices[0], indices[i], indices[i + 1]])
    if not verts:
        raise ValueError(f"No vertices found in {path}")
    if not faces:
        raise ValueError(f"No faces found in {path}")
    return np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int32)


# ---------------------------------------------------------------------------
# Fit mesh into voxel grid
# ---------------------------------------------------------------------------

def fit_to_grid(verts, grid_size, margin):
    """
    Uniformly scale and centre vertices so the mesh occupies
    [margin, grid_size-margin]^3 in voxel space.
    Returns (transformed_verts, scale_factor).
    """
    lo = verts.min(axis=0)
    hi = verts.max(axis=0)
    extent = (hi - lo).max()
    if extent == 0:
        raise ValueError("Mesh has zero extent — cannot voxelize")
    target = grid_size - 2 * margin
    scale = target / extent
    # Centre each axis independently within the target range
    offset = margin - lo * scale + (target - (hi - lo) * scale) / 2.0
    return verts * scale + offset, scale


# ---------------------------------------------------------------------------
# Triangle–AABB intersection  (Möller Separating Axis Test)
# ---------------------------------------------------------------------------

def _sat_test(tri_pts, axis, half_size):
    """Return False (separating axis found) if triangle and AABB don't overlap on axis."""
    p = tri_pts @ axis
    r = half_size * (abs(axis[0]) + abs(axis[1]) + abs(axis[2]))
    return not (p.min() > r or p.max() < -r)


def triangle_aabb_intersect(v0, v1, v2, cx, cy, cz, hs=0.5):
    """
    True if the triangle (v0,v1,v2) intersects the unit voxel centred at (cx,cy,cz).
    Implements the full 13-axis Möller SAT.
    """
    # Shift triangle so the AABB is at the origin
    t = np.array([
        [v0[0] - cx, v0[1] - cy, v0[2] - cz],
        [v1[0] - cx, v1[1] - cy, v1[2] - cz],
        [v2[0] - cx, v2[1] - cy, v2[2] - cz],
    ])

    e0 = t[1] - t[0]
    e1 = t[2] - t[1]
    e2 = t[0] - t[2]

    EX = np.array([1.0, 0.0, 0.0])
    EY = np.array([0.0, 1.0, 0.0])
    EZ = np.array([0.0, 0.0, 1.0])

    # 9 cross-product axes: each triangle edge × each AABB axis
    for edge in (e0, e1, e2):
        for ax in (EX, EY, EZ):
            a = np.cross(edge, ax)
            if np.dot(a, a) < 1e-10:
                continue
            if not _sat_test(t, a, hs):
                return False

    # 3 AABB face normals (x, y, z)
    for i in range(3):
        col = t[:, i]
        if col.min() > hs or col.max() < -hs:
            return False

    # 1 triangle face normal
    n = np.cross(e0, e1)
    if np.dot(n, n) > 1e-10:
        d = float(np.dot(n, t[0]))
        r = hs * (abs(n[0]) + abs(n[1]) + abs(n[2]))
        if d > r or d < -r:
            return False

    return True


# ---------------------------------------------------------------------------
# Surface voxelization
# ---------------------------------------------------------------------------

def voxelize(verts, faces, grid_size):
    """
    Walk every triangle, find candidate voxels from its AABB, then run the
    SAT intersection test. Returns a set of (ix, iy, iz) integer indices.
    """
    voxel_set = set()
    n = len(faces)

    for fi, face in enumerate(faces):
        if fi % 500 == 0:
            pct = 100 * fi // n
            print(f"\r  [{pct:3d}%] {fi}/{n} triangles", end='', flush=True, file=sys.stderr)

        v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
        tri = np.array([v0, v1, v2])

        # Conservative candidate range from triangle AABB
        lo = np.floor(tri.min(axis=0)).astype(int)
        hi = np.floor(tri.max(axis=0)).astype(int) + 1
        lo = np.clip(lo, 0, grid_size - 1)
        hi = np.clip(hi, 0, grid_size - 1)

        for ix in range(lo[0], hi[0] + 1):
            for iy in range(lo[1], hi[1] + 1):
                for iz in range(lo[2], hi[2] + 1):
                    # Voxel (ix,iy,iz) occupies [ix, ix+1] — centre is at ix+0.5
                    if triangle_aabb_intersect(v0, v1, v2, ix + 0.5, iy + 0.5, iz + 0.5):
                        voxel_set.add((ix, iy, iz))

    print(f"\r  [100%] {n}/{n} triangles — {len(voxel_set)} surface voxels", file=sys.stderr)
    return voxel_set


# ---------------------------------------------------------------------------
# Output: CSV
# ---------------------------------------------------------------------------

def write_csv(voxels, out_path, material_id):
    with open(out_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['x', 'y', 'z', 'material'])
        for x, y, z in sorted(voxels):
            w.writerow([x, y, z, material_id])
    print(f"CSV written: {out_path}  ({len(voxels)} voxels)")


# ---------------------------------------------------------------------------
# Output: Lua in-game placement script
# ---------------------------------------------------------------------------

LUA_TEMPLATE = """\
-- Auto-generated by obj_to_du_voxels.py
-- {count} voxels | material ID {mat} | grid {grid}^3
--
-- Paste into a Programming Board linked to the construct.
-- The script places voxels in batches across ticks to stay within CPU limits.

local VOXELS = {{
{entries}
}}

local MATERIAL = {mat}
local BATCH    = 50
local idx      = 1

function onUpdate()
    local last = math.min(idx + BATCH - 1, #VOXELS)
    for i = idx, last do
        local v = VOXELS[i]
        construct.setVoxel({{x = v[1], y = v[2], z = v[3]}}, MATERIAL)
    end
    idx = last + 1
    if idx > #VOXELS then
        system.print(string.format("Done — %d voxels placed.", #VOXELS))
        unit.deactivate()
    end
end
"""

def write_lua(voxels, out_path, material_id, grid_size):
    sorted_voxels = sorted(voxels)
    if len(sorted_voxels) > 50_000:
        print(f"WARNING: {len(sorted_voxels)} voxels — Lua file may exceed DU script size limits.")
        print("         Consider reducing --grid or splitting the model.")

    entries = '\n'.join(f"  {{{x},{y},{z}}}," for x, y, z in sorted_voxels)
    lua = LUA_TEMPLATE.format(
        count=len(sorted_voxels),
        mat=material_id,
        grid=grid_size,
        entries=entries,
    )
    out_path.write_text(lua, encoding='utf-8')
    print(f"Lua written: {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Convert a triangulated OBJ to DU voxel CSV + Lua placement script.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("obj", help="Input .obj file (triangulated)")
    ap.add_argument("--grid",     type=int, default=128, help="Voxel grid size (≤256)")
    ap.add_argument("--margin",   type=int, default=2,   help="Empty-voxel border width")
    ap.add_argument("--material", type=int, default=1,   help="DU material ID to place")
    ap.add_argument("--out",      default=None,          help="Output filename prefix")
    args = ap.parse_args()

    if args.grid > 256:
        ap.error("--grid cannot exceed 256 (DU construct limit)")

    obj_path = Path(args.obj)
    if not obj_path.exists():
        ap.error(f"File not found: {obj_path}")

    prefix = Path(args.out) if args.out else obj_path.with_suffix('')

    print(f"Loading {obj_path} ...")
    verts, faces = load_obj(obj_path)
    print(f"  {len(verts):,} vertices | {len(faces):,} triangles")

    print(f"Fitting to {args.grid}³ grid (margin={args.margin}) ...")
    verts, scale = fit_to_grid(verts, args.grid, args.margin)
    lo, hi = verts.min(axis=0), verts.max(axis=0)
    print(f"  Scale: {scale:.4f}  Bounds: ({lo[0]:.1f},{lo[1]:.1f},{lo[2]:.1f}) – ({hi[0]:.1f},{hi[1]:.1f},{hi[2]:.1f})")

    print("Voxelizing (surface only) ...")
    voxels = voxelize(verts, faces, args.grid)

    write_csv(voxels, prefix.with_suffix('.csv'), args.material)
    write_lua(voxels, prefix.with_suffix('.lua'), args.material, args.grid)


if __name__ == '__main__':
    main()
