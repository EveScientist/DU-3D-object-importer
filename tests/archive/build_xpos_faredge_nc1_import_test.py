#!/usr/bin/env python3
"""
Build a real test blueprint for X positive far edge with Nc_normal=1 (one
normal column at x=29.5 plus the far edge at x=30.5) in-game import
validation -- corrects and generalizes the marker formula beyond the
isolated (Nc_normal=0) case, also fixing a confounded-data error from an
earlier pass (the previously-documented "baseline+35-55*lx_near" formula,
derived from archived exports 1741/1743/1790, turned out to not match this
fresh test; the correct formula is "baseline+55*lx_near" with lx_near
measured as distance from the edge). Clone real export 1919 verbatim, and
replace all 4 h3 entries' voxel.data with bytes produced entirely by
h3_generator.py's generate_xpos_faredge_main_scan/generate_xpos_faredge_edge_scan.
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
    export_num = 1919
    path = find_export(export_num)
    with open(path) as f:
        bp = json.load(f)

    n_replaced = 0
    for e in bp['VoxelData']:
        if e['h'] != 3:
            continue
        key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
        cx, cy, cz = key
        real_blob = base64.b64decode(e['records']['voxel']['data']['$binary'])
        real_scan, real_mc = decode_chunk_from_blob(real_blob)

        if cx == 2:
            role = '212' if cy == 1 else '222'
            baseline = 178 if role == '212' else 82
            marker = (baseline + 55 * 1) % 256
            gen_scan = g.generate_xpos_faredge_main_scan(role, marker, real_mc, Nc_normal=1)
        elif cx == 3:
            role = '212' if cy == 1 else '222'
            baseline = 178 if role == '212' else 82
            gen_scan = g.generate_xpos_faredge_edge_scan(role, baseline, real_mc)
        else:
            continue
        assert gen_scan == real_scan, f'h3{key} scan mismatch'

        mat_info = ghc.MATERIALS_INFO['hcCarbon']
        mat = ghc._mat_section(mat_info[1], mat_info[0], real_mc)
        new_blob = ghc._blob(ghc._hdr(*key) + gen_scan + mat)
        e['records']['voxel']['data']['$binary'] = ghc._b64(new_blob)
        n_replaced += 1

    assert n_replaced == 4, f'expected 4, got {n_replaced}'
    out_path = os.path.join(HERE, 'xpos_faredge_nc1_import_test.blueprint')
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'X+ far edge, Nc_normal=1: sanity OK, {n_replaced} h3 entries substituted (from export {export_num}).')
    print(f'Written: {out_path}')


if __name__ == '__main__':
    main()
