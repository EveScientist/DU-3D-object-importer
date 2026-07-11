#!/usr/bin/env python3
"""
Build real test blueprints for the 3 simplest far-edge cases (isolated,
single voxel at the axis extreme) in-game import validation:
  - Y positive far edge (y=+30.5): export 1739, pure role relabel
  - X negative far edge (x=-31.5): export 1737, role-shift + universal +35/-35
  - Y negative far edge (y=-31.5): export 1745, role-shift + doubled +70/-70
Clone each real export verbatim, replace its 4 h3 entries' voxel.data with
bytes produced entirely by h3_generator.py.
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


def build(export_num, out_name, chunk_gens):
    """chunk_gens: dict {(cx,cy,cz): generator_fn(real_mc) -> scan_bytes}"""
    path = find_export(export_num)
    with open(path) as f:
        bp = json.load(f)

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
        assert gen_scan == real_scan, f'{out_name} h3{key} scan mismatch'

        mat_info = ghc.MATERIALS_INFO['hcCarbon']
        mat = ghc._mat_section(mat_info[1], mat_info[0], real_mc)
        new_blob = ghc._blob(ghc._hdr(*key) + gen_scan + mat)
        e['records']['voxel']['data']['$binary'] = ghc._b64(new_blob)
        n_replaced += 1

    assert n_replaced == 4, f'{out_name}: expected 4, got {n_replaced}'
    out_path = os.path.join(HERE, out_name)
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'{out_name}: sanity OK, {n_replaced} h3 entries substituted (from export {export_num}).')


def main():
    # Y positive far edge (1739)
    build(1739, 'faredge_ypos_import_test.blueprint', {
        (2, 2, 2): lambda mc: g.generate_212_scan(1, mc, lz=14, Yextent=1),
        (2, 3, 2): lambda mc: g.generate_222_scan(1, mc),
        (1, 2, 2): lambda mc: g.generate_112_scan(mc, lz=14, Yextent=1),
        (1, 3, 2): lambda mc: g.generate_122_scan(mc),
    })

    # X negative far edge (1737)
    build(1737, 'faredge_xneg_import_test.blueprint', {
        (1, 1, 2): lambda mc: g.generate_zspan_side_scan('212', 36, mc, 29),
        (1, 2, 2): lambda mc: g.generate_zspan_side_scan('222', 196, mc, 19),
        (0, 1, 2): lambda mc: g.generate_zspan_side_scan('112', 68, mc, 335),
        (0, 2, 2): lambda mc: g.generate_zspan_side_scan('122', 228, mc, 325),
    })

    # Y negative far edge (1745)
    build(1745, 'faredge_yneg_import_test.blueprint', {
        (2, 1, 2): lambda mc: g.generate_zspan_side_scan('222', 231, mc, 19),
        (2, 0, 2): lambda mc: g.generate_zspan_side_scan('212', 71, mc, 29),
        (1, 1, 2): lambda mc: g.generate_yneg_faredge_122_scan(7, mc),
        (1, 0, 2): lambda mc: g.generate_zspan_side_scan('112', 103, mc, 335),
    })


if __name__ == '__main__':
    main()
