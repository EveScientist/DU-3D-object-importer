#!/usr/bin/env python3
"""
Build a real test blueprint for the X positive far edge (x=+30.5, isolated,
Nc_normal=0) in-game import validation. Clone real export 1735 verbatim,
replace its 4 h3 entries' voxel.data with bytes produced entirely by
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
    export_num = 1735
    path = find_export(export_num)
    with open(path) as f:
        bp = json.load(f)

    chunk_gens = {
        (2, 1, 2): lambda mc: g.generate_xpos_faredge_main_scan('212', 178, mc),
        (2, 2, 2): lambda mc: g.generate_xpos_faredge_main_scan('222', 82, mc),
        (3, 1, 2): lambda mc: g.generate_xpos_faredge_edge_scan('212', 178, mc),
        (3, 2, 2): lambda mc: g.generate_xpos_faredge_edge_scan('222', 82, mc),
    }

    n_replaced = 0
    for e in bp['VoxelData']:
        if e['h'] != 3:
            continue
        key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
        if key not in chunk_gens:
            continue
        real_blob = base64.b64decode(e['records']['voxel']['data']['$binary'])
        real_scan, real_mc = decode_chunk_from_blob(real_blob)

        gen_scan = chunk_gens[key](real_mc)
        assert gen_scan == real_scan, f'h3{key} scan mismatch'

        mat_info = ghc.MATERIALS_INFO['hcCarbon']
        mat = ghc._mat_section(mat_info[1], mat_info[0], real_mc)
        new_blob = ghc._blob(ghc._hdr(*key) + gen_scan + mat)
        e['records']['voxel']['data']['$binary'] = ghc._b64(new_blob)
        n_replaced += 1

    assert n_replaced == 4, f'expected 4, got {n_replaced}'
    out_path = os.path.join(HERE, 'faredge_xpos_import_test.blueprint')
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'X+ far edge: sanity OK, {n_replaced} h3 entries substituted (from export {export_num}).')
    print(f'Written: {out_path}')


if __name__ == '__main__':
    main()
