"""Import tests for the VARYING x=0 / y=0 seam generators (incl 16-byte TRI
transition groups — first in-game exercise of that form from generated data).

Two novel shapes (never built in-game):

A) x0_varying_tri_import_0704_0952.blueprint — ASYMMETRIC-WIDTH hump across x=0
   (heights boundary-first: LOW [2,1], HIGH [2,1,1]).
   Chunks: (8,8,8) = gen_seam_x0_high_varying([2,1,1], [2,1])  (TRI ghost cluster)
           (7,8,8) = gen_seam_x0_low_varying([2,1], [2,1])     (TRI ghost cluster)
   mc: HIGH 642 (4-col plate base, far col h1), LOW 755 (base 756, ghost h2).
   Template/envelope: 3054 (same 2 chunks; bbox covers X ±2.5, Z to 11.5).
   EXPECTED IN-GAME (14 vox, hcCarbon):
     Z=10.5: X in {-1.5,-0.5,+0.5,+1.5,+2.5} x Y in {10.5,11.5}
     Z=11.5: X in {-0.5,+0.5} x Y in {10.5,11.5}
   + the sub-voxel transition bevel at the x=0 seam (both sides step 1 col out).

B) y0_varying_tri_import_0704_0952.blueprint — one-sided step on the -Y side
   (heights boundary-first: LOW [2,1], HIGH [1,1]) = the MIRROR of 3066.
   Chunks: (8,8,8) = gen_seam_y0_high_varying([1,1], [2,1])  (TRI: opp descends)
           (8,7,8) = gen_seam_y0_low_varying([2,1], [1,1])   (plain side)
   mc: HIGH 719 (far row h1), LOW 658 (ghost row h1).
   Template/envelope: 3066 (same 2 chunks; bbox covers Y ±1.5, Z to 11.5).
   EXPECTED IN-GAME (10 vox, hcCarbon):
     Z=10.5: X in {10.5,11.5} x Y in {-1.5,-0.5,+0.5,+1.5}
     Z=11.5: X in {10.5,11.5} x Y = -0.5
   + the transition bevel on the +Y side of the seam.
"""
import sys
sys.path.insert(0, "/home/du")
import du_solid as D
import du_assemble as A


def main():
    tests = []

    scans_a = {
        (8, 8, 8): (D.gen_seam_x0_high_varying([2, 1, 1], [2, 1]), 642),
        (7, 8, 8): (D.gen_seam_x0_low_varying([2, 1], [2, 1]), 755),
    }
    tests.append(('/home/du/exports/3054_export.blueprint',
                  '/home/du/tests/x0_varying_tri_import_0704_0952.blueprint',
                  scans_a))

    scans_b = {
        (8, 8, 8): (D.gen_seam_y0_high_varying([1, 1], [2, 1]), 719),
        (8, 7, 8): (D.gen_seam_y0_low_varying([2, 1], [1, 1]), 658),
    }
    tests.append(('/home/du/exports/3066_export.blueprint',
                  '/home/du/tests/y0_varying_tri_import_0704_0952.blueprint',
                  scans_b))

    for template, out, scans in tests:
        n = A.rebuild_h3(template, out, lambda cx, cy, cz: scans.get((cx, cy, cz)))
        assert n == 2, n
        print(f"wrote {out} ({n} chunks substituted)")

    # round-trip: decode what we wrote, confirm scans + hash recompute
    import json, base64, struct, lz4.block
    import du_hash
    for _, out, scans in tests:
        d = json.load(open(out))
        for e in d['VoxelData']:
            if e['h'] != 3:
                continue
            key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
            b = e['records']['voxel']['data']['$binary']
            b = b['base64'] if isinstance(b, dict) else b
            raw = base64.b64decode(b)
            v = lz4.block.decompress(raw[12:],
                                     uncompressed_size=struct.unpack('<I', raw[4:8])[0])
            i = v.find(b'Debug1')
            scan = v[64:i - 13]
            mc = struct.unpack('<I', v[64 + len(scan):68 + len(scan)])[0]
            want_scan, want_mc = scans[key]
            assert scan == want_scan, (out, key, 'scan mismatch')
            assert mc == want_mc, (out, key, mc, want_mc)
            assert du_hash.to_signed64(du_hash.compute_hash(raw)) == \
                e['records']['voxel']['hash']['$numberLong'], (out, key, 'hash')
        print(f"round-trip OK: {out}")


if __name__ == '__main__':
    main()
