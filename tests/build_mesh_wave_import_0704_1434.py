"""First MESH-DRIVEN import test: tests/mesh_wave_import_0704_1434.blueprint.

A cosine half-pipe valley -- a curved surface impossible to build blocky --
generated end-to-end through the du_mesh solver:

    z(x) = 0.75 + 0.25*cos(pi*x/2)   over a 4x1-cell patch (x = 0..4)

Corner offsets (84ths): 0, -21, -42, -21, 0 (smooth dip of half a voxel at
the middle). Blocky H = all 1 -> byte-identical blocky occupancy to donor
2700 (gen_linear_ramp footprint), whose envelope + mc (514) are reused
(mc is displacement-invariant, pinned by 3048 == 3081).

EXPECTED IN-GAME (4 vox, hcCarbon, at the 2700 build position lx0/ly0=10):
a 4x1 strip whose top surface is a smooth cosine valley -- full height at
both ends, dipping half a voxel at the center, no steps.
"""
import sys
import math

sys.path.insert(0, "/home/du")
import du_mesh as M
import du_assemble as A

TEMPLATE = '/home/du/exports/archive/2700_export.blueprint'
OUT = '/home/du/tests/mesh_wave_import_0704_1434.blueprint'
MC = 514

geom = M.plane_mesh(4, 1, lambda x, y: 0.75 + 0.25 * math.cos(math.pi * x / 2))
scan = M.gen_from_mesh(geom, 4, 1)

# sanity: same length family as the donor ramp (structure-only check)
import du_solid as D
blocky = D.gen_heightmap_unified([[1]] * 4)
assert len(scan) > len(blocky), "no displacement emitted?"

n = A.rebuild_h3(TEMPLATE, OUT,
                 lambda cx, cy, cz: (scan, MC) if (cx, cy, cz) == (8, 8, 8) else None)
assert n == 1, n
print("wrote", OUT)

# round-trip
import json, base64, struct, lz4.block
import du_hash
d = json.load(open(OUT))
for e in d['VoxelData']:
    if e['h'] != 3:
        continue
    b = e['records']['voxel']['data']['$binary']
    b = b['base64'] if isinstance(b, dict) else b
    raw = base64.b64decode(b)
    v = lz4.block.decompress(raw[12:], uncompressed_size=struct.unpack('<I', raw[4:8])[0])
    i = v.find(b'Debug1')
    assert v[64:i - 13] == scan, "scan mismatch"
    assert struct.unpack('<I', v[64 + len(scan):68 + len(scan)])[0] == MC
    assert du_hash.to_signed64(du_hash.compute_hash(raw)) == \
        e['records']['voxel']['hash']['$numberLong']
print("round-trip OK")
