#!/usr/bin/env python3
"""
Build a real test blueprint for in-game import validation, using h3_generator.py
(this session's from-scratch X-spanning implementation).

Approach: clone real export 1652 verbatim (Model, Elements, Bounds, h4/h5 entries,
meta blobs all untouched -- known to deploy/mesh correctly) and surgically replace
ONLY the 4 h3 entries' voxel.data with bytes produced entirely by h3_generator.py.
This isolates the test to exactly one question: are the from-scratch h3 scan bytes
correct, with zero packaging-template guesswork (the first attempt's from-scratch
JSON envelope used wrong Model.Size/version fields and failed at the migrate/copyTo
step on the server -- see session notes).
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

EXPORT_PATH = None
for d in ('exports', 'exports/archive'):
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), d,
                      '1652_export.blueprint')
    if os.path.exists(p):
        EXPORT_PATH = p
        break


def decode_chunk_from_blob(blob):
    unc = struct.unpack('<I', blob[4:8])[0]
    dec = lz4.block.decompress(blob[12:], uncompressed_size=unc)
    idx = dec.find(b'Debug1')
    return dec[64:idx - 13], int.from_bytes(dec[idx - 13:idx - 9], 'little')


def main():
    mat_info = ghc.MATERIALS_INFO['hcCarbon']
    mat_name_bytes, mat_hash_bytes = mat_info[1], mat_info[0]

    with open(EXPORT_PATH) as f:
        bp = json.load(f)

    roles = {
        (2, 1, 2): '212', (2, 2, 2): '222', (1, 1, 2): '112', (1, 2, 2): '122',
    }
    pos1_map = {(2, 1, 2): 19, (2, 2, 2): 9, (1, 1, 2): 325, (1, 2, 2): 317}
    own_212 = (126 - 35 * 1) % 256
    own_222 = (161 + 55 * 1 + 35) % 256
    own_112 = (158 - 35 * 1) % 256
    own_122 = (own_222 + 32) % 256
    own_map = {(2, 1, 2): own_212, (2, 2, 2): own_222, (1, 1, 2): own_112, (1, 2, 2): own_122}

    n_replaced = 0
    for e in bp['VoxelData']:
        if e['h'] != 3:
            continue
        key = (e['x']['$numberLong'], e['y']['$numberLong'], e['z']['$numberLong'])
        if key not in roles:
            continue
        real_blob = base64.b64decode(e['records']['voxel']['data']['$binary'])
        real_scan, real_mc = decode_chunk_from_blob(real_blob)

        role = roles[key]
        own = own_map[key]
        pos1 = pos1_map[key]
        gen_scan = g.generate_xspan_scan(role, own, real_mc, pos1)
        assert gen_scan == real_scan, f'h3{key} scan mismatch'

        mat = ghc._mat_section(mat_name_bytes, mat_hash_bytes, real_mc)
        new_blob = ghc._blob(ghc._hdr(*key) + gen_scan + mat)
        e['records']['voxel']['data']['$binary'] = ghc._b64(new_blob)
        n_replaced += 1

    assert n_replaced == 4, f'expected to replace 4 h3 entries, replaced {n_replaced}'
    print(f'Sanity check passed: all 4 h3 scans byte-exact, {n_replaced} entries substituted.')
    print('Model/Elements/Bounds/h4/h5 entries/meta blobs are untouched from 1652.')

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'xspan_import_test.blueprint')
    with open(out_path, 'w') as f:
        json.dump(bp, f)
    print(f'Written: {out_path} ({os.path.getsize(out_path)} bytes)')


if __name__ == '__main__':
    main()
