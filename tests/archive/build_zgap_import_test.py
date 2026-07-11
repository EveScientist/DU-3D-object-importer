#!/usr/bin/env python3
"""
Build a real test blueprint for sparse z-gap (K=2) in-game import validation.
Same clone-and-substitute approach as the other import tests: clone real
export 1579 (two voxels at z=+0.5 and z=+14.5, single x/y column, everything
in between empty -- a single gap spanning lz=1..13) verbatim, and replace
only the 8 h3 entries' voxel.data with bytes produced entirely by
h3_generator.py's generate_sparse_multiz_scan/generate_cz1_scan.
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
    export_num = 1579
    path = find_export(export_num)
    with open(path) as f:
        bp = json.load(f)

    base_map = {
        (2, 1): ('212', 1, 631, 29), (2, 2): ('222', 161, 727, 19),
        (1, 1): ('112', 33, 599, 335), (1, 2): ('122', 193, 695, 325),
    }

    def find_blob(cx, cy, cz):
        return base64.b64decode(next(
            e['records']['voxel']['data']['$binary'] for e in bp['VoxelData']
            if e['h'] == 3 and e['x']['$numberLong'] == cx and e['y']['$numberLong'] == cy and e['z']['$numberLong'] == cz
        ))

    n_replaced = 0
    for (cx, cy), (role, base_own, base_mc, pos1) in base_map.items():
        real_scan2, real_mc2 = decode_chunk_from_blob(find_blob(cx, cy, 2))
        gen_scan2, gen_mc2 = g.generate_sparse_multiz_scan(role, base_own, base_mc, 0, 14, pos1)
        assert gen_scan2 == real_scan2, f'cz=2 ({cx},{cy}) scan mismatch'
        assert gen_mc2 == real_mc2, f'cz=2 ({cx},{cy}) mc mismatch'
        replace_h3_entry(bp, (cx, cy, 2), gen_scan2, real_mc2)
        n_replaced += 1

        first_marker = (base_own + 14 + 0 + 7) % 256
        real_scan1, real_mc1 = decode_chunk_from_blob(find_blob(cx, cy, 1))
        gen_scan1, gen_mc1 = g.generate_cz1_scan(cx, cy, first_marker)
        assert gen_scan1 == real_scan1, f'cz=1 ({cx},{cy}) scan mismatch'
        assert gen_mc1 == real_mc1, f'cz=1 ({cx},{cy}) mc mismatch'
        replace_h3_entry(bp, (cx, cy, 1), gen_scan1, real_mc1)
        n_replaced += 1

    assert n_replaced == 8, f'expected 8, got {n_replaced}'
    out_path = os.path.join(HERE, 'zgap_import_test.blueprint')
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'Z-gap: sanity OK, {n_replaced} h3 entries substituted (from export {export_num}).')
    print(f'Written: {out_path} ({os.path.getsize(out_path)} bytes)')


if __name__ == '__main__':
    main()
