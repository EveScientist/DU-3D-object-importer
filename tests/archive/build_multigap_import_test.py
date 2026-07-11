#!/usr/bin/env python3
"""
Build a real test blueprint for K>=3 sparse z-gaps (multiple holes in one
column) in-game import validation. Clone real export 1675 (real voxels at
z=+10.5, +12.5, +14.5, with gaps at +11.5 and +13.5) verbatim, and replace
only the 4 h3 entries' voxel.data with bytes produced entirely by
h3_generator.py's generate_multigap_multiz_scan.
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
    export_num = 1675
    path = find_export(export_num)
    with open(path) as f:
        bp = json.load(f)

    base_map = {
        (2, 1): ('212', 1, 631, 29), (2, 2): ('222', 161, 727, 19),
        (1, 1): ('112', 33, 599, 335), (1, 2): ('122', 193, 695, 325),
    }
    mat_info = ghc.MATERIALS_INFO['hcCarbon']

    n_replaced = 0
    for e in bp['VoxelData']:
        if e['h'] != 3:
            continue
        key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
        if key[2] != 2 or (key[0], key[1]) not in base_map:
            continue
        cx, cy = key[0], key[1]
        role, base_own, base_mc, pos1 = base_map[(cx, cy)]

        real_blob = base64.b64decode(e['records']['voxel']['data']['$binary'])
        real_scan, real_mc = decode_chunk_from_blob(real_blob)
        gen_scan, gen_mc = g.generate_multigap_multiz_scan(role, base_own, base_mc, [10, 12, 14], pos1)
        assert gen_scan == real_scan, f'h3{key} scan mismatch'
        assert gen_mc == real_mc, f'h3{key} mc mismatch'

        mat = ghc._mat_section(mat_info[1], mat_info[0], real_mc)
        new_blob = ghc._blob(ghc._hdr(*key) + gen_scan + mat)
        e['records']['voxel']['data']['$binary'] = ghc._b64(new_blob)
        n_replaced += 1

    assert n_replaced == 4, f'expected 4, got {n_replaced}'
    out_path = os.path.join(HERE, 'multigap_import_test.blueprint')
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'Multi-gap: sanity OK, {n_replaced} h3 entries substituted (from export {export_num}).')
    print(f'Written: {out_path} ({os.path.getsize(out_path)} bytes)')


if __name__ == '__main__':
    main()
