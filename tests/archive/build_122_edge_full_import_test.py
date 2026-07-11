#!/usr/bin/env python3
"""
Build a real test blueprint for the role122 ABSOLUTE NEG-X EDGE (x=-31.5)
with ALL 8 spawned chunks generated from scratch. Clone real export 2053
(a 2x2x2 block whose far column sits on x=-31.5) and replace EVERY h3
chunk's voxel.data with generator output:
  (1,2,2)  MAIN          -> generate_122_dense_scan(lx_FAR=31, ...)
  (0,2,2)  cx=0 boundary -> generate_122_edge_cx0_scan(...)
  6 others EMPTY         -> generate_122_edge_empty_scan()
This validates the complete edge-touching generation end-to-end in-game.
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
    export_num = 2053
    # fill params: x=-30.5/-31.5 (edge), y=+1.5/+2.5, z=+1.5/+2.5
    Ye, lz_near, lz_far, ly_near, Ncols = 2, 1, 2, 1, 2
    path = find_export(export_num)
    with open(path) as f:
        bp = json.load(f)

    mat_info = ghc.MATERIALS_INFO['hcCarbon']
    n_replaced = 0
    for e in bp['VoxelData']:
        if e['h'] != 3:
            continue
        key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
        real_blob = base64.b64decode(e['records']['voxel']['data']['$binary'])
        real_scan, real_mc = decode_chunk_from_blob(real_blob)

        if key == (1, 2, 2):
            gen_scan, gen_mc = g.generate_122_dense_scan(31, ly_near, Ncols, Ye, lz_near, lz_far)
        elif key == (0, 2, 2):
            gen_scan, gen_mc = g.generate_122_edge_cx0_scan(Ye, lz_near, lz_far, ly_near)
        else:
            gen_scan, gen_mc = g.generate_122_edge_empty_scan()

        assert gen_scan == real_scan, f'chunk {key} scan mismatch'
        assert gen_mc == real_mc, f'chunk {key} mc mismatch (gen {gen_mc} real {real_mc})'

        mat = ghc._mat_section(mat_info[1], mat_info[0], real_mc)
        new_blob = ghc._blob(ghc._hdr(*key) + gen_scan + mat)
        e['records']['voxel']['data']['$binary'] = ghc._b64(new_blob)
        n_replaced += 1

    assert n_replaced == 8, f'expected 8, got {n_replaced}'
    out_path = os.path.join(HERE, '122_edge_full_import_test.blueprint')
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'role122 edge (ALL 8 chunks generated): sanity OK ({n_replaced} chunks, export {export_num}).')
    print(f'Written: {out_path}')


if __name__ == '__main__':
    main()
