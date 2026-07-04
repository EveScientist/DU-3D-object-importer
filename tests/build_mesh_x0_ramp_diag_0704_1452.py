"""DIAGNOSTIC import: tests/mesh_x0_ramp_diag_0704_1452.blueprint.

The x0 cosine-valley test rendered with the offsets on MIRRORED corner
lines (center flat, outer edges dipped) -- the displacement carriers work
but the cluster -> geometric-line mapping inside x0-seam chunks is wrong,
and a symmetric wave cannot distinguish candidate mappings. This build is
a LINEAR RAMP across x=0 with a DISTINCT offset per corner line:

    z(x) = 1 - (x + 2)/4  over global x in [-2, 2]
    intended line offsets: x=-2: 0, -1: -21, 0: -42, +1: -63, +2: -84

Same donor/blocky occupancy as the wave test (3032; H = all 1; mcs
{(8,8,8):587, (7,8,8):756}).

READ-OUT: report which offset renders at each face line (x = -2..+2 in
voxel units; e.g. "slopes down toward +x, deepest at +2" vs mirrored or
scrambled). Each of the five values is unique, so the render pins the
cluster->line mapping exactly; I then fix gen_x0_from_mesh's vline
assignment and re-issue the wave.
"""
import sys

sys.path.insert(0, "/home/du")
import du_mesh as M
import du_assemble as A

TEMPLATE = '/home/du/exports/archive/3032_export.blueprint'
OUT = '/home/du/tests/mesh_x0_ramp_diag_0704_1452.blueprint'
MCS = {(8, 8, 8): 587, (7, 8, 8): 756}

geom = M.plane_mesh(4, 2, lambda x, y: 1.0 - x / 4.0)   # mesh x 0..4 == global -2..2
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
