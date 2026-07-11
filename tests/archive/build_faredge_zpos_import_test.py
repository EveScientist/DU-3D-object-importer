#!/usr/bin/env python3
"""
Build a real test blueprint for the Z positive far edge (z=+30.5, isolated)
in-game import validation. Clone real export 1747 verbatim, replace its 8
h3 entries' voxel.data with bytes produced entirely by h3_generator.py's
generate_zpos_faredge_pair_scan.
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


def replace_h3_entry(bp, key, gen_scan, real_mc):
    mat_info = ghc.MATERIALS_INFO['hcCarbon']
    mat = ghc._mat_section(mat_info[1], mat_info[0], real_mc)
    new_blob = ghc._blob(ghc._hdr(*key) + gen_scan + mat)
    for e in bp['VoxelData']:
        if e['h'] == 3 and (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong']) == key:
            e['records']['voxel']['data']['$binary'] = ghc._b64(new_blob)
            return
    raise ValueError(f'h3 entry {key} not found')


def main():
    export_num = 1747
    path = find_export(export_num)
    with open(path) as f:
        bp = json.load(f)

    def find_blob(cx, cy, cz):
        return base64.b64decode(next(
            e['records']['voxel']['data']['$binary'] for e in bp['VoxelData']
            if e['h'] == 3 and e['x']['$numberLong'] == cx and e['y']['$numberLong'] == cy and e['z']['$numberLong'] == cz
        ))

    roles = [('212', 2, 1, 52, 29), ('222', 2, 2, 212, 19),
             ('112', 1, 1, 84, 335), ('122', 1, 2, 244, 325)]

    n_replaced = 0
    for role, cx, cy, marker_cz2, pos1 in roles:
        real_scan2, real_mc2 = decode_chunk_from_blob(find_blob(cx, cy, 2))
        cz2_scan, cz3_scan, gen_mc3 = g.generate_zpos_faredge_pair_scan(role, marker_cz2, real_mc2, pos1)
        assert cz2_scan == real_scan2, f'cz=2 {role} scan mismatch'
        replace_h3_entry(bp, (cx, cy, 2), cz2_scan, real_mc2)
        n_replaced += 1

        real_scan3, real_mc3 = decode_chunk_from_blob(find_blob(cx, cy, 3))
        assert cz3_scan == real_scan3, f'cz=3 {role} scan mismatch'
        assert gen_mc3 == real_mc3
        replace_h3_entry(bp, (cx, cy, 3), cz3_scan, real_mc3)
        n_replaced += 1

    assert n_replaced == 8, f'expected 8, got {n_replaced}'
    out_path = os.path.join(HERE, 'faredge_zpos_import_test.blueprint')
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'Z+ far edge: sanity OK, {n_replaced} h3 entries substituted (from export {export_num}).')
    print(f'Written: {out_path}')


if __name__ == '__main__':
    main()
