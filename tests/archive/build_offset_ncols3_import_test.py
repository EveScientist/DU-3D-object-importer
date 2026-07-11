#!/usr/bin/env python3
"""
Build a real test blueprint for offset/staggered voxel sets at Ncols=3
(3 columns at y=-0.5/-1.5/-2.5, '212' family) in-game import validation --
the Ncols generalization beyond the established Ncols=2 case. Clone real
export 1927 verbatim, and replace the '212' h3 entry's voxel.data with
bytes produced entirely by h3_generator.py's
generate_offset_212family_multicol_scan. Other h3 entries ('222'/'112'/
'122') showed no genuine offset-related content in this construct (all
real voxels are on the negative-y side), so they're left untouched.
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
    export_num = 1927
    path = find_export(export_num)
    with open(path) as f:
        bp = json.load(f)

    n_replaced = 0
    for e in bp['VoxelData']:
        if e['h'] != 3:
            continue
        key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
        if key != (2, 1, 2):
            continue
        real_blob = base64.b64decode(e['records']['voxel']['data']['$binary'])
        real_scan, real_mc = decode_chunk_from_blob(real_blob)

        gen_scan = g.generate_offset_212family_multicol_scan(1, 199, [1, 2], real_mc, 29)
        assert gen_scan == real_scan, f'h3{key} scan mismatch'

        mat_info = ghc.MATERIALS_INFO['hcCarbon']
        mat = ghc._mat_section(mat_info[1], mat_info[0], real_mc)
        new_blob = ghc._blob(ghc._hdr(*key) + gen_scan + mat)
        e['records']['voxel']['data']['$binary'] = ghc._b64(new_blob)
        n_replaced += 1

    assert n_replaced == 1, f'expected 1, got {n_replaced}'
    out_path = os.path.join(HERE, 'offset_ncols3_import_test.blueprint')
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'Offset/staggered Ncols=3: sanity OK, {n_replaced} h3 entries substituted (from export {export_num}).')
    print(f'Written: {out_path}')


if __name__ == '__main__':
    main()
