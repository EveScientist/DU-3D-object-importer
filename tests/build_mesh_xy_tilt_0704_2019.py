"""Multi-region composition probe: tests/mesh_xy_tilt_0704_2019.blueprint.

Displaced x=0+y=0 SURFACE CORNER -- one smooth tilted plane over the 3079
footprint (4x4 cells straddling BOTH center planes, h1), all 25 corner-line
offsets distinct:

    z(x, y) = 1 - (2*(x+2) + 10*(y+2))/84,  x,y global in [-2, 2]
    dz84(x, y) = -(2*(x+2) + 10*(y+2)):  0 at (-2,-2) .. -48 at (+2,+2)

Chunks via gen_xy_from_mesh: gen_corner_hh(verts) / displaced plates with
the y0-splice and x0-head recipes. Donor 3079; mcs {(8,8,8):681,
(8,7,8):620, (7,8,8):594, (7,7,8):533} (mc displacement-invariant).

EXPECTED IN-GAME (16 vox at the 3079 position, Z=10.5 layer): ONE continuous
tilted plane over the whole 4x4 plate -- sloping down gently toward +x
(2/84 per voxel) and strongly toward +y (10/84 per voxel), deepest corner
(-48, about -0.57 vox) at (+2,+2). NO crack or step at x=0, y=0, or the
corner point. Any discontinuity localizes which chunk's mapping is off.
"""
import sys

sys.path.insert(0, "/home/du")
import du_mesh as M
import du_assemble as A

TEMPLATE = M._find_export(3079)
OUT = '/home/du/tests/mesh_xy_tilt_0704_2019.blueprint'
MCS = {(8, 8, 8): 681, (8, 7, 8): 620, (7, 8, 8): 594, (7, 7, 8): 533}

geom = M.plane_mesh(4, 4, lambda x, y: 1.0 - (2 * x + 10 * y) / 84.0)
scans = M.gen_xy_from_mesh(geom, 2, 2, xoff=2.0, yoff=2.0)
assert set(scans) == set(MCS)
blocky = M.D.gen_corner_xy(2, 2)
assert all(scans[k] != blocky[k] for k in scans), "no displacement?"

n = A.rebuild_h3(TEMPLATE, OUT,
                 lambda cx, cy, cz: (scans[(cx, cy, cz)], MCS[(cx, cy, cz)])
                 if (cx, cy, cz) in scans else None)
assert n == 4, n
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
