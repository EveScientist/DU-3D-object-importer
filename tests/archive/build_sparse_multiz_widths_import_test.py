#!/usr/bin/env python3
"""
Build a real test blueprint for sparse multi-z K=2 with non-uniform
segment widths (segment 0 = z=10-11, width 2; gap at z=12-13; segment 1 =
z=14, width 1) in-game import validation -- the w0/w1 generalization of
the all-width-1 case. Clone real export 1911 verbatim, and replace all 4
h3 entries' voxel.data with bytes produced entirely by h3_generator.py's
generate_sparse_multiz_scan.
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
    export_num = 1911
    path = find_export(export_num)
    with open(path) as f:
        bp = json.load(f)

    roles = {
        (2, 1, 2): ('212', 1, 631, 29), (2, 2, 2): ('222', 161, 727, 19),
        (1, 1, 2): ('112', 33, 599, 335), (1, 2, 2): ('122', 193, 695, 325),
    }

    n_replaced = 0
    for e in bp['VoxelData']:
        if e['h'] != 3:
            continue
        key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
        if key not in roles:
            continue
        role, own, mc_singlez, pos1 = roles[key]
        real_blob = base64.b64decode(e['records']['voxel']['data']['$binary'])
        real_scan, real_mc = decode_chunk_from_blob(real_blob)

        gen_scan, gen_mc = g.generate_sparse_multiz_scan(role, own, mc_singlez, 10, 14, pos1, w0=2, w1=1)
        assert gen_scan == real_scan, f'h3{key} scan mismatch'
        assert gen_mc == real_mc, f'h3{key} mc mismatch'

        mat_info = ghc.MATERIALS_INFO['hcCarbon']
        mat = ghc._mat_section(mat_info[1], mat_info[0], real_mc)
        new_blob = ghc._blob(ghc._hdr(*key) + gen_scan + mat)
        e['records']['voxel']['data']['$binary'] = ghc._b64(new_blob)
        n_replaced += 1

    assert n_replaced == 4, f'expected 4, got {n_replaced}'
    out_path = os.path.join(HERE, 'sparse_multiz_widths_import_test.blueprint')
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'Sparse multi-z, multi-level widths: sanity OK, {n_replaced} h3 entries substituted (from export {export_num}).')
    print(f'Written: {out_path}')


if __name__ == '__main__':
    main()
