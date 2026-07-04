"""Second MESH-DRIVEN import test: tests/mesh_span_wave_0704_1439.blueprint.

The cosine half-pipe valley again, but SPANNING a chunk-grid boundary --
first hardware test of the mesh -> gen_terrain multi-chunk path:

    z(x) = 0.75 + 0.25*cos(pi*x/2)  over a 4x2 patch at gx=30, gy=10
    (cells 30,31 in chunk (8,8,8); cells 32,33 in chunk (9,8,8))

Corner offsets per y-line: 0/-21/-42/-21/0; the -42 dip line sits EXACTLY ON
the chunk boundary (global x=32), so the two chunks must share the ghost-line
offsets for the surface to be seamless. Blocky H = flat h1 4x2 == donor 2669
(flat gen_terrain(30,10,4,2)); envelope + mcs {(8,8,8):756, (9,8,8):587}
reused (mc displacement-invariant).

EXPECTED IN-GAME (8 vox, at the 2669 build position): a 4x2 plate whose top
curves smoothly down half a voxel at the chunk boundary and back up -- one
continuous valley with NO crack or step at the boundary.
"""
import sys
import math

sys.path.insert(0, "/home/du")
import du_mesh as M
import du_assemble as A

TEMPLATE = '/home/du/exports/archive/2669_export.blueprint'
OUT = '/home/du/tests/mesh_span_wave_0704_1439.blueprint'
MCS = {(8, 8, 8): 756, (9, 8, 8): 587}

geom = M.plane_mesh(4, 2, lambda x, y: 0.75 + 0.25 * math.cos(math.pi * x / 2))
scans = M.gen_terrain_from_mesh(geom, 4, 2, gx=30, gy=10)
assert set(scans) == set(MCS), sorted(scans)

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
