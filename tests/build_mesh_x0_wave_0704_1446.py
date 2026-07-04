"""Third MESH-DRIVEN import test: tests/mesh_x0_wave_0704_1446.blueprint.

The cosine half-pipe valley across the x=0 OCTANT SEAM (increment 3:
center-plane crossings through the varying seam generators + the per-group
displacement overlay):

    z(x) = 0.75 + 0.25*cos(pi*x/2),  x global in [-2, 2]

Corner-line offsets 0/-21/-42/-21/0 with the -42 dip line exactly ON x=0 --
the two octant chunks (8,8,8)/(7,8,8) encode the shared seam lines
independently (ghost overlap) and must agree for a seamless curve.
Blocky H = h1 2 cols/side == donor 3032 (uniform x0 seam pair);
envelope + mcs {(8,8,8):587, (7,8,8):756} reused (mc displacement-invariant).

EXPECTED IN-GAME (8 vox at the 3032 position, Y rows 10.5/11.5): a 4x2 plate
straddling x=0 whose top dips smoothly half a voxel AT the octant boundary --
one continuous valley, no crack/step at x=0.
"""
import sys
import math

sys.path.insert(0, "/home/du")
import du_mesh as M
import du_assemble as A

TEMPLATE = '/home/du/exports/archive/3032_export.blueprint'
OUT = '/home/du/tests/mesh_x0_wave_0704_1446.blueprint'
MCS = {(8, 8, 8): 587, (7, 8, 8): 756}

geom = M.plane_mesh(4, 2, lambda x, y: 0.75 + 0.25 * math.cos(math.pi * (x - 2) / 2))
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
