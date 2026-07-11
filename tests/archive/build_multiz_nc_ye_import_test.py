#!/usr/bin/env python3
"""
Build a real test blueprint for multi-z + Nc=2 + Ye=2 (a 2x2-column, full
z=0..14 tower) in-game import validation. Clone real export 1638 verbatim,
and replace all 8 h3 entries' voxel.data with bytes produced entirely by
h3_generator.py's generate_multiz_nc_ye_212family_scan/
generate_multiz_nc_ye_222family_scan (cz=2) and generate_cz1_scan/
generate_cz1_nc2_scan-style derivation (cz=1).
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
    export_num = 1638
    Ncols = 2
    path = find_export(export_num)
    with open(path) as f:
        bp = json.load(f)

    def find_blob(cx, cy, cz):
        return base64.b64decode(next(
            e['records']['voxel']['data']['$binary'] for e in bp['VoxelData']
            if e['h'] == 3 and e['x']['$numberLong'] == cx and e['y']['$numberLong'] == cy and e['z']['$numberLong'] == cz
        ))

    n_replaced = 0

    # 212 family
    for role, tracks_nc, cx, cy, own, mc_singlez, base_cz1_mc, pos1, cz1_pos1 in [
            ('212', True, 2, 1, 222, 686, 578, 27, 27),
            ('112', False, 1, 1, 254, 599, 546, 333, 335)]:
        real_scan2, real_mc2 = decode_chunk_from_blob(find_blob(cx, cy, 2))
        gen_scan2, gen_mc2 = g.generate_multiz_nc_ye_212family_scan(
            role, Ncols, own, mc_singlez, 0, 14, 2, pos1)
        assert gen_scan2 == real_scan2, f'cz=2 {role} scan mismatch'
        assert gen_mc2 == real_mc2
        replace_h3_entry(bp, (cx, cy, 2), gen_scan2, real_mc2)
        n_replaced += 1

        cz2_marker1 = (own + 14 + 0 + 7 - 35) % 256
        real_scan1, real_mc1 = decode_chunk_from_blob(find_blob(cx, cy, 1))
        gen_scan1, gen_mc1 = g.generate_cz1_nc_ye_212family_scan(
            role, tracks_nc, Ncols, cz2_marker1, base_cz1_mc, 2, cz1_pos1)
        assert gen_scan1 == real_scan1, f'cz=1 {role} scan mismatch'
        assert gen_mc1 == real_mc1
        replace_h3_entry(bp, (cx, cy, 1), gen_scan1, real_mc1)
        n_replaced += 1

    # 222 family
    for role, tracks_nc, cx, cy, own, mc_singlez, base_cz1_mc, pos1 in [
            ('222', True, 2, 2, 161, 526, 674, 19),
            ('122', False, 1, 2, 193, 695, 642, 325)]:
        real_scan2, real_mc2 = decode_chunk_from_blob(find_blob(cx, cy, 2))
        gen_scan2, gen_mc2 = g.generate_multiz_nc_ye_222family_scan(
            role, Ncols, own, mc_singlez, 0, 14, 2, pos1)
        assert gen_scan2 == real_scan2, f'cz=2 {role} scan mismatch'
        assert gen_mc2 == real_mc2
        replace_h3_entry(bp, (cx, cy, 2), gen_scan2, real_mc2)
        n_replaced += 1

        cz2_marker1 = (own + 14 + 0 + 7 - 35 * (2 - 1)) % 256
        real_scan1, real_mc1 = decode_chunk_from_blob(find_blob(cx, cy, 1))
        gen_scan1, gen_mc1 = g.generate_cz1_nc_ye_222family_scan(
            role, tracks_nc, Ncols, cz2_marker1, base_cz1_mc, pos1)
        assert gen_scan1 == real_scan1, f'cz=1 {role} scan mismatch'
        assert gen_mc1 == real_mc1
        replace_h3_entry(bp, (cx, cy, 1), gen_scan1, real_mc1)
        n_replaced += 1

    assert n_replaced == 8, f'expected 8, got {n_replaced}'
    out_path = os.path.join(HERE, 'multiz_nc_ye_import_test.blueprint')
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'Multi-z+Nc=2+Ye=2: sanity OK, {n_replaced} h3 entries substituted (from export {export_num}).')
    print(f'Written: {out_path} ({os.path.getsize(out_path)} bytes)')


if __name__ == '__main__':
    main()
