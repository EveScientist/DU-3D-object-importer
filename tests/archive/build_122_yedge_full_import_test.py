#!/usr/bin/env python3
"""Full role122 Y+ EDGE (y=+30.5) import test: clone export 2081 and
regenerate ALL 8 chunks from scratch (main + Y-boundary + spanning + edge-
spanning + 4 empties)."""
import sys, os, json, base64, struct
import lz4.block
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import h3_generator as g
import generate_hollow_cube as ghc
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def find_export(num):
    for d in ('exports', 'exports/archive'):
        p = os.path.join(ROOT, d, f'{num}_export.blueprint')
        if os.path.exists(p):
            return p


def decode_chunk_from_blob(blob):
    unc = struct.unpack('<I', blob[4:8])[0]
    dec = lz4.block.decompress(blob[12:], uncompressed_size=unc)
    idx = dec.find(b'Debug1')
    return dec[64:idx - 13], int.from_bytes(dec[idx - 13:idx - 9], 'little')


def main():
    # 2081: x=-1.5,-2.5 (Nc2,lxF2), y=+29.5,+30.5 (ly_near=29,Ye2,edge), z=+1.5,+2.5 (N2)
    Ncols, Ye, ly_near, lz_near, lz_far, N = 2, 2, 29, 1, 2, 2
    with open(find_export(2081)) as f:
        bp = json.load(f)
    mat_info = ghc.MATERIALS_INFO['hcCarbon']
    n = 0
    for e in bp['VoxelData']:
        if e['h'] != 3:
            continue
        key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
        cx, cy, cz = key
        real_scan, real_mc = decode_chunk_from_blob(base64.b64decode(e['records']['voxel']['data']['$binary']))
        if cz == 1:
            gen, gmc = g.generate_122_edge_empty_scan()
        elif (cx, cy) == (1, 2):
            gen, gmc = g.generate_122_dense_scan(2, ly_near, Ncols, Ye, lz_near, lz_far)
        elif (cx, cy) == (1, 3):
            gen, gmc = g.generate_122_yedge_132_scan(Ncols, lz_near, lz_far)
        elif (cx, cy) == (2, 2):
            gen, gmc = g.generate_122_spanning_222_scan(Ye, lz_near, lz_far, ly_near)
        elif (cx, cy) == (2, 3):
            gen, gmc = g.generate_122_yedge_232_scan(N, lz_far)
        assert gen == real_scan and gmc == real_mc, f'mismatch {key}'
        mat = ghc._mat_section(mat_info[1], mat_info[0], real_mc)
        e['records']['voxel']['data']['$binary'] = ghc._b64(ghc._blob(ghc._hdr(*key) + gen + mat))
        n += 1
    assert n == 8, n
    out = os.path.join(HERE, '122_yedge_full_import_test.blueprint')
    with open(out, 'w') as f:
        json.dump(bp, f)
    print(f'Y-edge full ({n} chunks generated): sanity OK. Written: {out}')


if __name__ == '__main__':
    main()
