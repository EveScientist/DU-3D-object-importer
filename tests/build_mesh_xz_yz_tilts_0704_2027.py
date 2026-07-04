"""xz / yz displaced-corner probes (the last unprobed carrier surface).

A) tests/mesh_xz_tilt_0704_2027.blueprint -- x=0+z=0 corner (2947 shape:
   x +-0.5, y 10.5..13.5, z +-0.5, 16 vox). Tilted top plane:
       dz84(xl, yl) = -(20*(xl+1) + 4*(yl-10)),  all 15 corners distinct
       (0 at (-1,10) .. -56 at (+1,14))
   EXPECTED: one continuous plane sloping strongly down toward +x
   (20/84 per voxel) and gently toward +y (4/84), deepest at (+x, far-y);
   NO crack at x=0 (nor at z=0 which is interior to the solid).

B) tests/mesh_yz_tilt_0704_2027.blueprint -- y=0+z=0 corner (3077 shape:
   x 10.5..12.5, y +-0.5, z +-0.5, 12 vox). Tilted top plane:
       dz84(xl, yl) = -(6*(xl-10) + 20*(yl+1)),  all 12 corners distinct
       (0 at (10,-1) .. -58 at (13,+1))
   EXPECTED: continuous plane sloping gently down toward +x (6/84) and
   strongly toward +y (20/84), deepest at (far-x, +y); NO crack at y=0.

The -z chunks mirror the +z chunks' surface offsets (3095 rule). Donors
2947 / 3077 (mc displacement-invariant). Any discontinuity or wrong slope
localizes the offending chunk/mapping.
"""
import sys

sys.path.insert(0, "/home/du")
import du_mesh as M
import du_assemble as A
import json, base64, struct, lz4.block
import du_hash


def verify(out, scans):
    d = json.load(open(out))
    for e in d['VoxelData']:
        if e['h'] != 3:
            continue
        key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
        b = e['records']['voxel']['data']['$binary']
        b = b['base64'] if isinstance(b, dict) else b
        raw = base64.b64decode(b)
        v = lz4.block.decompress(raw[12:], uncompressed_size=struct.unpack('<I', raw[4:8])[0])
        i = v.find(b'Debug1')
        assert v[64:i - 13] == scans[key], (out, key, "scan mismatch")
        assert du_hash.to_signed64(du_hash.compute_hash(raw)) == \
            e['records']['voxel']['hash']['$numberLong'], (out, key, "hash")
    print("round-trip OK:", out)


# A) xz corner, donor 2947 (ny=4)
MCS_XZ = {(8, 8, 8): 728, (8, 8, 7): 696, (7, 8, 8): 696, (7, 8, 7): 664}
geom = M.plane_mesh(2, 4, lambda x, y: 1.0 - (20 * x + 4 * y) / 84.0)
scans = M.gen_xz_from_mesh(geom, ny=4, xoff=1.0, yoff=-10.0)
assert set(scans) == set(MCS_XZ)
assert all(scans[k] != g for k, g in M.D.gen_corner_xz(4).items()), "xz no disp?"
out = '/home/du/tests/mesh_xz_tilt_0704_2027.blueprint'
n = A.rebuild_h3(M._find_export(2947), out,
                 lambda cx, cy, cz: (scans[(cx, cy, cz)], MCS_XZ[(cx, cy, cz)])
                 if (cx, cy, cz) in scans else None)
assert n == 4, n
verify(out, scans)

# B) yz corner, donor 3077 (nx=3)
MCS_YZ = {(8, 8, 8): 563, (8, 8, 7): 531, (8, 7, 8): 723, (8, 7, 7): 691}
geom = M.plane_mesh(4, 2, lambda x, y: 1.0 - (6 * x + 20 * y) / 84.0)
scans = M.gen_yz_from_mesh(geom, nx=3, xoff=-10.0, yoff=1.0)
assert set(scans) == set(MCS_YZ)
assert all(scans[k] != g for k, g in M.D.gen_corner_yz(3).items()), "yz no disp?"
out = '/home/du/tests/mesh_yz_tilt_0704_2027.blueprint'
n = A.rebuild_h3(M._find_export(3077), out,
                 lambda cx, cy, cz: (scans[(cx, cy, cz)], MCS_YZ[(cx, cy, cz)])
                 if (cx, cy, cz) in scans else None)
assert n == 4, n
verify(out, scans)
