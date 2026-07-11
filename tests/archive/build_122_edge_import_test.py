#!/usr/bin/env python3
"""
Build a real test blueprint validating the role122 ABSOLUTE NEG-X EDGE
(x=-31.5) MAIN chunk. Clone real export 2053 (a 2x2x2 block whose far column
sits on x=-31.5) verbatim, and replace its (1,2,2) MAIN chunk's voxel.data
with bytes produced entirely by generate_122_dense_scan(lx_FAR=31, ...).
The spawned cx=0 boundary chunk and 6 empty placeholders keep the real
export's bytes (they're correct -- only the main chunk's generation is under
test here).
"""
import sys
import os
import json
import base64
import struct
import lz4.block

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import h3_generator as g
import generate_hollow_cube as ghc

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def find_export(num):
    for d in ('exports', 'exports/archive'):
        p = os.path.join(ROOT, d, f'{num}_export.blueprint')
        if os.path.exists(p):
            return p
    return None


def decode_chunk_from_blob(blob):
    unc = struct.unpack('<I', blob[4:8])[0]
    dec = lz4.block.decompress(blob[12:], uncompressed_size=unc)
    idx = dec.find(b'Debug1')
    return dec[64:idx - 13], int.from_bytes(dec[idx - 13:idx - 9], 'little')


def main():
    export_num = 2053  # 2x2x2, x=-30.5/-31.5 (far col on edge), y=+1.5/+2.5, z=+1.5/+2.5
    lx_FAR, ly_near, Ncols, Ye, lz_near, lz_far = 31, 1, 2, 2, 1, 2
    path = find_export(export_num)
    with open(path) as f:
        bp = json.load(f)

    n_replaced = 0
    for e in bp['VoxelData']:
        if e['h'] != 3:
            continue
        key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
        if key != (1, 2, 2):
            continue
        real_blob = base64.b64decode(e['records']['voxel']['data']['$binary'])
        real_scan, real_mc = decode_chunk_from_blob(real_blob)

        gen_scan, gen_mc = g.generate_122_dense_scan(lx_FAR, ly_near, Ncols, Ye, lz_near, lz_far)
        assert gen_scan == real_scan, 'edge MAIN chunk (1,2,2) scan mismatch vs real'
        assert gen_mc == real_mc, f'mc mismatch: gen {gen_mc} real {real_mc}'

        mat_info = ghc.MATERIALS_INFO['hcCarbon']
        mat = ghc._mat_section(mat_info[1], mat_info[0], real_mc)
        new_blob = ghc._blob(ghc._hdr(*key) + gen_scan + mat)
        e['records']['voxel']['data']['$binary'] = ghc._b64(new_blob)
        n_replaced += 1

    assert n_replaced == 1, f'expected 1, got {n_replaced}'
    out_path = os.path.join(HERE, '122_edge_import_test.blueprint')
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'role122 edge MAIN chunk: sanity OK, (1,2,2) substituted from generator (export {export_num}).')
    print(f'Written: {out_path}')


if __name__ == '__main__':
    main()
