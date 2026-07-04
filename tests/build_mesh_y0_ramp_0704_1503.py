"""Increment-4 import test: tests/mesh_y0_ramp_0704_1503.blueprint.

Linear ramp across the y=0 OCTANT SEAM (asymmetric probe first, per the x0
lesson -- every corner line gets a distinct offset so the render uniquely
verifies the y0 cluster/group -> line mapping):

    z(y) = 1 - (y + 2)/4,  y global in [-2, 2], uniform in x
    intended line offsets: y=-2: 0, -1: -21, 0: -42, +1: -63, +2: -84

Blocky H = h1, 2 rows/side x 2 cols == donor 3038 (uniform y0 pair);
mcs {(8,8,8):719, (8,7,8):658} (mc displacement-invariant).

EXPECTED IN-GAME (8 vox at the 3038 position, X 10.5/11.5): a smooth wedge
sloping DOWN toward +y -- full height at y=-2 falling to a full voxel deep
at y=+2, continuous through y=0 with no crack. Any other per-line depth
order = mapping read-out (report which depth sits at which y face line).
"""
import sys

sys.path.insert(0, "/home/du")
import du_mesh as M
import du_assemble as A

TEMPLATE = None
for p in ('/home/du/exports/3038_export.blueprint',
          '/home/du/exports/archive/3038_export.blueprint'):
    import os
    if os.path.exists(p):
        TEMPLATE = p
        break
assert TEMPLATE, "3038 export not found"
OUT = '/home/du/tests/mesh_y0_ramp_0704_1503.blueprint'
MCS = {(8, 8, 8): 719, (8, 7, 8): 658}

geom = M.plane_mesh(2, 4, lambda x, y: 1.0 - y / 4.0)   # mesh y 0..4 == global -2..2
scans = M.gen_y0_from_mesh(geom, n_low=2, n_high=2, nx=2, xoff=-10.0, yoff=2.0)
assert set(scans) == set(MCS)

n = A.rebuild_h3(TEMPLATE, OUT,
                 lambda cx, cy, cz: (scans[(cx, cy, cz)], MCS[(cx, cy, cz)])
                 if (cx, cy, cz) in scans else None)
assert n == 2, n
print("wrote", OUT)

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
print("round-trip OK")
