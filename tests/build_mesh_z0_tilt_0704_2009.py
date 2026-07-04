"""z=0 displaced-crossing probe: tests/mesh_z0_tilt_0704_2009.blueprint.

Build AW (3095 vs 2986) pinned the z-seam displacement CARRIERS (same
grammar as x0/y0; LOW mirrors HIGH's surface offsets). This build probes
the remaining unknown -- the group -> corner-line MAPPING -- with a mesh
whose 9 corner offsets are all DISTINCT (asymmetric in both axes):

    z(x, y) = 1 - (x + 3y)/14  over the 2986 footprint (2x2 cells, floor -1)
    corner dz84 (x-major, y inner):
        (0,0):0  (0,1):-18  (0,2):-36
        (1,0):-6 (1,1):-24  (1,2):-42
        (2,0):-12 (2,1):-30 (2,2):-48

Donor 2986; mcs {(8,8,8):635, (8,8,7):603}.

EXPECTED IN-GAME (8 vox at the 2986 position, X/Y 10.5-11.5 straddling z=0):
a flat TILTED top plane sloping down toward +x (gently, 6/84 per voxel) and
toward +y (strongly, 18/84 per voxel); deepest corner (-48) at (+x,+y).
Any other orientation = mapping read-out (report which corner is deepest
and the slope directions).
"""
import sys

sys.path.insert(0, "/home/du")
import du_mesh as M
import du_assemble as A

TEMPLATE = M._find_export(2986)
OUT = '/home/du/tests/mesh_z0_tilt_0704_2009.blueprint'
MCS = {(8, 8, 8): 635, (8, 8, 7): 603}

geom = M.plane_mesh(2, 2, lambda x, y: 1.0 - (x + 3 * y) / 14.0)
scans = M.gen_z0_from_mesh(geom, 2, 2, floor=-1)
assert set(scans) == set(MCS)
assert scans[(8, 8, 8)] != M.D.gen_seam_z_high(2, 2, depth=2), "no displacement?"

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
