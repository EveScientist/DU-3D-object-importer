"""First LARGE bumpy landscape: tests/grid_tilt_0705_1805.blueprint.

A 100x100-voxel (4x4-chunk) displaced plate straddling three chunk-grid
boundaries per axis -- the first exercise of per-corner displacement through
the GRID-INTERIOR generators (gen_middle_x / gen_double_middle / gen_ymid_* /
gen_corner_middle), whose verts= paths were validated only at tiny sizes.

Displacement = an ASYMMETRIC diagonal tilt (grid analog of the corner-tilt
probes that all deployed cleanly), chosen so every corner gets a distinct dz
and any chunk's mis-ordered verts shows as a local slope break:

    dz84[x][y] = -round(0.4*x + 0.8*y),  x,y in 0..100
    (0 at (0,0); -120 = -1.43 vox at (100,100))

Blocky base = flat h1 == donor 3105 (4x4 grid); mc per-chunk from
_mc_from_scan (displacement-invariant). Continuity across all 16 chunks is
automatic (shared corner lines sampled once from the global grid).

EXPECTED IN-GAME (10000 vox at the 3105 position X,Y in [20.5,119.5], Z=10.5):
ONE continuous tilted plane over the whole 100x100 plate -- gentle downslope
toward +x, steeper toward +y, deepest at the (+x,+y) corner. NO crack, step,
or scrambled patch at ANY of the 6 internal chunk boundaries. Any localized
defect names the offending grid-interior generator's vert ordering.
"""
import sys

sys.path.insert(0, "/home/du")
import du_solid as D
import du_assemble as A

TEMPLATE = D  # placeholder; resolved below
OUT = '/home/du/tests/grid_tilt_0705_1805.blueprint'

import os
TPL = None
for p in ('/home/du/exports/3105_export.blueprint',
          '/home/du/exports/archive/3105_export.blueprint'):
    if os.path.exists(p):
        TPL = p
        break
assert TPL, "3105 donor not found"

N = 100
corner_z = [[-round(0.4 * i + 0.8 * j) for j in range(N + 1)] for i in range(N + 1)]
scans = D.gen_terrain_grid(corner_z, 20, 20)
assert len(scans) == 16, len(scans)

# flat sanity: at least one chunk must actually carry displacement
flat = D.gen_terrain_flat_grid(20, 20, N, N)
assert any(scans[k] != flat[k] for k in scans), "no displacement emitted"

mc_for = {k: D._mc_from_scan(v) for k, v in scans.items()}
n = A.rebuild_h3(TPL, OUT,
                 lambda cx, cy, cz: (scans[(cx, cy, cz)], mc_for[(cx, cy, cz)])
                 if (cx, cy, cz) in scans else None)
assert n == 16, n
print("wrote", OUT, f"({n} chunks)")

# round-trip: decode + verify scans + hashes
import json, base64, struct, lz4.block
import du_hash
d = json.load(open(OUT))
for e in d['VoxelData']:
    if e['h'] != 3:
        continue
    key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
    b = e['records']['voxel']['data']['$binary']
    b = b['base64'] if isinstance(b, dict) else b
    raw = base64.b64decode(b)
    v = lz4.block.decompress(raw[12:], uncompressed_size=struct.unpack('<I', raw[4:8])[0])
    i = v.find(b'Debug1')
    assert v[64:i - 13] == scans[key], (key, "scan mismatch")
    assert du_hash.to_signed64(du_hash.compute_hash(raw)) == \
        e['records']['voxel']['hash']['$numberLong'], (key, "hash")
print("round-trip OK (16/16)")
