"""CORRECTED x0 valley: tests/mesh_x0_valley_fixed_0704_1500.blueprint.

The first x0 wave build (0704_1446) had a PHASE BUG in its test mesh:
0.75 + 0.25*cos(pi*(x-2)/2) PEAKS at the seam (a hill) -- DU rendered the
buggy mesh faithfully; the solver/mapping were correct all along, as proven
by the ramp diagnostic (rendered 0/-21/-42/-63/-84 exactly, smooth wedge
through the octant seam, no crack).

This build is the intended valley (note the MINUS):

    z(x) = 0.75 - 0.25*cos(pi*x/2),  x global in [-2, 2]
    line offsets: x=-2: 0, -1: -21, 0: -42, +1: -21, +2: 0

Donor 3032; mcs {(8,8,8):587, (7,8,8):756}.
EXPECTED IN-GAME: the 4x2 plate with a smooth half-voxel dip AT x=0,
rising to full height at both outer edges -- a valley this time.
"""
import sys
import math

sys.path.insert(0, "/home/du")
import du_mesh as M
import du_assemble as A

TEMPLATE = '/home/du/exports/archive/3032_export.blueprint'
OUT = '/home/du/tests/mesh_x0_valley_fixed_0704_1500.blueprint'
MCS = {(8, 8, 8): 587, (7, 8, 8): 756}

geom = M.plane_mesh(4, 2, lambda x, y: 0.75 - 0.25 * math.cos(math.pi * (x - 2) / 2))
scans = M.gen_x0_from_mesh(geom, n_low=2, n_high=2, ny=2, xoff=2.0)
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
